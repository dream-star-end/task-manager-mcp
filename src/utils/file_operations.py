"""
文件操作工具函数

提供文件操作相关的通用功能，如保存JSON、清空目录等
"""

import logging
import os
import json
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

def save_task_to_json(task_dict: Dict[str, Any], tasks_dir: str) -> Optional[str]:
    """将任务保存到JSON文件
    
    Args:
        task_dict: 任务字典
        tasks_dir: 保存任务文件的目录路径
        
    Returns:
        Optional[str]: 保存成功返回文件路径，失败返回None
    """
    task_id = task_dict.get('id')
    if not task_id:
        logger.warning("无法保存任务：缺少任务ID")
        return None
    
    filename = f"task_{task_id}.json"
    file_path = os.path.join(tasks_dir, filename)
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(task_dict, f, ensure_ascii=False, indent=2)
        logger.debug(f"任务已保存到文件: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"保存任务到JSON文件失败: {str(e)}")
        return None

def save_tasks_to_json(tasks: List[Dict[str, Any]], tasks_dir: str, filename_prefix: str) -> Optional[str]:
    """将任务列表保存到JSON文件
    
    Args:
        tasks: 任务列表
        tasks_dir: 保存任务文件的目录路径
        filename_prefix: 文件名前缀
        
    Returns:
        Optional[str]: 保存成功返回文件路径，失败返回None
    """
    if not tasks:
        logger.warning("无法保存任务列表：任务列表为空")
        return None
    
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{timestamp}.json"
    file_path = os.path.join(tasks_dir, filename)
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        logger.debug(f"任务列表已保存到文件: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"保存任务列表到JSON文件失败: {str(e)}")
        return None

def clear_directory(directory_path: str) -> None:
    """清空指定目录中的所有文件
    
    Args:
        directory_path: 要清空的目录路径
    """
    try:
        if not os.path.exists(directory_path):
            logger.warning(f"目录不存在，无需清空: {directory_path}")
            return

        file_count = 0
        for filename in os.listdir(directory_path):
            file_path = os.path.join(directory_path, filename)
            # 只删除文件，不删除子目录
            if os.path.isfile(file_path):
                os.remove(file_path)
                file_count += 1
                logger.debug(f"已删除文件: {file_path}")
        
        logger.info(f"已清空目录 {directory_path}，共删除 {file_count} 个文件")
    except Exception as e:
        logger.error(f"清空目录失败 {directory_path}: {str(e)}") 