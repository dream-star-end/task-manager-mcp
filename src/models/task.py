"""
任务管理数据模型

定义系统中使用的核心数据模型，包括Task等。
"""

from enum import Enum
from typing import Dict, List, Optional, Set, Union, Any
from datetime import datetime
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """任务状态枚举"""
    TODO = "todo"           # 待办
    IN_PROGRESS = "in_progress"  # 进行中
    DONE = "done"           # 已完成
    BLOCKED = "blocked"     # 被阻塞
    CANCELLED = "cancelled"  # 已取消


class TaskPriority(str, Enum):
    """任务优先级枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskComplexity(str, Enum):
    """任务复杂度枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Task(BaseModel):
    """任务数据模型"""
    
    id: str = Field(..., description="任务唯一标识符")
    name: str = Field(..., description="任务名称")
    description: str = Field("", description="任务详细描述")
    status: TaskStatus = Field(default=TaskStatus.TODO, description="任务状态")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="任务优先级")
    complexity: TaskComplexity = Field(default=TaskComplexity.MEDIUM, description="任务复杂度")
    
    dependencies: Set[str] = Field(default_factory=set, description="依赖任务的ID集合")
    blocked_by: Set[str] = Field(default_factory=set, description="阻塞该任务的任务ID集合")
    
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="最后更新时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    
    tags: List[str] = Field(default_factory=list, description="任务标签")
    assigned_to: Optional[str] = Field(None, description="分配给谁")
    
    metadata: Dict[str, Union[str, int, float, bool]] = Field(
        default_factory=dict, description="附加元数据"
    )
    
    estimated_hours: Optional[float] = Field(None, description="预估工时")
    actual_hours: Optional[float] = Field(None, description="实际工时")
    
    code_references: List[str] = Field(default_factory=list, description="关联的代码引用")
    
    parent_task_id: Optional[str] = Field(None, description="父任务ID")
    subtasks: List[Dict[str, Any]] = Field(default_factory=list, description="子任务列表")
    
    class Config:
        use_enum_values = True

    def add_dependency(self, task_id: str) -> None:
        """添加依赖任务"""
        self.dependencies.add(task_id)
    
    def remove_dependency(self, task_id: str) -> None:
        """移除依赖任务"""
        if task_id in self.dependencies:
            self.dependencies.remove(task_id)
    
    def add_blocked_by(self, task_id: str) -> None:
        """添加阻塞任务"""
        self.blocked_by.add(task_id)
    
    def remove_blocked_by(self, task_id: str) -> None:
        """移除阻塞任务"""
        if task_id in self.blocked_by:
            self.blocked_by.remove(task_id)
    
    def is_executable(self) -> bool:
        """检查任务是否可执行（没有阻塞且未完成）"""
        return len(self.blocked_by) == 0 and self.status != TaskStatus.DONE and self.status != TaskStatus.CANCELLED
    
    def mark_as_in_progress(self) -> None:
        """将任务标记为进行中"""
        self.status = TaskStatus.IN_PROGRESS
        self.updated_at = datetime.now()
    
    def mark_as_done(self) -> None:
        """将任务标记为已完成"""
        self.status = TaskStatus.DONE
        self.updated_at = datetime.now()
        self.completed_at = datetime.now()
    
    def mark_as_blocked(self) -> None:
        """将任务标记为已阻塞"""
        self.status = TaskStatus.BLOCKED
        self.updated_at = datetime.now()
    
    def mark_as_cancelled(self) -> None:
        """将任务标记为已取消"""
        self.status = TaskStatus.CANCELLED
        self.updated_at = datetime.now()


class TaskListResponse(BaseModel):
    """任务列表响应模型"""
    tasks: List[Task]
    total: int
    page: int = 1
    page_size: int = 100
    

class TaskResponse(BaseModel):
    """单个任务响应模型"""
    task: Task
    success: bool = True
    message: str = "Task operation successful"


class ErrorResponse(BaseModel):
    """错误响应模型"""
    success: bool = False
    error: str
    error_code: str
    details: Optional[Dict] = None 