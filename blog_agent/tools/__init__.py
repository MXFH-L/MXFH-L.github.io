"""tools/ — 工具层。"""
from .registry import ToolRegistry, Tool, make_tool
from .post import build_post_tools
from .git import build_git_tools
from .todo import build_todo_tools
from .filesystem import build_filesystem_tools
from .verify import verify_post_file, verify_frontmatter, VerificationError

from ..config import AgentConfig
from ..harness.todo import TodoStore
from ..harness.state import StateStore
from typing import Callable


def build_default_registry(cfg: AgentConfig,
                           todo_store: TodoStore,
                           state_store: StateStore,
                           state_ref: Callable) -> ToolRegistry:
    """构建带全部工具的注册表。"""
    reg = ToolRegistry()

    for tool in build_post_tools(cfg):
        reg.register(tool)
    for tool in build_git_tools(cfg):
        reg.register(tool)
    for tool in build_todo_tools(todo_store, state_store, state_ref):
        reg.register(tool)
    for tool in build_filesystem_tools(cfg):
        reg.register(tool)

    return reg


__all__ = [
    "ToolRegistry", "Tool", "make_tool",
    "build_default_registry",
    "verify_post_file", "verify_frontmatter", "VerificationError",
]
