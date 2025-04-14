"""
PRD解析服务

负责解析PRD文档，提取任务和依赖关系
"""

import re
import os
import json
# ----> Remove httpx, add google.genai <----
# import httpx 
import google.generativeai as genai
from typing import List, Dict, Optional, Any, Tuple
# ----> Remove asyncio? (Maybe not needed directly) <----
# import asyncio 
import sys
import logging

# 将项目根目录添加到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# 兼容从不同目录运行的导入路径
try:
    from ..models.task import Task, TaskStatus, TaskPriority
    from ..storage.task_storage import TaskStorage
    # ----> Import the new LLM class <----
    from ..llm.gemini import GeminiLLM
    from ..llm.base import LLMInterface # Import base for type hinting if needed
except (ImportError, ValueError):
    from src.models.task import Task, TaskStatus, TaskPriority
    from src.storage.task_storage import TaskStorage
    from src.llm.gemini import GeminiLLM
    from src.llm.base import LLMInterface

# ----> 获取 logger 实例 <----
logger = logging.getLogger(__name__)

class PrdParser:
    """PRD文档解析器，使用注入的LLM客户端（如果提供）"""
    
    def __init__(self, storage: TaskStorage, llm_client: Optional[LLMInterface] = None):
        """
        初始化PRD解析器。
        
        Args:
            storage: 任务存储后端实例。
            llm_client: 一个实现了 LLMInterface 的可选客户端实例。
                        如果提供，将用于解析PRD；否则，将回退到基本解析。
        """
        self.storage = storage
        # ----> Assign the injected client <----
        self.llm_client = llm_client

        if self.llm_client:
             logger.info(f"[PrdParser Init] Initialized with LLM client: {type(self.llm_client).__name__}")
        else:
             logger.info("[PrdParser Init] Initialized without an LLM client. Will use fallback parsing.")

        # ----> Remove the internal GeminiLLM initialization block <----
        # try:
        #      # GeminiLLM reads API key from env var by default
        #      self.llm_client: Optional[LLMInterface] = GeminiLLM() 
        #      logger.info("[PrdParser Init] GeminiLLM client initialized successfully.")
        # except (ValueError, RuntimeError) as llm_init_e:
        #      logger.error(f"[PrdParser Init] Failed to initialize GeminiLLM client: {llm_init_e}")
        #      self.llm_client = None # Set client to None if initialization fails
        
        # Remove comments about old setup

    async def parse(self, prd_content: str) -> Tuple[List[Task], Optional[str]]:
        """
        解析PRD文档并提取任务和依赖。
        
        首先尝试使用配置的LLM客户端解析，如果失败或未配置LLM客户端，则回退到使用正则表达式解析。
        
        注意：如果prd_content是以file://开头的文件路径，必须使用绝对路径，否则无法正确解析。
        
        Args:
            prd_content: PRD文档内容
            
        Returns:
            Tuple[List[Task], Optional[str]]: 提取的任务列表和LLM解析错误信息 (if LLM was attempted and failed)
        """
        tasks = []
        llm_error = None 
        
        # Check if an LLM client was provided during initialization
        if self.llm_client:
            try:
                logger.info(f"[PrdParser Parse] Attempting parsing with injected LLM client ({type(self.llm_client).__name__})...")
                parsed_tasks = await self.parse_with_llm(prd_content)
                logger.info(f"[PrdParser Parse] LLM parsing successful, found {len(parsed_tasks)} tasks.")
                return parsed_tasks, None 
            except Exception as e:
                llm_error_msg = f"{type(e).__name__}: {str(e)}"
                logger.error(f"[PrdParser Parse] LLM parsing failed: {llm_error_msg}", exc_info=True) 
                logger.info("[PrdParser Parse] Falling back to basic regex parsing.")
                llm_error = llm_error_msg 
        else:
             # No LLM client provided, go directly to fallback
             logger.info("[PrdParser Parse] No LLM client provided. Using basic regex parsing.")
             # llm_error remains None as LLM wasn't attempted

        # ----> Fallback Logic with Hierarchical Numeric IDs <----
        logger.info("[PrdParser Fallback] Starting basic regex parsing...")
        headers = re.findall(r'#\s+(.*)|##\s+(.*)', prd_content)
        
        tasks_map = {} # Map generated ID to {task: Task, level: int}
        h1_counter = 0
        h2_counter = 0
        current_h1_id = "0" # Keep track of the current H1 ID for H2 subtasks
        
        for i, (h1, h2) in enumerate(headers):
            title = h1 or h2
            level = 1 if h1 else 2
            
            if not title.strip():
                continue
                
            # Generate hierarchical ID
            if level == 1:
                h1_counter += 1
                h2_counter = 0 # Reset H2 counter for new H1 section
                task_id = str(h1_counter)
                current_h1_id = task_id
            elif level == 2:
                h2_counter += 1
                task_id = f"{current_h1_id}.{h2_counter}"
            else:
                # Should not happen with current regex, but handle defensively
                logger.warning(f"Unexpected header level detected for title: {title}. Skipping.")
                continue
                
            logger.debug(f"[PrdParser Fallback] Creating task with ID: {task_id}, Title: {title.strip()}")
            try:
                # --> Pass the generated ID to create_task <--
                task = self.storage.create_task(
                                id=task_id, # Pass the generated ID here
                    name=title.strip(),
                                description=f"从PRD自动提取的任务 (Fallback): {title}",
                    priority=TaskPriority.MEDIUM if level == 1 else TaskPriority.LOW
                )
                tasks.append(task)
                tasks_map[task_id] = {"task": task, "level": level}
            except Exception as create_exc:
                # Log error if task creation with specific ID fails
                logger.error(f"[PrdParser Fallback] Failed to create task with ID {task_id} for title '{title.strip()}': {create_exc}", exc_info=True)
                # Skip this task for dependency setting etc.
                continue
        
        # --- Dependency setting logic (uses the generated IDs stored in tasks_map) ---
        current_parent_task_id = None
        for i, task in enumerate(tasks):
            if task.id not in tasks_map:
                # Task creation might have failed, already logged.
                continue 
                
            current_level = tasks_map[task.id]["level"]
            
            # Set parent dependency (H2 depends on the H1 it falls under)
            if current_level == 1:
                current_parent_task_id = task.id # Store the ID of the H1 task
            elif current_level == 2 and current_parent_task_id:
                try: 
                    logger.debug(f"[PrdParser Fallback] Setting parent dependency: {task.id} -> {current_parent_task_id}")
                    success, _ = self.storage.set_task_dependency(task.id, current_parent_task_id)
                    if not success:
                         logger.warning(f"[PrdParser Fallback] Failed setting parent dependency for task {task.id} -> {current_parent_task_id}")
                except Exception as dep_exc:
                     logger.error(f"[PrdParser Fallback] Error setting parent dependency for task {task.id} -> {current_parent_task_id}: {dep_exc}", exc_info=True)

            # Set sequential dependency (task depends on previous task of the same level)
            if i > 0:
                prev_task_index = -1
                # Find the actual previous task with the same level that was successfully created
                for j in range(i - 1, -1, -1):
                     if tasks[j].id in tasks_map and tasks_map[tasks[j].id]["level"] == current_level:
                          prev_task_index = j
                          break
                          
                if prev_task_index != -1:
                     prev_task = tasks[prev_task_index]
                     try:
                         logger.debug(f"[PrdParser Fallback] Setting sequential dependency: {task.id} -> {prev_task.id}")
                         success, msg = self.storage.set_task_dependency(task.id, prev_task.id)
                         if not success:
                            logger.warning(f"[PrdParser Fallback] Failed setting sequential dependency for task {task.id} -> {prev_task.id}: {msg}") 
                     except Exception as seq_dep_exc:
                         logger.error(f"[PrdParser Fallback] Error setting sequential dependency for task {task.id} -> {prev_task.id}: {seq_dep_exc}", exc_info=True)
                # else: # No previous task of the same level found (e.g., first H2 under an H1)
                #     logger.debug(f"[PrdParser Fallback] No preceding task of level {current_level} found for sequential dependency for task {task.id}.")

        logger.info(f"[PrdParser Fallback] Basic parsing complete, attempted creation of {len(tasks_map)} tasks with numeric IDs.")
        # If LLM was attempted and failed, llm_error will contain the error message
        # Otherwise (no LLM client provided), llm_error will be None
        return tasks, llm_error 
    
    async def parse_with_llm(self, prd_content: str) -> List[Task]:
        """
        使用配置的 LLMInterface 客户端的 parse_prd_to_tasks_async 方法解析PRD文档。
        现在期望 LLM 直接生成层级数字 ID。
        假定 self.llm_client 在调用此方法前已被验证存在。
        
        注意：如果prd_content是以file://开头的文件路径，必须使用绝对路径，否则无法正确解析。
        
        Args:
            prd_content: PRD文档内容
            
        Returns:
            List[Task]: 提取并转换为 Task 对象的任务列表
            
        Raises:
            RuntimeError: If LLM client is somehow None when called.
            Exception: If LLM parsing or subsequent task processing fails.
        """
        if not self.llm_client:
             logger.error("[PrdParser LLM] Internal Error: parse_with_llm called but llm_client is None.")
             raise RuntimeError("LLM client is not available for parsing.")
             
        logger.info(f"[PrdParser LLM] Calling llm_client.parse_prd_to_tasks_async with {type(self.llm_client).__name__}...")
        
        try:
            logger.debug("[PrdParser LLM] Awaiting llm_client.parse_prd_to_tasks_async...")
            # LLM is now expected to return hierarchical IDs in the 'id' field
            tasks_data: List[Dict[str, Any]] = await self.llm_client.parse_prd_to_tasks_async(prd_content)
            
            logger.info(f"[PrdParser LLM] Received {len(tasks_data)} validated task dictionaries from LLM client.")
            
            tasks = []
            # ----> Use task_id_map to map LLM-generated ID to task name for dependency lookup <----
            task_id_map = {} # Map generated ID to task name
            llm_id_to_task_id = {} # Map LLM generated ID to the one actually used/created (in case of duplicates/errors)
            successful_tasks = [] # Store tasks that were successfully created
                    
            # Step 1: Create tasks using LLM-generated IDs
            for task_info in tasks_data:
                 # Validation already happened in GeminiLLM, but double check essentials
                 if not isinstance(task_info, dict) or 'id' not in task_info or 'name' not in task_info:
                      logger.warning(f"[PrdParser LLM] Skipping task missing required fields: {task_info}")
                      continue
                 
                 llm_task_id = str(task_info['id']) # ID generated by LLM
                 task_name = task_info['name'].strip()
                 if not task_name:
                     logger.warning(f"[PrdParser LLM] Skipping task with effectively empty name: {task_info}")
                     continue

                 # Validate priority, hours, tags (logic remains the same)
                 priority_str = task_info.get('priority', 'medium').lower()
                 try: task_priority = TaskPriority(priority_str)
                 except ValueError: task_priority = TaskPriority.MEDIUM
                 
                 est_hours = task_info.get('estimated_hours')
                 if est_hours is not None:
                     try:
                         est_hours = float(est_hours)
                         if est_hours < 0: est_hours = None
                     except (ValueError, TypeError): est_hours = None
                 
                 tags = task_info.get('tags', [])
                 if isinstance(tags, list):
                     valid_tags = [str(tag) for tag in tags if isinstance(tag, (str, int, float))]
                     tags = valid_tags
                 else: tags = []

                 logger.debug(f"[PrdParser LLM] Attempting to create task with LLM-generated ID: {llm_task_id}, Name: {task_name}")
                 try:
                     # ----> Pass the LLM-generated ID to create_task <----
                    task = self.storage.create_task(
                        id=llm_task_id, # Use ID from LLM
                        name=task_name,
                            description=task_info.get('description', ''),
                        priority=task_priority,
                        tags=tags,
                        estimated_hours=est_hours
                    )
                    successful_tasks.append(task)
                    # Use the actual ID from the created task object
                    llm_id_to_task_id[llm_task_id] = task.id 
                    # Map name to the actual ID for dependency resolution
                    if task_name in task_id_map:
                        logger.warning(f"[PrdParser LLM] Duplicate task name '{task_name}' detected from LLM. Dependency resolution might be ambiguous.")
                    # Store the actual task ID, not the potentially duplicate LLM ID
                    task_id_map[task_name] = task.id 
                 except ValueError as ve:
                      # Catch potential ID collision from TaskStorage
                      logger.error(f"[PrdParser LLM] Failed to create task with LLM-generated ID {llm_task_id} for name '{task_name}' (ID might already exist): {ve}", exc_info=False) # Don't need full traceback for expected error
                      # Map LLM ID to None to indicate failure
                      llm_id_to_task_id[llm_task_id] = None 
                 except Exception as create_exc:
                      logger.error(f"[PrdParser LLM] Failed to create task with LLM-generated ID {llm_task_id} for name '{task_name}': {create_exc}", exc_info=True)
                      # Map LLM ID to None
                      llm_id_to_task_id[llm_task_id] = None 
                      continue

            # ----> NEW Step 2: Analyze dependencies with a second LLM call <----
            if successful_tasks:
                logger.info(f"[PrdParser LLM] Preparing second LLM call for dependency analysis on {len(successful_tasks)} tasks...")
                
                # Prepare input for the dependency analysis prompt
                tasks_for_prompt = []
                task_lookup_by_id = {task.id: task for task in successful_tasks} # For quick validation
                for task in successful_tasks:
                    tasks_for_prompt.append({
                        "id": task.id,
                        "name": task.name,
                        "description": task.description
                    })
                
                tasks_input_str = json.dumps(tasks_for_prompt, indent=2, ensure_ascii=False)

                # Define the schema for the dependency output
                dependency_schema = {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string", "description": "The ID of the task that has a dependency."},
                            "depends_on_id": {"type": "string", "description": "The ID of the task that must be completed first."}
                        },
                        "required": ["task_id", "depends_on_id"]
                    }
                }

                # Define the prompt for dependency analysis
                dependency_prompt = f"""你是一个任务依赖关系分析专家。请分析以下已提取的任务列表 (JSON格式)，识别它们之间的逻辑依赖关系。

任务列表如下:
```json
{tasks_input_str}
```

分析规则:
1.  仔细阅读每个任务的 ID, 名称 和 描述。
2.  **必须添加结构性和核心逻辑依赖:**
    *   **层级依赖:** **所有**子任务（ID 中包含 '.'，例如 '1.1', '2.3'）**必须**依赖其直接父任务（ID 为去掉最后一部分，例如 '1.1' 依赖 '1', '2.3' 依赖 '2'）。
    *   **基础模块依赖:** 主要的功能模块（如 ID '2' - 运动记录, ID '3' - 统计与仪表盘, ID '4' - 设置）**必须**依赖于最基础的用户认证模块（ID '1'）。
    *   **功能模块依赖:** 实现更高级功能的模块（如 ID '3' - 统计与仪表盘）**必须**依赖于提供基础数据的模块（如 ID '2' - 运动记录）。
    *   **部署依赖:** 部署和维护相关的任务（如 ID '5', '5.1', '5.2'）**必须**依赖于所有核心功能模块（通常是 ID '1', '2', '3', '4'）的完成。请为每个核心模块添加一个依赖关系。
3.  **识别任务描述中的明确依赖:** 如果任务A的描述明确说明它需要任务B完成后才能开始（例如，\"需要先完成用户注册\"，\"基于运动记录数据进行统计\"），则任务A**必须**依赖于任务B (确保 B 的 ID 有效)。
4.  **识别隐含的顺序依赖:** 同一层级下的任务（例如 '1.1' 和 '1.2'，或 '2.1' 和 '2.2'），如果存在非常明显的**业务逻辑先后顺序**（例如，登录 '1.2' 必须在注册 '1.1' 之后），则后一个任务**应该**依赖前一个。**仅在逻辑顺序非常明确时添加此类型依赖。**
5.  **验证与输出:**
    *   确保所有生成的 `task_id` 和 `depends_on_id` 都是任务列表中存在的有效 ID。
    *   **不要**创建循环依赖或任务自我依赖。
    *   只输出符合上述规则推导出的依赖关系。**避免**添加不确定、逻辑上不合理或弱的依赖。

请严格按照 JSON 格式返回一个依赖关系对的列表，每个对象包含 `task_id` 和 `depends_on_id` 两个字段，如 schema 定义。不要添加任何额外的解释或说明。如果分析后认为没有明确的依赖关系（除了必要的结构性依赖），请只返回必要的结构性依赖。
"""

                try:
                    logger.debug("[PrdParser LLM] Awaiting second LLM call for dependency analysis...")
                    dependency_data = await self.llm_client.generate_structured_content_async(
                        prompt=dependency_prompt,
                        schema=dependency_schema,
                        temperature=0.2 # Low temperature for more deterministic dependency analysis
                    )

                    if isinstance(dependency_data, list):
                        logger.info(f"[PrdParser LLM] Received {len(dependency_data)} dependency pairs from LLM.")
                        applied_count = 0
                        for dep_pair in dependency_data:
                            if not isinstance(dep_pair, dict) or 'task_id' not in dep_pair or 'depends_on_id' not in dep_pair:
                                logger.warning(f"[PrdParser LLM] Skipping invalid dependency pair: {dep_pair}")
                                continue

                            task_id = str(dep_pair['task_id'])
                            depends_on_id = str(dep_pair['depends_on_id'])

                            # Validate IDs exist and are not the same
                            if task_id == depends_on_id:
                                logger.warning(f"[PrdParser LLM] Skipping self-dependency: {task_id} -> {depends_on_id}")
                                continue
                            if task_id not in task_lookup_by_id:
                                logger.warning(f"[PrdParser LLM] Skipping dependency: Task ID '{task_id}' not found.")
                                continue
                            if depends_on_id not in task_lookup_by_id:
                                logger.warning(f"[PrdParser LLM] Skipping dependency: Depends on ID '{depends_on_id}' not found.")
                                continue
                                
                            # Attempt to set dependency
                            try:
                                logger.debug(f"[PrdParser LLM] Setting dependency from LLM: {task_id} -> {depends_on_id}")
                                # 确保调用 set_task_dependency 时两个 ID 都存在于 task_lookup_by_id
                                if task_id in task_lookup_by_id and depends_on_id in task_lookup_by_id:
                                    success, msg = self.storage.set_task_dependency(task_id, depends_on_id)
                                    if success:
                                         applied_count += 1
                                    elif msg != "Dependency already exists": # Don't warn if it just exists
                                         logger.warning(f"[PrdParser LLM] Failed setting dependency from LLM: {task_id} -> {depends_on_id}: {msg}")
                                else:
                                    logger.warning(f"[PrdParser LLM] Skipping setting dependency because one or both tasks ({task_id}, {depends_on_id}) were not successfully created initially.")
                            except Exception as set_dep_exc:
                                logger.error(f"[PrdParser LLM] Error setting dependency from LLM: {task_id} -> {depends_on_id}: {set_dep_exc}", exc_info=True)
                        logger.info(f"[PrdParser LLM] Successfully applied {applied_count} dependency pairs from second LLM call.")
                    else:
                        logger.error(f"[PrdParser LLM] Dependency analysis LLM call did not return a list. Got: {type(dependency_data)}")

                except Exception as dep_analysis_exc:
                    logger.error(f"[PrdParser LLM] Error during second LLM call for dependency analysis: {dep_analysis_exc}", exc_info=True)
                    # Continue without applying LLM dependencies if this step fails

            logger.info(f"[PrdParser LLM] Successfully created {len(successful_tasks)} Task objects using LLM-generated IDs. Dependency analysis complete.")
            return successful_tasks

        except Exception as e:
             logger.error(f"[PrdParser LLM] Error during LLM parsing or task processing: {type(e).__name__}: {str(e)}", exc_info=True)
             raise

    # Remove extract_sections and find_code_references if not used elsewhere
    # def extract_sections(...)
    # def find_code_references(...) 