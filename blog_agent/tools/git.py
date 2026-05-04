"""
tools/git.py — Git 工具

对应"Git 版本控制集成"。
git_commit_push 标记 requires_approval=True，由 safety/approval 拦截。
"""
from __future__ import annotations
import subprocess
from pathlib import Path

from .registry import make_tool
from ..config import AgentConfig


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8")


def build_git_tools(cfg: AgentConfig) -> list:

    @make_tool(
        name="git_status",
        description="查看当前 Git 仓库的修改状态（哪些文件被修改/新增）。只读。",
        input_schema={"type": "object", "properties": {}},
    )
    def git_status() -> dict:
        r = _run(["git", "status", "--short"], cfg.blog_root)
        if r.returncode != 0:
            return {"success": False, "error": r.stderr.strip()}
        lines = [l for l in r.stdout.splitlines() if l.strip()]
        return {"success": True, "changes": lines, "clean": not lines}

    @make_tool(
        name="git_current_sha",
        description="获取当前 HEAD 的 commit SHA，用于回滚或快照。",
        input_schema={"type": "object", "properties": {}},
    )
    def git_current_sha() -> dict:
        r = _run(["git", "rev-parse", "HEAD"], cfg.blog_root)
        if r.returncode != 0:
            return {"success": False, "error": r.stderr.strip()}
        return {"success": True, "sha": r.stdout.strip()}

    @make_tool(
        name="git_commit_push",
        description=(
            "把所有当前改动 commit 并 push 到远程，触发 GitHub Pages 部署。"
            "**重要：调用此工具前必须得到用户明确确认（确认/发布/推送/y）。**"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "commit_message": {"type": "string", "description": "Git commit 信息（中文亦可）"},
            },
            "required": ["commit_message"],
        },
        requires_approval=True,
    )
    def git_commit_push(commit_message: str) -> dict:
        r = _run(["git", "add", "-A"], cfg.blog_root)
        if r.returncode != 0:
            return {"success": False, "stage": "add", "error": r.stderr.strip()}

        r = _run(["git", "commit", "-m", commit_message], cfg.blog_root)
        if r.returncode != 0:
            if "nothing to commit" in r.stdout:
                return {"success": True, "message": "没有新变更，无需推送。"}
            return {"success": False, "stage": "commit", "error": r.stderr.strip()}

        r = _run(["git", "push"], cfg.blog_root)
        if r.returncode != 0:
            return {"success": False, "stage": "push", "error": r.stderr.strip()}

        # 取出 push 后的最新 SHA
        r2 = _run(["git", "rev-parse", "HEAD"], cfg.blog_root)
        sha = r2.stdout.strip() if r2.returncode == 0 else "?"

        return {
            "success": True,
            "sha": sha,
            "message": (
                f"推送成功！约 1~2 分钟后可在 {cfg.site_url} 看到更新。"
            ),
        }

    @make_tool(
        name="git_reset_hard",
        description=(
            "把工作区强制重置到指定 SHA。"
            "**仅在任务失败需要回滚时由系统调用，禁止智能体主动调用此工具。**"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "target_sha": {"type": "string", "description": "目标 commit SHA"}
            },
            "required": ["target_sha"],
        },
    )
    def git_reset_hard(target_sha: str) -> dict:
        r = _run(["git", "reset", "--hard", target_sha], cfg.blog_root)
        if r.returncode != 0:
            return {"success": False, "error": r.stderr.strip()}
        return {"success": True, "message": f"已回滚到 {target_sha}"}

    return [git_status, git_current_sha, git_commit_push, git_reset_hard]
