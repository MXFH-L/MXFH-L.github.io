"""
subagents/writer.py — 写作专员

只允许写文章和读已有文章；不能 git push。
工具白名单：write_post / list_posts / read_post。
"""
from __future__ import annotations

from .base import Subagent


class WriterSubagent(Subagent):

    @property
    def name(self) -> str:
        return "writer"

    @property
    def allowed_tools(self) -> list[str]:
        return ["write_post", "list_posts", "read_post"]

    @property
    def system_prompt(self) -> str:
        return (
            "你是「梦醒繁花落」博客的写作专员。\n"
            "你的唯一职责是写出高质量的 Markdown 博客文章并写入本地。\n\n"
            "## 写作规范\n"
            "- 结构：引言（点题）→ 正文（3~5 个分小节）→ 总结（升华或展望）\n"
            "- 长度：1200~3000 字之间为宜\n"
            "- 标签：3~5 个，准确反映主题\n"
            "- 分类：1~2 个\n"
            "- 代码主题：必须包含可运行代码块，标注语言\n"
            "- 风格：简洁有力，避免空话套话；可在合适处用类比或例子\n\n"
            "## 工作流程\n"
            "1. 必要时先用 list_posts 看看已有文章避免重复\n"
            "2. 用 write_post 写入文章\n"
            "3. 写完后向主智能体返回一句话摘要：标题 + 文件名 + 字数\n\n"
            "## 禁止\n"
            "- 不能调用任何 git 工具——发布是发布专员的事\n"
            "- 不能修改已发布的文章——修改请明确告知主智能体让其分配给编辑专员\n"
        )
