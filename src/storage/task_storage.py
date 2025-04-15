"""
任务存储层

提供任务数据的存储和检索功能。
使用 JSON 文件进行持久化存储。
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
    """任务 JSON 文件存储类"""
    
    def __init__(self, tasks_dir: str = None):
        """初始化任务存储
        
        Args:
            tasks_dir: 任务 JSON 文件存储目录，若为 None 则使用默认目录
        """
        # 如果未指定目录，使用默认路径
        if tasks_dir is None:
            # 获取项目根目录
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.tasks_dir = os.path.join(project_root, 'output', 'tasks')
        else:
            self.tasks_dir = tasks_dir
            
        # 确保目录存在
        os.makedirs(self.tasks_dir, exist_ok=True)
        
        self.master_file_path = os.path.join(self.tasks_dir, "all_tasks.json")
        
        # 任务字典 (内存缓存)
        self.tasks: Dict[str, Task] = {}
        # 依赖关系图（任务ID -> 被该任务阻塞的任务ID集合）
        self.dependency_graph: Dict[str, Set[str]] = {}
        
        # 从文件加载任务
        self._load_tasks_from_file()
    
    def _load_tasks_from_file(self) -> None:
        """从主任务 JSON 文件加载所有任务"""
        if not os.path.exists(self.master_file_path):
            logger.info(f"主任务文件不存在，将创建新文件: {self.master_file_path}")
            return
        
        try:
            with open(self.master_file_path, 'r', encoding='utf-8') as f:
                tasks_data = json.load(f)
                
            # 清空当前缓存
            self.tasks.clear()
            self.dependency_graph.clear()
            
            # 加载主任务及其子任务
            for task_dict in tasks_data:
                task_id = task_dict.get('id')
                if not task_id or '.' in task_id: # 只处理主任务ID
                    logger.warning(f"跳过无效或非主任务数据: {task_dict}")
                    continue
                
                try:
                    # 创建任务对象 (包含递归创建的子任务Task对象)
                    task = self._dict_to_task(task_dict)
                    
                    # 存储主任务
                    self.tasks[task_id] = task
                    logger.debug(f"主任务 {task_id} 已加载，包含 {len(task.subtasks)} 个子任务对象")

                except Exception as load_e:
                    logger.error(f"加载任务 {task_id} 失败: {load_e}", exc_info=True)
                    continue # 继续加载下一个任务
            
            # 所有主任务及其子任务对象加载完毕后，重建依赖图
            self._rebuild_dependency_graph()
            
            logger.info(f"从文件加载了 {len(self.tasks)} 个主任务及其子任务")
            
        except Exception as e:
            logger.error(f"从文件加载任务失败: {str(e)}", exc_info=True)
    
    def _dict_to_task(self, task_dict: Dict) -> Task:
        """将任务字典转换为 Task 对象"""
        # 获取依赖和被阻塞关系
        dependencies = set(task_dict.get('dependencies', []))
        blocked_by = set(task_dict.get('blocked_by', []))
        
        # 确保blocked_by包含所有依赖
        for dep_id in dependencies:
            blocked_by.add(dep_id)
        
        # 处理子任务（将字典列表转换为Task对象列表）
        subtasks_data = task_dict.get('subtasks', [])
        subtasks = []
        if isinstance(subtasks_data, list):
            for sub_dict in subtasks_data:
                if isinstance(sub_dict, dict):
                    try:
                        subtasks.append(self._dict_to_task(sub_dict)) # 递归调用
                    except Exception as e:
                        logger.error(f"转换子任务字典失败 ({sub_dict.get('id')}): {e}")
                elif isinstance(sub_dict, Task): # 如果已经是Task对象，直接添加
                    subtasks.append(sub_dict)

        task = Task(
            id=task_dict.get('id', ''),
            name=task_dict.get('name', ''),
            description=task_dict.get('description', ''),
            status=task_dict.get('status', 'todo'),
            priority=task_dict.get('priority', 'medium'),
            complexity=task_dict.get('complexity', 'medium'),
            dependencies=dependencies,
            blocked_by=blocked_by,
            tags=task_dict.get('tags', []), 
            assigned_to=task_dict.get('assigned_to'),
            estimated_hours=task_dict.get('estimated_hours'),
            actual_hours=task_dict.get('actual_hours'),
            code_references=task_dict.get('code_references', []),
            subtasks=subtasks, # 传入转换后的Task对象列表
            parent_task_id=task_dict.get('parent_task_id') # 确保父任务ID也被处理
        )
        
        # 设置时间字段
        if 'created_at' in task_dict and task_dict['created_at']:
            try:
                task.created_at = datetime.fromisoformat(task_dict['created_at'])
            except (ValueError, TypeError):
                task.created_at = datetime.now()
                
        if 'updated_at' in task_dict and task_dict['updated_at']:
            try:
                task.updated_at = datetime.fromisoformat(task_dict['updated_at'])
            except (ValueError, TypeError):
                task.updated_at = datetime.now()
                
        if 'completed_at' in task_dict and task_dict['completed_at']:
            try:
                task.completed_at = datetime.fromisoformat(task_dict['completed_at'])
            except (ValueError, TypeError):
                task.completed_at = None
        
        return task
    
    def _rebuild_dependency_graph(self) -> None:
        """重建依赖关系图"""
        self.dependency_graph.clear()
        
        # 处理主任务依赖
        for task_id, task in self.tasks.items():
            self.dependency_graph[task_id] = set()
            
            # 添加依赖关系
            for dep_id in task.dependencies:
                if dep_id in self.tasks:
                    if dep_id not in self.dependency_graph:
                        self.dependency_graph[dep_id] = set()
                    self.dependency_graph[dep_id].add(task_id)
        
        # 处理子任务依赖
        for task_id, task in self.tasks.items():
            if hasattr(task, 'subtasks') and isinstance(task.subtasks, list):
                for subtask in task.subtasks:
                    if not isinstance(subtask, Task):
                        continue
                    
                    subtask_id = subtask.id
                    if not subtask_id:
                        continue
                    
                    # 确保存在依赖图条目
                    if subtask_id not in self.dependency_graph:
                        self.dependency_graph[subtask_id] = set()
                    
                    # 添加子任务的依赖关系
                    for dep_id in subtask.dependencies:
                        if dep_id not in self.dependency_graph:
                            self.dependency_graph[dep_id] = set()
                        self.dependency_graph[dep_id].add(subtask_id)
    
    def _task_to_dict(self, task: Task) -> Dict:
        """将 Task 对象（包括子任务）转换为适合JSON序列化的字典"""
        if not task:
            return {}
        
        task_dict = {
            'id': task.id,
            'name': task.name,
            'description': task.description,
            'status': task.status,
            'priority': task.priority,
            'complexity': task.complexity,
            'dependencies': list(task.dependencies),
            'blocked_by': list(task.blocked_by),
            'tags': task.tags,
            'assigned_to': task.assigned_to,
            'estimated_hours': task.estimated_hours,
            'actual_hours': task.actual_hours,
            'code_references': task.code_references,
            'created_at': task.created_at.isoformat() if task.created_at else None,
            'updated_at': task.updated_at.isoformat() if task.updated_at else None,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'parent_task_id': task.parent_task_id, # 从Task对象获取
            # 初始化 subtasks 为空列表，后面填充
            'subtasks': [] 
        }

        # --- 修复: 递归处理子任务 --- 
        if hasattr(task, 'subtasks') and isinstance(task.subtasks, list):
            task_dict['subtasks'] = [self._task_to_dict(sub) for sub in task.subtasks if isinstance(sub, Task)]
        
        return task_dict
    
    def _save_tasks_to_file(self) -> None:
        """将所有任务保存到主任务 JSON 文件"""
        try:
            tasks_data = []
            # 只迭代主任务进行保存
            for task_id, task in self.tasks.items():
                if "." not in task_id: 
                    # --- 修复: 直接使用 _task_to_dict 返回的完整字典 --- 
                    tasks_data.append(self._task_to_dict(task))
            
            # 写入文件
            with open(self.master_file_path, 'w', encoding='utf-8') as f:
                json.dump(tasks_data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"所有主任务及其子任务已递归转换为字典并保存到文件: {self.master_file_path}")
        except Exception as e:
            logger.error(f"保存任务到文件失败: {str(e)}", exc_info=True)
    
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
        
        # 判断是否为子任务
        if "." in task_id:
            # 寻找父任务
            parent_id = task_id.split(".")[0]
            parent_task = self.tasks.get(parent_id)
            
            if parent_task:
                # 初始化父任务的子任务列表（如果不存在）
                if not hasattr(parent_task, 'subtasks') or parent_task.subtasks is None:
                    parent_task.subtasks = []
                
                # 添加到父任务的子任务列表
                parent_task.subtasks.append(task)
                logger.info(f"子任务 {task_id} 已添加到父任务 {parent_id}")
            else:
                logger.warning(f"未找到子任务 {task_id} 的父任务 {parent_id}，将作为独立任务处理")
                # 仍将其存储为独立任务
                self.tasks[task_id] = task
        else:
            # 主任务直接存储
            self.tasks[task_id] = task
        
        # 更新依赖关系图
        self.dependency_graph[task_id] = set()
        
        # 处理依赖关系
        if task_dependencies:
            for dep_id in task_dependencies:
                # 查找依赖是主任务还是子任务
                if dep_id in self.tasks:  # 主任务
                    # 更新依赖图
                    if dep_id not in self.dependency_graph:
                        self.dependency_graph[dep_id] = set()
                    self.dependency_graph[dep_id].add(task_id)
                    # 更新被阻塞状态
                    task.add_blocked_by(dep_id)
                else:
                    # 检查是否为某个主任务的子任务
                    found = False
                    for main_task in self.tasks.values():
                        if hasattr(main_task, 'subtasks') and isinstance(main_task.subtasks, list):
                            for subtask in main_task.subtasks:
                                if isinstance(subtask, Task) and subtask.id == dep_id:
                                    # 更新依赖图
                                    if dep_id not in self.dependency_graph:
                                        self.dependency_graph[dep_id] = set()
                                    self.dependency_graph[dep_id].add(task_id)
                                    # 更新被阻塞状态
                                    task.add_blocked_by(dep_id)
                                    found = True
                                    break
                        if found:
                            break
        
        # 保存到文件
        self._save_tasks_to_file()
        
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务信息
        
        先从内存中查找主任务，如果是子任务则在父任务的子任务列表中查找
        """
        # 检查是否为主任务
        if task_id in self.tasks:
            return self.tasks[task_id]
        
        # 如果是子任务，找到父任务然后在子任务列表中查找
        if "." in task_id:
            parent_id = task_id.split(".")[0]
            parent_task = self.tasks.get(parent_id)
            
            found_subtask = None
            if parent_task and hasattr(parent_task, 'subtasks') and isinstance(parent_task.subtasks, list):
                for subtask in parent_task.subtasks:
                    if isinstance(subtask, Task) and subtask.id == task_id:
                        found_subtask = subtask
                        break
            
            # 如果第一次查找失败，尝试重新加载数据再查找一次 (处理可能的缓存问题)
            if not found_subtask:
                logger.warning(f"第一次查找子任务 {task_id} 失败，尝试重新加载数据...")
                self._load_tasks_from_file() # 强制重新加载
                parent_task = self.tasks.get(parent_id) # 重新获取父任务
                if parent_task and hasattr(parent_task, 'subtasks') and isinstance(parent_task.subtasks, list):
                    for subtask in parent_task.subtasks:
                        if isinstance(subtask, Task) and subtask.id == task_id:
                            logger.info(f"重新加载后成功找到子任务 {task_id}")
                            found_subtask = subtask
                            break
            
            return found_subtask # 返回找到的子任务或 None
        
        return None
    
    def update_task(self, task_id: str, **kwargs) -> Optional[Task]:
        """更新任务信息"""
        task = self.get_task(task_id)
        if not task:
            return None
        
        # 处理可更新的字段
        for field, value in kwargs.items():
            if field == "subtasks":
                # 特殊处理子任务列表
                if not isinstance(value, list):
                    logger.error(f"更新任务 {task_id} 失败: subtasks 字段值不是列表")
                    continue
                
                # --- 修复: 根据传入列表的类型决定如何处理 --- 
                if not value: # 空列表
                    task.subtasks = []
                    logger.info(f"任务 {task_id} 的子任务列表已更新为空列表")
                elif isinstance(value[0], Task): # 传入的是 List[Task]
                    task.subtasks = value
                    logger.info(f"任务 {task_id} 的子任务列表已直接更新 (传入类型: List[Task])")
                elif isinstance(value[0], dict): # 传入的是 List[Dict]
                    try:
                        task.subtasks = [self._dict_to_task(sub_dict) for sub_dict in value]
                        logger.info(f"任务 {task_id} 的子任务列表已更新 (传入类型: List[Dict], 已转换为 List[Task])")
                    except Exception as convert_e:
                        logger.error(f"更新任务 {task_id} 时转换子任务字典列表失败: {convert_e}", exc_info=True)
                        continue # 跳过更新此字段
                else: # 列表包含未知类型
                    logger.error(f"更新任务 {task_id} 失败: subtasks 列表包含无效类型 ({type(value[0])})")
                    continue

            elif hasattr(task, field) and field != "id":
                setattr(task, field, value)
        
        # 更新时间戳
        task.updated_at = datetime.now()
        
        # 保存到文件
        self._save_tasks_to_file()
        
        return task
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        # 先尝试找到这个任务
        task = self.get_task(task_id)
        if not task:
            return False
        
        # 清理依赖关系
        dependencies = task.dependencies
        for dep_id in dependencies:
            if dep_id in self.dependency_graph:
                self.dependency_graph[dep_id].discard(task_id)
        
        # 清理被阻塞关系
        blocked_tasks = self.dependency_graph.get(task_id, set())
        for blocked_id in blocked_tasks:
            blocked_task = self.get_task(blocked_id)
            if blocked_task:
                blocked_task.blocked_by.discard(task_id)
        
        # 判断是主任务还是子任务
        if "." in task_id:
            # 子任务，从父任务的子任务列表中删除
            parent_id = task_id.split(".")[0]
            parent_task = self.tasks.get(parent_id)
            
            if parent_task and hasattr(parent_task, 'subtasks') and isinstance(parent_task.subtasks, list):
                # 从父任务的子任务列表中删除
                parent_task.subtasks = [
                    subtask for subtask in parent_task.subtasks 
                    if not isinstance(subtask, Task) or subtask.id != task_id
                ]
        else:
            # 主任务，直接从字典中删除
            if task_id in self.tasks:
                del self.tasks[task_id]
        
        # 从依赖图中删除
        if task_id in self.dependency_graph:
            del self.dependency_graph[task_id]
        
        # 保存到文件
        self._save_tasks_to_file()
        
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
        # 收集所有任务（主任务和子任务）
        all_tasks = []
        
        # 添加主任务
        for task in self.tasks.values():
            all_tasks.append(task)
            
            # 添加子任务
            if hasattr(task, 'subtasks') and isinstance(task.subtasks, list):
                all_tasks.extend([
                    subtask for subtask in task.subtasks 
                    if isinstance(subtask, Task)
                ])
        
        # 应用筛选
        filtered_tasks = all_tasks
        
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
        # 获取任务对象
        task = self.get_task(task_id)
        depends_on_task = self.get_task(depends_on_id)
        
        # 检查任务是否存在
        if not task or not depends_on_task:
            return False, "One or both tasks do not exist"
        
        # 不能依赖自己
        if task_id == depends_on_id:
            return False, "Task cannot depend on itself"
        
        # 检测循环依赖
        if self._would_create_cycle(task_id, depends_on_id):
            return False, "This would create a circular dependency"
        
        # 添加依赖关系
        task.add_dependency(depends_on_id)
        task.add_blocked_by(depends_on_id)
        
        # 更新依赖图
        if depends_on_id not in self.dependency_graph:
            self.dependency_graph[depends_on_id] = set()
        self.dependency_graph[depends_on_id].add(task_id)
        
        # 如果被依赖任务已完成，移除阻塞
        if depends_on_task.status == TaskStatus.DONE:
            task.remove_blocked_by(depends_on_id)
        
        # 保存到文件
        self._save_tasks_to_file()
        
        return True, None
    
    def remove_task_dependency(self, task_id: str, depends_on_id: str) -> bool:
        """移除任务依赖关系"""
        # 获取任务对象
        task = self.get_task(task_id)
        depends_on_task = self.get_task(depends_on_id)
        
        # 检查任务是否存在
        if not task or not depends_on_task:
            return False
        
        # 移除依赖关系
        task.remove_dependency(depends_on_id)
        task.remove_blocked_by(depends_on_id)
        
        # 更新依赖图
        if depends_on_id in self.dependency_graph:
            self.dependency_graph[depends_on_id].discard(task_id)
        
        # 保存到文件
        self._save_tasks_to_file()
        
        return True
    
    def get_next_executable_tasks(self, limit: int = 5) -> List[Task]:
        """获取下一批可执行的任务
        
        新的逻辑：
        1. 先找出最优先的主任务（没有被阻塞且状态为todo或in_progress）
        2. 只在这个主任务的子任务中查找最优先的子任务
        3. 如果主任务有可执行的子任务，则返回子任务，否则返回主任务本身
        
        Args:
            limit: 返回任务数量限制
            
        Returns:
            List[Task]: 排序后的可执行任务列表
        """
        # 结果任务列表
        final_tasks = []
        
        # 找出所有没有被阻塞的主任务（不包括子任务）
        executable_parent_tasks = [
            task for task in self.tasks.values()
            if (task.status == TaskStatus.TODO or task.status == TaskStatus.IN_PROGRESS) and 
            len(task.blocked_by) == 0 and 
            "." not in task.id
        ]
        
        # 按优先级、依赖关系和创建时间排序主任务
        sorted_parent_tasks = sorted(
            executable_parent_tasks,
            key=lambda t: (
                # 状态优先级：in_progress优先于todo
                0 if t.status == TaskStatus.IN_PROGRESS else 1,
                # 优先级从高到低
                {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(t.priority, 4),
                # 依赖该任务的任务数量（越多越优先）
                -len(self.dependency_graph.get(t.id, set())),
                # 创建时间（越早创建越优先）
                t.created_at
            )
        )
        
        # 如果没有可执行的主任务，返回空列表
        if not sorted_parent_tasks:
            return []
        
        # 获取最优先的主任务
        top_parent_task = sorted_parent_tasks[0]
        logger.info(f"最优先的主任务是: {top_parent_task.id} ({top_parent_task.name}), 优先级: {top_parent_task.priority}")
        
        # 检查主任务是否有子任务
        subtasks = getattr(top_parent_task, 'subtasks', None)
        has_executable_subtasks = False
        
        if subtasks and isinstance(subtasks, list) and len(subtasks) > 0:
            logger.info(f"主任务 {top_parent_task.id} 有 {len(subtasks)} 个子任务")
            
            # 第一步：找出所有子任务的ID、状态和阻塞列表
            subtask_obj_map = {}
            for subtask in subtasks:
                if isinstance(subtask, Task):
                    subtask_obj_map[subtask.id] = subtask
                    logger.info(f"  检查子任务 {subtask.id} ({subtask.name}), 状态: {subtask.status}, 阻塞: {subtask.blocked_by}")
            
            # 当前主任务的可执行子任务
            executable_subtasks = []
            
            # 第二步：检查每个子任务是否可执行
            for subtask_id, subtask_obj in subtask_obj_map.items():
                # 子任务必须状态为todo或in_progress且没有被阻塞
                if (subtask_obj.status == TaskStatus.TODO or subtask_obj.status == TaskStatus.IN_PROGRESS) and \
                   len(subtask_obj.blocked_by) == 0:
                    logger.info(f"  子任务 {subtask_id} 可执行 (状态: {subtask_obj.status}, 无阻塞)")
                    executable_subtasks.append(subtask_obj)
                elif (subtask_obj.status == TaskStatus.TODO or subtask_obj.status == TaskStatus.IN_PROGRESS):
                    logger.info(f"  子任务 {subtask_id} 不可执行 (状态: {subtask_obj.status}, 被阻塞: {subtask_obj.blocked_by})")
            
            # 构建子任务ID到依赖数量的映射 (用于排序)
            subtask_dependencies = {}
            for subtask in executable_subtasks:
                dep_count = len(subtask.dependencies)
                subtask_dependencies[subtask.id] = dep_count
            
            # 如果找到了可执行的子任务
            if executable_subtasks:
                has_executable_subtasks = True
                
                # 按状态、优先级、依赖数量和创建时间排序子任务
                sorted_executable_subtasks = sorted(
                    executable_subtasks,
                    key=lambda t: (
                        # 状态优先级：in_progress优先于todo
                        0 if t.status == TaskStatus.IN_PROGRESS else 1,
                        # 优先级从高到低
                        {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(t.priority, 4),
                        # 依赖任务的数量（越少越优先）
                        subtask_dependencies.get(t.id, 0),
                        # 创建时间（越早创建越优先）
                        t.created_at
                    )
                )
                
                # 将排序后的子任务添加到结果列表
                for st in sorted_executable_subtasks[:limit]:
                    logger.info(f"选中可执行子任务: {st.id} ({st.name}), 优先级: {st.priority}, 依赖数量: {subtask_dependencies.get(st.id, 0)}")
                    final_tasks.append(st)
        
        # 如果主任务没有可执行的子任务
        if not has_executable_subtasks:
            # 检查主任务是否有子任务且是否全部完成
            all_subtasks_done = True
            if subtasks and isinstance(subtasks, list) and len(subtasks) > 0:
                for subtask in subtasks:
                    if isinstance(subtask, Task) and subtask.status != TaskStatus.DONE:
                        all_subtasks_done = False
                        break
            
            # 如果没有子任务或所有子任务都完成，则主任务可执行
            if not subtasks or len(subtasks) == 0 or all_subtasks_done:
                logger.info(f"主任务 {top_parent_task.id} 可执行 (没有子任务或所有子任务已完成)")
                final_tasks.append(top_parent_task)
        
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
            
            # 获取当前任务对象
            current_task = self.get_task(current)
            if not current_task:
                continue
                
            # 添加当前任务的依赖到队列
            dependencies = current_task.dependencies
            queue.extend([dep for dep in dependencies if dep not in visited])
        
        return False
    
    def _unblock_dependents(self, task_id: str) -> None:
        """解除依赖于给定任务ID的所有任务的阻塞状态"""
        blocked_tasks = self.dependency_graph.get(task_id, set())
        if not blocked_tasks:
            return
        
        logger.info(f"任务 {task_id} 完成/状态变更，尝试解除对以下任务的阻塞: {blocked_tasks}")
        for blocked_id in blocked_tasks:
            blocked_task = self.get_task(blocked_id)
            if blocked_task:
                logger.info(f"  - 正在从任务 {blocked_id} 的 blocked_by 列表中移除 {task_id}")
                blocked_task.remove_blocked_by(task_id)
                logger.info(f"  - 任务 {blocked_id} 的 blocked_by 列表更新为: {blocked_task.blocked_by}")
            else:
                logger.warning(f"  - 未找到任务 {blocked_id}，无法解除阻塞")

    def mark_task_done(self, task_id: str) -> bool:
        """将任务标记为已完成"""
        task = self.get_task(task_id)
        if not task:
            return False
        
        original_status = task.status # 记录原始状态
        task.mark_as_done()
        
        # --- 调用新的解除阻塞方法 ---
        if original_status != TaskStatus.DONE: # 仅当状态确实改变为DONE时才解除阻塞
            self._unblock_dependents(task_id)
        
        # 保存到文件
        self._save_tasks_to_file()
        
        return True
    
    def count_tasks_by_status(self) -> Dict[str, int]:
        """统计各状态任务数量"""
        counts = {status.value: 0 for status in TaskStatus}
        
        # 统计主任务状态
        for task in self.tasks.values():
            counts[task.status] += 1
            
            # 统计子任务状态
            if hasattr(task, 'subtasks') and isinstance(task.subtasks, list):
                for subtask in task.subtasks:
                    if isinstance(subtask, Task):
                        counts[subtask.status] += 1
            
        return counts

    def clear_all_tasks(self) -> None:
        """清空所有任务和依赖关系"""
        self.tasks.clear()
        self.dependency_graph.clear()
        
        # 同时清空文件
        try:
            if os.path.exists(self.master_file_path):
                with open(self.master_file_path, 'w', encoding='utf-8') as f:
                    json.dump([], f)
            logger.info("所有任务和依赖关系已被清空，文件已重置")
        except Exception as e:
            logger.error(f"清空任务文件失败: {str(e)}")
