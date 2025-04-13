import os
import asyncio
import logging
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 设置日志
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 尝试导入OpenAILLM
try:
    from src.llm.openai import OpenAILLM
    logger.info("成功导入OpenAILLM")
except ImportError:
    logger.error("导入OpenAILLM失败，请确保路径正确")
    exit(1)

async def test_openai_llm():
    """测试OpenAI LLM基本功能"""
    try:
        # 确保有API密钥
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("未找到OPENAI_API_KEY环境变量")
            return
        
        # 实例化OpenAILLM
        llm = OpenAILLM()
        logger.info(f"成功创建OpenAILLM实例，使用模型: {llm.model_name}")
        
        # 测试生成文本
        prompt = "用中文简短介绍一下Python语言的主要特点"
        logger.info(f"测试文本生成，prompt: {prompt}")
        result = await llm.generate_text_async(prompt, temperature=0.7)
        logger.info(f"生成结果: {result[:100]}...")  # 只显示前100个字符
        
        # 测试生成结构化内容
        schema = {
            "type": "object",
            "properties": {
                "features": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "description": {"type": "string"}
                        }
                    }
                }
            }
        }
        logger.info("测试结构化内容生成")
        structured_result = await llm.generate_structured_content_async(
            prompt="列出Python的三个主要特点及其简短描述，请用中文回答",
            schema=schema,
            temperature=0.1
        )
        logger.info(f"结构化结果: {structured_result}")
        
        logger.info("OpenAI LLM测试完成")
    except Exception as e:
        logger.error(f"测试OpenAI LLM时出错: {e}", exc_info=True)

if __name__ == "__main__":
    logger.info("开始测试OpenAI LLM")
    asyncio.run(test_openai_llm()) 