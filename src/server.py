"""
任务管理MCP服务入口

提供与MCP协议兼容的任务管理服务接口
"""

import logging
import os
import sys
import json
from mcp.server.fastmcp import FastMCP
import mcp.types as types

# 将项目根目录添加到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(current_dir))  # 添加上级目录

# 从相对路径导入
from services.task_service import TaskService
from config import get_llm_client
# 导入新的工具函数
from utils.logging_config import setup_logging
from utils.file_operations import save_task_to_json, save_tasks_to_json, clear_directory
from utils.task_utils import generate_next_task_id, format_task_table

# 全局变量，用于保存项目的PRD内容
PROJECT_PRD_CONTENT = ""

# 获取项目根目录 (server.py 的上上级目录)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 获取用于保存文件的目录路径（从环境变量获取，若未设置则使用项目根目录下的output文件夹）
DEFAULT_OUTPUT_DIR = os.path.join(project_root, 'output')  
OUTPUT_DIR = os.environ.get('MCP_OUTPUT_DIR', DEFAULT_OUTPUT_DIR)
LOGS_DIR = os.environ.get('MCP_LOGS_DIR', os.path.join(OUTPUT_DIR, 'logs'))
TASKS_DIR = os.environ.get('MCP_TASKS_DIR', os.path.join(OUTPUT_DIR, 'tasks'))
MD_DIR = os.environ.get('MCP_MD_DIR', os.path.join(OUTPUT_DIR, 'md'))

# 创建必要的目录结构
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(TASKS_DIR, exist_ok=True)
os.makedirs(MD_DIR, exist_ok=True)

# 修改日志文件路径
log_file_path = os.path.join(LOGS_DIR, 'server.log')
# 设置日志配置
logger = setup_logging(log_file_path, logging.INFO)

# ----> Initialize LLM Client using the factory <----
logger.info("Initializing LLM client based on environment configuration...")
llm_client = get_llm_client() # Returns LLMInterface instance or None

# 创建MCP实例 - 使用标准变量名 'mcp' 而不是 'mcp_app'
mcp = FastMCP("task-manager-mcp")

# ----> 创建任务服务实例，并注入 LLM 客户端 <----
logger.info("Initializing TaskService...")
task_service = TaskService(llm_client=llm_client)
logger.info(f"TaskService initialized successfully.")

# 以下是从server.py中移除的工具函数，它们已经被移到了utils目录中的相应模块

