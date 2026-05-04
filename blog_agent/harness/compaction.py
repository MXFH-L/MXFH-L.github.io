"""
harness/compaction.py — 上下文管理

两件事，对应你设计文档里：
  1. 工具输出卸载（Offloading）
     工具返回 >2000 字符时，写入 .agent/offload/ 文件，
     上下文中只保留路径 + 摘要，避免上下文窗口被一次大输出吃掉。
  2. 运行时上下文压缩（Compaction）
     messages 超过阈值时，把早期对话替换成一条摘要消息，
     释放空间；近期消息保持原样供模型连续推理。
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any

from ..utils.logging import get_logger

log = get_logger(__name__)


# ───────────────────────────────────────────────────────────
# 工具输出卸载
# ───────────────────────────────────────────────────────────

class OffloadStore:
    """
    把超大工具输出写入磁盘，仅在上下文中保留摘要 + 路径。
    后续若需完整内容，智能体可调用 read_file 工具读取。
    """

    def __init__(self, offload_dir: Path, threshold_chars: int = 2000):
        self.offload_dir = offload_dir
        self.threshold = threshold_chars

    def maybe_offload(self, tool_name: str, content: str) -> str:
        """
        若内容超阈值则卸载并返回精简描述；
        否则原样返回。
        """
        if len(content) <= self.threshold:
            return content

        self.offload_dir.mkdir(exist_ok=True)

        # 用内容哈希做文件名，幂等且能去重
        digest = hashlib.sha1(content.encode("utf-8")).hexdigest()[:10]
        fname = f"{tool_name}_{digest}.txt"
        fpath = self.offload_dir / fname
        fpath.write_text(content, encoding="utf-8")

        head = content[:300].replace("\n", " ")
        summary = (
            f"[已卸载] 工具 {tool_name} 返回内容超过 {self.threshold} 字符，"
            f"已写入 {fpath.name}（共 {len(content)} 字符）。\n"
            f"前 300 字符预览：{head}...\n"
            f"如需完整内容，调用 read_file('{fpath}') 读取。"
        )
        log.info("Offload: %s 字符 → %s", len(content), fname)
        return summary


# ───────────────────────────────────────────────────────────
# 上下文压缩
# ───────────────────────────────────────────────────────────

def estimate_messages_size(messages: list[dict]) -> int:
    """粗略估算 messages 总字符数（用于决策是否压缩）。"""
    total = 0
    for m in messages:
        c = m.get("content", "")
        if isinstance(c, str):
            total += len(c)
        elif isinstance(c, list):
            for blk in c:
                if isinstance(blk, dict):
                    total += len(json.dumps(blk, ensure_ascii=False))
                else:
                    total += len(str(blk))
    return total


def compact_messages(messages: list[dict], keep_recent: int = 12) -> list[dict]:
    """
    简单滑动窗口压缩：保留最近 N 条消息。
    更高级版本可以让 LLM 对早期对话生成摘要后插入开头。

    注意：必须保证压缩后 messages 仍然语法合法，
    即 tool_use 块和对应的 tool_result 必须配对，否则 API 会报错。
    本实现采用最朴素的"截尾保留"策略 + 边界修复。
    """
    if len(messages) <= keep_recent:
        return messages

    cut = messages[-keep_recent:]

    # 边界修复：如果首条 user 消息只包含 tool_result（孤儿），
    # 说明它对应的 tool_use 已被截掉，此时也应丢弃这条 user。
    while cut and _is_orphan_tool_result(cut[0]):
        cut = cut[1:]

    log.info("Compaction: %d → %d 条 messages", len(messages), len(cut))
    return cut


def _is_orphan_tool_result(message: dict) -> bool:
    """判断一条消息是否只包含 tool_result（即没有对应的 tool_use 在前文）。"""
    if message.get("role") != "user":
        return False
    content = message.get("content")
    if not isinstance(content, list):
        return False
    return all(
        isinstance(blk, dict) and blk.get("type") == "tool_result"
        for blk in content
    )
