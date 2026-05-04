"""
main.py — 命令行入口
运行方式：python -m blog_agent
"""
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import anthropic

from .loop import run_loop
from .harness import load_state, record_task


BANNER = """
╔══════════════════════════════════════════╗
║   🤖  Hexo 博客智能体  (Harness Mode)    ║
║   博客地址: https://mxfh-l.github.io/    ║
╚══════════════════════════════════════════╝

输入 '帮助' 查看示例任务 | 'exit' 退出 | '状态' 查看记录
"""

HELP_TEXT = """
示例任务（直接输入即可）：
  · 写一篇介绍 Python 装饰器的文章
  · 写一篇关于 Harness Engineering 的博客
  · 查看我现有的文章列表
  · 写三篇关于机器学习基础概念的系列文章
"""


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ 请在 .env 文件中设置 ANTHROPIC_API_KEY")
        sys.exit(1)

    blog_root = Path(os.environ.get("HEXO_BLOG_ROOT", ".")).expanduser().resolve()
    if not (blog_root / "source" / "_posts").exists():
        print(f"⚠️  警告：{blog_root}/source/_posts 不存在，请确认 HEXO_BLOG_ROOT 配置正确")

    client = anthropic.Anthropic(api_key=api_key)
    state = load_state()

    print(BANNER)
    print(f"📁 博客目录: {blog_root}")
    print(f"📊 已完成任务: {state.get('session_count', 0)} 个\n" + "─"*50)

    while True:
        try:
            user_input = input("\n你: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "退出", "q"):
            print("👋 再见！")
            break
        if user_input == "状态":
            print(f"\n📊 已完成任务数: {state.get('session_count', 0)}")
            for p in state.get('posts_created', [])[-5:]:
                print(f"  📝 {p}")
            for h in state.get('task_history', [])[-3:]:
                print(f"  📋 {h}")
            continue
        if user_input == "帮助":
            print(HELP_TEXT)
            continue

        print("\n⏳ 智能体执行中...\n")
        try:
            final_response, new_posts = run_loop(client, user_input, state)
            print(f"\n{'─'*50}\n🤖 智能体:\n{final_response}")
            record_task(state, user_input, new_posts)
        except anthropic.APIError as e:
            print(f"\n❌ API 错误: {e}")
        except Exception as e:
            print(f"\n❌ 执行出错: {e}")
            import traceback; traceback.print_exc()

        print("\n" + "─"*50)


if __name__ == "__main__":
    main()
