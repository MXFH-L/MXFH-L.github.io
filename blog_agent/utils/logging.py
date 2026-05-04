"""
utils/logging.py — 结构化日志

控制台输出彩色、人类可读；
同时落盘 .agent/agent.log 供事后审计、调试、复现。
"""
from __future__ import annotations
import logging
import sys
from pathlib import Path


class _ColorFormatter(logging.Formatter):
    """终端彩色格式化（按等级着色）。"""
    COLORS = {
        "DEBUG":    "\033[37m",   # 灰
        "INFO":     "\033[36m",   # 青
        "WARNING":  "\033[33m",   # 黄
        "ERROR":    "\033[31m",   # 红
        "CRITICAL": "\033[35m",   # 紫
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        message = super().format(record)
        return f"{color}{message}{self.RESET}" if sys.stdout.isatty() else message


def setup_logging(log_file: Path | None = None, verbose: bool = False) -> logging.Logger:
    """初始化全局 logger。返回 'agent' logger。"""
    logger = logging.getLogger("agent")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()

    # 控制台 handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(_ColorFormatter("%(asctime)s [%(levelname)s] %(message)s",
                                         datefmt="%H:%M:%S"))
    logger.addHandler(console)

    # 文件 handler（始终 DEBUG 级，便于事后排查）
    if log_file is not None:
        log_file.parent.mkdir(exist_ok=True)
        file = logging.FileHandler(log_file, encoding="utf-8")
        file.setLevel(logging.DEBUG)
        file.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
        ))
        logger.addHandler(file)

    return logger


def get_logger(name: str = "agent") -> logging.Logger:
    """模块内统一通过此函数获取 logger。"""
    return logging.getLogger(name)
