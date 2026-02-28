"""
PromptHub 集成模块

负责读取、解析、管理 PromptHub 中的提示词模板。
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class PromptStep:
    """流程步骤"""
    order: int
    name: str
    description: str
    template_content: str
    template_path: str
    variables: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, in_progress, completed, skipped


@dataclass
class Workflow:
    """工作流程"""
    id: str
    name: str
    description: str
    category: str  # new_feature, bug_fix, refactor, etc.
    steps: List[PromptStep] = field(default_factory=list)
    flowsheet: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def get_step(self, order: int) -> Optional[PromptStep]:
        """获取指定步骤"""
        for step in self.steps:
            if step.order == order:
                return step
        return None

    def get_current_step(self) -> Optional[PromptStep]:
        """获取当前进行中的步骤"""
        for step in self.steps:
            if step.status == "in_progress":
                return step
        # 如果没有进行中的，返回第一个未完成的
        for step in self.steps:
            if step.status == "pending":
                return step
        return None

    def get_progress(self) -> tuple[int, int]:
        """获取进度 (已完成, 总数)"""
        completed = sum(1 for s in self.steps if s.status == "completed")
        return completed, len(self.steps)

    def advance_step(self, order: int) -> bool:
        """推进到下一步"""
        step = self.get_step(order)
        if step:
            step.status = "completed"
            next_step = self.get_step(order + 1)
            if next_step:
                next_step.status = "in_progress"
            return True
        return False


class PromptHubManager:
    """PromptHub 管理器

    功能：
    1. 扫描 prompts 目录
    2. 解析流程模板
    3. 提供提示词内容
    4. 支持编辑提示词
    """

    def __init__(self, prompts_dir: str = "./prompts"):
        self.prompts_dir = Path(prompts_dir)
        self.workflows: Dict[str, Workflow] = {}
        self._scan_workflows()

    def _scan_workflows(self) -> None:
        """扫描工作流程"""
        if not self.prompts_dir.exists():
            return

        for category_dir in self.prompts_dir.iterdir():
            if not category_dir.is_dir():
                continue

            category = category_dir.name

            # 读取流程图
            flowsheet_path = category_dir / "flowsheet.md"
            flowsheet = ""
            if flowsheet_path.exists():
                flowsheet = flowsheet_path.read_text(encoding='utf-8')

            # 扫描步骤文件 (按序号排序)
            steps = []
            for file_path in sorted(category_dir.glob("*.md")) + sorted(category_dir.glob("*.txt")):
                if file_path.name == "flowsheet.md":
                    continue

                # 解析序号
                match = re.match(r'^(\d+)', file_path.stem)
                if match:
                    order = int(match.group(1))
                else:
                    continue

                content = file_path.read_text(encoding='utf-8')
                steps.append(PromptStep(
                    order=order,
                    name=file_path.stem,
                    description=self._extract_description(content),
                    template_content=content,
                    template_path=str(file_path.relative_to(self.prompts_dir)),
                    variables=self._extract_variables(content)
                ))

            # 创建工作流程
            workflow_id = category
            self.workflows[workflow_id] = Workflow(
                id=workflow_id,
                name=category.replace("_", " ").title(),
                description=self._get_category_description(category),
                category=category,
                steps=steps,
                flowsheet=flowsheet
            )

    def _extract_description(self, content: str) -> str:
        """从内容中提取描述"""
        # 尝试从 markdown 标题提取
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        # 使用第一行
        first_line = content.split('\n')[0].strip()
        return first_line if first_line else "无描述"

    def _extract_variables(self, content: str) -> List[str]:
        """提取模板变量"""
        # 匹配 {{variable}} 格式
        pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}'
        return list(set(re.findall(pattern, content)))

    def _get_category_description(self, category: str) -> str:
        """获取分类描述"""
        descriptions = {
            "new_feature": "新功能开发流程",
            "bug_fix": "Bug 修复流程",
            "refactor": "代码重构流程",
            "other": "其他流程"
        }
        return descriptions.get(category, category)

    def list_workflows(self) -> List[Workflow]:
        """列出所有工作流程"""
        return list(self.workflows.values())

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """获取工作流程"""
        return self.workflows.get(workflow_id)

    def get_step_content(self, workflow_id: str, step_order: int, variables: Dict[str, Any] = None) -> Optional[str]:
        """获取步骤内容（可替换变量）"""
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            return None

        step = workflow.get_step(step_order)
        if not step:
            return None

        content = step.template_content

        # 替换变量
        if variables:
            for key, value in variables.items():
                content = content.replace(f"{{{{{key}}}}}", str(value))
                content = content.replace(f"{{{{ {key} }}}}", str(value))

        return content

    def update_step_content(self, workflow_id: str, step_order: int, new_content: str) -> bool:
        """更新步骤内容"""
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            return False

        step = workflow.get_step(step_order)
        if not step:
            return False

        # 更新内存中的内容
        step.template_content = new_content
        step.variables = self._extract_variables(new_content)

        # 写入文件
        template_path = self.prompts_dir / step.template_path
        template_path.parent.mkdir(parents=True, exist_ok=True)
        template_path.write_text(new_content, encoding='utf-8')

        return True

    def create_workflow_instance(self, workflow_id: str) -> Optional[Workflow]:
        """创建工作流程实例（用于执行）"""
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            return None

        # 深拷贝创建新实例
        import copy
        instance = copy.deepcopy(workflow)
        instance.id = f"{workflow_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        return instance

    def reload(self) -> None:
        """重新扫描工作流程"""
        self.workflows.clear()
        self._scan_workflows()
