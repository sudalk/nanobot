# Hot Search Skill

## Description

获取各大平台的热搜榜单数据，包括微博、知乎、抖音、B站等平台的热门话题。

## Requirements

- Python >= 3.11
- requests >= 2.32.0

## Installation

```bash
pip install requests
```

## Usage

### 获取单个平台热搜

```python
from nanobot.skills.hot_search import HotSearchFetcher

fetcher = HotSearchFetcher()

# 获取微博热搜
weibo_data = fetcher.fetch_platform("weibo")

# 获取知乎热榜
zhihu_data = fetcher.fetch_platform("zhihu")
```

### 获取多个平台热搜

```python
# 获取所有支持的平台
all_data = fetcher.fetch_all()

# 获取指定平台列表
platforms = ["weibo", "zhihu", "douyin", "bilibili"]
data = fetcher.fetch_multiple(platforms)
```

### 命令行使用

```bash
# 获取所有平台
python -m nanobot.skills.hot_search

# 获取指定平台
python -m nanobot.skills.hot_search --platforms weibo zhihu

# 输出为 JSON
python -m nanobot.skills.hot_search --format json
```

## Supported Platforms

| 平台ID | 平台名称 | 说明 |
|--------|----------|------|
| weibo | 微博热搜 | 微博实时热搜榜 |
| zhihu | 知乎热榜 | 知乎全站热榜 |
| douyin | 抖音热榜 | 抖音实时热点 |
| bilibili | B站热搜 | 哔哩哔哩搜索热榜 |
| baidu | 百度热搜 | 百度搜索风云榜 |
| toutiao | 今日头条 | 头条热榜 |
| pengpai | 澎湃新闻 | 澎湃新闻热榜 |
| sina | 新浪新闻 | 新浪新闻热榜 |
| netease | 网易新闻 | 网易新闻热榜 |
| tencent | 腾讯新闻 | 腾讯新闻热榜 |
| thepaper | 界面新闻 | 界面新闻热榜 |
| sputniknewscn | 俄罗斯卫星通讯社 | 国际新闻 |
| cankaoxiaoxi | 参考消息 | 参考消息热榜 |
| ifeng | 凤凰网 | 凤凰网热榜 |
| guancha | 观察者网 | 观察者网热榜 |

## Data Format

### 返回数据结构

```python
{
    "platform_id": "weibo",
    "platform_name": "微博热搜",
    "fetch_time": "2026-02-14 10:30:00",
    "items": [
        {
            "rank": 1,
            "title": "热搜标题",
            "url": "https://...",
            "mobile_url": "https://m...",
            "heat": "1234567",  # 热度值（部分平台）
        }
    ]
}
```

## Configuration

在 `~/.nanobot/config.json` 中添加配置：

```json
{
  "tools": {
    "hot_search": {
      "default_platforms": ["weibo", "zhihu", "douyin"],
      "max_items": 20,
      "request_timeout": 10,
      "cache_ttl": 300
    }
  }
}
```

## API Reference

### HotSearchFetcher

#### `__init__(api_url=None, proxy_url=None)`

初始化获取器。

**参数：**
- `api_url`: API 基础 URL（可选，默认使用 NewsNow API）
- `proxy_url`: 代理服务器 URL（可选）

#### `fetch_platform(platform_id: str) -> dict`

获取单个平台的热搜数据。

**参数：**
- `platform_id`: 平台ID

**返回：**
- 包含热搜数据的字典

#### `fetch_multiple(platform_ids: list) -> dict`

获取多个平台的热搜数据。

**参数：**
- `platform_ids`: 平台ID列表

**返回：**
- 以平台ID为键的数据字典

#### `fetch_all() -> dict`

获取所有支持平台的热搜数据。

**返回：**
- 以平台ID为键的数据字典

## Error Handling

```python
from nanobot.skills.hot_search import HotSearchFetcher, PlatformNotSupportedError

fetcher = HotSearchFetcher()

try:
    data = fetcher.fetch_platform("unsupported_platform")
except PlatformNotSupportedError as e:
    print(f"不支持的的平台: {e}")
except Exception as e:
    print(f"获取失败: {e}")
```

## Rate Limiting

- 默认请求间隔：100ms
- 最大重试次数：2次
- 重试等待时间：3-5秒随机

## Notes

1. 数据来源于 [NewsNow](https://newsnow.busiyi.world/) API
2. 部分平台可能需要特殊处理（如登录、反爬）
3. 建议添加适当的缓存机制，避免频繁请求
4. 遵守各平台的使用条款和 robots.txt

## License

MIT
