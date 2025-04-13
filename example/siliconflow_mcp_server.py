# 描述：基于 SiliconFlow 的 Kolors 图像生成服务，专门设计用于与 Cursor IDE 集成

import os
import logging
from sys import stdin, stdout
import json
from fastmcp import FastMCP
import mcp.types as types
import base64
import requests
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor
import asyncio
from pathlib import Path
import urllib.request

# API 配置
SILICONFLOW_API_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
if not SILICONFLOW_API_KEY:
    raise ValueError("未设置 SILICONFLOW_API_KEY 环境变量，请先设置")

# 服务配置
CONFIG = {
    "api": {
        "url": "https://api.siliconflow.cn/v1/images/generations",
        "model": "Kwai-Kolors/Kolors",
        "timeout": 60,
        "max_retries": 3,
        "retry_delay": 5
    },
    "image": {
        "max_width": 1024,
        "max_height": 1024,
        "default_size": "1024x1024",
        "allowed_sizes": ["1024x1024", "960x1280", "768x1024", "720x1440", "720x1280"],
        "default_steps": 30,
        "default_guidance_scale": 7.5,
        "max_batch_size": 1
    },
    "output": {
        "base_folder": str(Path.home() / "Documents/siliconflow_images"),
        "allowed_extensions": [".png", ".jpg", ".jpeg"],
        "default_extension": ".png"
    }
}

def validate_save_path(save_folder: str) -> tuple[bool, str, Path]:
    """验证保存路径
    
    Args:
        save_folder: 保存目录路径
        
    Returns:
        tuple: (是否有效, 错误信息, Path对象)
    """
    try:
        # 转换为 Path 对象
        save_path = Path(save_folder)
        
        # 检查是否是绝对路径
        if not save_path.is_absolute():
            example_path = Path.home() / "Documents/images"
            return False, f"请使用绝对路径。例如: {example_path}", save_path
            
        # 检查父目录是否存在且有写权限
        parent = save_path.parent
        if not parent.exists():
            return False, f"父目录不存在: {parent}", save_path
            
        # 尝试创建目录以测试权限
        try:
            save_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            return False, f"没有权限创建或访问目录: {save_path}", save_path
            
        # 测试写权限
        test_file = save_path / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
        except PermissionError:
            return False, f"没有目录的写入权限: {save_path}", save_path
            
        return True, "", save_path
        
    except Exception as e:
        return False, f"路径验证失败: {str(e)}", Path(save_folder)

# 配置编码
stdin.reconfigure(encoding='utf-8')
stdout.reconfigure(encoding='utf-8')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建 FastMCP 实例
mcp = FastMCP("siliconflow-kolors-generation")

