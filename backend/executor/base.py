"""
执行器模块

支持调用 OpenCode 或直接使用 Minimax API
"""
import asyncio
import subprocess
import sys
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

import aiohttp


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    content: str = ""
    thought_process: str = ""
    tool_calls: List[Dict] = None
    error: str = ""
    duration_ms: float = 0
    executor: str = ""

    @classmethod
    def success(cls, content: str, thought: str = "", **kwargs):
        return cls(success=True, content=content, thought_process=thought, **kwargs)

    @classmethod
    def error(cls, error: str, **kwargs):
        return cls(success=False, content="", error=error, **kwargs)


class Executor(ABC):
    """执行器抽象基类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enabled", True)

    @abstractmethod
    async def execute(self, prompt: str, context: Dict[str, Any] = None) -> ExecutionResult:
        """执行提示词

        Args:
            prompt: 提示词内容
            context: 上下文信息

        Returns:
            ExecutionResult: 执行结果
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查执行器是否可用"""
        pass


class MinimaxExecutor(Executor):
    """Minimax 直接执行器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key", "")
        self.group_id = config.get("group_id", "")
        self.model = config.get("model", "abab6.5s-chat")
        self.base_url = "https://api.minimax.chat/v1"

    async def execute(self, prompt: str, context: Dict[str, Any] = None) -> ExecutionResult:
        """执行提示词"""
        if not self.is_available():
            return ExecutionResult.error("Minimax API Key 未配置")

        start_time = datetime.now()

        try:
            # 构建消息
            messages = [
                {"role": "system", "content": self._build_system_prompt(context)},
                {"role": "user", "content": prompt}
            ]

            # 调用 API
            payload = {
                "model": f"{self.group_id}/{self.model}",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 4096
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    if response.status != 200:
                        error_data = await response.json()
                        return ExecutionResult.error(
                            f"API 错误: {error_data.get('error', {}).get('message', 'Unknown error')}"
                        )

                    data = await response.json()
                    choice = data["choices"][0]
                    content = choice["message"].get("content", "")

                    duration_ms = (datetime.now() - start_time).total_seconds() * 1000

                    return ExecutionResult.success(
                        content=content,
                        thought_process="",  # Minimax 不返回思考过程
                        duration_ms=duration_ms,
                        executor="minimax"
                    )

        except aiohttp.ClientError as e:
            return ExecutionResult.error(f"网络错误: {str(e)}")
        except Exception as e:
            return ExecutionResult.error(f"执行错误: {str(e)}")

    def _build_system_prompt(self, context: Dict[str, Any]) -> str:
        """构建系统提示词"""
        if context:
            project_path = context.get("project_path", ".")
            language = context.get("language", "python")
            return f"""你是一位资深后端工程师。
项目路径: {project_path}
编程语言: {language}
"""
        return "你是一位资深后端工程师。"

    def is_available(self) -> bool:
        """检查是否可用"""
        return bool(self.api_key and self.group_id)


class OpenCodeExecutor(Executor):
    """OpenCode 执行器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.opencode_path = config.get("path", "opencode")

    async def execute(self, prompt: str, context: Dict[str, Any] = None) -> ExecutionResult:
        """通过 OpenCode 执行"""
        if not self.is_available():
            return ExecutionResult.error("OpenCode 不可用")

        start_time = datetime.now()

        try:
            # 构建命令 - Windows 需要 shell=True 来执行 .cmd 文件
            cmd = f"{self.opencode_path} chat {prompt}"
            shell = True if sys.platform == "win32" else False

            # 执行命令
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=context.get("project_path", ".") if context else "."
            )

            stdout, stderr = await process.communicate()

            duration_ms = (datetime.now() - start_time).total_seconds() * 1000

            if process.returncode != 0:
                return ExecutionResult.error(
                    f"OpenCode 执行失败: {stderr.decode('utf-8', errors='ignore')}"
                )

            content = stdout.decode('utf-8', errors='ignore')

            return ExecutionResult.success(
                content=content,
                duration_ms=duration_ms,
                executor="opencode"
            )

        except FileNotFoundError:
            return ExecutionResult.error(f"找不到 OpenCode: {self.opencode_path}")
        except Exception as e:
            return ExecutionResult.error(f"执行错误: {str(e)}")

    def is_available(self) -> bool:
        """检查是否可用"""
        if not self.enabled:
            return False

        # 检查 OpenCode 是否存在（跨平台）
        try:
            # Windows 使用 where，Unix 使用 which
            cmd = "where" if sys.platform == "win32" else "which"
            result = subprocess.run(
                [cmd, self.opencode_path],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False


class ExecutorManager:
    """执行器管理器"""

    def __init__(self):
        self.executors: Dict[str, Executor] = {}
        self.default_executor: str = "minimax"

    def register(self, name: str, executor: Executor) -> None:
        """注册执行器"""
        self.executors[name] = executor

    def get(self, name: str) -> Optional[Executor]:
        """获取执行器"""
        return self.executors.get(name)

    async def execute(
        self,
        prompt: str,
        executor: str = None,
        context: Dict[str, Any] = None
    ) -> ExecutionResult:
        """执行提示词

        Args:
            prompt: 提示词
            executor: 执行器名称，不指定则使用默认
            context: 上下文

        Returns:
            ExecutionResult: 执行结果
        """
        executor_name = executor or self.default_executor
        exec_obj = self.get(executor_name)

        if not exec_obj:
            return ExecutionResult.error(f"执行器不存在: {executor_name}")

        if not exec_obj.is_available():
            return ExecutionResult.error(f"执行器不可用: {executor_name}")

        return await exec_obj.execute(prompt, context)

    def list_executors(self) -> List[Dict[str, Any]]:
        """列出所有执行器"""
        return [
            {
                "name": name,
                "available": exec.is_available(),
                "enabled": exec.enabled
            }
            for name, exec in self.executors.items()
        ]
