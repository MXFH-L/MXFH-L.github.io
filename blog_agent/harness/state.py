"""
harness/state.py — 智能体运行时状态

用 dataclass + JSON 持久化，保证：
  · 类型安全（IDE 能补全字段）
  · 可序列化（容易调试、可手动编辑）
  · 进程崩溃不丢数据（每次变更立即写盘）
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from ..utils.exceptions import HarnessError


class AgentMode(str, Enum):
    """智能体当前所处的模式。"""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"


@dataclass
class TaskRecord:
    """单次任务的归档记录。"""
    timestamp: str
    user_input: str
    summary: str
    posts_created: list[str]
    status: str  # "completed" | "failed" | "rolled_back"


@dataclass
class AgentState:
    """整个智能体的可持久化状态。"""
    session_count: int = 0
    mode: AgentMode = AgentMode.IDLE
    current_task: Optional[str] = None
    task_history: list[TaskRecord] = field(default_factory=list)
    posts_created: list[str] = field(default_factory=list)
    last_safe_commit: Optional[str] = None  # 用于回滚

    # ── 序列化 ───────────────────────────
    def to_dict(self) -> dict:
        d = asdict(self)
        d["mode"] = self.mode.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "AgentState":
        records = [TaskRecord(**r) for r in data.get("task_history", [])]
        return cls(
            session_count=data.get("session_count", 0),
            mode=AgentMode(data.get("mode", "idle")),
            current_task=data.get("current_task"),
            task_history=records,
            posts_created=data.get("posts_created", []),
            last_safe_commit=data.get("last_safe_commit"),
        )


class StateStore:
    """状态读写门面。"""

    def __init__(self, state_file: Path):
        self.state_file = state_file

    def load(self) -> AgentState:
        """加载状态，文件不存在时返回初始状态。"""
        if not self.state_file.exists():
            return AgentState()
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            return AgentState.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise HarnessError(f"状态文件损坏（{self.state_file}）：{e}") from e

    def save(self, state: AgentState) -> None:
        """原子化写盘：先写临时文件再 rename，避免崩溃损坏。"""
        self.state_file.parent.mkdir(exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.state_file)

    def record_task(self, state: AgentState, *,
                    user_input: str,
                    summary: str,
                    posts_created: list[str],
                    status: str = "completed") -> None:
        """记录一次任务并持久化。"""
        record = TaskRecord(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_input=user_input[:200],
            summary=summary[:200],
            posts_created=posts_created,
            status=status,
        )
        state.task_history.append(record)
        state.task_history = state.task_history[-50:]  # 滚动保留最近 50 条
        state.posts_created.extend(posts_created)
        state.posts_created = state.posts_created[-50:]
        state.session_count += 1
        state.current_task = None
        state.mode = AgentMode.IDLE
        self.save(state)
