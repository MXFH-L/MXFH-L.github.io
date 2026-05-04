"""
core/loop.py — Agentic Loop 引擎

职责单一：跑一次"模型→工具→模型"的循环，直到模型决定结束。
所有 Harness 能力（压缩、卸载、审批、回滚）通过依赖注入传入。
"""
from __future__ import annotations
import json
from dataclasses import dataclass

import anthropic

from ..config import AgentConfig
from ..harness import (
    AgentState, AgentMode, StateStore,
    PromptBuilder, TodoStore,
    OffloadStore, compact_messages, estimate_messages_size,
)
from ..safety import ApprovalGate
from ..skills import SkillLoader
from ..subagents.base import Subagent, SubagentResult
from ..tools.registry import ToolRegistry
from ..utils.exceptions import AgentError, ApprovalDeniedError, ToolError
from ..utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class LoopOutcome:
    """单次任务的最终结果。"""
    success: bool
    final_message: str
    new_posts: list[str]
    iterations: int


class AgenticLoop:
    """主 Agentic Loop。"""

    def __init__(self,
                 *,
                 cfg: AgentConfig,
                 client: anthropic.Anthropic,
                 registry: ToolRegistry,
                 prompt_builder: PromptBuilder,
                 state_store: StateStore,
                 todo_store: TodoStore,
                 offload_store: OffloadStore,
                 skill_loader: SkillLoader,
                 approval_gate: ApprovalGate,
                 subagents: dict[str, Subagent]):
        self.cfg = cfg
        self.client = client
        self.registry = registry
        self.prompt_builder = prompt_builder
        self.state_store = state_store
        self.todo_store = todo_store
        self.offload_store = offload_store
        self.skill_loader = skill_loader
        self.approval_gate = approval_gate
        self.subagents = subagents

    # ─────────────────────────────────────────
    def run(self, user_input: str, state: AgentState) -> LoopOutcome:
        """跑一个完整任务直到 end_turn 或失败。"""
        # 选出本次任务相关的技能
        matched_skills = self.skill_loader.select(user_input)
        skill_docs = self.skill_loader.render_docs(matched_skills) if matched_skills else None
        if matched_skills:
            log.info("命中技能：%s", [s.name for s in matched_skills])

        # 建立子智能体调度协议（注入到主 system prompt 末尾）
        subagent_prompt = self._render_subagent_protocol()

        # 组装初始 messages
        messages: list[dict] = [{"role": "user", "content": user_input}]
        new_posts: list[str] = []

        for iteration in range(self.cfg.max_iterations):
            # 每轮都重建 system prompt，因为 todo / state 可能已变
            todo = self.todo_store.load()
            current_state = self.state_store.load()
            system_prompt = (
                self.prompt_builder.build(current_state, todo, skill_docs)
                + "\n\n" + subagent_prompt
            )

            # 上下文压缩
            if len(messages) > self.cfg.compaction_threshold:
                messages = compact_messages(messages, keep_recent=self.cfg.compaction_keep_recent)

            response = self._call_llm(system_prompt, messages)

            if response.stop_reason == "end_turn":
                final_text = "".join(b.text for b in response.content if hasattr(b, "text"))
                return LoopOutcome(
                    success=True,
                    final_message=final_text,
                    new_posts=new_posts,
                    iterations=iteration + 1,
                )

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results = self._execute_tools(response.content, new_posts)
                messages.append({"role": "user", "content": tool_results})
                continue

            # 其他停止原因
            log.warning("非预期停止：%s", response.stop_reason)
            return LoopOutcome(
                success=False,
                final_message=f"模型异常停止：{response.stop_reason}",
                new_posts=new_posts,
                iterations=iteration + 1,
            )

        return LoopOutcome(
            success=False,
            final_message=f"达到最大轮次 {self.cfg.max_iterations}，任务可能未完成",
            new_posts=new_posts,
            iterations=self.cfg.max_iterations,
        )

    # ─────────────────────────────────────────
    def _call_llm(self, system_prompt: str, messages: list[dict]):
        """带重试的 API 调用。"""
        last_err: Exception | None = None
        for attempt in range(self.cfg.max_retries):
            try:
                return self.client.messages.create(
                    model=self.cfg.model,
                    max_tokens=self.cfg.max_tokens,
                    system=system_prompt,
                    tools=self.registry.schemas(),
                    messages=messages,
                )
            except anthropic.APIError as e:
                last_err = e
                log.warning("API 调用失败（%d/%d）：%s",
                            attempt + 1, self.cfg.max_retries, e)
        raise AgentError(f"API 重试 {self.cfg.max_retries} 次仍失败：{last_err}")

    # ─────────────────────────────────────────
    def _execute_tools(self, content_blocks, new_posts: list[str]) -> list[dict]:
        """处理本轮所有 tool_use 调用并返回 tool_result 列表。"""
        out: list[dict] = []
        for blk in content_blocks:
            if blk.type != "tool_use":
                continue

            tool_name = blk.name
            tool_input = blk.input
            log.info("🔧 调用 %s", tool_name)

            # ── 子智能体派发拦截 ──
            if tool_name == "delegate_to_subagent":
                result_str = self._delegate(tool_input)
                out.append({
                    "type": "tool_result",
                    "tool_use_id": blk.id,
                    "content": result_str,
                })
                continue

            # ── 审批门 ──
            try:
                tool = self.registry.get(tool_name)
            except ToolError as e:
                out.append({
                    "type": "tool_result",
                    "tool_use_id": blk.id,
                    "content": json.dumps({"error": str(e)}, ensure_ascii=False),
                })
                continue

            if tool.requires_approval:
                approved = self.approval_gate.request(tool_name, dict(tool_input))
                if not approved:
                    out.append({
                        "type": "tool_result",
                        "tool_use_id": blk.id,
                        "content": json.dumps({
                            "success": False,
                            "error": "用户拒绝了此操作。请向用户解释或选择其他方式。",
                        }, ensure_ascii=False),
                    })
                    continue

            # ── 执行 ──
            result_str = self.registry.execute(tool_name, dict(tool_input))

            # ── 卸载大输出 ──
            result_str = self.offload_store.maybe_offload(tool_name, result_str)

            # ── 收集产物 ──
            self._extract_artifacts(tool_name, result_str, new_posts)

            out.append({
                "type": "tool_result",
                "tool_use_id": blk.id,
                "content": result_str,
            })
        return out

    @staticmethod
    def _extract_artifacts(tool_name: str, result_str: str, new_posts: list[str]) -> None:
        """从工具结果中抓取产物（目前只关心新建的文章文件名）。"""
        if tool_name != "write_post":
            return
        try:
            data = json.loads(result_str)
            if data.get("success") and "filename" in data:
                new_posts.append(data["filename"])
                log.info("✅ 已写入：%s", data["filename"])
        except json.JSONDecodeError:
            pass

    # ─────────────────────────────────────────
    def _delegate(self, args: dict) -> str:
        """派发任务给子智能体。"""
        name = args.get("subagent")
        task = args.get("task", "")
        if name not in self.subagents:
            return json.dumps({
                "error": f"未知子智能体：{name}。可用：{list(self.subagents.keys())}",
            }, ensure_ascii=False)

        log.info("→ 派发给 [%s]：%s", name, task[:80])
        try:
            result: SubagentResult = self.subagents[name].run(task)
        except Exception as e:
            log.exception("子智能体 %s 异常", name)
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        return json.dumps(result.to_dict(), ensure_ascii=False)

    # ─────────────────────────────────────────
    def _render_subagent_protocol(self) -> str:
        """告诉主智能体如何调用 delegate_to_subagent。"""
        names = ", ".join(self.subagents.keys())
        return (
            "## 子智能体派发协议\n"
            f"你可以调用伪工具 `delegate_to_subagent` 把子任务委托给：{names}\n"
            "调用格式：subagent=<name>, task=<自然语言描述>\n"
            "派发原则：\n"
            "  - 写新文章 → writer\n"
            "  - 润色已有文章 → editor\n"
            "  - 推送前的检查 + 摘要 → publisher\n"
            "  - 简单的查询/状态查看由你自己用工具完成，无需派发\n"
            "  - 真正的 git_commit_push 由你自己调用（受审批门拦截）\n"
            "子智能体返回 {success, summary, artifacts} 三字段；"
            "你负责把多个子智能体的结果整合后向用户汇报。"
        )
