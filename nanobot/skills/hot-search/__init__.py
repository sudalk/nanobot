"""
Hot Search Skill - 获取各大平台热搜榜单

基于 NewsNow API 的热搜数据获取工具
"""

from .fetcher import HotSearchFetcher, PlatformNotSupportedError

__all__ = ["HotSearchFetcher", "PlatformNotSupportedError"]
__version__ = "1.0.0"