class ImageGenerator:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
            "Content-Type": "application/json"
        })
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def generate(self, prompt: str, negative_prompt: str = "", image_size: str = None, 
                      steps: int = None, guidance_scale: float = None, seed: int = None,
                      batch_size: int = 1) -> List[str]:
        """异步生成图像
        
        Args:
            prompt: 图片生成提示词
            negative_prompt: 负面提示词
            image_size: 图片尺寸 (例如 "1024x1024")
            steps: 生成步数
            guidance_scale: 引导比例
            seed: 随机种子
            batch_size: 生成图片数量
            
        Returns:
            List[str]: 生成的图片的URL列表
        """
        image_size = image_size or CONFIG["image"]["default_size"]
        steps = steps or CONFIG["image"]["default_steps"]
        guidance_scale = guidance_scale or CONFIG["image"]["default_guidance_scale"]

        # 构建请求参数
        payload = {
            "model": CONFIG["api"]["model"],
            "prompt": prompt,
            "image_size": image_size,
            "num_inference_steps": steps,
            "guidance_scale": guidance_scale,
            "batch_size": min(batch_size, CONFIG["image"]["max_batch_size"])
        }
        
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
            
        if seed is not None:
            payload["seed"] = seed

        logger.info(f"API请求参数: {json.dumps(payload, ensure_ascii=False)}")

        for attempt in range(CONFIG["api"]["max_retries"]):
            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    self.executor,
                    lambda: self.session.post(
                        CONFIG["api"]["url"],
                        json=payload,
                        timeout=CONFIG["api"]["timeout"]
                    )
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"API响应状态码: {response.status_code}")
                    if 'images' in data and len(data['images']) > 0:
                        # 响应格式: {"images": [{"url": "..."}, ...], "timings": {"inference": 123}, "seed": 123}
                        image_urls = [img.get('url', '') for img in data['images'] if img.get('url')]
                        logger.info(f"获取到 {len(image_urls)} 个图像URL")
                        return image_urls
                    else:
                        logger.error(f"API响应格式不正确: {data}")
                elif response.status_code == 429:  # Rate limit
                    logger.warning(f"API请求达到频率限制 (尝试 {attempt + 1}/{CONFIG['api']['max_retries']})")
                    if attempt < CONFIG["api"]["max_retries"] - 1:
                        await asyncio.sleep(CONFIG["api"]["retry_delay"])
                        continue
                
                logger.error(f"API请求失败: {response.status_code}")
                logger.error(f"响应: {response.text}")
                return []
                
            except requests.Timeout:
                logger.error(f"API请求超时 (尝试 {attempt + 1}/{CONFIG['api']['max_retries']})")
                if attempt < CONFIG["api"]["max_retries"] - 1:
                    await asyncio.sleep(CONFIG["api"]["retry_delay"])
                    continue
                return []
            except Exception as e:
                logger.error(f"生成图片时出错: {str(e)}")
                return []
        
        return []

    async def download_image(self, url: str, save_path: Path) -> bool:
        """下载图像
        
        Args:
            url: 图像URL
            save_path: 保存路径
            
        Returns:
            bool: 是否成功下载
        """
        try:
            loop = asyncio.get_event_loop()
            
            def download():
                opener = urllib.request.build_opener()
                opener.addheaders = [('Authorization', f'Bearer {SILICONFLOW_API_KEY}')]
                urllib.request.install_opener(opener)
                urllib.request.urlretrieve(url, save_path)
                return True
                
            result = await loop.run_in_executor(self.executor, download)
            return result
        except Exception as e:
            logger.error(f"下载图像失败: {str(e)}")
            return False

# 创建生成器实例
generator = ImageGenerator()

@mcp.tool("use_description")
async def list_tools():
    """列出所有可用的工具及其参数"""
    example_path = str(Path.home() / "Documents/images")
    return {
        "tools": [
            {
                "name": "generate_image",
                "description": "使用硅基流动的Kolors模型生成图片",
                "parameters": {
                    "prompt": {
                        "type": "string",
                        "description": "图片生成提示词，建议不超过500字符",
                        "required": True
                    },
                    "file_name": {
                        "type": "string",
                        "description": "保存的文件名(不含路径，如果没有后缀则默认使用.png)",
                        "required": True
                    },
                    "save_folder": {
                        "type": "string",
                        "description": f"保存目录的绝对路径 (例如: {example_path})",
                        "required": True
                    },
                    "negative_prompt": {
                        "type": "string",
                        "description": "负面提示词，描述不希望在图像中出现的内容",
                        "required": False
                    },
                    "image_size": {
                        "type": "string",
                        "description": f"图像尺寸 (可选值: {', '.join(CONFIG['image']['allowed_sizes'])}，默认: {CONFIG['image']['default_size']})",
                        "required": False
                    },
                    "steps": {
                        "type": "number",
                        "description": f"生成步数(可选,默认{CONFIG['image']['default_steps']})",
                        "required": False
                    },
                    "guidance_scale": {
                        "type": "number",
                        "description": f"引导比例(可选,默认{CONFIG['image']['default_guidance_scale']}),控制图像与提示的匹配程度",
                        "required": False
                    },
                    "seed": {
                        "type": "number",
                        "description": "随机种子(可选),设置相同的种子可以生成相似的图像",
                        "required": False
                    }
                }
            }
        ]
    }

