"""
任务服务

提供任务的业务逻辑实现
"""

from typing import Dict, List, Optional, Any, Tuple
import logging
import sys
import os
import traceback
from datetime import datetime

# 将项目根目录添加到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# 兼容从不同目录运行的导入路径
try:
    from ..models.task import Task, TaskStatus, TaskPriority
    from ..storage.task_storage import TaskStorage
    from ..services.prd_parser import PrdParser
    # Import the LLM interface for type hinting
    from ..llm.base import LLMInterface 
except (ImportError, ValueError):
    from src.models.task import Task, TaskStatus, TaskPriority
    from src.storage.task_storage import TaskStorage
    from src.services.prd_parser import PrdParser
    from src.llm.base import LLMInterface

# 配置日志
logger = logging.getLogger(__name__)


class TaskService:
    """任务服务类，提供任务管理的业务逻辑"""
    
    def __init__(self, storage: Optional[TaskStorage] = None, llm_client: Optional[LLMInterface] = None):
        """
        初始化任务服务
        
        Args:
            storage: 任务存储实例，如果为None则创建新实例。
            llm_client: 可选的 LLM 客户端实例，用于 PRD 解析。
        """
        self.storage = storage or TaskStorage()
        self.prd_parser = PrdParser(storage=self.storage, llm_client=llm_client)
        logger.info(f"TaskService initialized. PrdParser configured {'with' if llm_client else 'without'} LLM support.")
    
    def clear_all_tasks(self) -> None:
        """清空所有任务"""
        self.storage.clear_all_tasks()
    
    async def decompose_prd(self, prd_content: str) -> Dict[str, Any]:
        """
        解析PRD文档，自动拆解为任务列表
        
        Args:
            prd_content: PRD文档内容或文件路径
            
        Returns:
            Dict: 包含提取任务信息的响应
        """
        logger.info(f"解析PRD文档: {prd_content[:50]}...")
        
        # 处理文件路径
        if prd_content.startswith("file://"):
            file_path = prd_content[7:]
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    prd_content = f.read()
            except Exception as e:
                logger.error(f"读取PRD文件失败: {str(e)}")
                return {
                    "success": False,
                    "error": f"Failed to read PRD file: {str(e)}",
                    "error_code": "file_read_error"
                }
        
        try:
            # 解析PRD，现在返回 (任务列表, LLM错误信息或None)
            tasks, llm_error = await self.prd_parser.parse(prd_content)
            
            # 构造成功响应
            response_data = {
                "success": True,
                "message": f"已从PRD中提取{len(tasks)}个任务",
                "tasks": [self._task_to_dict(task) for task in tasks]
            }
            
            # 如果存在LLM解析错误，将其添加到响应中
            if llm_error:
                response_data["llm_parsing_warning"] = f"LLM parsing failed, fell back to basic parsing. Error: {llm_error}"
                
            return response_data
            
        except Exception as e:
            # 记录更详细的错误信息，包括异常类型和堆栈跟踪
            error_details = traceback.format_exc()
            logger.error(
                f"在 TaskService.decompose_prd 中处理任务时发生异常: {type(e).__name__}: {str(e)}\n" \
                f"Traceback:\n{error_details}"
            )
            # 修改返回的字典，包含详细错误信息
            return {
                "success": False,
                "error": f"Failed to decompose PRD: {type(e).__name__}: {str(e)}",
                "error_code": "decompose_prd_error",
                "error_details": error_details
            }
    
    def add_task(self, name: str, description: str = "", **kwargs) -> Dict[str, Any]:
        """
        创建新任务
        
        Args:
            name: 任务名称
            description: 任务描述
            **kwargs: 其他任务属性
            
        Returns:
            Dict: 包含新创建任务信息的响应
        """
        logger.info(f"创建新任务: {name}")
        
        try:
            # 处理优先级
            priority = kwargs.get("priority", TaskPriority.MEDIUM)
            if isinstance(priority, str):
                try:
                    priority = TaskPriority(priority.lower())
                except ValueError:
                    return {
                        "success": False,
                        "error": f"Invalid priority: {priority}",
                        "error_code": "invalid_priority",
                        "details": {"valid_values": [p.value for p in TaskPriority]}
                    }
            
            # 处理依赖
            dependencies = kwargs.get("dependencies", [])
            
            # 创建任务
            task = self.storage.create_task(
                name=name,
                description=description,
                priority=priority,
                tags=kwargs.get("tags", []),
                assigned_to=kwargs.get("assigned_to"),
                estimated_hours=kwargs.get("estimated_hours"),
                dependencies=dependencies
            )
            
            return {
                "success": True,
                "message": "Task created successfully",
                "task": self._task_to_dict(task)
            }
        except Exception as e:
            logger.error(f"创建任务失败: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to add task: {str(e)}",
                "error_code": "add_task_error"
            }
    
    def update_task(self, task_id: str, **kwargs) -> Dict[str, Any]:
        """
        更新现有任务信息
        
        Args:
            task_id: 任务ID
            **kwargs: 要更新的任务属性
            
        Returns:
            Dict: 包含更新后任务信息的响应
        """
        logger.info(f"更新任务 {task_id}")
        
        try:
            # 检查任务是否存在
            task = self.storage.get_task(task_id)
            if not task:
                return {
                    "success": False,
                    "error": f"Task not found: {task_id}",
                    "error_code": "task_not_found"
                }
            
            # 处理状态
            if "status" in kwargs:
                status = kwargs["status"]
                if isinstance(status, str):
                    try:
                        kwargs["status"] = TaskStatus(status.lower())
                    except ValueError:
                        return {
                            "success": False,
                            "error": f"Invalid status: {status}",
                            "error_code": "invalid_status",
                            "details": {"valid_values": [s.value for s in TaskStatus]}
                        }
            
            # 处理优先级
            if "priority" in kwargs:
                priority = kwargs["priority"]
                if isinstance(priority, str):
                    try:
                        kwargs["priority"] = TaskPriority(priority.lower())
                    except ValueError:
                        return {
                            "success": False,
                            "error": f"Invalid priority: {priority}",
                            "error_code": "invalid_priority",
                            "details": {"valid_values": [p.value for p in TaskPriority]}
                        }
            
            # 更新任务
            updated_task = self.storage.update_task(task_id, **kwargs)
            
            return {
                "success": True,
                "message": "Task updated successfully",
                "task": self._task_to_dict(updated_task)
            }
        except Exception as e:
            logger.error(f"更新任务失败: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to update task: {str(e)}",
                "error_code": "update_task_error"
            }
    
    def set_task_dependency(self, task_id: str, depends_on: List[str]) -> Dict[str, Any]:
        """
        设置任务依赖关系
        
        Args:
            task_id: 任务ID
            depends_on: 依赖的任务ID列表
            
        Returns:
            Dict: 操作结果的响应
        """
        logger.info(f"设置任务 {task_id} 的依赖关系")
        
        try:
            # 检查任务是否存在
            task = self.storage.get_task(task_id)
            if not task:
                return {
                    "success": False,
                    "error": f"Task not found: {task_id}",
                    "error_code": "task_not_found"
                }
            
            # 设置依赖关系
            results = []
            for dep_id in depends_on:
                success, message = self.storage.set_task_dependency(task_id, dep_id)
                results.append({
                    "depends_on_id": dep_id,
                    "success": success,
                    "message": message or "Dependency set successfully"
                })
            
            # 获取更新后的任务
            updated_task = self.storage.get_task(task_id)
            
            return {
                "success": True,
                "message": "Dependencies updated",
                "results": results,
                "task": self._task_to_dict(updated_task)
            }
        except Exception as e:
            logger.error(f"设置任务依赖关系失败: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to set task dependency: {str(e)}",
                "error_code": "set_dependency_error"
            }
    
    def get_task_list(self,
                      status: Optional[str] = None,
                      priority: Optional[str] = None,
                      tag: Optional[str] = None,
                      assigned_to: Optional[str] = None,
                      parent_task: Optional[str] = None,
                      page: int = 1,
                      page_size: int = 100) -> Dict[str, Any]:
        """
        获取任务列表
        
        Args:
            status: 按状态筛选
            priority: 按优先级筛选
            tag: 按标签筛选
            assigned_to: 按负责人筛选
            parent_task: 按父任务筛选
            page: 页码
            page_size: 每页数量
            
        Returns:
            Dict: 包含任务列表的响应
        """
        logger.info(f"获取任务列表 (状态: {status}, 优先级: {priority}, 标签: {tag}, 负责人: {assigned_to}, 页码: {page})")
        
        try:
            # 处理状态筛选
            task_status = None
            if status:
                try:
                    task_status = TaskStatus(status.lower())
                except ValueError:
                    return {
                        "success": False,
                        "error": f"Invalid status: {status}",
                        "error_code": "invalid_status",
                        "details": {"valid_values": [s.value for s in TaskStatus]}
                    }
            
            # 处理优先级筛选
            task_priority = None
            if priority:
                try:
                    task_priority = TaskPriority(priority.lower())
                except ValueError:
                    return {
                        "success": False,
                        "error": f"Invalid priority: {priority}",
                        "error_code": "invalid_priority",
                        "details": {"valid_values": [p.value for p in TaskPriority]}
                    }
            
            # 获取任务列表
            tasks, total = self.storage.list_tasks(
                status=task_status,
                priority=task_priority,
                tag=tag,
                assigned_to=assigned_to,
                page=page,
                page_size=page_size
            )
            
            return {
                "success": True,
                "total": total,
                "page": page,
                "page_size": page_size,
                "tasks": [self._task_to_dict(task) for task in tasks]
            }
        except Exception as e:
            logger.error(f"获取任务列表失败: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to get task list: {str(e)}",
                "error_code": "get_task_list_error"
            }
    
    def get_next_executable_task(self, limit: int = 5) -> Dict[str, Any]:
        """
        获取下一个可执行任务
        
        Args:
            limit: 查询时的任务数量限制，用于选择最优的一个任务
            
        Returns:
            Dict: 包含单个可执行任务的响应
        """
        logger.info("获取下一个可执行任务")
        
        try:
            executable_tasks = self.storage.get_next_executable_tasks(limit=limit)
            
            if not executable_tasks:
                # 没有可执行任务
                return {
                    "success": True,
                    "found": False,
                    "message": "没有找到可执行的任务"
                }
            
            # 只返回第一个任务（已经按优先级等排序）
            next_task = executable_tasks[0]
            
            return {
                "success": True,
                "found": True,
                "task": self._task_to_dict(next_task)
            }
        except Exception as e:
            logger.error(f"获取可执行任务失败: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to get next executable tasks: {str(e)}",
                "error_code": "get_executable_tasks_error"
            }
    
    def mark_task_done(self, task_id: str) -> Dict[str, Any]:
        """
        将任务标记为已完成
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict: 操作结果的响应
        """
        logger.info(f"将任务 {task_id} 标记为已完成")
        
        try:
            success = self.storage.mark_task_done(task_id)
            
            if not success:
                return {
                    "success": False,
                    "error": f"Failed to mark task as done. Task {task_id} not found.",
                    "error_code": "mark_task_done_error"
                }
            
            # 获取更新后的任务
            task = self.storage.get_task(task_id)
            
            return {
                "success": True,
                "message": f"Task {task_id} has been marked as done",
                "task": self._task_to_dict(task)
            }
        except Exception as e:
            logger.error(f"标记任务完成失败: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to mark task as done: {str(e)}",
                "error_code": "mark_task_done_error"
            }
    
    def get_tasks_by_status(self) -> Dict[str, Any]:
        """
        获取各状态的任务统计
        
        Returns:
            Dict: 包含任务统计信息的响应
        """
        logger.info("获取任务状态统计")
        
        try:
            counts = self.storage.count_tasks_by_status()
            
            return {
                "success": True,
                "counts": counts
            }
        except Exception as e:
            logger.error(f"获取任务统计失败: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to get task statistics: {str(e)}",
                "error_code": "get_task_stats_error"
            }
    
    def update_task_code_references(self, task_id: str, code_references: List[str]) -> Dict[str, Any]:
        """
        更新任务的代码引用列表。

        Args:
            task_id: 要更新的任务ID。
            code_references: 新的代码引用路径列表。

        Returns:
            包含更新结果的响应字典。
        """
        logger.info(f"更新任务 {task_id} 的代码引用: {code_references}")
        task = self.storage.get_task(task_id)
        if not task:
            logger.error(f"任务 {task_id} 未找到，无法更新代码引用")
            return {
                "success": False,
                "error": f"Task not found: {task_id}",
                "error_code": "task_not_found"
            }

        try:
            # 直接更新任务对象的 code_references 字段
            updated_task = self.storage.update_task(task_id, code_references=code_references)
            if updated_task:
                return {
                    "success": True,
                    "message": f"Successfully updated code references for task {task_id}",
                    "task": self._task_to_dict(updated_task)
                }
            else:
                # 更新失败通常意味着任务不存在，虽然前面检查过，但以防万一
                logger.error(f"更新任务 {task_id} 的代码引用失败（任务可能已被删除）")
                return {
                    "success": False,
                    "error": f"Failed to update task {task_id}, it might have been deleted.",
                    "error_code": "update_failed_not_found"
                }
        except Exception as e:
            logger.error(f"更新任务 {task_id} 代码引用时出错: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error updating code references for task {task_id}: {e}",
                "error_code": "update_code_reference_error"
            }
    
    def _task_to_dict(self, task: Task) -> Dict[str, Any]:
        """将Task对象转换为字典"""
        if not task:
            return {}
            
        # 从任务ID中提取父任务ID，如果有的话
        parent_task_id = None
        if "." in task.id:
            parent_task_id = task.id.rsplit(".", 1)[0]
            
        return {
            "id": task.id,
            "name": task.name,
            "description": task.description,
            "status": task.status,
            "priority": task.priority,
            "dependencies": list(task.dependencies),
            "blocked_by": list(task.blocked_by),
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "tags": task.tags,
            "assigned_to": task.assigned_to,
            "estimated_hours": task.estimated_hours,
            "actual_hours": task.actual_hours,
            "code_references": task.code_references,
            "parent_task_id": parent_task_id,
            "complexity": task.complexity,
            "subtasks": task.subtasks if hasattr(task, 'subtasks') else []
        }
    
    async def expand_task(
        self,
        task_id: str,
        num_subtasks: int = 5,
        project_context: str = "",
        main_tasks: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """展开任务，为指定任务生成子任务列表
        
        Args:
            task_id: 要展开的任务ID
            num_subtasks: 希望生成的子任务数量
            project_context: 项目背景上下文信息
            main_tasks: 所有主任务的列表
            
        Returns:
            包含父任务和子任务列表的字典
        """
        if not task_id:
            return {"success": False, "error": "Missing task ID."}
        
        # 获取父任务
        parent_task = self.storage.get_task(task_id)
        if not parent_task:
            return {"success": False, "error": f"Task not found: {task_id}"}
        
        # 如果没有提供LLM客户端，返回错误
        if not self.prd_parser.llm_client:
            return {"success": False, "error": "LLM client not available. Cannot generate subtasks."}
        
        parent_task_dict = self._task_to_dict(parent_task)
        
        try:
            # 调用LLM客户端生成子任务数据
            subtasks_data_from_llm = await self.prd_parser.llm_client.generate_subtasks_for_task_async(
                parent_task_dict,
                num_subtasks=num_subtasks,
                project_context=project_context,
                main_tasks=main_tasks
            )

            processed_subtasks_data = []
            # 获取父任务当前的 subtasks 列表，用于生成 ID 和合并
            # **警告**: 这假设 parent_task.subtasks 是 List[Dict] 或 None/List[]
            current_subtasks_list = []
            if isinstance(parent_task.subtasks, list):
                current_subtasks_list = parent_task.subtasks
            elif parent_task.subtasks:
                 logger.warning(f"Parent task {task_id} subtasks field is not a list or None. Initializing as empty list.")


            for index, subtask_data in enumerate(subtasks_data_from_llm):
                # 确保有 ID，如果LLM没提供，生成一个基于父ID的
                if "id" not in subtask_data or not subtask_data["id"]:
                    # 基于当前父任务已知子任务数量生成ID
                    new_id_suffix = len(current_subtasks_list) + index + 1
                    subtask_data["id"] = f"{task_id}.{new_id_suffix}"

                # 添加默认字段值
                subtask_data["status"] = subtask_data.get("status", "todo") # 使用 LLM status 或默认
                subtask_data["parent_task_id"] = task_id # 显式设置父 ID

                # 确保依赖包含父任务ID
                dependencies = subtask_data.get("dependencies", [])
                subtask_data["dependencies"] = dependencies

                # 添加其他可能缺失的默认值，使其结构与Task一致
                subtask_data.setdefault("name", f"Subtask {subtask_data['id']}")
                subtask_data.setdefault("description", "")
                subtask_data.setdefault("priority", "medium")
                subtask_data.setdefault("tags", [])
                subtask_data.setdefault("assigned_to", None)
                subtask_data.setdefault("estimated_hours", None)
                subtask_data.setdefault("actual_hours", None)
                subtask_data.setdefault("code_references", [])
                subtask_data.setdefault("complexity", "medium")
                # 添加时间戳
                now_iso = datetime.now().isoformat()
                subtask_data["created_at"] = now_iso
                subtask_data["updated_at"] = now_iso
                subtask_data["completed_at"] = None
                # 假设新子任务的 blocked_by 和 subtasks 为空
                subtask_data["blocked_by"] = []
                subtask_data["subtasks"] = [] # 子任务本身也可以有子任务，初始化为空

                processed_subtasks_data.append(subtask_data)

            # 更新父任务，将新的子任务数据列表合并到现有列表后存入 subtasks 字段
            # **警告**: 这假设 TaskStorage.update_task 和 Task model 支持 subtasks: List[Dict]
            all_subtasks_data = current_subtasks_list + processed_subtasks_data
            update_result = self.storage.update_task(task_id, subtasks=all_subtasks_data)

            if not update_result:
                 logger.error(f"Failed to update parent task {task_id} with new subtasks data.")
                 return {
                     "success": False,
                     "error": f"Failed to update parent task {task_id} with subtasks.",
                     "parent_task": parent_task_dict, # 返回原始父任务信息
                     "subtasks": []
                 }

            # 获取更新后的父任务以确认更改
            updated_parent_task = self.storage.get_task(task_id)
            updated_parent_task_dict = self._task_to_dict(updated_parent_task) if updated_parent_task else parent_task_dict


            # 返回结果
            return {
                "success": True,
                "parent_task": updated_parent_task_dict, # 返回更新后的父任务信息
                "subtasks": processed_subtasks_data # 返回本次新生成的子任务数据列表
            }

        except Exception as e:
            logger.error(f"Error generating subtasks: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to generate subtasks: {str(e)}",
                "parent_task": parent_task_dict # 返回原始父任务信息
            } 