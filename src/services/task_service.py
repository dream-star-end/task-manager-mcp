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
                "tasks": [self.storage._task_to_dict(task) for task in tasks]
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
                "task": self.storage._task_to_dict(task)
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
        更新现有任务信息，包括依赖关系。
        
        Args:
            task_id: 任务ID
            **kwargs: 要更新的任务属性。如果提供了 'dependencies'，它将覆盖现有的依赖关系。
            
        Returns:
            Dict: 包含更新后任务信息的响应
        """
        logger.info(f"更新任务 {task_id}")
        
        try:
            # 检查是否为子任务(ID包含点号)
            if "." in task_id:
                parent_task_id = task_id.split(".")[0]
                parent_task = self.storage.get_task(parent_task_id)
                
                if parent_task and hasattr(parent_task, 'subtasks') and parent_task.subtasks:
                    subtask_found = False
                    updated_subtask_object = None # 用于存储找到并更新的Task对象
                    
                    for i, subtask in enumerate(parent_task.subtasks):
                        # --- 修复: 检查Task对象而不是字典 ---
                        if isinstance(subtask, Task) and subtask.id == task_id:
                            logger.info(f"找到子任务对象: {task_id}")
                            # --- 修复: 直接更新Task对象的属性 ---
                            update_data_for_subtask = {k: v for k, v in kwargs.items() if k != 'dependencies'}
                            for field, value in update_data_for_subtask.items():
                                if hasattr(subtask, field) and field != "id":
                                    # 特别处理枚举类型
                                    if field == "status" and isinstance(value, str):
                                        try: value = TaskStatus(value.lower())
                                        except ValueError: 
                                            logger.warning(f"更新子任务 {task_id} 时遇到无效状态值: {value}, 跳过更新状态")
                                            continue
                                    if field == "priority" and isinstance(value, str):
                                        try: value = TaskPriority(value.lower())
                                        except ValueError: 
                                            logger.warning(f"更新子任务 {task_id} 时遇到无效优先级值: {value}, 跳过更新优先级")
                                            continue
                                    setattr(subtask, field, value)
                            
                            subtask.updated_at = datetime.now()
                            if 'status' in update_data_for_subtask and subtask.status == TaskStatus.DONE:
                                subtask.completed_at = datetime.now()
                            
                            subtask_found = True
                            updated_subtask_object = subtask # 保存更新后的对象引用
                            break # 找到并更新后退出循环
                    
                    if not subtask_found:
                        logger.error(f"在父任务 {parent_task_id} 的子任务对象列表中未找到 ID 为 {task_id} 的任务")
                        return {
                            "success": False,
                            "error": f"在父任务 {parent_task_id} 的子任务列表中未找到任务 {task_id}", # 保持错误信息一致性
                            "error_code": "subtask_not_found"
                        }
                        
                    # --- 修复: 调用 storage.update_task 保存整个父任务 (因为子任务是父任务的一部分) ---
                    # TaskStorage.update_task 内部会处理 Task 对象列表
                    logger.info(f"准备调用 storage.update_task 更新父任务 {parent_task_id} 以保存子任务 {task_id} 的变更")
                    updated_parent = self.storage.update_task(parent_task_id, subtasks=parent_task.subtasks)
                    
                    if updated_parent:
                        logger.info(f"父任务 {parent_task_id} 更新成功，子任务 {task_id} 变更已保存")
                        
                        # --- 新增: 如果子任务状态变为DONE，则解除其依赖者的阻塞 ---
                        status_changed_to_done = False
                        if 'status' in update_data_for_subtask and updated_subtask_object.status == TaskStatus.DONE:
                            status_changed_to_done = True
                        
                        if status_changed_to_done:
                            logger.info(f"子任务 {task_id} 状态更新为 DONE，调用解除依赖者阻塞逻辑")
                            self.storage._unblock_dependents(task_id)
                        
                        # 同步父任务状态 (如果子任务状态改变)
                        status_changed = 'status' in update_data_for_subtask
                        if status_changed:
                            self._sync_parent_task_status(parent_task_id)
                            
                        return {
                            "success": True,
                            # --- 修复: 返回更新后的子任务对象的字典表示 ---
                            "task": self.storage._task_to_dict(updated_subtask_object),
                            "message": f"子任务 {task_id} 已更新"
                        }
                    else:
                        logger.error(f"调用 storage.update_task 更新父任务 {parent_task_id} 失败")
                        return {
                            "success": False,
                            "error": f"更新父任务 {parent_task_id} 失败",
                            "error_code": "parent_task_update_failed"
                        }

                else:
                    # 父任务不存在或没有子任务列表的情况
                    logger.error(f"查找父任务 {parent_task_id} 失败或该任务没有子任务列表")
                    return {
                        "success": False,
                        "error": f"父任务 {parent_task_id} 不存在或没有子任务列表",
                        "error_code": "parent_task_not_found"
                    }

            # 处理普通任务(非子任务)的更新
            # 检查任务是否存在
            task = self.storage.get_task(task_id)
            if not task:
                return {
                    "success": False,
                    "error": f"Task not found: {task_id}",
                    "error_code": "task_not_found"
                }
            
            # 备份原始依赖，以防新依赖验证失败需要回滚
            original_dependencies = list(task.dependencies)
            new_dependencies = None
            
            # 检查是否需要更新依赖
            if "dependencies" in kwargs:
                new_dependencies = kwargs.pop("dependencies") # 从kwargs中取出，单独处理
                if not isinstance(new_dependencies, list):
                     return {"success": False, "error": "Dependencies must be a list of task IDs.", "error_code": "invalid_dependencies_format"}
                
                # 验证新的依赖关系 (存在性、非自身、无循环)
                for dep_id in new_dependencies:
                    if not self.storage.get_task(dep_id):
                        return {"success": False, "error": f"Dependency task not found: {dep_id}", "error_code": "dependency_not_found"}
                    if dep_id == task_id:
                        return {"success": False, "error": "Task cannot depend on itself.", "error_code": "self_dependency"}
                    # 模拟添加，检查是否会产生循环
                    if self.storage._would_create_cycle(task_id, dep_id):
                        return {"success": False, "error": f"Adding dependency on {dep_id} would create a circular dependency.", "error_code": "circular_dependency"}
                
                # 验证通过，先移除所有旧依赖
                logger.info(f"移除任务 {task_id} 的旧依赖: {original_dependencies}")
                for old_dep_id in original_dependencies:
                    self.storage.remove_task_dependency(task_id, old_dep_id)
                
                # 添加新依赖
                logger.info(f"为任务 {task_id} 添加新依赖: {new_dependencies}")
                for new_dep_id in new_dependencies:
                    success, msg = self.storage.set_task_dependency(task_id, new_dep_id)
                    if not success:
                        # 如果添加新依赖失败，尝试恢复旧依赖 (尽力而为)
                        logger.error(f"添加新依赖 {new_dep_id} 失败: {msg}. 尝试恢复旧依赖...")
                        for old_dep_id in original_dependencies:
                             self.storage.set_task_dependency(task_id, old_dep_id) # 忽略恢复的错误
                        return {"success": False, "error": f"Failed to set new dependency {new_dep_id}: {msg}", "error_code": "set_dependency_failed"}

            task_was_updated_to_done = False # 标记状态是否变更为 DONE
            # 处理状态
            if "status" in kwargs:
                status = kwargs["status"]
                if isinstance(status, str):
                    try:
                        new_status_enum = TaskStatus(status.lower())
                        # 检查状态是否实际改变为 DONE
                        if task.status != TaskStatus.DONE and new_status_enum == TaskStatus.DONE:
                            task_was_updated_to_done = True 
                        kwargs["status"] = new_status_enum # 更新kwargs中的值为枚举
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
            
            # --- 新增: 如果任务状态变为DONE，则解除其依赖者的阻塞 ---
            if task_was_updated_to_done and updated_task:
                logger.info(f"任务 {task_id} 状态更新为 DONE，调用解除依赖者阻塞逻辑")
                self.storage._unblock_dependents(task_id)
                # 需要重新获取任务以反映解除阻塞后的 blocked_by 状态
                updated_task = self.storage.get_task(task_id)

            # 处理代码引用更新
            if "code_files" in kwargs and kwargs["code_files"]:
                code_files = kwargs["code_files"]
                # 确保code_files是列表
                if isinstance(code_files, str):
                    code_files = [file.strip() for file in code_files.split(",")]
                # 更新任务的代码引用
                updated_task = self.storage.update_task(task_id, code_references=code_files)
            
            if updated_task:
                # 如果更新了依赖，重新获取任务以确保 blocked_by 状态正确
                final_task = self.storage.get_task(task_id) if new_dependencies is not None else updated_task
                return {
                    "success": True,
                    "task": self.storage._task_to_dict(final_task),
                    "message": f"Task {task_id} updated successfully"
                }
            else:
                # 如果依赖更新成功但其他字段更新失败，可能需要回滚依赖？(暂时不处理)
                return {
                    "success": False,
                    "error": f"Failed to update task {task_id} other fields",
                    "error_code": "update_failed"
                }
                
        except Exception as e:
            logger.error(f"Error updating task {task_id}: {str(e)}", exc_info=True)
            # 如果依赖更新过程中出错，可能需要回滚 (暂时不处理)
            return {
                "success": False,
                "error": f"Internal error updating task: {str(e)}",
                "error_code": "internal_error"
            }
    
    def _sync_parent_task_status(self, parent_task_id: str) -> None:
        """
        根据子任务状态同步更新父任务状态
        
        规则:
        1. 如果所有子任务都完成，则父任务也完成
        2. 如果有任何子任务被阻塞，则父任务也被阻塞
        3. 如果有任何子任务进行中，则父任务也进行中
        
        Args:
            parent_task_id: 父任务ID
        """
        try:
            parent_task = self.storage.get_task(parent_task_id)
            if not parent_task or not hasattr(parent_task, 'subtasks') or not parent_task.subtasks:
                return
            
            # 收集所有子任务状态
            child_statuses = []
            for subtask in parent_task.subtasks:
                # --- 修复: 从 Task 对象获取状态 ---
                if isinstance(subtask, Task):
                    child_statuses.append(subtask.status)
                elif isinstance(subtask, dict) and 'status' in subtask: # 保留对旧格式字典的兼容性（以防万一）
                    child_statuses.append(subtask['status'])
            
            if not child_statuses:
                logger.warning(f"无法从父任务 {parent_task_id} 的子任务列表获取状态")
                return
            
            # 确定父任务的新状态
            new_parent_status = None
            
            # 规则1: 如果所有子任务都完成，则父任务也完成
            if all(s == 'done' for s in child_statuses):
                new_parent_status = TaskStatus.DONE
                logger.info(f"所有子任务已完成，将父任务 {parent_task_id} 状态更新为 'done'")
            
            # 规则2: 如果有任何子任务被阻塞，则父任务也被阻塞
            elif 'blocked' in child_statuses:
                new_parent_status = TaskStatus.BLOCKED
                logger.info(f"存在被阻塞的子任务，将父任务 {parent_task_id} 状态更新为 'blocked'")
            
            # 规则3: 如果有任何子任务进行中，则父任务也进行中
            elif 'in_progress' in child_statuses:
                new_parent_status = TaskStatus.IN_PROGRESS
                logger.info(f"存在进行中的子任务，将父任务 {parent_task_id} 状态更新为 'in_progress'")
            
            # 如果需要更新父任务状态
            if new_parent_status and parent_task.status != new_parent_status:
                self.storage.update_task(parent_task_id, status=new_parent_status)
                logger.info(f"父任务 {parent_task_id} 状态已更新为 '{new_parent_status}'")
        
        except Exception as e:
            logger.error(f"同步父任务状态时出错: {str(e)}", exc_info=True)
            # 不抛出异常，因为这是辅助功能
    
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
                "task": self.storage._task_to_dict(updated_task)
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
                "tasks": [self.storage._task_to_dict(task) for task in tasks]
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
                "task": self.storage._task_to_dict(next_task)
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
                "task": self.storage._task_to_dict(task)
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
            task_id: 要更新的任务ID (子任务使用 '父ID.子ID' 格式)。
            code_references: 新的代码引用路径列表。

        Returns:
            包含更新结果的响应字典。
        """
        logger.info(f"更新任务 {task_id} 的代码引用: {code_references}")

        try:
            # 检查是否为子任务
            if "." in task_id:
                parent_task_id = task_id.split(".")[0]
                parent_task = self.storage.get_task(parent_task_id)
                
                if parent_task and hasattr(parent_task, 'subtasks') and parent_task.subtasks:
                    subtask_found = False
                    updated_subtask_object = None
                    for subtask in parent_task.subtasks:
                        # --- 修复: 检查 Task 对象 ---
                        if isinstance(subtask, Task) and subtask.id == task_id:
                            # --- 修复: 更新 Task 对象属性 ---
                            subtask.code_references = code_references
                            subtask.updated_at = datetime.now()
                            subtask_found = True
                            updated_subtask_object = subtask
                            break
                    
                    if not subtask_found:
                        return {
                            "success": False,
                            "error": f"在父任务 {parent_task_id} 的子任务列表中未找到任务 {task_id}",
                            "error_code": "subtask_not_found"
                        }
                        
                    # --- 修复: 更新父任务以保存子任务变更 ---
                    updated_parent = self.storage.update_task(parent_task_id, subtasks=parent_task.subtasks)
                    if updated_parent:
                        # --- 修复: 返回更新后的子任务对象的字典表示 ---
                        return {
                            "success": True,
                            "message": f"Successfully updated code references for subtask {task_id}",
                            "task": self.storage._task_to_dict(updated_subtask_object) # 使用 _task_to_dict 转换
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"更新父任务 {parent_task_id} 失败",
                            "error_code": "parent_task_update_failed"
                        }
                else:
                    return {
                        "success": False,
                        "error": f"父任务 {parent_task_id} 不存在或没有子任务列表",
                        "error_code": "parent_task_not_found"
                    }
            else:
                # 处理普通任务
                task = self.storage.get_task(task_id)
                if not task:
                    logger.error(f"任务 {task_id} 未找到，无法更新代码引用")
                    return {
                        "success": False,
                        "error": f"Task not found: {task_id}",
                        "error_code": "task_not_found"
                    }

                # 直接更新任务对象的 code_references 字段
                updated_task = self.storage.update_task(task_id, code_references=code_references)
                if updated_task:
                    return {
                        "success": True,
                        "message": f"Successfully updated code references for task {task_id}",
                        "task": self.storage._task_to_dict(updated_task)
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
        
        parent_task_dict = self.storage._task_to_dict(parent_task)
        
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
            current_subtasks_list = []
            if hasattr(parent_task, 'subtasks') and isinstance(parent_task.subtasks, list):
                current_subtasks_list = parent_task.subtasks
            else:
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

            # 将新的子任务数据加入现有子任务后更新父任务
            # 直接使用字典操作，避免类型混用问题
            all_subtasks_data = []
            # 确保现有子任务是以字典形式
            for subtask in current_subtasks_list:
                if isinstance(subtask, dict):
                    all_subtasks_data.append(subtask)
                elif hasattr(subtask, '__dict__'):  # 如果是Task对象
                    all_subtasks_data.append(self.storage._task_to_dict(subtask))
                else:
                    logger.warning(f"跳过无效子任务数据类型: {type(subtask)}")
            
            # 添加新生成的子任务
            all_subtasks_data.extend(processed_subtasks_data)
            
            # 更新父任务
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
            updated_parent_task_dict = self.storage._task_to_dict(updated_parent_task) if updated_parent_task else parent_task_dict


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