@mcp.tool("generate_image")
async def generate_image(prompt: str, file_name: str, save_folder: str, negative_prompt: str = "", 
                        image_size: str = None, steps: int = None, guidance_scale: float = None, 
                        seed: int = None) -> list[types.TextContent]:
    """生成图片
    
    Args:
        prompt: 图片生成提示词
        file_name: 保存的文件名
        save_folder: 保存目录路径
        negative_prompt: 负面提示词
        image_size: 图像尺寸
        steps: 生成步数
        guidance_scale: 引导比例
        seed: 随机种子
        
    Returns:
        List: 包含生成结果的 JSON 字符串
    """
    logger.info(f"收到生成请求: {prompt}")
    
    try:
        # 参数验证
        if not prompt:
            raise ValueError("prompt不能为空")
            
        if not save_folder:
            save_folder = CONFIG["output"]["base_folder"]
            
        # 验证保存路径
        is_valid, error_msg, save_path = validate_save_path(save_folder)
        if not is_valid:
            raise ValueError(error_msg)
            
        # 验证图像尺寸
        if image_size and image_size not in CONFIG["image"]["allowed_sizes"]:
            raise ValueError(f"不支持的图像尺寸: {image_size}，可选值: {', '.join(CONFIG['image']['allowed_sizes'])}")
            
        # 确保文件名有正确的扩展名
        file_ext = Path(file_name).suffix.lower()
        if not file_ext or file_ext not in CONFIG["output"]["allowed_extensions"]:
            file_name = f"{Path(file_name).stem}{CONFIG['output']['default_extension']}"
            
        # 生成图片
        image_urls = await generator.generate(
            prompt, negative_prompt, image_size, steps, guidance_scale, seed
        )
        
        if not image_urls:
            raise Exception("未能生成图片")
            
        # 下载并保存图片
        saved_images = []
        for i, image_url in enumerate(image_urls):
            try:
                # 构造保存路径
                if i > 0:
                    current_save_path = save_path / f"{Path(file_name).stem}_{i}{Path(file_name).suffix}"
                else:
                    current_save_path = save_path / file_name
                    
                # 下载图片
                download_success = await generator.download_image(image_url, current_save_path)
                if download_success:
                    saved_images.append(str(current_save_path))
                    logger.info(f"图片已保存: {current_save_path}")
                else:
                    logger.error(f"下载图片失败: {image_url}")
            except Exception as e:
                logger.error(f"保存图片失败: {str(e)}")
                continue
        
        if not saved_images:
            raise Exception(
                "所有图片保存失败。请确保:\n"
                "1. 使用绝对路径 (例如: /Users/username/Documents/images)\n"
                "2. 目录具有写入权限\n"
                "3. 磁盘空间充足\n"
                "4. 图片URL有效且可访问"
            )
        
        return [
            types.TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "error": None,
                    "images": saved_images,
                    "settings": {
                        "prompt": prompt,
                        "negative_prompt": negative_prompt,
                        "image_size": image_size or CONFIG["image"]["default_size"],
                        "steps": steps or CONFIG["image"]["default_steps"],
                        "guidance_scale": guidance_scale or CONFIG["image"]["default_guidance_scale"],
                        "seed": seed
                    }
                }, ensure_ascii=False)
            )
        ]

    except Exception as e:
        error_msg = str(e)
        logger.error(f"生成图片失败: {error_msg}")
        return [
            types.TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": error_msg,
                    "images": []
                }, ensure_ascii=False)
            )
        ]

if __name__ == "__main__":
    logger.info("启动 SiliconFlow Kolors 图像生成服务...")
    mcp.run() 