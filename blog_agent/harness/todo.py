"""
harness/todo.py — 显性任务清单

强制智能体把多步任务拆成 [ ] 子任务，
每完成一步必须更新状态。
对应你设计文档里的"显性任务清单"+"反思与验证钩子"。
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class TodoStatus(str, Enum):
    PENDING = "pending"      # [ ]
    IN_PROGRESS = "in_progress"  # [→]
    DONE = "done"            # [✓]
    FAILED = "failed"        # [✗]


@dataclass
class TodoItem:
    id: str                  # 形如 "t1", "t2"
    description: str
    status: TodoStatus = TodoStatus.PENDING
    verification: Optional[str] = None   # 完成标准（自然语言描述）
    notes: Optional[str] = None          # 执行过程中的备注
    completed_at: Optional[str] = None

    def render(self) -> str:
        """渲染成 Markdown checkbox 文本（注入 Prompt 用）。"""
        marker = {
            TodoStatus.PENDING:     "[ ]",
            TodoStatus.IN_PROGRESS: "[→]",
            TodoStatus.DONE:        "[✓]",
            TodoStatus.FAILED:      "[✗]",
        }[self.status]
        line = f"{marker} {self.id}: {self.description}"
        if self.verification:
            line += f"  (验证: {self.verification})"
        if self.notes:
            line += f"  // {self.notes}"
        return line


@dataclass
class TodoList:
    """整张任务清单。"""
    goal: str = ""
    items: list[TodoItem] = field(default_factory=list)
    created_at: str = ""

    def render(self) -> str:
        """整体渲染：注入 System Prompt。"""
        if not self.items:
            return "（当前无活跃任务清单）"
        lines = [f"目标: {self.goal}", ""]
        lines.extend(item.render() for item in self.items)
        return "\n".join(lines)

    def progress(self) -> tuple[int, int]:
        """(已完成数, 总数)"""
        done = sum(1 for i in self.items if i.status == TodoStatus.DONE)
        return done, len(self.items)

    def is_complete(self) -> bool:
        return all(i.status == TodoStatus.DONE for i in self.items) and len(self.items) > 0

    def find(self, item_id: str) -> Optional[TodoItem]:
        return next((i for i in self.items if i.id == item_id), None)

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "created_at": self.created_at,
            "items": [
                {**asdict(i), "status": i.status.value}
                for i in self.items
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TodoList":
        items = [
            TodoItem(
                id=i["id"],
                description=i["description"],
                status=TodoStatus(i.get("status", "pending")),
                verification=i.get("verification"),
                notes=i.get("notes"),
                completed_at=i.get("completed_at"),
            )
            for i in data.get("items", [])
        ]
        return cls(
            goal=data.get("goal", ""),
            items=items,
            created_at=data.get("created_at", ""),
        )


class TodoStore:
    """Todo 列表的持久化层。"""

    def __init__(self, todo_file: Path):
        self.todo_file = todo_file

    def load(self) -> TodoList:
        if not self.todo_file.exists():
            return TodoList()
        data = json.loads(self.todo_file.read_text(encoding="utf-8"))
        return TodoList.from_dict(data)

    def save(self, todo: TodoList) -> None:
        self.todo_file.parent.mkdir(exist_ok=True)
        self.todo_file.write_text(
            json.dumps(todo.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def reset(self, goal: str, items: list[tuple[str, str | None]]) -> TodoList:
        """
        创建新清单。items 是 [(描述, 验证标准), ...]
        """
        todo_items = [
            TodoItem(
                id=f"t{idx+1}",
                description=desc,
                verification=verify,
            )
            for idx, (desc, verify) in enumerate(items)
        ]
        todo = TodoList(
            goal=goal,
            items=todo_items,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        self.save(todo)
        return todo

    def update(self, item_id: str, *,
               status: TodoStatus | None = None,
               notes: str | None = None) -> TodoList:
        """更新某个 item 的状态或备注。"""
        todo = self.load()
        item = todo.find(item_id)
        if item is None:
            raise KeyError(f"找不到 todo 项：{item_id}")
        if status is not None:
            item.status = status
            if status == TodoStatus.DONE:
                item.completed_at = datetime.now().strftime("%H:%M:%S")
        if notes is not None:
            item.notes = notes
        self.save(todo)
        return todo

    def clear(self) -> None:
        """任务彻底完成后清空清单。"""
        if self.todo_file.exists():
            self.todo_file.unlink()
