# coding=utf-8
"""
Hot Search Fetcher - 热搜数据获取器

负责从 NewsNow API 抓取各大平台的热搜数据
"""

import json
import random
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

import requests


class PlatformNotSupportedError(Exception):
    """平台不支持错误"""
    pass


class HotSearchFetcher:
    """热搜数据获取器"""

    # 默认 API 地址
    DEFAULT_API_URL = "https://newsnow.busiyi.world/api/s"

    # 平台配置
    PLATFORMS = {
        "weibo": {"name": "微博热搜", "id": "weibo"},
        "zhihu": {"name": "知乎热榜", "id": "zhihu"},
        "douyin": {"name": "抖音热榜", "id": "douyin"},
        "bilibili": {"name": "B站热搜", "id": "bilibili"},
        "baidu": {"name": "百度热搜", "id": "baidu"},
        "toutiao": {"name": "今日头条", "id": "toutiao"},
        "pengpai": {"name": "澎湃新闻", "id": "pengpai"},
        "sina": {"name": "新浪新闻", "id": "sina"},
        "netease": {"name": "网易新闻", "id": "netease"},
        "tencent": {"name": "腾讯新闻", "id": "tencent"},
        "thepaper": {"name": "界面新闻", "id": "thepaper"},
        "sputniknewscn": {"name": "俄罗斯卫星通讯社", "id": "sputniknewscn"},
        "cankaoxiaoxi": {"name": "参考消息", "id": "cankaoxiaoxi"},
        "ifeng": {"name": "凤凰网", "id": "ifeng"},
        "guancha": {"name": "观察者网", "id": "guancha"},
    }

    # 默认请求头
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    }

    def __init__(
        self,
        api_url: Optional[str] = None,
        proxy_url: Optional[str] = None,
        request_interval: int = 100,
        max_retries: int = 2,
        timeout: int = 10,
    ):
        """
        初始化热搜数据获取器

        Args:
            api_url: API 基础 URL（可选，默认使用 NewsNow API）
            proxy_url: 代理服务器 URL（可选）
            request_interval: 请求间隔（毫秒，默认100ms）
            max_retries: 最大重试次数（默认2次）
            timeout: 请求超时时间（秒，默认10秒）
        """
        self.api_url = api_url or self.DEFAULT_API_URL
        self.proxy_url = proxy_url
        self.request_interval = request_interval
        self.max_retries = max_retries
        self.timeout = timeout

        self.proxies = None
        if self.proxy_url:
            self.proxies = {"http": self.proxy_url, "https": self.proxy_url}

    def _make_request(self, url: str) -> Tuple[Optional[dict], Optional[str]]:
        """
        发起 HTTP 请求，支持重试

        Args:
            url: 请求 URL

        Returns:
            (响应数据, 错误信息) 元组
        """
        retries = 0
        last_error = None

        while retries <= self.max_retries:
            try:
                response = requests.get(
                    url,
                    proxies=self.proxies,
                    headers=self.DEFAULT_HEADERS,
                    timeout=self.timeout,
                )
                response.raise_for_status()

                data = response.json()

                status = data.get("status", "unknown")
                if status not in ["success", "cache"]:
                    return None, f"API 返回异常状态: {status}"

                return data, None

            except requests.Timeout:
                last_error = f"请求超时 ({self.timeout}s)"
            except requests.RequestException as e:
                last_error = f"请求失败: {e}"
            except json.JSONDecodeError:
                last_error = "JSON 解析失败"
            except Exception as e:
                last_error = f"未知错误: {e}"

            retries += 1
            if retries <= self.max_retries:
                wait_time = random.uniform(3, 5) + (retries - 1) * random.uniform(1, 2)
                time.sleep(wait_time)

        return None, last_error

    def fetch_platform(self, platform_id: str) -> dict:
        """
        获取单个平台的热搜数据

        Args:
            platform_id: 平台ID

        Returns:
            包含热搜数据的字典

        Raises:
            PlatformNotSupportedError: 如果平台不支持
        """
        if platform_id not in self.PLATFORMS:
            raise PlatformNotSupportedError(f"不支持的平台: {platform_id}")

        platform_config = self.PLATFORMS[platform_id]
        url = f"{self.api_url}?id={platform_config['id']}&latest"

        data, error = self._make_request(url)

        if error:
            return {
                "platform_id": platform_id,
                "platform_name": platform_config["name"],
                "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "success": False,
                "error": error,
                "items": [],
            }

        # 解析数据
        items = []
        for index, item in enumerate(data.get("items", []), 1):
            title = item.get("title")
            if title is None or isinstance(title, float) or not str(title).strip():
                continue

            title = str(title).strip()
            url_field = item.get("url", "")
            mobile_url = item.get("mobileUrl", "")
            heat = item.get("heat", "")

            items.append({
                "rank": index,
                "title": title,
                "url": url_field,
                "mobile_url": mobile_url,
                "heat": heat,
            })

        return {
            "platform_id": platform_id,
            "platform_name": platform_config["name"],
            "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "success": True,
            "items": items,
        }

    def fetch_multiple(self, platform_ids: List[str]) -> Dict[str, dict]:
        """
        获取多个平台的热搜数据

        Args:
            platform_ids: 平台ID列表

        Returns:
            以平台ID为键的数据字典
        """
        results = {}

        for i, platform_id in enumerate(platform_ids):
            try:
                results[platform_id] = self.fetch_platform(platform_id)
            except PlatformNotSupportedError as e:
                results[platform_id] = {
                    "platform_id": platform_id,
                    "platform_name": platform_id,
                    "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "success": False,
                    "error": str(e),
                    "items": [],
                }

            # 请求间隔（除了最后一个）
            if i < len(platform_ids) - 1:
                actual_interval = self.request_interval + random.randint(-10, 20)
                actual_interval = max(50, actual_interval)
                time.sleep(actual_interval / 1000)

        return results

    def fetch_all(self) -> Dict[str, dict]:
        """
        获取所有支持平台的热搜数据

        Returns:
            以平台ID为键的数据字典
        """
        return self.fetch_multiple(list(self.PLATFORMS.keys()))

    def get_supported_platforms(self) -> List[dict]:
        """
        获取所有支持的平台列表

        Returns:
            平台信息列表
        """
        return [
            {"id": k, "name": v["name"]}
            for k, v in self.PLATFORMS.items()
        ]

    def format_as_text(self, data: Union[dict, Dict[str, dict]], max_items: int = 10) -> str:
        """
        将热搜数据格式化为文本

        Args:
            data: 单个平台或多个平台的数据
            max_items: 每个平台显示的最大条目数

        Returns:
            格式化后的文本
        """
        lines = []

        # 判断是单个平台还是多个平台
        if "platform_id" in data:
            # 单个平台
            platforms = [data]
        else:
            # 多个平台
            platforms = list(data.values())

        for platform in platforms:
            platform_name = platform.get("platform_name", "未知平台")
            items = platform.get("items", [])
            success = platform.get("success", False)
            error = platform.get("error", "")

            lines.append(f"\n📰 {platform_name}")
            lines.append("=" * 40)

            if not success:
                lines.append(f"❌ 获取失败: {error}")
                continue

            if not items:
                lines.append("暂无数据")
                continue

            for item in items[:max_items]:
                rank = item.get("rank", 0)
                title = item.get("title", "")
                heat = item.get("heat", "")

                heat_str = f" [{heat}]" if heat else ""
                lines.append(f"{rank:2d}. {title}{heat_str}")

        return "\n".join(lines)


