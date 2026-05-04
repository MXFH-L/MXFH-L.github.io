"""
main.py — 命令行入口

只负责：
  1. 加载 .env、初始化 logging
  2. 构造 Coordinator
  3. REPL 循环，把用户输入派发给 Coordinator.handle_task
"""
from __future__ import annotations
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from .config import AgentConfig
from .core import Coordinator
from .utils.logging import setup_logging, get_logger
from .utils.exceptions import AgentError


BANNER = """
╔══════════════════════════════════════════════════╗
║   🤖 梦醒繁花落 · 博客智能体 (Engineered)         ║
║   https://mxfh-l.github.io/                      ║
╚══════════════════════════════════════════════════╝

可用指令：
  · 直接输入任务（如 "写一篇关于耗散结构的文章"）
  · 状态        — 查看会话状态
  · 清单        — 查看当前 Todo 清单
  · 技能        — 列出已加载的技能
  · 帮助        — 示例任务
  · exit        — 退出
"""

HELP = """
示例任务：
  · 写一篇关于复杂系统的小品文
  · 帮我把上一篇文章改得更短更有力，然后发布
  · 写三篇关于 Harness Engineering 的系列文章
  · 列出我现在所有的文章
  · 把最新文章里所有"我们认为"改成"我认为"
"""


def _print_state(coord: Coordinator) -> None:
    s = coord.state_store.load()
    print(f"\n📊 会话编号：{s.session_count}")
    print(f"🔄 当前模式：{s.mode.value}")
    print(f"📝 累计文章：{len(s.posts_created)}")
    if s.task_history:
        print("📋 最近任务：")
        for r in s.task_history[-5:]:
            print(f"   [{r.timestamp}] {r.user_input[:50]}... → {r.status}")


def _print_todo(coord: Coordinator) -> None:
    t = coord.todo_store.load()
    if not t.items:
        print("\n（当前无活跃任务清单）")
        return
    done, total = t.progress()
    print(f"\n📋 任务清单（{done}/{total}）：{t.goal}")
    print(t.render())


def _print_skills(coord: Coordinator) -> None:
    skills = coord.skill_loader._skills
    if not skills:
        print(f"\n（{coord.cfg.skills_dir} 中暂无技能文件）")
        return
    print(f"\n🎯 已加载 {len(skills)} 个技能：")
    for name, s in skills.items():
        print(f"   · {name}  triggers={s.triggers}  tools={s.tools}")


def main() -> int:
    # ── 配置加载 ────────────────────────
    try:
        cfg = AgentConfig.from_env()
    except RuntimeError as e:
        print(f"❌ 配置错误：{e}")
        return 1

    setup_logging(cfg.log_file, verbose=False)
    log = get_logger("agent.main")

    # ── 构造协调者 ──────────────────────
    try:
        coord = Coordinator(cfg)
    except Exception as e:
        log.exception("初始化失败")
        print(f"❌ 初始化失败：{e}")
        return 1

    # ── 主循环 ──────────────────────────
    print(BANNER)
    print(f"📁 博客根目录：{cfg.blog_root}")
    print(f"📦 已注册工具：{len(coord.registry.names())}")
    print(f"👥 子智能体：{list(coord.subagents.keys())}")
    print("─" * 60)

    while True:
        try:
            user_input = input("\n你: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 再见")
            return 0

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "退出", "q"):
            print("👋 再见")
            return 0
        if user_input == "状态":
            _print_state(coord); continue
        if user_input == "清单":
            _print_todo(coord); continue
        if user_input == "技能":
            _print_skills(coord); continue
        if user_input == "帮助":
            print(HELP); continue

        # ── 派发给协调者 ──────────────
        print("\n⏳ 智能体执行中…\n")
        try:
            outcome = coord.handle_task(user_input)
        except AgentError as e:
            print(f"\n❌ 错误：{e}")
            continue
        except Exception as e:
            log.exception("未捕获异常")
            print(f"\n❌ 未预期的异常：{e}")
            continue

        # ── 展示结果 ──────────────────
        print(f"\n{'─' * 60}")
        marker = "✅" if outcome.success else "⚠️ "
        print(f"{marker} 智能体（{outcome.iterations} 轮）：\n{outcome.final_message}")
        if outcome.new_posts:
            print(f"\n📝 新增文章：{outcome.new_posts}")
        print("─" * 60)


if __name__ == "__main__":
    sys.exit(main())
