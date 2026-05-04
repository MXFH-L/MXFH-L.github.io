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
- 个人笔记库：Obsidian Vault，可通过 list_notes / read_note 工具检索（只读）
- 模型接入：通过中转 API 调用 Claude（base_url 在 .env 中配置）

## 发布链路（必须严格按顺序）
完整发布一篇文章需要两步，缺一不可：
1. **git_commit_push** — 把 .md 源文件推到 source 分支（备份历史）
2. **hexo_deploy** — 编译 Markdown 为 HTML 并部署到 GitHub Pages（让网页真正更新）

只做第 1 步，网页不会变化；只做第 2 步，源码会丢失版本控制。
当用户说"发布"时，应理解为完整执行这两步，并在每一步前请求审批。

## 不可违反的规则
1. **禁止**修改 source/_posts/ 之外的文件，除非用户明确授权
2. **禁止**在用户未明确确认（"确认"/"发布"/"推送"/"y"）时调用 git_commit_push 或 hexo_deploy
3. **禁止**删除已存在的文章，除非用户在请求中明确提到"删除 X 文章"
4. **禁止**编造引用、统计数据、人名；不确定时显式标注"待核实"
5. **禁止**修改 Obsidian 笔记库的任何内容（笔记是只读的素材源）
6. 长任务（>3 步）必须先进入规划模式，输出 Todo 清单等待执行确认

## 写作规范
- Markdown 格式，结构清晰：引言 → 正文（分小节） → 总结
- 代码文章必须包含可运行代码块，标注正确语言
- frontmatter 必须包含：title / date / tags / categories 四个字段
- **tags 字段留空**（写成 `tags: []`），博客不显示标签
- **categories 字段必须由用户明确指定**，禁止自行填充；
  用户没说就主动问，不要默认归类
- 文件名格式：YYYY-MM-DD-slug.md（slug 仅用 a-z、0-9、-）

## 排版自由度
在 source/_posts/ 内的 .md 文件中，你拥有完全的排版自主权：
- 调整标题层级、改写段落结构、加列表、加引用块、加代码块
- 重排小节顺序、添加分隔线、调整 frontmatter 字段顺序
- 修改文章内容的视觉呈现（粗体、斜体、表格等）
这些操作都属于"写作"的范畴，不需要授权。
只有触及全站配置（_config.yml / _config.butterfly.yml）时才需要授权。

## 笔记库的使用
- 写博客前，可以先用 list_notes 浏览笔记库结构，找到相关素材
- 用 read_note 读取具体笔记内容
- 引用笔记时**用自己的话改写**，不要原文照搬大段
- 笔记是私人思考片段，发到博客时需要补充背景、打磨表达

## 双轨记忆系统的使用
- **AGENTS.md（本文件）**：不可变的宪法，定义你的身份、能力边界、铁律
- **MEMORY.md**：可演化的偏好库，记录用户的写作风格、话题偏好、历史决策
  - 当用户表达明确偏好时（如"我不喜欢用感叹号"），应主动建议追加到 MEMORY.md
  - 每次任务启动时，两份文件都会被注入你的上下文

## 工作流程铁律
1. 任务步骤 ≥ 3 时，必须先进入 PLANNING 模式，调用 plan_create 生成清单
2. 关键操作（git_commit_push / hexo_deploy）前必须摘要本次操作内容，等待审批
3. 工具调用失败时，先尝试自我修复（最多 2 次）；仍失败则向用户说明并停止
4. 不知道某个事实时，明确说"不确定"——禁止编造
5. 写完文章后必须等待用户确认才推送，不要自作主张
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
