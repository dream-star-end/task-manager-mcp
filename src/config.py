import os
import logging
from typing import Optional

# 将项目根目录添加到Python路径 (如果需要从不同地方运行此文件)
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from src.llm.base import LLMInterface
    from src.llm.gemini import GeminiLLM
    from src.llm.openai import OpenAILLM  # 导入OpenAILLM实现
except (ImportError, ValueError):
    # Fallback for potential relative import issues
    from llm.base import LLMInterface
    from llm.gemini import GeminiLLM
    from llm.openai import OpenAILLM  # 导入OpenAILLM实现

logger = logging.getLogger(__name__)

def get_llm_client() -> Optional[LLMInterface]:
    """
    创建LLM客户端实例，基于环境变量配置。

    读取LLM_PROVIDER环境变量确定使用哪种LLM实现。
    读取GEMINI_API_KEY或OPENAI_API_KEY等凭据。

    返回:
        实现LLMInterface的实例，如果配置缺失或无效则返回None。
    """
    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    logger.info(f"配置的LLM提供商: {provider}")

    try:
        if provider == "gemini":
            # GeminiLLM从环境变量读取GEMINI_API_KEY
            # 如果检测到代理设置也会记录日志
            client = GeminiLLM()
            logger.info("创建GeminiLLM客户端成功")
            return client
        elif provider == "openai":
            # OpenAILLM从环境变量读取OPENAI_API_KEY
            # 如果检测到代理设置也会记录日志
            client = OpenAILLM()
            logger.info("创建OpenAILLM客户端成功")
            return client
        else:
            logger.error(f"不支持的LLM提供商: {provider}")
            return None
    except (ValueError, RuntimeError, ImportError) as e:
        # 捕获客户端初始化过程中的潜在错误（例如，缺少API密钥、配置错误）
        logger.error(f"初始化'{provider}'提供商的LLM客户端失败: {e}", exc_info=True)
        # 添加更具体的错误信息以便排查
        if provider == "gemini" and "GOOGLE_API_KEY" not in os.environ:
            logger.error("未找到GOOGLE_API_KEY环境变量，请确保已设置")
        elif provider == "openai" and "OPENAI_API_KEY" not in os.environ:
            logger.error("未找到OPENAI_API_KEY环境变量，请确保已设置")
        return None

# Example usage (you would typically call get_llm_client from your main app setup):
# if __name__ == "__main__":
#     # Configure logging basic setup for standalone testing
#     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     
#     # You might need to set environment variables before running this directly
#     # e.g., export GEMINI_API_KEY="your_key"
#     # export LLM_PROVIDER="gemini"
#     # export HTTPS_PROXY="http://your.proxy.server:port"
#     
#     llm_instance = get_llm_client()
#     
#     if llm_instance:
#         print(f"Successfully created LLM client: {type(llm_instance).__name__}")
#         # You could potentially test a method here if needed, adapting for async
#         # import asyncio
#         # async def test_call():
#         #     try:
#         #         # Replace with an actual test, e.g., simple text generation
#         #         result = await llm_instance.generate_text_async("Hello!") 
#         #         print(f"Test call successful: {result[:50]}...")
#         #     except Exception as test_e:
#         #         print(f"Test call failed: {test_e}")
#         # asyncio.run(test_call())
#     else:
#         print("Failed to create LLM client based on environment settings.") 

# 设置日志记录
def setup_logging():
    """
    配置日志记录。
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

# 如果此文件作为主程序运行，可以用于测试LLM客户端
if __name__ == "__main__":
    setup_logging()
    client = get_llm_client()
    if client:
        # 这里可以添加测试代码
        print(f"成功创建LLM客户端: {type(client).__name__}")
    else:
        print("LLM客户端创建失败") 