@mcp.tool("decompose_prd")
async def decompose_prd(prd_content: str) -> list[types.TextContent]:
    """解析PRD文档，自动拆解为主任务列表
    
    Args:
        prd_content: PRD文档内容或文件路径，支持直接文本或以file://开头的文件路径（使用file://格式时必须提供绝对路径）
        
    Returns:
        List: 包含提取的主任务列表的格式化响应
    """
    global PROJECT_PRD_CONTENT
    
    logger.info(f"清空现有任务并解析PRD文档为主任务: {prd_content[:50]}...")
    
    # 保存PRD内容到全局变量
    PROJECT_PRD_CONTENT = prd_content
    logger.info("已保存PRD内容到全局变量，供后续任务展开使用")
    
    # 先清空所有任务和相关文件
    try:
        # 清空任务存储
        task_service.clear_all_tasks()
        logger.info("旧任务已成功清空")
        
        # 清空任务JSON文件和Markdown文件
        clear_directory(TASKS_DIR)
        clear_directory(MD_DIR)
        logger.info("所有任务相关文件已清空")
    except Exception as clear_e:
        logger.error(f"清空任务或文件失败: {clear_e}")
        # 即使清空失败，也继续尝试解析，但要记录错误
        pass
    
    try:
        result = await task_service.decompose_prd(prd_content)
        
        if result["success"] and result["tasks"]:
            # 只保留主任务（无 . 的任务ID）
            main_tasks = [task for task in result["tasks"] if "." not in task["id"]]
            
            # 为每个主任务添加空的subtasks字段
            for task in main_tasks:
                if "subtasks" not in task:
                    task["subtasks"] = []
            
            result["tasks"] = main_tasks
            result["message"] = f"已从PRD中提取{len(main_tasks)}个主任务"
            
            tasks = main_tasks
            task_count = len(tasks)
            
            # 计算任务状态和优先级统计
            status_stats = {}
            priority_stats = {}
            tag_stats = {}
            
            for task in tasks:
                # 状态统计
                status = task["status"]
                status_stats[status] = status_stats.get(status, 0) + 1
                
                # 优先级统计
                priority = task["priority"]
                priority_stats[priority] = priority_stats.get(priority, 0) + 1
                
                # 标签统计
                for tag in task["tags"]:
                    tag_stats[tag] = tag_stats.get(tag, 0) + 1
            
            # 构建任务列表表格
            table = format_task_table(tasks, ["id", "name", "status", "priority", "estimated_hours", "tags"])
            
            # 构建优先级统计表格
            priority_table = "| 优先级 | 数量 | 百分比 |\n"
            priority_table += "|--------|------|--------|\n"
            
            for priority in ["critical", "high", "medium", "low"]:
                count = priority_stats.get(priority, 0)
                percentage = (count / task_count) * 100 if task_count > 0 else 0
                priority_table += f"| {priority} | {count} | {percentage:.1f}% |\n"
            
            # 构建标签统计
            tag_list = [f"**{tag}** ({count})" for tag, count in sorted(tag_stats.items(), key=lambda x: x[1], reverse=True)]
            tag_summary = ", ".join(tag_list) if tag_list else "无标签"
            
            # 检查是否有 LLM 解析警告
            llm_warning = ""
            if "llm_parsing_warning" in result:
                llm_warning = f"\n\n**警告: 使用大模型解析PRD失败，已回退到基本标题解析。**\n错误详情: `{result['llm_parsing_warning']}`\n"
            
            # 创建Markdown任务列表
            md_content = "# PRD主任务列表\n\n"
            md_content += f"## 摘要\n已从PRD中提取 **{task_count}** 个主任务。\n\n"
            
            if llm_warning:
                md_content += f"## 警告\n{llm_warning}\n\n"
            
            md_content += "## 优先级分布\n"
            md_content += priority_table + "\n\n"
            
            md_content += f"## 标签统计\n{tag_summary}\n\n"
            
            md_content += "## 任务列表\n"
            
            for task in tasks:
                md_content += f"### {task['name']}\n"
                md_content += f"- **ID**: {task['id']}\n"
                md_content += f"- **优先级**: {task['priority']}\n"
                md_content += f"- **状态**: {task['status']}\n"
                if task.get("parent_task_id"):
                    md_content += f"- **父任务**: {task['parent_task_id']}\n"
                if task["estimated_hours"]:
                    md_content += f"- **估计工时**: {task['estimated_hours']} 小时\n"
                if task["tags"]:
                    md_content += f"- **标签**: {', '.join(task['tags'])}\n"
                md_content += f"- **描述**: {task['description']}\n\n"
            
            # 同时为每个任务单独创建JSON文件
            for task in tasks:
                save_task_to_json(task, TASKS_DIR)
            
            # 保存任务到JSON文件
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            json_filename = f"prd_tasks_{timestamp}.json"
            json_file_path = os.path.join(TASKS_DIR, json_filename)
            try:
                with open(json_file_path, "w", encoding="utf-8") as f:
                    json.dump(result["tasks"], f, ensure_ascii=False, indent=2)
                logger.info(f"任务列表已保存到JSON文件: {json_file_path}")
            except Exception as json_e:
                logger.error(f"保存JSON文件失败: {str(json_e)}")
            
            # 修改保存Markdown文件的路径
            md_filename = f"prd_main_tasks_{timestamp}.md"
            md_file_path = os.path.join(MD_DIR, md_filename)
            
            try:
                with open(md_file_path, "w", encoding="utf-8") as f:
                    f.write(md_content)
                logger.info(f"主任务列表已写入文件: {md_file_path}")
            except Exception as file_e:
                logger.error(f"写入Markdown文件失败: {str(file_e)}")
            
            # 最终输出
            formatted_output = f"""## PRD解析结果 - 仅主任务
{llm_warning}
### 摘要
已从PRD中提取 **{task_count}** 个主任务。
- 主任务列表已保存到Markdown文件: **{md_file_path}**
- 任务数据已保存到JSON文件: **{json_file_path}**

### 优先级分布
{priority_table}

### 标签统计
{tag_summary}

### 任务列表
{table}

### 详细JSON数据
```json
{json.dumps(result, ensure_ascii=False, indent=2)}
```
"""
            
            return [
                types.TextContent(
                    type="text",
                    text=formatted_output
                )
            ]
        
        # 如果没有成功提取任务或处理失败，返回原始JSON或添加提示
        if not result["success"] and result.get("tasks"):
            # 任务已创建但后续处理失败
            error_message = f"""## PRD解析部分失败

**注意**: 任务可能已成功创建，但后续处理步骤遇到错误。请检查任务列表。

**错误详情**:
```json
{json.dumps(result, ensure_ascii=False, indent=2)}
```
"""
            return [
                types.TextContent(
                    type="text",
                    text=error_message
                )
            ]
        else:
            # 其他失败情况，直接返回原始错误
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(result, ensure_ascii=False, indent=2)
                )
            ]
    except Exception as e:
        logger.error(f"PRD解析失败: {str(e)}", exc_info=True)  # 添加exc_info=True获取完整堆栈
        
        # 获取详细的异常信息
        import traceback
        error_traceback = traceback.format_exc()
        
        error_result = {
            "success": False,
            "error": f"PRD解析失败: {str(e)}",
            "error_code": "prd_parse_error",
            "error_details": error_traceback  # 添加完整的异常堆栈信息
        }
        
        return [
            types.TextContent(
                type="text",
                text=json.dumps(error_result, ensure_ascii=False, indent=2)
            )
        ]


