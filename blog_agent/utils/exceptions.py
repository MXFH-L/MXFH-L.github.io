"""
utils/exceptions.py — 自定义异常体系
按层抛出，由 main.py 顶层统一捕获并展示。
"""


class AgentError(Exception):
    """所有智能体异常的基类。"""


class HarnessError(AgentError):
    """Harness 层错误：状态损坏、配置缺失、记忆文件读取失败等。"""


class ToolError(AgentError):
    """工具执行错误。"""

    def __init__(self, tool_name: str, message: str):
        self.tool_name = tool_name
        super().__init__(f"[{tool_name}] {message}")


class VerificationError(AgentError):
    """验证钩子失败。"""

    def __init__(self, step: str, reason: str):
        self.step = step
        self.reason = reason
        super().__init__(f"验证失败 @ {step}：{reason}")


class ApprovalDeniedError(AgentError):
    """用户拒绝了关键操作的批准。"""


class SubagentError(AgentError):
    """子智能体执行失败。"""

    def __init__(self, subagent_name: str, message: str):
        self.subagent_name = subagent_name
        super().__init__(f"<{subagent_name}> {message}")


class RollbackError(AgentError):
    """回滚操作本身失败（最严重）。"""
