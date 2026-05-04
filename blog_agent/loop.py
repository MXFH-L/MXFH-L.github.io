"""
loop.py — 智能体执行循环（Agentic Loop）
"""
import json
import anthropic

from .tools import TOOL_SCHEMAS, TOOL_MAP
from .harness import build_system_prompt, compress_messages


MAX_ITERATIONS = 15
MAX_RETRIES = 3


def _execute_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name not in TOOL_MAP:
        return json.dumps({"error": f"未知工具：{tool_name}"})

    # 安全护栏：git push 前必须人工确认
    if tool_name == "git_commit_push":
        msg = tool_input.get("commit_message", "")
        print(f"\n{'─'*50}")
        print(f"⚠️  智能体请求推送到 GitHub")
        print(f"   Commit 信息：「{msg}」")
        print(f"   目标仓库：git@github.com:MXFH-L/MXFH-L.github.io.git")
        confirm = input("确认发布？(y/n): ").strip().lower()
        if confirm != "y":
            return json.dumps({"success": False, "error": "用户取消了推送，文章已保存在本地。"})

    try:
        result = TOOL_MAP[tool_name](**tool_input)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"工具执行异常：{e}"})


def run_loop(client: anthropic.Anthropic, user_message: str, state: dict) -> tuple:
    """
    运行一次完整的智能体任务。
    返回 (final_text: str, new_posts: list[str])
    """
    system_prompt = build_system_prompt(state)
    messages = [{"role": "user", "content": user_message}]
    new_posts = []

    for iteration in range(MAX_ITERATIONS):
        messages = compress_messages(messages)

        response = None
        for attempt in range(MAX_RETRIES):
            try:
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=4096,
                    system=system_prompt,
                    tools=TOOL_SCHEMAS,
                    messages=messages,
                )
                break
            except anthropic.APIError as e:
                if attempt == MAX_RETRIES - 1:
                    raise
                print(f"\n  ⚠️  API 调用失败（第 {attempt+1} 次重试）：{e}")

        if response.stop_reason == "end_turn":
            final_text = "".join(b.text for b in response.content if hasattr(b, "text"))
            return final_text, new_posts

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_name = block.name
                tool_input = block.input

                print(f"\n  🔧 调用工具: {tool_name}")
                if tool_name == "write_post":
                    print(f"     标题: {tool_input.get('title', '')}")

                result_str = _execute_tool(tool_name, tool_input)
                result_data = json.loads(result_str)

                if tool_name == "write_post" and result_data.get("success"):
                    fname = result_data.get("filename", "")
                    new_posts.append(fname)
                    print(f"     ✅ 已写入: {fname}")
                elif tool_name == "git_commit_push" and result_data.get("success"):
                    print(f"     ✅ {result_data.get('message', '推送成功')}")
                elif not result_data.get("success", True):
                    print(f"     ❌ 失败: {result_data.get('error', '未知错误')}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str,
                })

            messages.append({"role": "user", "content": tool_results})

        else:
            print(f"\n  ⚠️  意外的停止原因: {response.stop_reason}")
            break

    return "（已达最大执行轮次，任务可能未完全完成）", new_posts