@mcp.tool("add_task")
async def add_task(
    name: str,
    description: str = "",
    id: str = "",
    priority: str = "medium",
    tags: str = "",
    assigned_to: str = "",
    estimated_hours: str = "",
    dependencies: str = ""
) -> list[types.TextContent]:
    """创建新任务
    
    Args:
        name: 任务名称
        description: 任务详细描述
        id: 任务ID（可选，如未提供则自动生成）
        priority: 任务优先级，可选值为：low, medium, high, critical
        tags: 任务标签，多个标签以逗号分隔
        assigned_to: 任务分配给谁
        estimated_hours: 预估完成时间（小时）
        dependencies: 依赖的任务ID，多个依赖以逗号分隔
        
    Returns:
        List: 包含新创建任务信息的JSON响应
    """
    logger.info(f"创建新任务: {name}")
    
    # 处理标签
    task_tags = [tag.strip() for tag in tags.split(",")] if tags else []
    
    # 处理依赖
    task_dependencies = [dep.strip() for dep in dependencies.split(",")] if dependencies else []
    
    # 如果没有提供ID，则生成一个顺延的ID
    task_id = id.strip() if id.strip() else generate_next_task_id()
    logger.info(f"使用任务ID: {task_id}")
    
    try:
        result = task_service.add_task(
            id=task_id,  # 使用提供的ID或生成的顺延ID
            name=name,
            description=description,
            priority=priority,
            tags=task_tags,
            assigned_to=assigned_to or None,
            estimated_hours=float(estimated_hours) if estimated_hours else None,
            dependencies=task_dependencies
        )
        
        # 如果创建成功，保存任务到JSON文件
        if result.get("success") and result.get("task"):
            task_json_path = save_task_to_json(result["task"])
            if task_json_path:
                result["task_json_path"] = task_json_path
        
        return [
            types.TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False)
            )
        ]
    except Exception as e:
        error_result = {
            "success": False,
            "error": f"创建任务失败: {str(e)}",
            "error_code": "add_task_error"
        }
        logger.error(f"创建任务失败: {str(e)}", exc_info=True)
        return [
            types.TextContent(
                type="text",
                text=json.dumps(error_result, ensure_ascii=False)
            )
        ]


