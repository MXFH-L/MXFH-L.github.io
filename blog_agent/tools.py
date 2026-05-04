"""
tools.py — Harness 工具层
每个函数是智能体能真实操作的一个能力单元。
LLM 只返回"我要调用 XX"，这里才是真正执行的地方。
"""
import os
import subprocess
import json
from datetime import datetime
from pathlib import Path


def _blog_root() -> Path:
    root = os.environ.get("HEXO_BLOG_ROOT", ".")
    return Path(root).expanduser().resolve()


# ── 工具 1：写文章 ──────────────────────────────────────
def write_post(title: str, content: str,
               tags: list | None = None,
               categories: list | None = None) -> dict:
    """在 source/_posts/ 创建一篇新 Hexo 文章。"""
    posts_dir = _blog_root() / "source" / "_posts"
    posts_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    safe = title.lower().replace(" ", "-")
    safe = "".join(c for c in safe if c.isalnum() or c == "-")[:50]
    filename = f"{date_str}-{safe}.md"
    filepath = posts_dir / filename

    tags_yaml  = "\n".join(f"  - {t}" for t in (tags or []))
    cats_yaml  = "\n".join(f"  - {c}" for c in (categories or []))

    frontmatter = (
        f"---\n"
        f"title: {title}\n"
        f"date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"tags:\n{tags_yaml  or '  []'}\n"
        f"categories:\n{cats_yaml or '  []'}\n"
        f"---\n\n"
    )

    filepath.write_text(frontmatter + content, encoding="utf-8")
    return {"success": True, "filename": filename, "path": str(filepath)}


# ── 工具 2：列出文章 ────────────────────────────────────
def list_posts(limit: int = 10) -> dict:
    """列出最近的博客文章（文件名 + 标题）。"""
    posts_dir = _blog_root() / "source" / "_posts"
    if not posts_dir.exists():
        return {"posts": [], "total": 0}

    posts = []
    for f in sorted(posts_dir.glob("*.md"), reverse=True)[:limit]:
        title = f.stem
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("title:"):
                title = line.split("title:", 1)[1].strip()
                break
        posts.append({"filename": f.name, "title": title})

    return {"posts": posts, "total": len(posts)}


# ── 工具 3：读取文章 ────────────────────────────────────
def read_post(filename: str) -> dict:
    """读取某篇文章的完整内容。"""
    filepath = _blog_root() / "source" / "_posts" / filename
    if not filepath.exists():
        return {"success": False, "error": f"找不到文件：{filename}"}
    return {"success": True, "filename": filename,
            "content": filepath.read_text(encoding="utf-8")}


# ── 工具 4：提交并推送 ──────────────────────────────────
def git_commit_push(commit_message: str) -> dict:
    """git add → commit → push，触发 GitHub Pages 部署。"""
    root = _blog_root()

    def run(cmd):
        return subprocess.run(cmd, cwd=root, capture_output=True, text=True)

    r = run(["git", "add", "-A"])
    if r.returncode != 0:
        return {"success": False, "stage": "git add", "error": r.stderr}

    r = run(["git", "commit", "-m", commit_message])
    if r.returncode != 0:
        if "nothing to commit" in r.stdout:
            return {"success": True, "message": "没有新变更，无需提交。"}
        return {"success": False, "stage": "git commit", "error": r.stderr}

    r = run(["git", "push"])
    if r.returncode != 0:
        return {"success": False, "stage": "git push", "error": r.stderr}

    return {
        "success": True,
        "message": "推送成功！GitHub Actions 正在部署，约 1~2 分钟后可访问 https://mxfh-l.github.io/"
    }


# ── Tool Schemas（提供给 Claude API）─────────────────────
TOOL_SCHEMAS = [
    {
        "name": "write_post",
        "description": "在 Hexo 博客 source/_posts/ 目录创建新文章，自动生成 frontmatter。",
        "input_schema": {
            "type": "object",
            "properties": {
                "title":      {"type": "string", "description": "文章标题"},
                "content":    {"type": "string", "description": "文章正文，Markdown 格式"},
                "tags":       {"type": "array",  "items": {"type": "string"}, "description": "标签列表"},
                "categories": {"type": "array",  "items": {"type": "string"}, "description": "分类列表"},
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "list_posts",
        "description": "列出最近的博客文章（文件名和标题），用于了解已有内容。",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "返回数量上限，默认 10"}
            },
        },
    },
    {
        "name": "read_post",
        "description": "读取某篇文章的完整内容，用于修改或参考。",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "文件名，如 2025-05-04-my-post.md"}
            },
            "required": ["filename"],
        },
    },
    {
        "name": "git_commit_push",
        "description": (
            "将本地改动提交并推送到 GitHub，触发 GitHub Pages 自动部署。"
            "必须在用户明确确认后才可调用。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "commit_message": {"type": "string", "description": "Git commit 信息"}
            },
            "required": ["commit_message"],
        },
    },
]

TOOL_MAP = {
    "write_post":      write_post,
    "list_posts":      list_posts,
    "read_post":       read_post,
    "git_commit_push": git_commit_push,
}
