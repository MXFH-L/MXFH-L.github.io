"""
tools/post.py — 文章 CRUD 工具
每个写操作都内置最小验证（frontmatter 合法、文件存在等）。
"""
from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path

from .registry import make_tool
from .verify import verify_frontmatter, verify_post_file
from ..config import AgentConfig
from ..utils.exceptions import VerificationError


_SLUG_PATTERN = re.compile(r"[^a-z0-9-]")


def _slugify(title: str) -> str:
    """生成英文 slug；非 ASCII 字符无法转换时降级用 'post'。"""
    s = title.lower().replace(" ", "-")
    s = _SLUG_PATTERN.sub("", s)
    return (s or "post")[:50].strip("-")


def build_post_tools(cfg: AgentConfig) -> list:

    @make_tool(
        name="write_post",
        description=(
            "在 source/_posts/ 创建一篇新文章。"
            "自动生成符合 Hexo 规范的 frontmatter。"
            "完成后会自动校验文件合法性。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "title":      {"type": "string", "description": "文章标题（中文亦可）"},
                "slug":       {"type": "string", "description": "URL slug，仅 a-z 0-9 -；可选，省略时自动生成"},
                "content":    {"type": "string", "description": "正文 Markdown"},
                "tags":       {"type": "array",  "items": {"type": "string"}, "description": "标签 3-5 个"},
                "categories": {"type": "array",  "items": {"type": "string"}, "description": "分类 1-2 个"},
            },
            "required": ["title", "content"],
        },
    )
    def write_post(title: str, content: str,
                   slug: str | None = None,
                   tags: list[str] | None = None,
                   categories: list[str] | None = None) -> dict:
        cfg.posts_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        slug = _slugify(slug or title)
        filename = f"{date_str}-{slug}.md"
        filepath = cfg.posts_dir / filename

        if filepath.exists():
            return {
                "success": False,
                "error": f"文件已存在：{filename}。请改用不同 slug 或先删除旧文件。",
            }

        tags_yaml = "\n".join(f"  - {t}" for t in (tags or [])) or "  []"
        cats_yaml = "\n".join(f"  - {c}" for c in (categories or [])) or "  []"
        frontmatter = (
            f"---\n"
            f"title: {title}\n"
            f"date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"tags:\n{tags_yaml}\n"
            f"categories:\n{cats_yaml}\n"
            f"---\n\n"
        )
        filepath.write_text(frontmatter + content, encoding="utf-8")

        # 验证钩子：写完立即检查 frontmatter 合法
        try:
            verify_post_file(filepath)
        except VerificationError as ve:
            filepath.unlink(missing_ok=True)
            return {"success": False, "error": f"文章写入但验证失败：{ve}"}

        return {
            "success": True,
            "filename": filename,
            "path": str(filepath),
            "word_count": len(content),
        }

    @make_tool(
        name="list_posts",
        description="列出最近的博客文章（文件名 + 标题）。",
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "返回数量上限，默认 10"},
            },
        },
    )
    def list_posts(limit: int = 10) -> dict:
        if not cfg.posts_dir.exists():
            return {"posts": [], "total": 0}

        posts: list[dict] = []
        for f in sorted(cfg.posts_dir.glob("*.md"), reverse=True)[:limit]:
            title = f.stem
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.startswith("title:"):
                    title = line.split("title:", 1)[1].strip()
                    break
            posts.append({"filename": f.name, "title": title})

        return {"posts": posts, "total": len(posts)}

    @make_tool(
        name="read_post",
        description="读取已存在文章的完整内容（包含 frontmatter）。",
        input_schema={
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "文件名，如 2025-05-04-my-post.md"},
            },
            "required": ["filename"],
        },
    )
    def read_post(filename: str) -> dict:
        fp = cfg.posts_dir / filename
        if not fp.exists():
            return {"success": False, "error": f"找不到文件：{filename}"}
        return {
            "success": True,
            "filename": filename,
            "content": fp.read_text(encoding="utf-8"),
        }

    return [write_post, list_posts, read_post]
