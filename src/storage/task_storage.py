"""
任务存储层

提供任务数据的存储和检索功能。
目前实现内存存储，未来可扩展为数据库存储。
"""

import uuid
import sys
import os
from typing import Dict, List, Optional, Set, Tuple, Union
from datetime import datetime
import logging
import json

# 将项目根目录添加到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# 兼容从不同目录运行的导入路径
try:
    from ..models.task import Task, TaskStatus, TaskPriority, TaskComplexity
except (ImportError, ValueError):
    from src.models.task import Task, TaskStatus, TaskPriority, TaskComplexity

logger = logging.getLogger(__name__)

class TaskStorage:
    """任务内存存储类"""
    
    def __init__(self):
        """初始化内存存储"""
        self.tasks: Dict[str, Task] = {}
        # 依赖关系图（任务ID -> 被该任务阻塞的任务ID集合）
        self.dependency_graph: Dict[str, Set[str]] = {}
    
    def create_task(
        self, 
        name: str, 
        description: str = "", 
        id: Optional[str] = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        complexity: TaskComplexity = TaskComplexity.MEDIUM,
        tags: List[str] = None,
        assigned_to: Optional[str] = None,
        estimated_hours: Optional[float] = None,
        dependencies: List[str] = None,
        code_references: List[str] = None
    ) -> Task:
        """创建新任务"""
        task_id = id if id is not None else str(uuid.uuid4())
        
        if id is not None and task_id in self.tasks:
            raise ValueError(f"Task with ID '{task_id}' already exists.")
        
        # 初始化标签和依赖
        task_tags = tags or []
        task_dependencies = set(dependencies or [])
        
        # 创建任务对象
        task = Task(
            id=task_id,
            name=name,
            description=description,
            status=TaskStatus.TODO,
            priority=priority,
            complexity=complexity,
            dependencies=task_dependencies,
            blocked_by=set(),  # 初始无阻塞
            created_at=datetime.now(),
            updated_at=datetime.now(),
            tags=task_tags,
            assigned_to=assigned_to,
            estimated_hours=estimated_hours,
            **({"code_references": code_references} if code_references is not None else {})
        )
        
        # 存储任务
        self.tasks[task_id] = task
        self.dependency_graph[task_id] = set()
        
        # 处理依赖关系
        if task_dependencies:
            for dep_id in task_dependencies:
                if dep_id in self.tasks:
                    # 更新依赖图
                    if dep_id not in self.dependency_graph:
                        self.dependency_graph[dep_id] = set()
                    self.dependency_graph[dep_id].add(task_id)
                    # 更新被阻塞状态
                    task.add_blocked_by(dep_id)
        
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务信息"""
        return self.tasks.get(task_id)
    
    def update_task(self, task_id: str, **kwargs) -> Optional[Task]:
        """更新任务信息"""
        task = self.tasks.get(task_id)
        if not task:
            return None
        
        # 处理可更新的字段
        for field, value in kwargs.items():
            if hasattr(task, field) and field != "id":
                setattr(task, field, value)
        
        # 更新时间戳
        task.updated_at = datetime.now()
        
        return task
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        if task_id not in self.tasks:
            return False
        
        # 清理依赖关系
        dependencies = self.tasks[task_id].dependencies
        for dep_id in dependencies:
            if dep_id in self.dependency_graph:
                self.dependency_graph[dep_id].discard(task_id)
        
        # 清理被阻塞关系
        blocked_tasks = self.dependency_graph.get(task_id, set())
        for blocked_id in blocked_tasks:
            if blocked_id in self.tasks:
                self.tasks[blocked_id].blocked_by.discard(task_id)
        
        # 删除任务和依赖图条目
        del self.tasks[task_id]
        if task_id in self.dependency_graph:
            del self.dependency_graph[task_id]
        
        return True
    
    def list_tasks(
        self, 
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None, 
        tag: Optional[str] = None,
        assigned_to: Optional[str] = None,
        page: int = 1,
        page_size: int = 100
    ) -> Tuple[List[Task], int]:
        """列出任务，支持筛选和分页"""
        filtered_tasks = self.tasks.values()
        
        # 应用筛选
        if status:
            filtered_tasks = [t for t in filtered_tasks if t.status == status]
        if priority:
            filtered_tasks = [t for t in filtered_tasks if t.priority == priority]
        if tag:
            filtered_tasks = [t for t in filtered_tasks if tag in t.tags]
        if assigned_to:
            filtered_tasks = [t for t in filtered_tasks if t.assigned_to == assigned_to]
        
        # 计算总数
        total = len(filtered_tasks)
        
        # 应用分页
        start = (page - 1) * page_size
        end = start + page_size
        paged_tasks = sorted(
            filtered_tasks, 
            key=lambda t: (t.id),
            reverse=False
        )[start:end]
        
        return paged_tasks, total
    
    def set_task_dependency(self, task_id: str, depends_on_id: str) -> Tuple[bool, Optional[str]]:
        """设置任务依赖关系"""
        # 检查任务是否存在
        if task_id not in self.tasks or depends_on_id not in self.tasks:
            return False, "One or both tasks do not exist"
        
        # 不能依赖自己
        if task_id == depends_on_id:
            return False, "Task cannot depend on itself"
        
        # 检测循环依赖
        if self._would_create_cycle(task_id, depends_on_id):
            return False, "This would create a circular dependency"
        
        # 添加依赖关系
        task = self.tasks[task_id]
        task.add_dependency(depends_on_id)
        task.add_blocked_by(depends_on_id)
        
        # 更新依赖图
        if depends_on_id not in self.dependency_graph:
            self.dependency_graph[depends_on_id] = set()
        self.dependency_graph[depends_on_id].add(task_id)
        
        # 如果被依赖任务已完成，移除阻塞
        if self.tasks[depends_on_id].status == TaskStatus.DONE:
            task.remove_blocked_by(depends_on_id)
        
        return True, None
    
    def remove_task_dependency(self, task_id: str, depends_on_id: str) -> bool:
        """移除任务依赖关系"""
        # 检查任务是否存在
        if task_id not in self.tasks or depends_on_id not in self.tasks:
            return False
        
        # 移除依赖关系
        task = self.tasks[task_id]
        task.remove_dependency(depends_on_id)
        task.remove_blocked_by(depends_on_id)
        
        # 更新依赖图
        if depends_on_id in self.dependency_graph:
            self.dependency_graph[depends_on_id].discard(task_id)
        
        return True
    
    def get_next_executable_tasks(self, limit: int = 5) -> List[Task]:
        """获取下一批可执行的任务
        
        修改后的逻辑：
        1. 首先查找状态为in_progress的主任务，并优先检查其子任务
        2. 如果没有in_progress的主任务或其子任务不足以达到限制数量，
           则查找状态为todo且没有未完成依赖的主任务，并优先检查其子任务
        3. 如果仍未达到限制数量，则返回主任务本身
        
        Args:
            limit: 返回任务数量限制
            
        Returns:
            List[Task]: 排序后的可执行任务列表
        """
        # 结果任务列表
        final_tasks = []
        
        # 第一步: 找出所有正在进行中的主任务（即顶级任务，不是子任务）
        in_progress_parent_tasks = [
            task for task in self.tasks.values()
            if task.status == TaskStatus.IN_PROGRESS and "." not in task.id
        ]
        
        # 第二步: 找出所有状态为todo且没有未完成依赖的主任务
        executable_parent_tasks = [
            task for task in self.tasks.values()
            if task.status == TaskStatus.TODO and 
            len(task.blocked_by) == 0 and 
            "." not in task.id
        ]
        
        # 按优先级和创建时间排序进行中的主任务
        sorted_in_progress_parents = sorted(
            in_progress_parent_tasks,
            key=lambda t: (
                # 优先级从高到低
                {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(t.priority, 4),
                # 创建时间（越早创建越优先）
                t.created_at
            )
        )
        
        # 按优先级、依赖关系和创建时间排序可执行的主任务
        sorted_executable_parents = sorted(
            executable_parent_tasks,
            key=lambda t: (
                # 优先级从高到低
                {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(t.priority, 4),
                # 依赖该任务的任务数量（越多越优先）
                -len(self.dependency_graph.get(t.id, set())),
                # 创建时间（越早创建越优先）
                t.created_at
            )
        )
        
        # 第三步: 优先查找进行中主任务的子任务
        for parent_task in sorted_in_progress_parents:
            # 检查这个主任务是否有子任务列表
            subtasks = getattr(parent_task, 'subtasks', None)
            
            if subtasks and isinstance(subtasks, list):
                # 找出可执行的子任务：状态为todo且没有未完成依赖
                executable_subtasks = []
                
                for subtask_dict in subtasks:
                    # 检查子任务是否为字典格式（新的嵌套结构）
                    if isinstance(subtask_dict, dict):
                        subtask_status = subtask_dict.get('status')
                        subtask_blocked_by = subtask_dict.get('blocked_by', [])
                        
                        if subtask_status == 'todo' and len(subtask_blocked_by) == 0:
                            # 把子任务字典转换为Task对象
                            # 注意：这里可能需要根据实际Task类构造函数调整
                            subtask = Task(
                                id=subtask_dict.get('id', ''),
                                name=subtask_dict.get('name', ''),
                                description=subtask_dict.get('description', ''),
                                status=subtask_dict.get('status', 'todo'),
                                priority=subtask_dict.get('priority', 'medium'),
                                dependencies=set(subtask_dict.get('dependencies', [])),
                                blocked_by=set(subtask_dict.get('blocked_by', [])),
                                tags=subtask_dict.get('tags', []),
                                assigned_to=subtask_dict.get('assigned_to'),
                                estimated_hours=subtask_dict.get('estimated_hours'),
                                actual_hours=subtask_dict.get('actual_hours'),
                                code_references=subtask_dict.get('code_references', []),
                                complexity=subtask_dict.get('complexity', 'medium'),
                            )
                            
                            # 设置时间字段（如果存在）
                            if 'created_at' in subtask_dict:
                                subtask.created_at = datetime.fromisoformat(subtask_dict['created_at'])
                            if 'updated_at' in subtask_dict:
                                subtask.updated_at = datetime.fromisoformat(subtask_dict['updated_at'])
                            if 'completed_at' in subtask_dict and subtask_dict['completed_at']:
                                subtask.completed_at = datetime.fromisoformat(subtask_dict['completed_at'])
                                
                            executable_subtasks.append(subtask)
                
                # 按优先级和创建时间排序子任务
                sorted_executable_subtasks = sorted(
                    executable_subtasks,
                    key=lambda t: (
                        # 优先级从高到低
                        {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(t.priority, 4),
                        # 创建时间（越早创建越优先）
                        t.created_at
                    )
                )
                
                # 将排序后的子任务添加到结果列表
                final_tasks.extend(sorted_executable_subtasks)
                
                # 如果已经达到限制，则返回结果
                if len(final_tasks) >= limit:
                    return final_tasks[:limit]
        
        # 第四步: 如果还没达到限制，查找可执行主任务的子任务
        for parent_task in sorted_executable_parents:
            # 检查这个主任务是否有子任务列表
            subtasks = getattr(parent_task, 'subtasks', None)
            
            if subtasks and isinstance(subtasks, list):
                # 找出可执行的子任务：状态为todo且没有未完成依赖
                executable_subtasks = []
                
                for subtask_dict in subtasks:
                    # 检查子任务是否为字典格式（新的嵌套结构）
                    if isinstance(subtask_dict, dict):
                        subtask_status = subtask_dict.get('status')
                        subtask_blocked_by = subtask_dict.get('blocked_by', [])
                        
                        if subtask_status == 'todo' and len(subtask_blocked_by) == 0:
                            # 把子任务字典转换为Task对象
                            subtask = Task(
                                id=subtask_dict.get('id', ''),
                                name=subtask_dict.get('name', ''),
                                description=subtask_dict.get('description', ''),
                                status=subtask_dict.get('status', 'todo'),
                                priority=subtask_dict.get('priority', 'medium'),
                                dependencies=set(subtask_dict.get('dependencies', [])),
                                blocked_by=set(subtask_dict.get('blocked_by', [])),
                                tags=subtask_dict.get('tags', []),
                                assigned_to=subtask_dict.get('assigned_to'),
                                estimated_hours=subtask_dict.get('estimated_hours'),
                                actual_hours=subtask_dict.get('actual_hours'),
                                code_references=subtask_dict.get('code_references', []),
                                complexity=subtask_dict.get('complexity', 'medium'),
                            )
                            
                            # 设置时间字段（如果存在）
                            if 'created_at' in subtask_dict:
                                subtask.created_at = datetime.fromisoformat(subtask_dict['created_at'])
                            if 'updated_at' in subtask_dict:
                                subtask.updated_at = datetime.fromisoformat(subtask_dict['updated_at'])
                            if 'completed_at' in subtask_dict and subtask_dict['completed_at']:
                                subtask.completed_at = datetime.fromisoformat(subtask_dict['completed_at'])
                                
                            executable_subtasks.append(subtask)
                
                # 按优先级和创建时间排序子任务
                sorted_executable_subtasks = sorted(
                    executable_subtasks,
                    key=lambda t: (
                        # 优先级从高到低
                        {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(t.priority, 4),
                        # 创建时间（越早创建越优先）
                        t.created_at
                    )
                )
                
                # 将排序后的子任务添加到结果列表
                final_tasks.extend(sorted_executable_subtasks)
                
                # 如果已经达到限制，则返回结果
                if len(final_tasks) >= limit:
                    return final_tasks[:limit]
        
        # 第五步: 如果还没达到限制，添加进行中的主任务本身
        final_tasks.extend(sorted_in_progress_parents)
        
        # 如果已经达到限制，则返回结果
        if len(final_tasks) >= limit:
            return final_tasks[:limit]
        
        # 第六步: 如果还没达到限制，添加可执行的主任务本身
        final_tasks.extend(sorted_executable_parents)
        
        # 返回限制数量的任务
        return final_tasks[:limit]
    
    def _would_create_cycle(self, task_id: str, depends_on_id: str) -> bool:
        """检测添加依赖是否会导致循环依赖"""
        # 如果被依赖的任务已经直接或间接依赖于当前任务，则会形成循环
        visited = set()
        queue = [depends_on_id]
        
        while queue:
            current = queue.pop(0)
            if current == task_id:
                return True
            
            if current in visited:
                continue
                
            visited.add(current)
            dependencies = self.tasks.get(current, Task(id="", name="")).dependencies
            queue.extend([dep for dep in dependencies if dep not in visited])
        
        return False
    
    def mark_task_done(self, task_id: str) -> bool:
        """将任务标记为已完成"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        task.mark_as_done()
        
        # 解除对其他任务的阻塞
        blocked_tasks = self.dependency_graph.get(task_id, set())
        for blocked_id in blocked_tasks:
            if blocked_id in self.tasks:
                blocked_task = self.tasks[blocked_id]
                blocked_task.remove_blocked_by(task_id)
        
        return True
    
    def count_tasks_by_status(self) -> Dict[str, int]:
        """统计各状态任务数量"""
        counts = {status.value: 0 for status in TaskStatus}
        
        for task in self.tasks.values():
            counts[task.status] += 1
            
        return counts

    def clear_all_tasks(self) -> None:
        """清空所有任务和依赖关系"""
        self.tasks.clear()
        self.dependency_graph.clear()
        logger.info("所有任务和依赖关系已被清空")