@mcp.tool("update_task")
async def update_task(
    task_id: str,
    name: str = "",
    description: str = "",
    status: str = "",
    priority: str = "",
    tags: str = "",
    assigned_to: str = "",
    estimated_hours: str = "",
    actual_hours: str = "",
    dependencies: str = ""
) -> list[types.TextContent]:
    """更新现有任务信息，包括依赖关系
    
    Args:
        task_id: 要更新的任务ID
        name: 新的任务名称
        description: 新的任务描述
        status: 新的任务状态，可选值为：todo, in_progress, done, blocked, cancelled
        priority: 新的任务优先级，可选值为：low, medium, high, critical
        tags: 新的任务标签，多个标签以逗号分隔
        assigned_to: 新的任务负责人
        estimated_hours: 新的预估工时
        actual_hours: 实际工时
        dependencies: 新的依赖任务ID列表（逗号分隔），将覆盖现有依赖。
                      如果为空字符串或不提供，则依赖关系不变。
        
    Returns:
        List: 包含更新后任务信息的格式化响应
    """
    logger.info(f"更新任务 {task_id}")
    
    # 处理标签
    tags_list = []
    if tags:
        tags_list = [tag.strip() for tag in tags.split(',')]
    
    # 处理依赖
    dependencies_list = None # 使用None表示不更新依赖关系
    if dependencies: # 只有当dependencies不为空字符串时才处理
        dependencies_list = [dep.strip() for dep in dependencies.split(',') if dep.strip()]
        logger.info(f"请求更新任务 {task_id} 的依赖为: {dependencies_list}")
    elif dependencies == "": # 如果传入空字符串，则表示清空依赖
        dependencies_list = []
        logger.info(f"请求清空任务 {task_id} 的依赖")

    # 处理估计工时和实际工时
    estimated_hours_float = None
    if estimated_hours:
        try:
            estimated_hours_float = float(estimated_hours)
        except ValueError:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": f"Invalid estimated_hours: {estimated_hours}. Must be a number.",
                        "error_code": "invalid_estimated_hours"
                    }, ensure_ascii=False)
                )
            ]
    
    actual_hours_float = None
    if actual_hours:
        try:
            actual_hours_float = float(actual_hours)
        except ValueError:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": f"Invalid actual_hours: {actual_hours}. Must be a number.",
                        "error_code": "invalid_actual_hours"
                    }, ensure_ascii=False)
                )
            ]
    
    # 提取代码引用
    code_files = None
    if description and "[CODE_FILES:" in description:
        # 从描述中提取代码引用
        start_idx = description.find("[CODE_FILES:") + len("[CODE_FILES:")
        end_idx = description.find("]", start_idx)
        if start_idx > 0 and end_idx > start_idx:
            code_refs_str = description[start_idx:end_idx].strip()
            code_files = [ref.strip() for ref in code_refs_str.split(',')]
    
    # 准备更新参数
    update_params = {}
    if name:
        update_params["name"] = name
    if description:
        update_params["description"] = description
    if status:
        update_params["status"] = status
    if priority:
        update_params["priority"] = priority
    if tags_list:
        update_params["tags"] = tags_list
    if assigned_to:
        update_params["assigned_to"] = assigned_to
    if estimated_hours_float is not None:
        update_params["estimated_hours"] = estimated_hours_float
    if actual_hours_float is not None:
        update_params["actual_hours"] = actual_hours_float
    if code_files:
        update_params["code_files"] = code_files
    # 只有当 dependencies_list 不是 None 时才将其加入更新参数
    if dependencies_list is not None:
        update_params["dependencies"] = dependencies_list
    
    # 执行更新
    result = task_service.update_task(task_id, **update_params)
    
    # 如果更新成功，更新任务的JSON文件
    if result.get("success") and result.get("task"):
        task_json_path = save_task_to_json(result["task"], TASKS_DIR)
        if task_json_path:
            result["task_json_path"] = task_json_path
    
    return [
        types.TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False)
        )
    ]


