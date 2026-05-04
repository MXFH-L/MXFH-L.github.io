"""
config.py — 全局配置（不可变 dataclass）

所有路径、阈值、模型选择都收敛到这里。
其他模块通过 AgentConfig 实例传递配置，禁止读取环境变量。
"""
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AgentConfig:
    # ── 运行环境 ────────────────────────
    blog_root: Path
    api_key: str
    base_url: str | None = None
    obsidian_vault: Path | None = None   # 新增

    # ── 模型 ───────────────────────────
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 4096

    # ── 循环控制 ───────────────────────
    max_iterations: int = 20      # 单次任务最多 LLM 轮次
    max_retries: int = 3          # API 调用失败重试次数

    # ── 上下文管理 ─────────────────────
    offload_threshold: int = 2000   # 工具输出超过此字符数则卸载到文件
    compaction_threshold: int = 30  # messages 超过此数则触发压缩
    compaction_keep_recent: int = 12  # 压缩后保留最近 N 条

    # ── 公开站点 ───────────────────────
    site_url: str = "https://mxfh-l.github.io/"
    git_remote: str = "git@github.com:MXFH-L/MXFH-L.github.io.git"

    # ── 派生路径（动态属性，不参与构造） ──
    @property
    def state_dir(self) -> Path:
        return self.blog_root / ".agent"

    @property
    def state_file(self) -> Path:
        return self.state_dir / "state.json"

    @property
    def todo_file(self) -> Path:
        return self.state_dir / "todo.json"

    @property
    def offload_dir(self) -> Path:
        return self.state_dir / "offload"

    @property
    def log_file(self) -> Path:
        return self.state_dir / "agent.log"

    @property
    def agents_md(self) -> Path:
        return self.blog_root / "AGENTS.md"

    @property
    def memory_md(self) -> Path:
        return self.blog_root / "MEMORY.md"

    @property
    def skills_dir(self) -> Path:
        return self.blog_root / "skills"

    @property
    def posts_dir(self) -> Path:
        return self.blog_root / "source" / "_posts"

    # ── 工厂方法 ───────────────────────
    @classmethod
    def from_env(cls) -> "AgentConfig":
        """从 .env / 环境变量构造配置；缺失关键项时抛错。"""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "未找到 ANTHROPIC_API_KEY，请在 .env 中设置。"
            )

        blog_root = Path(os.environ.get("HEXO_BLOG_ROOT", ".")).expanduser().resolve()
        if not (blog_root / "source" / "_posts").exists():
            raise RuntimeError(
                f"博客目录无效：{blog_root}（缺少 source/_posts）"
            )

        base_url = os.environ.get("ANTHROPIC_BASE_URL")
        vault = os.environ.get("OBSIDIAN_VAULT")
        vault_path = Path(vault).expanduser().resolve() if vault else None
        return cls(
            blog_root=blog_root,
            api_key=api_key,
            base_url=base_url,
            obsidian_vault=vault_path,
        )

    def ensure_dirs(self) -> None:
        """确保所有运行时目录存在。"""
        self.state_dir.mkdir(exist_ok=True)
        self.offload_dir.mkdir(exist_ok=True)
        self.skills_dir.mkdir(exist_ok=True)
