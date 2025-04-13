"""
日志配置工具函数

提供日志配置相关的通用功能
"""

import logging
import os
from logging import FileHandler

def setup_logging(log_file_path: str, log_level: int = logging.INFO) -> logging.Logger:
    """设置日志配置
    
    Args:
        log_file_path: 日志文件路径
        log_level: 日志级别，默认为INFO
        
    Returns:
        logging.Logger: 配置好的logger实例
    """
    # 配置基本日志
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 添加文件日志处理器
    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 确保日志目录存在
    log_dir = os.path.dirname(log_file_path)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # 创建文件处理器
    file_handler = FileHandler(log_file_path, encoding='utf-8')
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(log_level)
    
    # 添加到根日志记录器
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    
    # 返回名为__main__的logger
    logger = logging.getLogger('__main__')
    logger.info(f"日志配置已设置，日志文件: {log_file_path}")
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """获取指定名称的logger
    
    Args:
        name: logger名称
        
    Returns:
        logging.Logger: 指定名称的logger实例
    """
    return logging.getLogger(name) 