@mcp.tool("get_task")
async def get_task(task_id: str) -> list[types.TextContent]:
    """获取任务详情
    
    Args:
        task_id: 要获取的任务ID
        
    Returns:
        List: 包含任务详细信息的格式化响应
    """
    logger.info(f"获取任务 {task_id} 的详情")
    
    task = task_service.storage.get_task(task_id)
    if not task:
        result = {
            "success": False,
            "error": f"Task not found: {task_id}",
            "error_code": "task_not_found"
        }
        
        return [
            types.TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False)
            )
        ]
    else:
        task_dict = task_service._task_to_dict(task)
        result = {
            "success": True,
            "task": task_dict
        }
        
        # 生成格式化的任务详情
        formatted_task = f"""## 任务详情: {task_dict['name']}

**基本信息**
- **ID**: `{task_dict['id']}`
- **状态**: {task_dict['status']}
- **优先级**: {task_dict['priority']}
- **负责人**: {task_dict['assigned_to'] or '未分配'}
- **创建时间**: {task_dict['created_at']}
- **更新时间**: {task_dict['updated_at']}
- **完成时间**: {task_dict['completed_at'] or '未完成'}

**详细内容**
```
{task_dict['description']}
```

**工时信息**
- 预估工时: {task_dict['estimated_hours'] or '未设置'} 小时
- 实际工时: {task_dict['actual_hours'] or '未记录'} 小时

**标签**: {', '.join(task_dict['tags']) if task_dict['tags'] else '无标签'}

**依赖关系**:
- 依赖任务: {', '.join([f'`{dep}`' for dep in task_dict['dependencies']]) if task_dict['dependencies'] else '无依赖'}
- 被阻塞于: {', '.join([f'`{block}`' for block in task_dict['blocked_by']]) if task_dict['blocked_by'] else '无阻塞'}

**代码引用**: {', '.join(task_dict['code_references']) if task_dict['code_references'] else '无引用'}

```json
{json.dumps(task_dict, ensure_ascii=False, indent=2)}
```
"""
        
        return [
            types.TextContent(
                type="text",
                text=formatted_task
            )
        ]


@mcp.tool("get_task_list")
async def get_task_list(
    status: str = "",
    priority: str = "",
    tag: str = "",
    assigned_to: str = "",
    page: str = "1",
    page_size: str = "100"
) -> list[types.TextContent]:
    """获取任务列表
    
    Args:
        status: 按状态筛选，可选值为：todo, in_progress, done, blocked, cancelled
        priority: 按优先级筛选，可选值为：low, medium, high, critical
        tag: 按标签筛选
        assigned_to: 按负责人筛选
        page: 页码，默认为1
        page_size: 每页任务数量，默认为100
        
    Returns:
        List: 包含分页任务列表的JSON响应和格式化表格
    """
    logger.info(f"获取任务列表 (状态: {status}, 优先级: {priority}, 标签: {tag}, 页码: {page})")
    
    try:
        page_num = int(page)
        size_num = int(page_size)
    except ValueError:
        page_num = 1
        size_num = 100
    
    result = task_service.get_task_list(
        status=status,
        priority=priority,
        tag=tag, 
        assigned_to=assigned_to,
        page=page_num,
        page_size=size_num
    )
    
    # 创建格式化的表格输出
    if result["success"] and result["tasks"]:
        # 构建Markdown表格
        table = "| ID | 名称 | 状态 | 优先级 | 负责人 | 标签 |\n"
        table += "|-----|------|------|--------|--------|------|\n"
        
        for task in result["tasks"]:
            task_id = task["id"][:8] + "..." # 截取ID前8位
            name = task["name"]
            status = task["status"]
            priority = task["priority"]
            assigned_to = task["assigned_to"] or "-"
            tags = ", ".join(task["tags"]) if task["tags"] else "-"
            
            table += f"| {task_id} | {name} | {status} | {priority} | {assigned_to} | {tags} |\n"
        
        return [
            types.TextContent(
                type="text",
                text=f"## 任务列表\n总计: {result['total']} 任务, 页码: {result['page']}/{(result['total'] + result['page_size'] - 1) // result['page_size']}\n\n{table}\n\n详细数据:\n```json\n{json.dumps(result, ensure_ascii=False, indent=2)}\n```"
            )
        ]
    
    return [
        types.TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False)
        )
    ]


