"""
tools/todo.py — Todo 操控工具

智能体在 PLANNING 模式下用 plan_create 创建清单；
切到 EXECUTING 模式后，每完成一个子任务用 plan_update 标记进度。
"""
from __future__ import annotations
from typing import Callable

from .registry import make_tool
from ..harness.todo import TodoStore, TodoStatus
from ..harness.state import AgentState, AgentMode, StateStore


def build_todo_tools(todo_store: TodoStore,
                     state_store: StateStore,
                     state_ref: Callable[[], AgentState]) -> list:
    """
    state_ref 是一个无参回调，每次调用时返回最新的 AgentState 实例。
    这是为了避免闭包捕获已过期的状态。
    """

    @make_tool(
        name="plan_create",
        description=(
            "创建任务清单（仅在 PLANNING 模式下使用）。"
            "把目标拆成 3~10 个原子子任务，每个子任务可选地附带验证标准。"
            "调用后会将状态切换到 EXECUTING（待用户确认）。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "总体目标的一句话描述"},
                "items": {
                    "type": "array",
                    "description": "子任务列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string", "description": "子任务描述"},
                            "verification": {"type": "string", "description": "完成标准（可选）"},
                        },
                        "required": ["description"],
                    },
                },
            },
            "required": ["goal", "items"],
        },
    )
    def plan_create(goal: str, items: list[dict]) -> dict:
        parsed: list[tuple[str, str | None]] = [
            (it["description"], it.get("verification")) for it in items
        ]
        todo = todo_store.reset(goal, parsed)
        # 切到 executing 模式
        state = state_ref()
        state.mode = AgentMode.EXECUTING
        state_store.save(state)
        return {
            "success": True,
            "message": f"清单已创建（{len(parsed)} 项），模式切换为 EXECUTING。",
            "rendered": todo.render(),
        }

    @make_tool(
        name="plan_update",
        description=(
            "更新某个子任务的状态。每完成一项立即调用此工具。"
            "status 可选：pending / in_progress / done / failed。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "子任务编号，如 t1"},
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "done", "failed"],
                },
                "notes": {"type": "string", "description": "可选的执行备注"},
            },
            "required": ["item_id", "status"],
        },
    )
    def plan_update(item_id: str, status: str, notes: str | None = None) -> dict:
        try:
            todo = todo_store.update(
                item_id,
                status=TodoStatus(status),
                notes=notes,
            )
        except KeyError as e:
            return {"success": False, "error": str(e)}
        done, total = todo.progress()
        return {
            "success": True,
            "progress": f"{done}/{total}",
            "complete": todo.is_complete(),
        }

    @make_tool(
        name="plan_show",
        description="查看当前任务清单（仅查询，不修改）。",
        input_schema={"type": "object", "properties": {}},
    )
    def plan_show() -> dict:
        todo = todo_store.load()
        if not todo.items:
            return {"items": [], "rendered": "（暂无任务清单）"}
        return {
            "goal": todo.goal,
            "rendered": todo.render(),
            "progress": "/".join(map(str, todo.progress())),
        }

    return [plan_create, plan_update, plan_show]
