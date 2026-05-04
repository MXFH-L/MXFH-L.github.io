"""
harness/memory.py — 长期记忆层

两份 Markdown 文件构成"虚拟文件系统"中智能体的世界观：
  · AGENTS.md  — 不可逾越的"宪法"（写作规范、安全规则、技术栈）
  · MEMORY.md  — 可演化的偏好（喜好的话题、配图风格、句式偏好等）

两者都在每次任务启动时被读取并注入 System Prompt，
让 LLM 永远从"当前一致的世界"开始思考。
"""
from __future__ import annotations
from pathlib import Path

from ..utils.logging import get_logger

log = get_logger(__name__)


# ───────────────────────────────────────────────────────────
# 默认模板（首次启动时写入磁盘，之后由用户/智能体自行编辑）
# ───────────────────────────────────────────────────────────

DEFAULT_AGENTS_MD = """\
# AGENTS.md — 博客智能体宪法（不可逾越）

## 身份与定位
你是 https://mxfh-l.github.io/ 「梦醒繁花落」博客的写作与发布助手。
博客主题：保持鲜活的人生需要不断构建、维持耗散结构。

## 技术栈（事实）
- 静态站点生成器：Hexo
- 主题：Butterfly
- 文章存储路径：source/_posts/*.md
- 发布方式：git push 到 main 分支后由 hexo deploy 部署
- 部署仓库：git@github.com:MXFH-L/MXFH-L.github.io.git

## 不可违反的规则
1. **禁止**修改 source/_posts/ 之外的文件，除非用户明确授权
2. **禁止**在用户未明确确认（"确认"/"发布"/"y"）时调用 git_commit_push
3. **禁止**删除已存在的文章，除非用户在请求中明确提到"删除 X 文章"
4. **禁止**编造引用、统计数据、人名；不确定时显式标注"待核实"
5. 长任务（>3 步）必须先进入规划模式，输出 Todo 清单等待执行确认

## 写作规范
- Markdown 格式，结构清晰：引言 → 正文（分小节） → 总结
- 代码文章必须包含可运行代码块，标注正确语言
- 标签 3~5 个；分类 1~2 个；都需准确反映内容
- frontmatter 必须包含：title / date / tags / categories
- 文件名格式：YYYY-MM-DD-slug.md（slug 仅用 a-z、0-9、-）
"""

DEFAULT_MEMORY_MD = """\
# MEMORY.md — 长期偏好与习惯

> 本文件记录用户的写作偏好。智能体可在征得同意后追加内容。

## 内容偏好
（暂无，待积累）

## 风格偏好
（暂无，待积累）

## 历史决策
（暂无，待积累）
"""


# ───────────────────────────────────────────────────────────
# 读写接口
# ───────────────────────────────────────────────────────────

class MemoryStore:
    """统一管理 AGENTS.md 与 MEMORY.md 的读写。"""

    def __init__(self, agents_md: Path, memory_md: Path):
        self.agents_md = agents_md
        self.memory_md = memory_md

    def ensure_initialized(self) -> None:
        """首次运行时创建默认文件，已存在则不覆盖（保护用户的修改）。"""
        if not self.agents_md.exists():
            self.agents_md.write_text(DEFAULT_AGENTS_MD, encoding="utf-8")
            log.info("已创建默认 AGENTS.md：%s", self.agents_md)
        if not self.memory_md.exists():
            self.memory_md.write_text(DEFAULT_MEMORY_MD, encoding="utf-8")
            log.info("已创建默认 MEMORY.md：%s", self.memory_md)

    def read_agents(self) -> str:
        """读取宪法，必读。"""
        return self.agents_md.read_text(encoding="utf-8") if self.agents_md.exists() else ""

    def read_memory(self) -> str:
        """读取偏好库。"""
        return self.memory_md.read_text(encoding="utf-8") if self.memory_md.exists() else ""

    def append_memory(self, section: str, line: str) -> None:
        """向 MEMORY.md 的某节追加一行（智能体收集的偏好）。"""
        if not self.memory_md.exists():
            self.ensure_initialized()
        content = self.memory_md.read_text(encoding="utf-8")
        marker = f"## {section}"
        if marker not in content:
            content += f"\n{marker}\n"
        # 找到该节，在节标题后插入新行
        lines = content.splitlines()
        out: list[str] = []
        inserted = False
        for ln in lines:
            out.append(ln)
            if not inserted and ln.strip() == marker:
                out.append(f"- {line}")
                inserted = True
        self.memory_md.write_text("\n".join(out) + "\n", encoding="utf-8")
        log.info("MEMORY.md 已追加：[%s] %s", section, line)