@mcp.tool("get_next_executable_task")
async def get_next_executable_task(limit: str = "5") -> list[types.TextContent]:
    """获取下一个可执行任务
    
    返回一个最优先的可执行任务，按照以下逻辑排序：
    1. 首先查找状态为'in_progress'的任务，优先返回这些任务
    2. 如果没有'in_progress'状态的任务，则查找所有状态为'todo'且没有未完成依赖的任务
    3. 按优先级排序（critical > high > medium > low）
    4. 同等优先级下，被更多任务依赖的排前面
    5. 进行中的父任务的子任务会优先展示
    6. 再同等条件下，创建时间早的排前面
    
    Args:
        limit: 内部查询任务数量限制，默认为5。只会返回排序后的第一个任务
        
    Returns:
        List: 包含下一个可执行任务的格式化响应
    """
    logger.info("获取下一个可执行任务")
    
    try:
        limit_num = int(limit)
    except ValueError:
        limit_num = 5
    
    result = task_service.get_next_executable_task(limit=limit_num)
    
    if result["success"]:
        if not result.get("found", False):
            return [
                types.TextContent(
                    type="text",
                    text="## 可执行任务\n\n当前没有可执行的任务。所有任务可能已完成或仍有依赖未满足。"
                )
            ]
        
        task = result["task"]
        
        output = "## 下一个待执行任务\n\n"
        
        # 任务基本信息
        output += f"### {task['name']}\n\n"
        output += f"- **ID**: `{task['id']}`\n"
        output += f"- **优先级**: {task['priority']}\n"
        
        # 附加信息
        if task.get('estimated_hours'):
            output += f"- **预计耗时**: {task['estimated_hours']} 小时\n"
        
        tags = ", ".join(task['tags']) if task.get('tags') else "无"
        output += f"- **标签**: {tags}\n"
        
        # 描述
        output += f"\n**任务描述**:\n{task['description']}\n\n"
        
        # 依赖信息
        if task.get('dependencies'):
            deps = ", ".join([f"`{d}`" for d in task['dependencies']])
            output += f"**依赖任务**: {deps}\n\n"
        
        # 父任务信息
        if task.get('parent_task_id'):
            output += f"**父任务**: `{task['parent_task_id']}`\n\n"
        
        # 添加详细JSON数据
        output += "### 详细数据\n\n"
        output += f"```json\n{json.dumps(result, ensure_ascii=False, indent=2)}\n```"
        
        return [
            types.TextContent(
                type="text",
                text=output
            )
        ]
    
    # 如果没有成功获取任务或发生错误，返回原始JSON
    return [
        types.TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2)
        )
    ]


