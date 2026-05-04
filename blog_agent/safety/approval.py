"""
safety/approval.py — 人工审批门

任何 requires_approval=True 的工具调用必须先经过这里。
默认实现是命令行交互；未来可以替换成 Slack / Web UI。
"""
from __future__ import annotations
from typing import Protocol

from ..utils.logging import get_logger

log = get_logger(__name__)


class ApprovalGate(Protocol):
    """审批门接口；未来可注入不同实现。"""
    def request(self, tool_name: str, arguments: dict) -> bool: ...


class CLIApprovalGate:
    """命令行审批：在终端弹出确认提示。"""

    def request(self, tool_name: str, arguments: dict) -> bool:
        print(f"\n{'─' * 60}")
        print(f"⚠️  智能体请求执行需审批的操作：{tool_name}")
        for k, v in arguments.items():
            preview = str(v)
            if len(preview) > 200:
                preview = preview[:200] + "..."
            print(f"   {k}: {preview}")
        print(f"{'─' * 60}")
        try:
            ans = input("批准此操作？(y/n): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return False
        approved = ans in ("y", "yes", "确认", "ok", "是")
        log.info("审批 %s: %s", tool_name, "通过" if approved else "拒绝")
        return approved


class AutoApproveGate:
    """无人值守模式：自动通过。仅用于测试，慎用。"""

    def request(self, tool_name: str, arguments: dict) -> bool:
        log.warning("AutoApprove 通过：%s", tool_name)
        return True
