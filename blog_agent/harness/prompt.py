"""
harness/prompt.py — 动态 System Prompt 组装

每次调用 LLM 之前，按以下顺序拼接：
  1. AGENTS.md      （宪法，永远在最前）
  2. MEMORY.md      （长期偏好）
  3. 当前模式与状态（IDLE / PLANNING / EXECUTING）
  4. 当前 Todo 清单（如果有）
  5. 已加载的技能说明（按当前阶段动态注入）
  6. 历史摘要（最近 5 条任务）

每一节都是可选的；缺失的节直接跳过。
"""
from __future__ import annotations
from datetime import datetime

from .memory import MemoryStore
from .state import AgentState, AgentMode
from .todo import TodoList


class PromptBuilder:
    """组装最终的 System Prompt。"""

    def __init__(self, memory: MemoryStore, site_url: str):
        self.memory = memory
        self.site_url = site_url

    def build(self,
              state: AgentState,
              todo: TodoList,
              skill_docs: list[str] | None = None) -> str:
        """组装 System Prompt 字符串。"""
        sections: list[str] = []

        # ── 1. 头部 ─────────────────────────
        sections.append(
            f"# 系统时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"# 博客站点：{self.site_url}\n"
            f"# 当前会话编号：{state.session_count}"
        )

        # ── 2. AGENTS.md（宪法） ────────────
        agents_text = self.memory.read_agents()
        if agents_text:
            sections.append("# === 宪法（AGENTS.md，不可违反） ===\n" + agents_text)

        # ── 3. MEMORY.md（偏好库） ──────────
        memory_text = self.memory.read_memory()
        if memory_text:
            sections.append("# === 长期记忆（MEMORY.md） ===\n" + memory_text)

        # ── 4. 当前模式与状态 ───────────────
        mode_block = self._render_mode(state)
        sections.append("# === 当前状态 ===\n" + mode_block)

        # ── 5. Todo 清单 ────────────────────
        if todo.items:
            done, total = todo.progress()
            sections.append(
                f"# === 当前任务清单（{done}/{total} 已完成） ===\n"
                + todo.render()
            )

        # ── 6. 技能说明 ─────────────────────
        if skill_docs:
            sections.append(
                "# === 当前已加载技能 ===\n"
                + "\n\n".join(skill_docs)
            )

        # ── 7. 近期任务历史 ─────────────────
        if state.task_history:
            recent = state.task_history[-5:]
            history = "\n".join(
                f"- [{r.timestamp}] {r.user_input} → {r.status}"
                for r in recent
            )
            sections.append("# === 最近任务历史 ===\n" + history)

        # ── 8. 工作流程铁律 ─────────────────
        sections.append(self._render_workflow_rules(state))

        return "\n\n".join(sections)

    # ─────────────────────────────────────────
    def _render_mode(self, state: AgentState) -> str:
        mode_desc = {
            AgentMode.IDLE: "空闲。可以接受新任务。",
            AgentMode.PLANNING: (
                "规划模式。**只能调用 plan_create / plan_update 工具**，"
                "禁止执行任何写操作，直到清单被批准并切换到 EXECUTING。"
            ),
            AgentMode.EXECUTING: (
                "执行模式。按 Todo 清单顺序执行；每完成一项立即调用 "
                "todo_update 更新状态。"
            ),
        }
        return f"模式：{state.mode.value}\n含义：{mode_desc[state.mode]}"

    def _render_workflow_rules(self, state: AgentState) -> str:
        return (
            "# === 工作流程铁律 ===\n"
            "1. 任务步骤 ≥ 3 时，必须先进入 PLANNING 模式，调用 plan_create 生成清单，"
            "等待用户确认后再切换到 EXECUTING。\n"
            "2. 每次调用 git_commit_push 之前，必须先用自然语言摘要本次推送的内容，"
            "等待用户明确说「确认 / 发布 / 推送 / y」才能调用。\n"
            "3. 工具调用失败时，先尝试自我修复（最多 2 次）；仍失败则向用户说明并停止。\n"
            "4. 不知道某个事实时，明确说「不确定」，**禁止编造**。\n"
            "5. 写文章时，遵循 AGENTS.md 中的写作规范；写完后必须等待确认才推送。"
        )