@mcp.tool("expand_task")
async def expand_task(task_id: str, num_subtasks: str = "5") -> list[types.TextContent]:
    """为指定任务生成子任务
    
    Args:
        task_id: 要展开的任务ID，必须是现有任务
        num_subtasks: 希望生成的子任务数量，默认为5
        
    Returns:
        List: 包含生成的子任务信息和保存的文件路径
    """
    global PROJECT_PRD_CONTENT
    
    logger.info(f"为任务 {task_id} 生成 {num_subtasks} 个子任务")
    
    try:
        # 将参数转换为整数
        try:
            n_subs = int(num_subtasks)
            if n_subs <= 0 or n_subs > 10: # 限制数量在合理范围 (1-10)
                logger.warning(f"子任务数量 {n_subs} 无效或过大，将使用默认值 3")
                n_subs = 3
        except ValueError:
            logger.warning(f"无法解析子任务数量 '{num_subtasks}'，将使用默认值 3")
            n_subs = 3
        
        # 获取所有主任务作为上下文信息传递给LLM
        main_tasks = []
        try:
            all_tasks = task_service.storage.list_tasks()
            # 只提取顶级任务（ID中不包含点号的任务）
            main_tasks = [task_service._task_to_dict(task) for task in all_tasks if "." not in task.id]
            logger.info(f"获取到 {len(main_tasks)} 个主任务作为上下文")
        except Exception as e:
            logger.warning(f"获取主任务列表失败: {str(e)}")
        
        # 使用保存的PRD内容作为项目上下文信息
        project_context = ""
        if PROJECT_PRD_CONTENT:
            # 如果PRD内容过长，截取前2000个字符作为上下文
            project_context = PROJECT_PRD_CONTENT[:2000] 
            if len(PROJECT_PRD_CONTENT) > 2000:
                project_context += "...(内容已截断)"
            logger.info("使用保存的PRD内容作为项目上下文")
        else:
            # 如果没有PRD内容，使用默认描述
            project_context = "这是一个任务管理系统，用于分解项目需求文档(PRD)并生成任务列表，支持任务依赖关系管理、任务状态跟踪和任务执行顺序建议等功能。"
            logger.info("未找到PRD内容，使用默认项目描述作为上下文")
        
        # 调用任务服务的展开任务方法，传递更多上下文信息
        result = await task_service.expand_task(
            task_id, 
            num_subtasks=n_subs,
            project_context=project_context,
            main_tasks=main_tasks
        )
        
        if result["success"] and result.get("subtasks"):
            parent_task = result["parent_task"]
            subtasks = result["subtasks"]
            subtask_count = len(subtasks)
            
            # 将子任务添加到父任务的subtasks字段中
            if "subtasks" not in parent_task:
                parent_task["subtasks"] = []
            
            parent_task["subtasks"] = subtasks
            
            # 构建Markdown子任务列表
            md_content = f"# 任务 '{parent_task['name']}' 的子任务列表\n\n"
            md_content += f"## 父任务信息\n"
            md_content += f"- **ID**: {parent_task['id']}\n"
            md_content += f"- **名称**: {parent_task['name']}\n"
            md_content += f"- **描述**: {parent_task['description']}\n"
            md_content += f"- **优先级**: {parent_task['priority']}\n\n"
            
            md_content += f"## 子任务列表 ({subtask_count}个)\n\n"
            
            # 构建子任务表格
            md_content += format_task_table(subtasks, ["id", "name", "priority", "estimated_hours", "dependencies", "tags"])
            
            md_content += "\n## 详细子任务信息\n\n"
            
            for task in subtasks:
                md_content += f"### {task['name']}\n"
                md_content += f"- **ID**: {task['id']}\n"
                md_content += f"- **优先级**: {task['priority']}\n"
                md_content += f"- **状态**: {task['status']}\n"
                
                # 显示依赖关系
                dependencies = task.get("dependencies", [])
                if dependencies:
                    md_content += f"- **依赖任务**: {', '.join(dependencies)}\n"
                else:
                    md_content += f"- **依赖任务**: 无\n"
                
                if task["estimated_hours"]:
                    md_content += f"- **估计工时**: {task['estimated_hours']} 小时\n"
                if task["tags"]:
                    md_content += f"- **标签**: {', '.join(task['tags'])}\n"
                md_content += f"- **描述**: {task['description']}\n\n"
            
            # 添加依赖关系图
            md_content += "## 任务依赖关系\n\n"
            md_content += "```mermaid\nflowchart TD\n"
            md_content += f"  {parent_task['id']}[{parent_task['name']}]\n"
            
            # 添加所有子任务节点
            for task in subtasks:
                md_content += f"  {task['id']}[{task['name']}]\n"
            
            # 添加父任务到子任务的依赖关系
            for task in subtasks:
                md_content += f"  {parent_task['id']} --> {task['id']}\n"
            
            # 添加子任务之间的依赖关系
            for task in subtasks:
                dependencies = task.get("dependencies", [])
                for dep_id in dependencies:
                    md_content += f"  {dep_id} --> {task['id']}\n"
            
            md_content += "```\n"
            
            # 添加timestamp定义
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 更新父任务的JSON文件（包含子任务信息）
            task_json_path = save_task_to_json(parent_task, TASKS_DIR)
            if task_json_path:
                logger.info(f"包含子任务的父任务已保存到JSON文件: {task_json_path}")
            
            # 保存Markdown文件
            md_filename = f"task_{parent_task['id']}_subtasks_{timestamp}.md"
            md_file_path = os.path.join(MD_DIR, md_filename)
            
            try:
                with open(md_file_path, "w", encoding="utf-8") as f:
                    f.write(md_content)
                logger.info(f"子任务列表已写入文件: {md_file_path}")
            except Exception as file_e:
                logger.error(f"写入Markdown文件失败: {str(file_e)}")
            
            # 构建表格输出
            table = format_task_table(subtasks, ["id", "name", "priority", "estimated_hours", "dependencies", "tags"])
            
            # 最终输出
            formatted_output = f"""## 任务展开结果
            
### 父任务: {parent_task['name']} (ID: {parent_task['id']})

成功为任务生成了 **{subtask_count}** 个子任务。
- 子任务列表已保存到Markdown文件: **{md_file_path}**
- 子任务已添加到父任务的subtasks字段并保存: **{task_json_path}**

### 子任务列表
{table}

### 任务依赖关系图
任务依赖关系图已保存到上述Markdown文件中。

### 详细JSON数据
```json
{json.dumps(result, ensure_ascii=False, indent=2)}
```
"""
            
            return [
                types.TextContent(
                    type="text",
                    text=formatted_output
                )
            ]
        
        # 如果生成失败，返回错误信息
        return [
            types.TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2)
            )
        ]
    except Exception as e:
        logger.error(f"展开任务失败: {str(e)}", exc_info=True)
        
        # 获取详细的异常信息
        import traceback
        error_traceback = traceback.format_exc()
        
        error_result = {
            "success": False,
            "error": f"展开任务失败: {str(e)}",
            "error_code": "expand_task_error",
            "error_details": error_traceback
        }
        
        return [
            types.TextContent(
                type="text",
                text=json.dumps(error_result, ensure_ascii=False, indent=2)
            )
        ]


