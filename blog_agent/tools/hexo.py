"""
tools/hexo.py — Hexo 编译与部署

完整的发布链路：
  hexo clean      → 清空旧产物
  hexo generate   → 编译 Markdown 为静态 HTML
  hexo deploy     → 推到 GitHub Pages 部署分支
"""
from __future__ import annotations
import subprocess
from pathlib import Path

from .registry import make_tool
from ..config import AgentConfig


def _run_hexo(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """跑一条 hexo 命令；Windows 下需要用 shell=True 才能找到 hexo.cmd。"""
    return subprocess.run(
        ["hexo", *args],
        cwd=cwd,
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        shell=True,  # Windows 必需，不然找不到 hexo
    )


def build_hexo_tools(cfg: AgentConfig) -> list:

    @make_tool(
        name="hexo_deploy",
        description=(
            "完整发布博客到 GitHub Pages：依次执行 hexo clean、hexo generate、hexo deploy。"
            "会把所有 Markdown 文章编译成 HTML 并推送到部署分支。"
            "**调用前必须得到用户明确确认。**"
            "通常在 git_commit_push（推送源码）之后调用，"
            "也可以单独调用以重新部署已有内容。"
        ),
        input_schema={"type": "object", "properties": {}},
        requires_approval=True,
    )
    def hexo_deploy() -> dict:
        log_steps: list[str] = []

        # 1. clean
        r = _run_hexo(["clean"], cfg.blog_root)
        log_steps.append(f"clean: {'OK' if r.returncode == 0 else 'FAIL'}")
        if r.returncode != 0:
            return {
                "success": False,
                "stage": "clean",
                "error": (r.stderr or r.stdout)[:500],
                "steps": log_steps,
            }

        # 2. generate
        r = _run_hexo(["generate"], cfg.blog_root)
        log_steps.append(f"generate: {'OK' if r.returncode == 0 else 'FAIL'}")
        if r.returncode != 0:
            return {
                "success": False,
                "stage": "generate",
                "error": (r.stderr or r.stdout)[:500],
                "steps": log_steps,
            }

        # 3. deploy
        r = _run_hexo(["deploy"], cfg.blog_root)
        log_steps.append(f"deploy: {'OK' if r.returncode == 0 else 'FAIL'}")
        if r.returncode != 0:
            return {
                "success": False,
                "stage": "deploy",
                "error": (r.stderr or r.stdout)[:500],
                "steps": log_steps,
            }

        return {
            "success": True,
            "steps": log_steps,
            "message": (
                f"Hexo 部署完成！约 1~2 分钟后可访问 {cfg.site_url} 查看更新。"
            ),
        }

    @make_tool(
        name="hexo_generate",
        description=(
            "本地编译 Markdown 为 HTML（不部署），用于检查文章渲染是否正常。"
            "产物在 public/ 目录下。"
        ),
        input_schema={"type": "object", "properties": {}},
    )
    def hexo_generate() -> dict:
        r = _run_hexo(["generate"], cfg.blog_root)
        if r.returncode != 0:
            return {
                "success": False,
                "error": (r.stderr or r.stdout)[:500],
            }
        # 提取关键信息（generated 文件数）
        return {
            "success": True,
            "output_tail": r.stdout.splitlines()[-10:] if r.stdout else [],
        }

    return [hexo_deploy, hexo_generate]