"""
任务工具函数

提供任务相关的通用功能，如生成任务ID等
"""

import logging
import time
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def generate_next_task_id(tasks: List[Dict[str, Any]]) -> str:
    """生成下一个顺延的任务ID
    
    Args:
        tasks: 所有现有任务的列表
        
    Returns:
        str: 生成的下一个任务ID
    """
    try:
        # 找出所有数字格式的顶级任务ID（如"1", "2", "3"等）
        numeric_ids = []
        for task in tasks:
            task_id = task.get('id', '')
            # 只考虑纯数字ID和以数字开头、包含点的ID（如"1.1"）
            if task_id.isdigit():
                numeric_ids.append(int(task_id))
            elif '.' in task_id and task_id.split('.')[0].isdigit():
                numeric_ids.append(int(task_id.split('.')[0]))
        
        # 如果没有数字ID，从1开始
        if not numeric_ids:
            return "1"
        
        # 否则返回最大ID + 1
        next_id = max(numeric_ids) + 1
        return str(next_id)
    except Exception as e:
        logger.error(f"生成下一个任务ID时出错: {str(e)}")
        # 发生错误时返回一个时间戳作为备选
        return f"task-{int(time.time())}"

def format_task_table(tasks: List[Dict[str, Any]], include_fields: List[str] = None) -> str:
    """将任务列表格式化为Markdown表格
    
    Args:
        tasks: 任务列表
        include_fields: 要包含在表格中的字段，默认为None表示使用标准字段
        
    Returns:
        str: 格式化的Markdown表格
    """
    if not tasks:
        return "任务列表为空"
    
    # 默认包含的字段
    default_fields = ["id", "name", "status", "priority", "assigned_to", "tags"]
    fields = include_fields or default_fields
    
    # 构建表头
    header_map = {
        "id": "ID", 
        "name": "名称", 
        "status": "状态", 
        "priority": "优先级", 
        "assigned_to": "负责人",
        "estimated_hours": "估计工时",
        "actual_hours": "实际工时",
        "tags": "标签",
        "dependencies": "依赖任务",
        "blocked_by": "被阻塞于"
    }
    
    # 创建表头
    header = "| " + " | ".join([header_map.get(field, field) for field in fields]) + " |\n"
    separator = "|" + "|".join(["-----" for _ in fields]) + "|\n"
    
    # 构建表格内容
    rows = []
    for task in tasks:
        row = []
        for field in fields:
            if field == "id":
                # ID字段截断显示
                row.append(task.get(field, "")[:8] + "..." if len(task.get(field, "")) > 8 else task.get(field, ""))
            elif field == "tags":
                # 标签格式化
                tags = task.get(field, [])
                row.append(", ".join(tags) if tags else "-")
            elif field == "dependencies" or field == "blocked_by":
                # 依赖关系格式化
                deps = task.get(field, [])
                row.append(", ".join(deps) if deps else "-")
            elif field == "estimated_hours" or field == "actual_hours":
                # 工时格式化
                hours = task.get(field)
                row.append(f"{hours} 小时" if hours else "-")
            else:
                # 其他字段
                row.append(str(task.get(field, "-") or "-"))
        
        rows.append("| " + " | ".join(row) + " |")
    
    return header + separator + "\n".join(rows) 