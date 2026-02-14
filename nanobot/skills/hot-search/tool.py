# coding=utf-8
"""
Hot Search Tool - 热搜工具

为 nanobot agent 提供热搜获取功能的工具
"""

from typing import Any, Optional

from nanobot.agent.tools.base import Tool
from .fetcher import HotSearchFetcher


class HotSearchTool(Tool):
    """热搜获取工具"""

    def __init__(self):
        self.fetcher = HotSearchFetcher()

    @property
    def name(self) -> str:
        return "get_hot_search"

    @property
    def description(self) -> str:
        return "获取各大平台的热搜榜单数据，支持微博、知乎、抖音、B站等平台"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "description": "平台ID，如 weibo(微博)、zhihu(知乎)、douyin(抖音)、bilibili(B站)等。不指定则获取所有平台",
                    "enum": [
                        "weibo", "zhihu", "douyin", "bilibili", "baidu",
                        "toutiao", "pengpai", "sina", "netease", "tencent",
                        "thepaper", "sputniknewscn", "cankaoxiaoxi", "ifeng", "guancha"
                    ],
                },
                "platforms": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "多个平台ID列表，用于同时获取多个平台的热搜",
                },
                "max_items": {
                    "type": "integer",
                    "description": "每个平台返回的最大条目数（默认10条）",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 10,
                },
                "format": {
                    "type": "string",
                    "description": "输出格式",
                    "enum": ["text", "json"],
                    "default": "text",
                },
            },
        }

    async def execute(
        self,
        platform: Optional[str] = None,
        platforms: Optional[list] = None,
        max_items: int = 10,
        format: str = "text",
    ) -> str:
        """
        执行热搜获取

        Args:
            platform: 单个平台ID
            platforms: 多个平台ID列表
            max_items: 每个平台返回的最大条目数
            format: 输出格式（text 或 json）

        Returns:
            格式化后的热搜数据
        """
        try:
            if platform:
                # 获取单个平台
                data = self.fetcher.fetch_platform(platform)
            elif platforms:
                # 获取多个平台
                data = self.fetcher.fetch_multiple(platforms)
            else:
                # 获取所有平台
                data = self.fetcher.fetch_all()

            if format == "json":
                import json
                return json.dumps(data, ensure_ascii=False, indent=2)
            else:
                return self.fetcher.format_as_text(data, max_items=max_items)

        except Exception as e:
            return f"获取热搜失败: {str(e)}"


class ListHotSearchPlatformsTool(Tool):
    """列出支持的热搜平台工具"""

    def __init__(self):
        self.fetcher = HotSearchFetcher()

    @property
    def name(self) -> str:
        return "list_hot_search_platforms"

    @property
    def description(self) -> str:
        return "列出所有支持的热搜平台"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self) -> str:
        """列出所有支持的平台"""
        platforms = self.fetcher.get_supported_platforms()

        lines = ["📱 支持的热搜平台：", ""]
        for platform in platforms:
            lines.append(f"- {platform['id']}: {platform['name']}")

        return "\n".join(lines)
