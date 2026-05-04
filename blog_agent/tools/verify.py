"""
tools/verify.py — 验证钩子

对应你设计文档里的"反思与验证钩子"：
每个写操作之后，自动用代码硬性检查产物合法性。
失败时抛 VerificationError，由上层决定回滚还是让模型重试。
"""
from __future__ import annotations
import re
from pathlib import Path

from ..utils.exceptions import VerificationError


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_REQUIRED_FIELDS = {"title", "date", "tags", "categories"}


def verify_frontmatter(text: str) -> dict:
    """
    解析并校验 Hexo frontmatter。
    返回字段字典；不合法则抛 VerificationError。
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise VerificationError("frontmatter", "缺失或格式不正确（必须以 --- 包围）")

    fm = m.group(1)
    fields: dict[str, str] = {}
    for line in fm.splitlines():
        if ":" in line and not line.startswith(" "):
            key, _, val = line.partition(":")
            fields[key.strip()] = val.strip()

    missing = _REQUIRED_FIELDS - fields.keys()
    if missing:
        raise VerificationError(
            "frontmatter",
            f"缺少必需字段：{', '.join(sorted(missing))}",
        )

    if not fields.get("title"):
        raise VerificationError("frontmatter", "title 不能为空")

    return fields


def verify_post_file(filepath: Path) -> None:
    """
    校验一篇已写入磁盘的文章：
      1. 文件存在
      2. UTF-8 编码
      3. frontmatter 合法
      4. 正文非空（至少 50 字）
    """
    if not filepath.exists():
        raise VerificationError("file_exists", f"文件不存在：{filepath}")

    try:
        text = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise VerificationError("encoding", "文件不是 UTF-8 编码") from e

    verify_frontmatter(text)

    body = _FRONTMATTER_RE.sub("", text, count=1).strip()
    if len(body) < 50:
        raise VerificationError(
            "body_length",
            f"正文过短（{len(body)} 字符），疑似生成不完整",
        )
