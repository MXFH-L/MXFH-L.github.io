"""
tools/filesystem.py — 受限文件系统工具

read_file  → 只允许读博客根目录里的文件
read_note  → 只允许读 Obsidian 笔记库；只读，不能写
list_notes → 列出笔记库的目录结构（可指定子目录）
"""
from __future__ import annotations
from pathlib import Path

from .registry import make_tool
from ..config import AgentConfig


def _safe_join(root: Path, rel: str) -> Path | None:
    """把相对路径解析到根目录之内，越权返回 None。"""
    full = (root / rel).resolve()
    try:
        full.relative_to(root.resolve())
    except ValueError:
        return None
    return full


def build_filesystem_tools(cfg: AgentConfig) -> list:
    tools: list = []

    # ── 博客内文件读取 ─────────────────────
    @make_tool(
        name="read_file",
        description=(
            "读取博客根目录内的纯文本文件（AGENTS.md、MEMORY.md、"
            ".agent/offload/ 下的卸载产物等）。"
            "禁止读取博客目录之外的文件。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对博客根目录的路径"}
            },
            "required": ["path"],
        },
    )
    def read_file(path: str) -> dict:
        full = _safe_join(cfg.blog_root, path)
        if full is None:
            return {"success": False, "error": "禁止读取博客目录之外的文件"}
        if not full.exists():
            return {"success": False, "error": f"文件不存在：{path}"}
        if not full.is_file():
            return {"success": False, "error": f"不是文件：{path}"}
        try:
            content = full.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return {"success": False, "error": "文件编码不是 UTF-8"}
        return {"success": True, "path": str(full),
                "size": len(content), "content": content}

    tools.append(read_file)

    # ── Obsidian 笔记库（只读） ─────────────
    if cfg.obsidian_vault is not None and cfg.obsidian_vault.exists():
        vault = cfg.obsidian_vault

        @make_tool(
            name="read_note",
            description=(
                f"读取 Obsidian 笔记库（{vault}）中的某篇笔记。"
                "用于在写博客时引用我的个人笔记内容。只读，不能写。"
                "路径用相对笔记库根目录的形式，如 '主题/某篇笔记.md'。"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "相对笔记库根目录的路径"}
                },
                "required": ["path"],
            },
        )
        def read_note(path: str) -> dict:
            full = _safe_join(vault, path)
            if full is None:
                return {"success": False, "error": "禁止读取笔记库之外的文件"}
            if not full.exists():
                return {"success": False, "error": f"笔记不存在：{path}"}
            if not full.is_file():
                return {"success": False, "error": f"不是文件：{path}"}
            try:
                content = full.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                return {"success": False, "error": "文件编码不是 UTF-8"}
            return {
                "success": True,
                "path": str(full.relative_to(vault)),
                "size": len(content),
                "content": content,
            }

        @make_tool(
            name="list_notes",
            description=(
                f"列出 Obsidian 笔记库（{vault}）中的笔记。"
                "可指定子目录；不指定则列出根目录。"
                "只列 .md 文件和子文件夹，不返回正文。"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "subdir": {
                        "type": "string",
                        "description": "笔记库下的子目录路径（可选，默认根目录）",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "是否递归列出所有子目录的笔记（默认 false）",
                    },
                },
            },
        )
        def list_notes(subdir: str = "", recursive: bool = False) -> dict:
            base = _safe_join(vault, subdir) if subdir else vault
            if base is None or not base.exists():
                return {"success": False, "error": f"目录不存在：{subdir}"}
            if not base.is_dir():
                return {"success": False, "error": f"不是目录：{subdir}"}

            pattern = "**/*.md" if recursive else "*.md"
            notes: list[str] = []
            folders: list[str] = []

            for p in sorted(base.glob(pattern)):
                if p.is_file():
                    notes.append(str(p.relative_to(vault)))

            if not recursive:
                for p in sorted(base.iterdir()):
                    if p.is_dir() and not p.name.startswith("."):
                        folders.append(str(p.relative_to(vault)))

            return {
                "success": True,
                "subdir": subdir or "(root)",
                "notes": notes,
                "folders": folders,
                "total_notes": len(notes),
            }

        tools.extend([read_note, list_notes])

    return tools