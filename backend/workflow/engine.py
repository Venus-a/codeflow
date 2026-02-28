"""
流程引擎

管理工作流程的执行状态、步骤推进、模式切换等。
"""
import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum

from prompthub import PromptHubManager, Workflow, PromptStep
from executor.base import ExecutorManager, ExecutionResult


class ExecutionMode(str, Enum):
    """执行模式"""
    AUTO = "auto"  # 自动执行每一步
    MANUAL = "manual"  # 手动确认每步
    HYBRID = "hybrid"  # 混合模式


@dataclass
class Session:
    """会话"""
    id: str
    workflow_id: str
    workflow_name: str
    mode: ExecutionMode
    created_at: datetime = field(default_factory=datetime.now)
    current_step: int = 1
    status: str = "running"  # running, paused, completed, failed
    steps_status: Dict[int, str] = field(default_factory=dict)  # step_order -> status
    step_results: Dict[int, ExecutionResult] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "mode": self.mode.value,
            "created_at": self.created_at.isoformat(),
            "current_step": self.current_step,
            "status": self.status,
            "steps_status": self.steps_status,
            "context": self.context,
            "notes": self.notes
        }


class WorkflowEngine:
    """工作流程引擎

    核心功能：
    1. 创建会话
    2. 执行步骤
    3. 推进流程
    4. 管理模式
    """

    def __init__(
        self,
        prompthub: PromptHubManager,
        executor: ExecutorManager,
        sessions_dir: str = "./data/sessions"
    ):
        self.prompthub = prompthub
        self.executor = executor
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        self.sessions: Dict[str, Session] = {}
        self._load_sessions()

    def _load_sessions(self) -> None:
        """加载保存的会话"""
        for session_file in self.sessions_dir.glob("*.json"):
            try:
                data = json.loads(session_file.read_text(encoding='utf-8'))
                session = Session(
                    id=data["id"],
                    workflow_id=data["workflow_id"],
                    workflow_name=data["workflow_name"],
                    mode=ExecutionMode(data["mode"]),
                    created_at=datetime.fromisoformat(data["created_at"]),
                    current_step=data["current_step"],
                    status=data["status"],
                    steps_status=data.get("steps_status", {}),
                    context=data.get("context", {}),
                    notes=data.get("notes", [])
                )
                self.sessions[session.id] = session
            except Exception:
                continue

    def create_session(
        self,
        workflow_id: str,
        mode: ExecutionMode = ExecutionMode.MANUAL,
        context: Dict[str, Any] = None
    ) -> Optional[Session]:
        """创建新会话

        Args:
            workflow_id: 工作流程 ID
            mode: 执行模式
            context: 上下文信息

        Returns:
            Session: 创建的会话
        """
        workflow = self.prompthub.get_workflow(workflow_id)
        if not workflow:
            return None

        session_id = f"session_{uuid.uuid4().hex[:12]}"
        session = Session(
            id=session_id,
            workflow_id=workflow_id,
            workflow_name=workflow.name,
            mode=mode,
            context=context or {}
        )

        # 初始化步骤状态
        for step in workflow.steps:
            session.steps_status[step.order] = "pending"

        # 第一步设为进行中
        if workflow.steps:
            session.steps_status[1] = "in_progress"

        self.sessions[session_id] = session
        self._save_session(session)

        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话"""
        return self.sessions.get(session_id)

    def list_sessions(self) -> List[Session]:
        """列出所有会话"""
        return sorted(self.sessions.values(), key=lambda s: s.created_at, reverse=True)

    def get_current_prompt(self, session_id: str) -> Optional[str]:
        """获取当前步骤的提示词"""
        session = self.get_session(session_id)
        if not session:
            return None

        return self.prompthub.get_step_content(
            session.workflow_id,
            session.current_step,
            session.context
        )

    def get_workflow_info(self, session_id: str) -> Optional[Workflow]:
        """获取会话对应的工作流程信息"""
        session = self.get_session(session_id)
        if not session:
            return None
        return self.prompthub.get_workflow(session.workflow_id)

    async def execute_step(
        self,
        session_id: str,
        executor: str = None,
        user_input: str = None
    ) -> ExecutionResult:
        """执行当前步骤

        Args:
            session_id: 会话 ID
            executor: 执行器名称
            user_input: 用户额外输入

        Returns:
            ExecutionResult: 执行结果
        """
        session = self.get_session(session_id)
        if not session:
            return ExecutionResult.error("会话不存在")

        # 获取提示词
        prompt = self.get_current_prompt(session_id)
        if not prompt:
            return ExecutionResult.error("没有可执行的步骤")

        # 添加用户输入
        if user_input:
            prompt = f"{prompt}\n\n# 用户输入\n{user_input}"

        # 执行
        result = await self.executor.execute(
            prompt=prompt,
            executor=executor,
            context=session.context
        )

        # 保存结果
        session.step_results[session.current_step] = result
        self._save_session(session)

        return result

    def advance_step(self, session_id: str) -> bool:
        """推进到下一步"""
        session = self.get_session(session_id)
        if not session:
            return False

        # 标记当前步骤完成
        session.steps_status[session.current_step] = "completed"

        # 获取工作流程
        workflow = self.prompthub.get_workflow(session.workflow_id)
        if not workflow:
            return False

        # 推进到下一步
        next_step = workflow.get_step(session.current_step + 1)
        if next_step:
            session.current_step = next_step.order
            session.steps_status[next_step.order] = "in_progress"
            self._save_session(session)
            return True
        else:
            # 没有下一步了，会话完成
            session.status = "completed"
            self._save_session(session)
            return True

    def skip_step(self, session_id: str) -> bool:
        """跳过当前步骤"""
        session = self.get_session(session_id)
        if not session:
            return False

        session.steps_status[session.current_step] = "skipped"
        session.notes.append(f"步骤 {session.current_step} 已跳过")

        return self.advance_step(session_id)

    def pause_session(self, session_id: str) -> bool:
        """暂停会话"""
        session = self.get_session(session_id)
        if session:
            session.status = "paused"
            self._save_session(session)
            return True
        return False

    def resume_session(self, session_id: str) -> bool:
        """恢复会话"""
        session = self.get_session(session_id)
        if session:
            session.status = "running"
            self._save_session(session)
            return True
        return False

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]

        session_file = self.sessions_dir / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()
            return True
        return False

    def add_note(self, session_id: str, note: str) -> bool:
        """添加笔记"""
        session = self.get_session(session_id)
        if session:
            session.notes.append(note)
            self._save_session(session)
            return True
        return False

    def update_context(self, session_id: str, context: Dict[str, Any]) -> bool:
        """更新上下文"""
        session = self.get_session(session_id)
        if session:
            session.context.update(context)
            self._save_session(session)
            return True
        return False

    def _save_session(self, session: Session) -> None:
        """保存会话"""
        session_file = self.sessions_dir / f"{session.id}.json"
        session_file.write_text(json.dumps(session.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')

    def get_progress(self, session_id: str) -> Dict[str, Any]:
        """获取会话进度"""
        session = self.get_session(session_id)
        if not session:
            return {}

        workflow = self.prompthub.get_workflow(session.workflow_id)
        if not workflow:
            return {}

        completed = sum(1 for s in session.steps_status.values() if s == "completed")
        total = len(workflow.steps)

        return {
            "current_step": session.current_step,
            "completed": completed,
            "total": total,
            "percentage": int(completed / total * 100) if total > 0 else 0,
            "steps_status": session.steps_status
        }
