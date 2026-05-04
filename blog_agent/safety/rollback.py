"""
safety/rollback.py — 失败回滚

任务执行失败、用户驳回时，git reset --hard 回到任务开始前的安全 SHA。
对应"异常中断与回滚"。
"""
from __future__ import annotations
import subprocess
from pathlib import Path

from ..utils.exceptions import RollbackError
from ..utils.logging import get_logger

log = get_logger(__name__)


class RollbackManager:
    """以 git SHA 为锚点的回滚管理。"""

    def __init__(self, blog_root: Path):
        self.blog_root = blog_root
        self._snapshot: str | None = None

    def snapshot(self) -> str | None:
        """记录当前 HEAD 作为回滚锚点。返回 SHA；若不在 git 仓库则返回 None。"""
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.blog_root, capture_output=True, text=True,
        )
        if r.returncode != 0:
            log.warning("无法获取 HEAD（不是 git 仓库或无任何 commit），跳过快照。")
            self._snapshot = None
            return None
        self._snapshot = r.stdout.strip()
        log.info("已记录回滚锚点：%s", self._snapshot[:8])
        return self._snapshot

    def rollback(self, reason: str = "") -> bool:
        """回滚到上次快照；返回是否成功。"""
        if self._snapshot is None:
            log.warning("没有可用的回滚锚点。")
            return False

        log.warning("触发回滚到 %s（原因：%s）", self._snapshot[:8], reason or "未指明")

        # 先做软回退：还原工作区文件（保留 untracked）
        r = subprocess.run(
            ["git", "reset", "--hard", self._snapshot],
            cwd=self.blog_root, capture_output=True, text=True,
        )
        if r.returncode != 0:
            raise RollbackError(f"回滚失败：{r.stderr.strip()}")

        # 清理 untracked 文件（智能体新建但未 commit 的内容）
        subprocess.run(
            ["git", "clean", "-fd", "--", "source/_posts/"],
            cwd=self.blog_root, capture_output=True, text=True,
        )
        log.info("回滚完成。")
        return True

    def clear(self) -> None:
        """任务成功完成后清除快照。"""
        self._snapshot = None
