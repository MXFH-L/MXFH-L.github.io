"""
subagents/base.py — 子智能体基类

子智能体是隔离的小型 Agent：
  · 自己的 System Prompt
  · 自己的工具子集（受限权限）
  · 不共享主对话上下文
  · 完成后只向主智能体返回一份结构化摘要

对应你设计文档里的"上下文隔离的专用子智能体" + "结果摘要接口"。
"""
from __future__ import annotations
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict

import anthropic

from ..config import AgentConfig
from ..tools.registry import ToolRegistry
from ..utils.exceptions import SubagentError
from ..utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class SubagentResult:
    """子智能体的标准化返回结构。"""
    success: bool
    summary: str          # ≤ 500 字的执行摘要
    artifacts: list[str]  # 产物清单（文件名/SHA/URL）
    iterations: int

    def to_dict(self) -> dict:
        return asdict(self)


class Subagent(ABC):
    """所有子智能体的抽象基类。"""

    def __init__(self,
                 cfg: AgentConfig,
                 client: anthropic.Anthropic,
                 registry: ToolRegistry):
        self.cfg = cfg
        self.client = client
        self.registry = registry

    # ── 子类必须实现 ─────────────────────
    @property
    @abstractmethod
    def name(self) -> str:
        """子智能体名称（如 'writer'）"""

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """子智能体的 System Prompt（独立于主智能体）"""

    @property
    @abstractmethod
    def allowed_tools(self) -> list[str]:
        """允许使用的工具白名单。空列表表示无工具，即纯文本生成。"""

    # ── 通用执行逻辑 ─────────────────────
    def run(self, task: str, max_iterations: int = 10) -> SubagentResult:
        """执行单个任务，返回结构化结果。"""
        log.info("[%s] 接受任务：%s", self.name, task[:80])

        messages: list[dict] = [{"role": "user", "content": task}]
        artifacts: list[str] = []
        tools_param = self.registry.schemas(only=self.allowed_tools) if self.allowed_tools else None

        for iteration in range(max_iterations):
            try:
                response = self.client.messages.create(
                    model=self.cfg.model,
                    max_tokens=self.cfg.max_tokens,
                    system=self.system_prompt,
                    tools=tools_param,
                    messages=messages,
                )
            except anthropic.APIError as e:
                raise SubagentError(self.name, f"API 错误：{e}") from e

            if response.stop_reason == "end_turn":
                final_text = "".join(
                    b.text for b in response.content if hasattr(b, "text")
                )
                self._collect_artifacts(messages, artifacts)
                return SubagentResult(
                    success=True,
                    summary=final_text[:500],
                    artifacts=artifacts,
                    iterations=iteration + 1,
                )

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results: list[dict] = []
                for blk in response.content:
                    if blk.type != "tool_use":
                        continue
                    log.debug("[%s] 调用工具 %s", self.name, blk.name)
                    result_str = self.registry.execute(blk.name, blk.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": blk.id,
                        "content": result_str,
                    })
                messages.append({"role": "user", "content": tool_results})
                continue

            # 其他停止原因
            return SubagentResult(
                success=False,
                summary=f"非预期停止：{response.stop_reason}",
                artifacts=artifacts,
                iterations=iteration + 1,
            )

        return SubagentResult(
            success=False,
            summary=f"达到最大轮次 {max_iterations}，任务未完成",
            artifacts=artifacts,
            iterations=max_iterations,
        )

    # ── 产物收集 ─────────────────────────
    def _collect_artifacts(self, messages: list[dict], artifacts: list[str]) -> None:
        """从对话历史中提取产物（文件名 / SHA / URL）。"""
        for m in messages:
            if m.get("role") != "user":
                continue
            content = m.get("content")
            if not isinstance(content, list):
                continue
            for blk in content:
                if not (isinstance(blk, dict) and blk.get("type") == "tool_result"):
                    continue
                try:
                    data = json.loads(blk.get("content", "{}"))
                except (json.JSONDecodeError, TypeError):
                    continue
                for key in ("filename", "sha", "path"):
                    if key in data and data.get("success"):
                        artifacts.append(str(data[key]))
