"""
skills/loader.py — 技能渐进披露

技能 = skills/ 目录下的 .md 文件，文件名即技能名。
每个 .md 文件可在头部用 YAML 风格元数据声明触发关键词：
  ---
  triggers: ["写", "文章", "post"]
  tools: ["write_post", "list_posts"]
  ---

加载时根据当前任务的关键词，只把匹配的技能注入 Prompt，
避免一次性塞入大量无关说明导致 Context Rot。
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path

from ..utils.logging import get_logger

log = get_logger(__name__)


_META_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


@dataclass
class Skill:
    name: str
    triggers: list[str]
    tools: list[str]
    body: str
    path: Path


class SkillLoader:
    """技能注册表 + 渐进披露逻辑。"""

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._skills: dict[str, Skill] = {}

    def reload(self) -> None:
        """重新扫描 skills/ 目录。"""
        self._skills.clear()
        if not self.skills_dir.exists():
            log.info("技能目录不存在，跳过加载：%s", self.skills_dir)
            return

        for md in self.skills_dir.glob("*.md"):
            skill = self._parse(md)
            if skill is not None:
                self._skills[skill.name] = skill

        log.info("已加载 %d 个技能：%s",
                 len(self._skills), list(self._skills.keys()))

    def _parse(self, path: Path) -> Skill | None:
        text = path.read_text(encoding="utf-8")
        m = _META_RE.match(text)
        if not m:
            log.warning("技能 %s 缺少元数据头，跳过", path.name)
            return None

        meta_block = m.group(1)
        body = text[m.end():].strip()

        # 极简 YAML 解析（仅支持 key: [a, b, c] 形式，足够用了）
        triggers = self._parse_list(meta_block, "triggers")
        tools = self._parse_list(meta_block, "tools")
        name = path.stem

        return Skill(
            name=name,
            triggers=triggers,
            tools=tools,
            body=body,
            path=path,
        )

    @staticmethod
    def _parse_list(meta: str, key: str) -> list[str]:
        m = re.search(rf"^{key}:\s*\[(.*?)\]\s*$", meta, re.MULTILINE)
        if not m:
            return []
        raw = m.group(1)
        return [
            item.strip().strip('"').strip("'")
            for item in raw.split(",")
            if item.strip()
        ]

    def select(self, user_input: str) -> list[Skill]:
        """
        根据用户输入选出相关技能。
        匹配规则：input 包含 trigger 关键词的任意一个则命中。
        """
        text = user_input.lower()
        matched: list[Skill] = []
        for skill in self._skills.values():
            if any(trig.lower() in text for trig in skill.triggers):
                matched.append(skill)
        return matched

    def all_tools_in_skills(self, skills: list[Skill]) -> list[str]:
        """返回这些技能引用到的全部工具名（去重）。"""
        seen: set[str] = set()
        out: list[str] = []
        for s in skills:
            for t in s.tools:
                if t not in seen:
                    seen.add(t)
                    out.append(t)
        return out

    def render_docs(self, skills: list[Skill]) -> list[str]:
        """生成可注入 System Prompt 的技能说明字符串列表。"""
        return [f"## 技能：{s.name}\n{s.body}" for s in skills]
