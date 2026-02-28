---
name: image-generation
description: 使用智谱 AI (CogView) 生成图片，支持文生图功能
metadata: {"nanobot":{"emoji":"🖼️","always":true}}
---

# 图像生成 (Image Generation)

使用智谱 AI 的 CogView 模型生成图片。

## API Key 配置

在配置文件 `~/.nanobot/config.json` 中配置智谱 API Key:

```json
{
  "providers": {
    "zhipu": {
      "apiKey": "your-api-key"
    }
  }
}
```

备选方案：也可以设置环境变量 `ZHIPU_API_KEY`。

获取 API Key: https://open.bigmodel.cn/

## 使用方法

### 基本图像生成

使用 `generate_image` 工具生成图片:

```
prompt: "一只可爱的小猫咪"
```

### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| prompt | string | 是 | 图片描述文本，越详细越好 |
| model | string | 否 | 模型选择: `cogview-3-flash`(默认免费) 或 `cogview-4-250304` |
| size | string | 否 | 图片尺寸，默认 `1024x1024` |
| quality | string | 否 | 质量模式，仅 cogview-4 支持: `standard`(默认) 或 `hd` |

### 可用的尺寸

- `1024x1024` - 正方形 (默认)
- `768x1344` - 竖版
- `864x1152` - 竖版
- `1344x768` - 横版
- `1152x864` - 横版
- `1440x720` - 横版宽屏
- `720x1440` - 竖版长图

## 示例

### 示例 1: 简单图片

```
prompt: "一只可爱的橘猫"
```

### 示例 2: 详细描述

```
prompt: "一只可爱的橘猫坐在草地上，阳光明媚，背景有盛开的花朵，摄影风格，浅景深"
```

### 示例 3: 指定尺寸

```
prompt: "一幅水墨画风格的山水风景"
size: "1344x768"
```

### 示例 4: 高清质量

```
prompt: "赛博朋克风格的未来城市夜景"
model: "cogview-4-250304"
quality: "hd"
```

## 模型选择建议

- **CogView-3-Flash**: 免费使用，适合快速生成、测试、简单场景
- **CogView-4**: 付费，更高质量，适合需要精细细节的商业场景

## 注意事项

1. 图片链接有效期为 30 天，请及时保存
2. prompt 描述越详细，生成效果越好
3. 避免使用侵权或不当内容
4. CogView-3-Flash 是免费的，可以无限制使用
