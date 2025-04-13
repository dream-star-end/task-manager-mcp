import os
import json
import logging
import re
from typing import Any, Dict, Optional, List

import google.generativeai as genai
from google.generativeai.types import GenerationConfig, ContentDict, PartDict
from google.api_core.exceptions import GoogleAPIError  # More specific error handling

from .base import LLMInterface

logger = logging.getLogger(__name__)

class GeminiLLM(LLMInterface):
    """Google Gemini LLM implementation using the google-generativeai SDK."""

    def __init__(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """
        Initializes the Gemini LLM client.

        Args:
            api_key: API key (optional, defaults to GEMINI_API_KEY env var).
            config: Additional configuration (optional, e.g., model_name).
        """
        super().__init__(api_key, config) # Initialize base class

        # Log proxy settings if detected
        http_proxy = os.environ.get('HTTP_PROXY')
        https_proxy = os.environ.get('HTTPS_PROXY')
        if http_proxy:
            logger.info(f"HTTP_PROXY environment variable detected: {http_proxy}")
        if https_proxy:
            logger.info(f"HTTPS_PROXY environment variable detected: {https_proxy}")
        if http_proxy or https_proxy:
             logger.info("Proxy settings will be used by the underlying HTTP client if supported.")

        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            logger.error("Gemini API Key not provided or found in environment variable GEMINI_API_KEY.")
            raise ValueError("Gemini API Key is required.")

        try:
            genai.configure(api_key=self.api_key)
            logger.info("Google Generative AI SDK configured successfully.")
        except Exception as e:
            logger.error(f"Failed to configure Google Generative AI SDK: {e}", exc_info=True)
            raise RuntimeError(f"Failed to configure Google Generative AI SDK: {e}") from e

        model_name = os.getenv("MODEL_NAME", "gemini-2.0-flash")
        # Allow overriding the model via config, default to a reasonable one
        self.model_name = self.config.get("model_name", model_name) # Changed default to 2.0 flash
        try:
            self.model = genai.GenerativeModel(self.model_name)
            logger.info(f"Initialized Gemini model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model '{self.model_name}': {e}", exc_info=True)
            raise RuntimeError(f"Failed to initialize Gemini model '{self.model_name}': {e}") from e

    async def generate_text_async(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> str:
        """
        Generates text content using the Gemini model (async).

        Args:
            prompt: The input prompt.
            temperature: Controls randomness (0.0-1.0).
            max_tokens: Maximum tokens to generate (optional).
            **kwargs: Additional parameters for GenerationConfig.

        Returns:
            The generated text string.

        Raises:
            Exception: If the API call fails or response is invalid.
        """
        logger.debug(f"Generating text with Gemini (model: {self.model_name}, temp: {temperature}, max_tokens: {max_tokens})")

        generation_config = GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            **kwargs # Pass other relevant args like stop_sequences if needed
        )

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=generation_config,
                # safety_settings=... # Optional safety settings
            )
            # Access text safely, considering potential lack of response parts
            if response.parts:
                 generated_text = response.text # response.text joins parts
                 logger.debug("Gemini text generation successful.")
                 return generated_text
            else:
                 logger.warning(f"Gemini response for prompt '{prompt[:50]}...' contained no text parts.")
                 # Check for prompt feedback or other issues
                 if response.prompt_feedback:
                      logger.warning(f"Prompt feedback: {response.prompt_feedback}")
                 return "" # Return empty string if no content

        except GoogleAPIError as e:
            logger.error(f"Gemini API error during text generation: {e}", exc_info=True)
            raise Exception(f"Gemini API error: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during Gemini text generation: {e}", exc_info=True)
            raise Exception(f"Unexpected error during text generation: {e}") from e

    async def generate_structured_content_async(
        self,
        prompt: str,
        schema: Dict[str, Any],
        temperature: float = 0.1, # Lower temp for structured output
        **kwargs: Any
    ) -> Any:
        """
        Generates structured content (JSON) using the Gemini model based on a schema (async).

        Args:
            prompt: The input prompt.
            schema: The desired JSON schema definition.
            temperature: Controls randomness (usually low for structure).
            **kwargs: Additional parameters for GenerationConfig.

        Returns:
            The parsed structured data (e.g., list or dict).

        Raises:
            ValueError: If the schema is invalid.
            Exception: If API call fails or response cannot be parsed.
        """
        logger.debug(f"Generating structured content with Gemini (model: {self.model_name}, temp: {temperature})")

        if not isinstance(schema, dict):
             raise ValueError("Schema must be a dictionary.")

        # The SDK handles schema validation internally when passed to GenerationConfig
        generation_config = GenerationConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=schema, # Pass the schema directly
            **kwargs
        )

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=generation_config,
                # safety_settings=...
            )

            # The SDK should enforce the schema and return JSON in response.text
            if not response.parts:
                logger.warning(f"Gemini structured response for prompt '{prompt[:50]}...' contained no parts.")
                if response.prompt_feedback:
                      logger.warning(f"Prompt feedback: {response.prompt_feedback}")
                raise Exception("Gemini returned an empty response for structured content.")


            json_string = response.text
            logger.debug(f"Received raw JSON string: {json_string[:200]}...") # Log snippet

            # Parse the JSON string returned by the SDK
            parsed_data = json.loads(json_string)
            logger.debug("Successfully parsed JSON response from Gemini.")
            return parsed_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON response from Gemini: {e}. Response text: {json_string}", exc_info=True)
            raise Exception(f"Failed to parse LLM JSON response: {e}") from e
        except GoogleAPIError as e:
            logger.error(f"Gemini API error during structured generation: {e}", exc_info=True)
            # Include details from the error if available
            error_details = getattr(e, 'details', '')
            raise Exception(f"Gemini API error: {e} - {error_details}") from e
        except Exception as e:
            # Catch potential issues if the response structure isn't as expected
            logger.error(f"Unexpected error during Gemini structured generation: {e}", exc_info=True)
            raise Exception(f"Unexpected error during structured generation: {e}") from e

    async def parse_prd_to_tasks_async(
        self,
        prd_content: str,
        **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """
        Implements the PRD parsing logic specifically for the Gemini model.
        Attempts to generate hierarchical numeric IDs (e.g., 1, 1.1, 2) directly.
        Constructs the prompt and schema, then calls the underlying
        structured content generation method.
        """
        logger.info(f"Parsing PRD content using Gemini model: {self.model_name}")

        # Schema definition specific to the task of parsing PRD into tasks
        task_schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    # Add ID field with description
                    "id": {
                        "type": "string", 
                        "description": "Hierarchical ID based on ## H1 and ### H2 structure (e.g., '1', '1.1', '2')."
                    },
                    "name": {"type": "string"},
                    "description": {
                        "type": "string",
                        "description": "Detailed description outlining the main purpose and key deliverables of the task."
                    },
                    "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                    "estimated_hours": {"type": "number"},
                    "dependencies": {"type": "array", "items": {"type": "string"}}, # Dependencies by name
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "parent_task_id": {
                        "type": "string",
                        "description": "ID of the parent task (e.g., '1' is parent of '1.1'). Leave empty for top-level tasks."
                    },
                    "complexity": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Estimated complexity of the task."
                    }
                },
                # Make ID required
                "required": ["id", "name", "description"] 
            }
        }

        # ----> Updated Prompt with clearer instructions for semantic dependencies <----
        prompt = f"""你是一个专业的产品需求文档解析助手。请仔细分析以下 Markdown 格式的 PRD 文档，并提取 **顶级主任务**。

任务提取规则：
1.  **分析文档结构**，识别主要的功能模块或需求类别，将其视为**顶级主任务**。
2.  任务的 **名称** 应简洁明确地表达任务的主要目标或功能模块。
3.  任务的 **描述** 应清晰、详细地概括该任务的主要目标、要解决的问题以及关键的交付成果或功能点。
4.  为每个任务生成一个 **顶级数字 ID**，例如 `1`, `2`, `3`, ...。
5.  **parent_task_id** 字段应始终为空或省略，因为只提取顶级任务。
6.  根据任务内容和预期工作量判断 **优先级** (low/medium/high/critical)。
7.  根据任务的实现难度和涉及范围评估 **复杂度** (low/medium/high)。
8.  如果内容中提到，提取 **估计工时** (小时，数字)。
9.  **关键**: 识别顶级任务之间的**语义依赖关系**（例如，模块B依赖模块A）：
    *   如果任务描述中明确提到它**依赖于**另一个任务才能开始，请在 `dependencies` 列表中包含**被依赖任务的ID**。
    *   请确保 `dependencies` 列表中的ID与你在此列表中生成的其他任务的ID**完全匹配**。
10. 提取与任务相关的 **标签** (选择相关性高的关键词，简洁表达)。

请严格按照JSON格式返回一个**仅包含顶级主任务对象**的列表，每个对象需包含 `id`, `name`, `description`, `priority`, `complexity`, `dependencies` 等字段（如 schema 定义）。不要添加任何额外的解释或说明。请特别注意只输出顶级任务，且 ID 格式为纯数字。

PRD文档如下：
-----------------
{prd_content}
-----------------"""

        temperature = kwargs.pop('temperature', 0.1) # Keep low for structure

        try:
            parsed_data = await self.generate_structured_content_async(
                prompt=prompt,
                schema=task_schema,
                temperature=temperature,
                **kwargs
            )

            # Validate the output structure (should be a list of dicts)
            if not isinstance(parsed_data, list) or not all(isinstance(item, dict) for item in parsed_data):
                logger.error(f"Gemini returned unexpected structure for PRD parsing. Expected List[Dict], got {type(parsed_data)}.")
                # Attempt to log part of the response for debugging
                try:
                     response_snippet = str(parsed_data)[:500]
                     logger.error(f"Response snippet: {response_snippet}")
                except Exception:
                     logger.error("Could not get response snippet.")
                raise TypeError("LLM response for PRD parsing was not a list of dictionaries.")

            validated_tasks = []
            for i, task_info in enumerate(parsed_data):
                 if not isinstance(task_info, dict):
                     logger.warning(f"Skipping non-dictionary item at index {i}: {task_info}")
                     continue
                 # Check if required fields 'id' and 'name' exist
                 if 'id' not in task_info or 'name' not in task_info:
                     logger.warning(f"Skipping task at index {i} due to missing 'id' or 'name': {task_info}")
                     continue
                 # Basic validation for ID format (e.g., starts with number, may contain '.')
                 task_id = str(task_info['id']) # Ensure string
                 if not re.match(r'^[1-9][0-9]*(\.[1-9][0-9]*)*$', task_id):
                     logger.warning(f"Skipping task at index {i} due to invalid ID format '{task_id}': {task_info}")
                     continue
                 
                 validated_tasks.append(task_info)

            if len(validated_tasks) != len(parsed_data):
                logger.warning(f"Some tasks were filtered out during validation. Original count: {len(parsed_data)}, Validated count: {len(validated_tasks)}")
            
            if not validated_tasks and len(parsed_data) > 0:
                 logger.error("All tasks failed validation after LLM response.")
                 raise ValueError("LLM response contained tasks, but none passed validation (missing/invalid ID or name).")

            logger.info(f"Successfully parsed PRD into {len(validated_tasks)} validated task dictionaries using Gemini.")
            return validated_tasks # Return only validated tasks

        except Exception as e:
            logger.error(f"Error during Gemini PRD parsing with hierarchical IDs: {e}", exc_info=True)
            raise

    async def generate_subtasks_for_task_async(
        self,
        task_info: Dict[str, Any],
        num_subtasks: int = 5, # 添加数量参数
        temperature: float = 0.2,
        project_context: str = "",
        main_tasks: List[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """
        为指定的任务生成子任务列表，使用Gemini模型实现。
        
        Args:
            task_info: 父任务的信息字典
            num_subtasks: 希望生成的子任务数量。
            temperature: 控制生成随机性的温度参数
            project_context: 项目的整体背景和上下文信息
            main_tasks: 所有主任务的列表，用于提供更全面的上下文
            **kwargs: 其他参数
            
        Returns:
            子任务字典列表
        """
        task_id = task_info.get("id")
        task_name = task_info.get("name")
        task_description = task_info.get("description", "")
        
        logger.info(f"Generating subtasks for task {task_id} ({task_name}) using Gemini model")
        
        # 如果未提供main_tasks，则使用空列表
        if main_tasks is None:
            main_tasks = []
        
        # 定义子任务的JSON schema
        subtask_schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": f"Hierarchical ID following the pattern {task_id}.X format"
                    },
                    "name": {"type": "string"},
                    "description": {
                        "type": "string",
                        "description": "Detailed description including implementation steps, key considerations, or expected outcomes."
                    },
                    "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                    "estimated_hours": {"type": "number"},
                    "dependencies": {
                        "type": "array", 
                        "items": {"type": "string"},
                        "description": "IDs of other subtasks this subtask depends on (only subtask IDs, NOT the parent task ID)."
                    },
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "complexity": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Estimated complexity of the subtask."
                    },
                    "code_references": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of relevant code files (initially empty)."
                    }
                },
                "required": ["id", "name", "description", "priority", "complexity", "dependencies", "code_references"]
            }
        }
        
        # 构建主任务信息列表
        main_tasks_info = ""
        if main_tasks:
            main_tasks_info = "项目所有主任务信息:\n"
            for i, main_task in enumerate(main_tasks):
                main_task_id = main_task.get("id", "未知")
                main_task_name = main_task.get("name", "未知")
                main_task_description = main_task.get("description", "").split('\n')[0][:100] + "..."
                main_tasks_info += f"{i+1}. ID: {main_task_id}, 名称: {main_task_name}, 描述: {main_task_description}\n"
        
        # 创建提示词
        prompt = f"""你是一个任务拆解专家。请为特定主任务生成子任务，并分析子任务之间的依赖关系。主任务信息以及相关项目背景如下：

=== 项目背景 ===
{project_context}

=== 所有主任务 ===
{main_tasks_info}

=== 当前要拆解的主任务 ===
ID: {task_id}
名称: {task_name}
描述: {task_description}

请为上述主任务生成 **{num_subtasks}** 个子任务，确保它们：
1. 是完成主任务的必要步骤，仔细分析主任务描述中的所有功能点和需求点
2. 具有明确、具体的目标，每个子任务专注于一个特定功能点或模块
3. 覆盖主任务描述中提到的所有关键需求和功能点
4. 与其他主任务的内容协调一致，避免功能重复或冲突
5. 采用合理的技术实现方案，考虑主流技术框架和最佳实践

对于每个子任务：
1. 指定层级结构的ID，格式为"{task_id}.序号"（如 {task_id}.1、{task_id}.2 等）
2. 提供清晰的名称，表达子任务的核心目标
3. 提供**详细的描述**，说明子任务要完成的具体工作、可能的实现步骤、关键的考虑因素或预期的产出
4. 根据重要性分配优先级: critical（核心）, high（重要）, medium（一般）, low（次要）
5. 评估实现**复杂度**: low, medium, high
6. 估计完成所需工时（小时）
7. 添加**最多3个**简洁且与子任务内容**高度相关**的标签
8. 指定子任务之间的依赖关系，但**重要**: 子任务的dependencies字段中**不要包含父任务ID**（即{task_id}）
9. **code_references** 字段必须包含，初始值为空列表 `[]`

依赖关系规则：
1. 必须考虑任务的逻辑前后关系，例如"测试功能"依赖于"实现功能"
2. 依赖项使用任务ID表示，如 {task_id}.2 依赖于 {task_id}.1
3. **不要**将父任务（{task_id}）添加到任何子任务的dependencies中，系统会自动处理这个关系

示例子任务格式：
```json
[
  {{
    "id": "{task_id}.1",
    "name": "设计数据库模型",
    "description": "根据需求设计用户、运动记录等相关的数据库表结构，确定字段类型和关系。",
    "priority": "high",
    "complexity": "medium",
    "estimated_hours": 4,
    "dependencies": [],
    "tags": ["后端", "数据库"],
    "code_references": []
  }},
  {{
    "id": "{task_id}.2",
    "name": "开发用户认证API",
    "description": "实现注册、登录、密码重置的后端API接口，包括参数校验、业务逻辑处理和数据库操作。",
    "priority": "critical",
    "complexity": "high",
    "estimated_hours": 16,
    "dependencies": ["{task_id}.1"],
    "tags": ["API", "后端"],
    "code_references": []
  }}
]
```

请输出格式化的JSON数组，仅包含子任务对象，不要添加任何额外的解释文本。请确保每个子任务都不包含父任务ID在dependencies字段中。
"""
        
        try:
            # 调用通用的结构化内容生成方法
            subtasks_data = await self.generate_structured_content_async(
                prompt=prompt,
                schema=subtask_schema,
                temperature=temperature,
                **kwargs
            )
            
            # 验证输出结构
            if not isinstance(subtasks_data, list):
                logger.error(f"Gemini returned unexpected structure for subtask generation. Expected list, got {type(subtasks_data)}")
                raise TypeError("LLM response for subtask generation was not a list")
                
            # 验证子任务数据
            validated_subtasks = []
            for i, subtask in enumerate(subtasks_data):
                if not isinstance(subtask, dict):
                    logger.warning(f"Skipping non-dictionary subtask at index {i}")
                    continue
                    
                # 检查必填字段
                if 'id' not in subtask or 'name' not in subtask or 'description' not in subtask or 'complexity' not in subtask:
                    logger.warning(f"Skipping subtask at index {i} due to missing required fields")
                    continue
                    
                # 验证ID格式
                subtask_id = str(subtask.get('id'))
                if not subtask_id.startswith(f"{task_id}."):
                    logger.warning(f"Fixing subtask with invalid ID format: {subtask_id}")
                    subtask['id'] = f"{task_id}.{i+1}"
                
                # 清理标签：更加灵活地处理标签
                if 'tags' in subtask and isinstance(subtask['tags'], list):
                    cleaned_tags = []
                    for tag in subtask['tags']:
                        if isinstance(tag, str):
                            tag = str(tag).strip()
                            # 允许使用中文标签和带空格的标签
                            if len(tag) <= 20 and tag:
                                cleaned_tags.append(tag)
                    subtask['tags'] = cleaned_tags[:3] # 最多保留3个清理后的标签
                else:
                    subtask['tags'] = []
                
                # 确保dependencies不包含父任务ID
                if 'dependencies' in subtask and isinstance(subtask['dependencies'], list):
                    subtask['dependencies'] = [
                        dep_id for dep_id in subtask['dependencies']
                        if dep_id != task_id
                    ]
                else:
                    subtask['dependencies'] = []
                    
                validated_subtasks.append(subtask)
                
            logger.info(f"Successfully generated {len(validated_subtasks)} subtasks for task {task_id}")
            return validated_subtasks
                
        except Exception as e:
            logger.error(f"Error generating subtasks with Gemini: {e}", exc_info=True)
            raise Exception(f"Failed to generate subtasks: {e}") from e

    # Synchronous wrappers are inherited from LLMInterface 