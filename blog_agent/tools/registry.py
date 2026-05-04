"""
tools/registry.py — 工具注册表

用装饰器 @tool 注册函数；同时收集供 Claude API 用的 schema。
其他模块只与 ToolRegistry 交互，不直接接触工具实现细节。
"""
from __future__ import annotations
import inspect
import json
from dataclasses import dataclass
from typing import Callable, Any

from ..utils.exceptions import ToolError
from ..utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    func: Callable[..., dict]
    requires_approval: bool = False  # True 时由 safety/approval 拦截


class ToolRegistry:
    """全局工具注册表。"""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"工具重名：{tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise ToolError(name, "工具未注册")
        return self._tools[name]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def schemas(self, only: list[str] | None = None) -> list[dict]:
        """生成传给 Claude API 的 tools 参数。可指定子集（实现技能渐进披露）。"""
        items = self._tools.values() if only is None else [
            self._tools[n] for n in only if n in self._tools
        ]
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in items
        ]

    def execute(self, name: str, arguments: dict) -> str:
        """统一执行入口；返回 JSON 字符串结果。"""
        tool = self.get(name)
        log.debug("执行工具 %s，参数：%s", name, arguments)

        # 过滤多余参数：只保留工具签名声明过的参数
        # （某些中转 API 可能在 schema 转译时塞入 _ 等占位字段）
        import inspect
        try:
            sig = inspect.signature(tool.func)
            valid_keys = set(sig.parameters.keys())
            # 若函数签名里有 **kwargs 形参，则全部放行
            has_var_kw = any(
                p.kind == inspect.Parameter.VAR_KEYWORD
                for p in sig.parameters.values()
            )
            if not has_var_kw:
                filtered = {k: v for k, v in arguments.items() if k in valid_keys}
                dropped = set(arguments.keys()) - valid_keys
                if dropped:
                    log.debug("丢弃 %s 的多余参数：%s", name, dropped)
                arguments = filtered
        except (ValueError, TypeError):
            pass  # 无法内省时按原样传

        try:
            result = tool.func(**arguments)
            return json.dumps(result, ensure_ascii=False)
        except TypeError as e:
            raise ToolError(name, f"参数错误：{e}") from e
        except Exception as e:
            log.exception("工具 %s 执行异常", name)
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# ───────────────────────────────────────────────────────────
# 装饰器
# ───────────────────────────────────────────────────────────

def make_tool(*,
              name: str,
              description: str,
              input_schema: dict,
              requires_approval: bool = False):
    """
    将函数封装成 Tool 对象。返回的对象既可直接调用（保留原函数语义），
    也可作为 Tool 注册到 registry。

    用法：
        my_tool = make_tool(name=..., description=..., input_schema=...)(my_func)
        registry.register(my_tool)
    """
    def decorator(func: Callable[..., dict]) -> Tool:
        return Tool(
            name=name,
            description=description,
            input_schema=input_schema,
            func=func,
            requires_approval=requires_approval,
        )
    return decorator
