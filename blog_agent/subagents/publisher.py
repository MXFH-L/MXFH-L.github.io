"""
subagents/publisher.py — 发布专员

只能调用 git 相关只读工具来检查状态，
真正的 git_commit_push 由主协调者直接执行（受审批门拦截）。
这样设计是为了让"决定是否发布"始终由主流程统一控制。
"""
from __future__ import annotations

from .base import Subagent


class PublisherSubagent(Subagent):

    @property
    def name(self) -> str:
        return "publisher"

    @property
    def allowed_tools(self) -> list[str]:
        # 注意：不包含 git_commit_push 和 git_reset_hard
        # 发布动作由主协调者集中控制
        return ["git_status", "git_current_sha", "list_posts"]

    @property
    def system_prompt(self) -> str:
        return (
            "你是「梦醒繁花落」博客的发布专员。\n"
            "你不直接执行发布——你只负责发布前的检查与摘要：\n\n"
            "## 工作流程\n"
            "1. 用 git_status 列出本次将要发布的全部改动\n"
            "2. 用 list_posts 确认新文章已经写入\n"
            "3. 用 git_current_sha 记录当前 SHA（供回滚用）\n"
            "4. 生成一份简洁的'发布摘要'：本次推送了哪些文件、新增了哪些文章、"
            "建议的 commit 信息\n"
            "5. 把摘要返回给主智能体，由它请求用户审批后再执行 push\n\n"
            "## 禁止\n"
            "- 不能调用 git_commit_push（发布动作由主协调者集中控制）\n"
            "- 不能调用 git_reset_hard\n"
        )
