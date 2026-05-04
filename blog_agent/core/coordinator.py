"""
core/coordinator.py — 协调者（顶层 Agent）

职责：
  · 组装所有依赖（受 AgentConfig 驱动）
  · 决定任务级流程：snapshot → run loop → record/rollback
  · 统一异常处理边界
"""
from __future__ import annotations

import anthropic

from ..config import AgentConfig
from ..harness import (
    AgentState, AgentMode, StateStore, MemoryStore,
    PromptBuilder, TodoStore, OffloadStore,
)
from ..safety import ApprovalGate, CLIApprovalGate, RollbackManager
from ..skills import SkillLoader
from ..subagents import (
    Subagent, WriterSubagent, EditorSubagent, PublisherSubagent,
)
from ..tools import build_default_registry
from ..tools.registry import make_tool, ToolRegistry, Tool
from ..utils.exceptions import AgentError
from ..utils.logging import get_logger

from .loop import AgenticLoop, LoopOutcome

log = get_logger(__name__)


def _add_delegate_pseudo_tool(reg: ToolRegistry, subagent_names: list[str]) -> None:
    """
    向注册表添加 delegate_to_subagent 伪工具。
    这是一个 schema-only 工具——真正的执行被 AgenticLoop 拦截了，
    不会调用这里的 func（但 func 仍需存在，否则注册时报错）。
    """
    @make_tool(
        name="delegate_to_subagent",
        description=(
            "把一个子任务委托给独立的子智能体。"
            f"可用子智能体：{', '.join(subagent_names)}。"
            "适用于需要上下文隔离的子任务（如写一篇完整文章、推送前检查）。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "subagent": {"type": "string", "enum": subagent_names},
                "task": {"type": "string", "description": "子任务的自然语言描述"},
            },
            "required": ["subagent", "task"],
        },
    )
    def _delegate_pseudo(subagent: str, task: str) -> dict:  # 永远不会被真正调用
        return {"error": "should be intercepted by loop"}

    reg.register(_delegate_pseudo)


class Coordinator:
    """顶层智能体：博客系统的"协调者"。"""

    def __init__(self,
                 cfg: AgentConfig,
                 approval_gate: ApprovalGate | None = None):
        self.cfg = cfg
        self.cfg.ensure_dirs()

        client_kwargs = {"api_key": cfg.api_key}
        if cfg.base_url:
            client_kwargs["base_url"] = cfg.base_url
        self.client = anthropic.Anthropic(**client_kwargs)

        # ── Harness 层 ────────────────────
        self.memory_store = MemoryStore(cfg.agents_md, cfg.memory_md)
        self.memory_store.ensure_initialized()

        self.state_store = StateStore(cfg.state_file)
        self.todo_store = TodoStore(cfg.todo_file)
        self.offload_store = OffloadStore(cfg.offload_dir, cfg.offload_threshold)

        self.skill_loader = SkillLoader(cfg.skills_dir)
        self.skill_loader.reload()

        self.prompt_builder = PromptBuilder(self.memory_store, cfg.site_url)

        # ── 工具层（含子智能体派发伪工具） ──
        # state_ref 让工具们总能拿到最新状态
        self.registry = build_default_registry(
            cfg, self.todo_store, self.state_store,
            state_ref=lambda: self.state_store.load(),
        )

        # ── 子智能体 ──────────────────────
        self.subagents: dict[str, Subagent] = {
            "writer": WriterSubagent(cfg, self.client, self.registry),
            "editor": EditorSubagent(cfg, self.client, self.registry),
            "publisher": PublisherSubagent(cfg, self.client, self.registry),
        }
        _add_delegate_pseudo_tool(self.registry, list(self.subagents.keys()))

        # ── 安全层 ────────────────────────
        self.approval_gate = approval_gate or CLIApprovalGate()
        self.rollback = RollbackManager(cfg.blog_root)

        # ── 主循环 ────────────────────────
        self.loop = AgenticLoop(
            cfg=cfg,
            client=self.client,
            registry=self.registry,
            prompt_builder=self.prompt_builder,
            state_store=self.state_store,
            todo_store=self.todo_store,
            offload_store=self.offload_store,
            skill_loader=self.skill_loader,
            approval_gate=self.approval_gate,
            subagents=self.subagents,
        )

    # ─────────────────────────────────────────
    def handle_task(self, user_input: str) -> LoopOutcome:
        """处理一次用户任务的完整生命周期。"""
        state = self.state_store.load()
        state.current_task = user_input[:200]
        self.state_store.save(state)

        # 任务开始前打快照，失败时回滚
        self.rollback.snapshot()

        try:
            outcome = self.loop.run(user_input, state)
        except AgentError as e:
            log.error("任务失败：%s", e)
            self.rollback.rollback(reason=str(e))
            self.state_store.record_task(
                self.state_store.load(),
                user_input=user_input,
                summary=f"失败：{e}",
                posts_created=[],
                status="rolled_back",
            )
            return LoopOutcome(
                success=False,
                final_message=f"任务失败并已回滚。原因：{e}",
                new_posts=[],
                iterations=0,
            )

        # 成功路径
        status = "completed" if outcome.success else "failed"
        self.state_store.record_task(
            self.state_store.load(),
            user_input=user_input,
            summary=outcome.final_message[:200],
            posts_created=outcome.new_posts,
            status=status,
        )

        # 任务正常结束后清空 Todo（避免下次任务被旧清单干扰）
        if outcome.success:
            self.todo_store.clear()

        return outcome