@mcp.tool("update_task_code_references")
async def update_task_code_references(task_id: str, code_files: str) -> list[types.TextContent]:
    """更新任务实现的代码文件引用

    Args:
        task_id: 要更新的任务ID
        code_files: 代码文件路径列表，以逗号分隔

    Returns:
        List: 包含更新结果的JSON响应
    """
    logger.info(f"更新任务 {task_id} 的代码引用")
    references = [f.strip() for f in code_files.split(",") if f.strip()]
    
    result = task_service.update_task_code_references(task_id, references)
    
    # 如果更新成功，更新任务的JSON文件
    if result.get("success") and result.get("task"):
        task_json_path = save_task_to_json(result["task"], TASKS_DIR)
        if task_json_path:
            result["task_json_path"] = task_json_path
    
    # 如果成功，返回格式化的任务详情，否则返回错误JSON
    if result["success"] and result.get("task"):
        task_dict = result["task"]
        formatted_task = f"""## 代码引用更新成功: {task_dict['name']}

已将任务 `{task_dict['id']}` 的代码引用更新为:
- {', '.join(task_dict['code_references']) if task_dict['code_references'] else '无引用'}

**完整任务信息:**
```json
{json.dumps(task_dict, ensure_ascii=False, indent=2)}
```
"""
        return [
            types.TextContent(
                type="text",
                text=formatted_task
            )
        ]
    else:
        return [
            types.TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2)
            )
        ]


if __name__ == "__main__":
    # 使用FastMCP的run方法运行服务
    try:
        logger.info("正在启动任务管理MCP服务...")
        mcp.run()
    except Exception as e:
        logger.error(f"服务启动失败: {str(e)}")
        sys.exit(1) 