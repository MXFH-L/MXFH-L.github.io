# 梦醒繁花落 · 博客智能体（工程化版）

基于 Harness Engineering 的个人博客写作与发布智能体。

## 模块架构

```
blog_agent/
├── config.py            # 全局配置（dataclass，唯一真理来源）
├── main.py              # CLI 入口
│
├── core/                # 主控
│   ├── coordinator.py   # 顶层协调者（任务级生命周期）
│   └── loop.py          # Agentic Loop 引擎
│
├── harness/             # 状态层
│   ├── state.py         # AgentState + 持久化
│   ├── memory.py        # AGENTS.md / MEMORY.md 管理
│   ├── todo.py          # 显性任务清单
│   ├── prompt.py        # 动态 System Prompt 组装
│   └── compaction.py    # 上下文压缩 + 卸载
│
├── tools/               # 工具层
│   ├── registry.py      # 装饰器注册表
│   ├── post.py          # 文章 CRUD
│   ├── git.py           # 版本控制
│   ├── todo.py          # Todo 操作
│   ├── filesystem.py    # 受限文件读
│   └── verify.py        # 验证钩子
│
├── subagents/           # 子智能体（上下文隔离）
│   ├── base.py          # ABC 基类
│   ├── writer.py        # 写作专员
│   ├── editor.py        # 编辑专员
│   └── publisher.py     # 发布专员
│
├── safety/              # 安全
│   ├── approval.py      # 人工审批门
│   └── rollback.py      # git reset 回滚
│
├── skills/              # 技能渐进披露
│   └── loader.py
│
└── utils/               # 横切
    ├── exceptions.py    # 异常体系
    └── logging.py       # 结构化日志
```

## 设计能力对照表

| 设计文档要求 | 实现位置 |
|---|---|
| 显性任务清单（Todo List） | `harness/todo.py` + `tools/todo.py` |
| 反思与验证钩子 | `tools/verify.py` |
| 规划/执行模式切换 | `harness/state.py::AgentMode` + `prompt.py` |
| AGENTS.md 宪法 | `harness/memory.py` |
| 进度持久化 | `harness/state.py::StateStore` |
| Git 集成 | `tools/git.py` |
| 主从架构（Coordinator） | `core/coordinator.py` |
| 上下文隔离子智能体 | `subagents/*.py` |
| 结果摘要接口 | `subagents/base.py::SubagentResult` |
| 动态 System Prompt | `harness/prompt.py::PromptBuilder` |
| 工具输出卸载 | `harness/compaction.py::OffloadStore` |
| 运行时上下文压缩 | `harness/compaction.py::compact_messages` |
| 长期记忆库 | `harness/memory.py::MemoryStore` |
| 强制审批节点 | `safety/approval.py::CLIApprovalGate` |
| 异常中断与回滚 | `safety/rollback.py::RollbackManager` |
| 技能渐进披露 | `skills/loader.py::SkillLoader` |

## 安装

```powershell
pip install -r requirements.txt
copy .env.example .env
# 编辑 .env，填入 ANTHROPIC_API_KEY
```

把 `blog_agent/` 整个文件夹和 `skills/` 文件夹放到 Hexo 博客根目录。

## 启动

```powershell
python -m blog_agent
```

## 运行时产生的文件

启动后会在博客根目录自动创建：

```
hexo-source/
├── AGENTS.md            # 智能体宪法（首次自动生成，可手动编辑）
├── MEMORY.md            # 长期偏好库（首次自动生成，会逐渐积累）
└── .agent/              # 运行时数据
    ├── state.json       # 持久化状态
    ├── todo.json        # 当前任务清单
    ├── agent.log        # 完整调试日志
    └── offload/         # 卸载的大输出
```

记得把这些路径加进 `.gitignore`：
```
.agent/
.env
```

`AGENTS.md` 和 `MEMORY.md` 是否提交到仓库由你决定（提交可以让博客本身解释自己的"操作宪法"，是个有趣的元层）。
