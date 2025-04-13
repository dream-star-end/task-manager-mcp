from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
import logging
import asyncio

logger = logging.getLogger(__name__)

class LLMInterface(ABC):
    """大语言模型调用的抽象基类接口"""

    def __init__(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """
        初始化 LLM 客户端。

        Args:
            api_key: API 密钥 (可选, 某些模型可能需要)。
            config: 其他配置选项 (可选)。
        """
        self.api_key = api_key
        self.config = config or {}
        logger.info(f"Initializing {self.__class__.__name__}")

    @abstractmethod
    async def generate_text_async(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> str:
        """
        生成文本内容 (异步)。

        Args:
            prompt: 输入的提示词。
            temperature: 控制生成文本的随机性 (0.0 - 1.0)。
            max_tokens: 生成的最大 token 数量 (可选)。
            **kwargs: 其他特定于模型的参数。

        Returns:
            生成的文本字符串。

        Raises:
            Exception: 如果 LLM 调用失败。
        """
        pass

    @abstractmethod
    async def generate_structured_content_async(
        self,
        prompt: str,
        schema: Dict[str, Any],
        temperature: float = 0.1,
        **kwargs: Any
    ) -> Any:
        """
        根据提供的 Schema 生成结构化内容 (通常是 JSON) (异步)。

        Args:
            prompt: 输入的提示词。
            schema: 期望输出的 JSON Schema 定义。
            temperature: 控制生成的随机性 (通常较低以保证结构)。
            **kwargs: 其他特定于模型的参数。

        Returns:
            解析后的结构化数据 (例如，列表或字典)。

        Raises:
            Exception: 如果无法生成或解析。
        """
        pass

    @abstractmethod
    async def parse_prd_to_tasks_async(
        self,
        prd_content: str,
        **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """
        解析 PRD 文档内容，提取结构化的任务列表 (异步)。

        这个方法封装了针对特定 LLM 的 prompt 工程和 schema 定义，
        旨在直接从 PRD 文本生成符合预定结构的任务数据。

        Args:
            prd_content: PRD 文档的原始内容。
            **kwargs: 其他特定于模型实现的参数（例如，指定解析温度等）。

        Returns:
            一个字典列表，每个字典代表一个任务，包含如 name, description,
            priority, estimated_hours, dependencies (by name), tags 等键。
            返回的结构应该与 PrdParser 中处理的结构一致。

        Raises:
            Exception: 如果 LLM 调用失败或无法解析出期望的任务列表结构。
        """
        pass

    @abstractmethod
    async def generate_subtasks_for_task_async(
        self,
        task_info: Dict[str, Any],
        num_subtasks: int = 5,
        temperature: float = 0.2,
        **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """
        为指定的任务生成子任务列表 (异步)。
        
        这个方法负责为现有任务生成子任务，包括层级ID、依赖关系等。
        具体实现由各LLM子类处理，包括提示词设计和模型调用逻辑。
        
        Args:
            task_info: 父任务的信息字典，包含id、name、description等字段。
            num_subtasks: 希望生成的子任务数量。
            temperature: 控制生成随机性的温度参数。
            **kwargs: 其他特定于模型实现的参数。
            
        Returns:
            一个字典列表，每个字典代表一个子任务，包含id、name、description、
            priority、estimated_hours、dependencies、tags等字段。
            子任务ID应遵循"{父任务ID}.序号"的格式。
            
        Raises:
            Exception: 如果LLM调用失败或无法生成有效的子任务列表。
        """
        pass

    # --- Synchronous Wrappers (Optional, use with caution) ---

    def _run_async_task(self, coro):
        """简单的同步执行异步任务的辅助函数。
        注意：这会在一个新的事件循环中运行任务。
        如果在已有运行事件循环的异步环境中使用，请直接 await 异步方法。
        """
        # 始终在一个新的事件循环中运行 coro
        # 这对于从同步代码调用是安全的，但效率低于在异步代码中直接 await
        try:
            return asyncio.run(coro)
        except RuntimeError as e:
            # asyncio.run() 在某些嵌套场景下（如已在运行的循环中）会抛出 RuntimeError
            # 记录错误，因为同步包装器不应在这种情况下使用
            logger.error(f"Error running async task synchronously: {e}. "
                         f"Consider using the async method directly in an async environment.")
            raise

    def generate_text(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> str:
        """
        生成文本内容 (同步)。

        注意: 这是异步方法的同步包装器。在异步环境 (如 FastAPI) 中，
              强烈建议直接调用 `generate_text_async`。
        """
        logger.warning("Calling synchronous wrapper 'generate_text'. Prefer 'generate_text_async' in async environments.")
        return self._run_async_task(
            self.generate_text_async(prompt, temperature, max_tokens, **kwargs)
        )

    def generate_structured_content(
        self,
        prompt: str,
        schema: Dict[str, Any],
        temperature: float = 0.1,
        **kwargs: Any
    ) -> Any:
        """
        根据提供的 Schema 生成结构化内容 (同步)。

        注意: 这是异步方法的同步包装器。在异步环境 (如 FastAPI) 中，
              强烈建议直接调用 `generate_structured_content_async`。
        """
        logger.warning("Calling synchronous wrapper 'generate_structured_content'. Prefer 'generate_structured_content_async' in async environments.")
        return self._run_async_task(
            self.generate_structured_content_async(prompt, schema, temperature, **kwargs)
        ) 