# coding=utf-8
"""
Image Generation Tool - 图像生成工具

为 nanobot agent 提供图像生成功能，基于智谱 API (CogView-3-Flash/CogView-4)
"""

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx

from nanobot.agent.tools.base import Tool
from nanobot.config.loader import load_config


class ImageGenerationTool(Tool):
    """图像生成工具 - 使用智谱 AI (CogView-3-Flash/CogView-4)"""

    def __init__(self):
        # 从配置文件获取 API Key，备选环境变量
        config = load_config()
        self.api_key = config.providers.zhipu.api_key or os.environ.get("ZHIPU_API_KEY", "")
        self.default_model = "cogview-3-flash"
        # 默认保存到 workspace
        self.workspace = Path(config.agents.defaults.workspace).expanduser()

    @property
    def name(self) -> str:
        return "generate_image"

    @property
    def description(self) -> str:
        return "使用智谱 AI 生成图片。支持 CogView-3-Flash（免费）和 CogView-4 模型。可以根据文本描述生成各种风格的图片。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "生成图片的文本描述，详细描述你想要生成的图像内容、风格、颜色等",
                },
                "model": {
                    "type": "string",
                    "description": "使用的模型名称",
                    "enum": ["cogview-3-flash", "cogview-4-250304"],
                    "default": "cogview-3-flash",
                },
                "size": {
                    "type": "string",
                    "description": "图片尺寸",
                    "enum": [
                        "1024x1024",
                        "768x1344",
                        "864x1152",
                        "1344x768",
                        "1152x864",
                        "1440x720",
                        "720x1440",
                    ],
                    "default": "1024x1024",
                },
                "quality": {
                    "type": "string",
                    "description": "生成图像的质量，仅支持 cogview-4-250304",
                    "enum": ["standard", "hd"],
                    "default": "standard",
                },
            },
            "required": ["prompt"],
        }

    async def execute(
        self,
        prompt: str,
        model: Optional[str] = None,
        size: str = "1024x1024",
        quality: str = "standard",
    ) -> str:
        """
        执行图像生成

        Args:
            prompt: 生成图片的文本描述
            model: 使用的模型（默认为 cogview-3-flash）
            size: 图片尺寸
            quality: 图像质量（仅 cogview-4 支持 hd 模式）

        Returns:
            生成的图片本地路径或错误信息
        """
        if not self.api_key:
            return "错误: 未配置智谱 API Key。请在配置文件 (~/.nanobot/config.json) 的 providers.zhipu.apiKey 中设置，或设置环境变量 ZHIPU_API_KEY。"

        if not prompt or len(prompt.strip()) == 0:
            return "错误: prompt 不能为空，请提供图片描述文本。"

        model = model or self.default_model

        # 质量参数仅支持 cogview-4
        if model != "cogview-4-250304":
            quality = "standard"

        try:
            from zhipuai import ZhipuAI

            client = ZhipuAI(api_key=self.api_key)

            # 构建请求参数
            params = {
                "model": model,
                "prompt": prompt,
                "size": size,
            }

            # 只有 cogview-4 才支持 quality 参数
            if model == "cogview-4-250304":
                params["quality"] = quality

            response = client.images.generations(**params)

            if response.data and len(response.data) > 0:
                image_url = response.data[0].url

                # 下载图片到本地
                try:
                    local_path = await self._download_image(image_url, prompt)
                    return f"✅ 图片已保存: {local_path}"
                except Exception as e:
                    return f"⚠️ 下载失败: {str(e)}\n\n在线链接: {image_url}"
            else:
                return "错误: 未能生成图片，请稍后重试。"

        except ImportError:
            return "错误: 未安装 zhipuai 库。请运行: pip install zhipuai"
        except Exception as e:
            error_msg = str(e)
            if "api_key" in error_msg.lower():
                return f"错误: API Key 无效或已过期。请检查配置文件 (~/.nanobot/config.json) 中的 providers.zhipu.apiKey。\n\n详细信息: {error_msg}"
            elif "quota" in error_msg.lower() or "余额" in error_msg:
                return f"错误: API 配额不足或已用完。\n\n详细信息: {error_msg}"
            else:
                return f"错误: 图片生成失败\n\n详细信息: {error_msg}"

    async def _download_image(self, url: str, prompt: str) -> str:
        """下载图片到本地"""
        # 创建 images 目录
        images_dir = self.workspace / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件名：从 prompt 提取关键词 + 时间戳
        clean_prompt = "".join(c for c in prompt if c.isalnum() or c in (" ", "-", "_")).strip()
        filename_prefix = clean_prompt[:20] if clean_prompt else "image"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{filename_prefix}_{timestamp}_{unique_id}.png"

        filepath = images_dir / filename

        # 下载图片
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

            content_length = len(response.content)
            if content_length == 0:
                raise Exception("下载的图片内容为空")

            filepath.write_bytes(response.content)

            if not filepath.exists():
                raise Exception("文件保存失败")

            return str(filepath)


class ListImageModelsTool(Tool):
    """列出支持的图像生成模型工具"""

    def __init__(self):
        pass

    @property
    def name(self) -> str:
        return "list_image_models"

    @property
    def description(self) -> str:
        return "列出所有支持的图像生成模型及其特点"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self) -> str:
        """列出支持的模型"""
        models_info = """
🎨 智谱 AI 图像生成模型

1. **CogView-3-Flash** (默认)
   - 免费使用
   - 生成速度: 约 5-10 秒
   - 推荐场景: 快速生成、测试使用

2. **CogView-4-250304**
   - 付费使用
   - standard 质量: 约 5-10 秒
   - hd 质量: 约 20 秒，更精细、细节更丰富
   - 推荐场景: 高质量图像需求

📐 支持的尺寸:
- 1024x1024 (默认，正方形)
- 768x1344 (竖版)
- 864x1152 (竖版)
- 1344x768 (横版)
- 1152x864 (横版)
- 1440x720 (横版宽屏)
- 720x1440 (竖版长图)

🔑 API Key:
请设置环境变量 ZHIPU_API_KEY 获取智谱 API Key。
"""
        return models_info.strip()