# 便捷函数
def get_hot_search(platform: Optional[str] = None, platforms: Optional[List[str]] = None) -> Union[dict, Dict[str, dict]]:
    """
    获取热搜数据（便捷函数）

    Args:
        platform: 单个平台ID
        platforms: 多个平台ID列表

    Returns:
        热搜数据

    Examples:
        >>> get_hot_search("weibo")  # 获取微博热搜
        >>> get_hot_search(platforms=["weibo", "zhihu"])  # 获取多个平台
        >>> get_hot_search()  # 获取所有平台
    """
    fetcher = HotSearchFetcher()

    if platform:
        return fetcher.fetch_platform(platform)
    elif platforms:
        return fetcher.fetch_multiple(platforms)
    else:
        return fetcher.fetch_all()


if __name__ == "__main__":
    # 命令行测试
    import argparse

    parser = argparse.ArgumentParser(description="获取热搜数据")
    parser.add_argument("--platforms", nargs="+", help="指定平台列表")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")
    parser.add_argument("--max-items", type=int, default=10, help="每个平台显示的最大条目数")

    args = parser.parse_args()

    fetcher = HotSearchFetcher()

    if args.platforms:
        data = fetcher.fetch_multiple(args.platforms)
    else:
        data = fetcher.fetch_all()

    if args.format == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(fetcher.format_as_text(data, max_items=args.max_items))
