"""
harness.py — Harness 层的核心
负责三件事：
  1. 状态管理（持久化到 .agent_state.json）
  2. System Prompt 构建（把状态注入到每次对话）
  3. 上下文压缩（对抗 Context Rot）
"""
import json
import os
from pathlib import Path
from datetime import datetime


def _state_file() -> Path:
    root = os.environ.get("HEXO_BLOG_ROOT", ".")
    return Path(root).expanduser().resolve() / ".agent_state.json"


# ─────────────────────────────────────────
# 状态持久化
# ─────────────────────────────────────────
def load_state() -> dict:
    """从磁盘加载智能体状态，不存在则返回初始状态。"""
    f = _state_file()
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {
        "session_count": 0,
        "task_history": [],    # 最近任务摘要
        "posts_created": [],   # 已创建文章文件名
    }


def save_state(state: dict) -> None:
    f = _state_file()
    f.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def record_task(state: dict, task_summary: str, new_posts: list) -> None:
    """任务完成后更新状态并保存。"""
    ts = datetime.now().strftime("%m-%d %H:%M")
    state["task_history"].append(f"[{ts}] {task_summary[:80]}")
    state["posts_created"].extend(new_posts)
    state["session_count"] = state.get("session_count", 0) + 1
    state["task_history"] = state["task_history"][-20:]
    state["posts_created"] = state["posts_created"][-20:]
    save_state(state)


# ─────────────────────────────────────────
# System Prompt 构建
# ─────────────────────────────────────────
def build_system_prompt(state: dict) -> str:
    """
    将当前状态注入 System Prompt。
    这是 Harness Engineering 对抗 LLM 无状态缺陷的核心手段：
    每次对话启动时，将历史摘要作为"长期记忆"注入。
    """
    recent_tasks = "\n".join(
        f"  - {t}" for t in state.get("task_history", [])[-5:]
    ) or "  （暂无）"

    recent_posts = "\n".join(
        f"  - {p}" for p in state.get("posts_created", [])[-5:]
    ) or "  （暂无）"

    return f"""你是 https://mxfh-l.github.io/ 的博客写作与发布助手，负责管理这个 Hexo 博客。

## 当前上下文（Harness 注入的长期记忆）
- 今日日期：{datetime.now().strftime("%Y-%m-%d")}
- 已完成任务总数：{state.get("session_count", 0)}
- 最近创建的文章：
{recent_posts}
- 最近任务记录：
{recent_tasks}

## 工作流程（严格遵守）
1. 理解用户需求，必要时先用 list_posts 了解已有文章
2. 撰写高质量 Markdown 文章，调用 write_post 写入本地
3. 写完后，向用户展示文章标题、文件名和内容摘要，**等待用户明确确认**
4. 用户说"确认"、"发布"、"推送"、"ok"等之后，才调用 git_commit_push

## 写作规范
- Markdown 格式，结构清晰：引言 → 正文分节 → 总结
- 代码文章必须包含代码块，并标注正确的语言
- 标签 3~5 个，分类 1~2 个，准确反映内容

## 安全护栏（不可绕过）
- 禁止在用户未明确确认的情况下调用 git_commit_push
- 禁止在没有先创建文章的情况下直接推送
- 工具调用失败时，向用户报告错误原因，不要静默忽略
"""


# ─────────────────────────────────────────
# 上下文压缩（对抗 Context Rot）
# ─────────────────────────────────────────
def compress_messages(messages: list) -> list:
    """
    滑动窗口压缩：保留最近 20 条消息。

    对抗 Context Rot 的原理：
    - 随着工具调用轮次增加，messages 越来越长
    - LLM 对早期内容的"注意力"会下降，导致行为漂移
    - 解法：丢弃远端历史，只保留最近的上下文
    - 长期记忆已通过 System Prompt 注入，不会真正丢失关键信息

    进阶方案（生产级）：
    - 调用 LLM 对历史轮次生成摘要，插入对话开头
    - 使用向量数据库存储历史，按需检索
    """
    MAX_MESSAGES = 20
    if len(messages) <= MAX_MESSAGES:
        return messages
    return messages[-MAX_MESSAGES:]
