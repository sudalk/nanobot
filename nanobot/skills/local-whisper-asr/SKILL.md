---
name: local-whisper-asr
description: Local Whisper ASR transcription skill. Uses OpenAI's Whisper model running locally in a Python virtual environment for speech-to-text transcription. No API key required, all processing happens on your machine. Supports multiple languages and output formats (txt, srt, lrc).
---

# Local Whisper ASR

本地 Whisper 语音识别工具 - 完全本地运行的语音转文字解决方案

## Overview

This skill provides local speech-to-text transcription using OpenAI's Whisper model. All processing happens on your machine - no data is sent to external APIs, no API keys required.

## Features

- **完全本地运行**: 所有处理在本地完成，保护隐私
- **无需 API Key**: 不需要任何云服务 API key
- **多语言支持**: 支持中文、英文、日文等多种语言
- **自动虚拟环境**: 自动创建和管理 Python 虚拟环境
- **自动模型下载**: 首次使用时自动下载模型文件
- **多种输出格式**: 支持 txt、srt、lrc 格式

## Requirements

- Python 3.8+
- FFmpeg (音频处理)
- 约 3GB 磁盘空间（用于模型文件）

## Installation

### 1. 安装 FFmpeg

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update && sudo apt install ffmpeg
```

**Windows:**
下载并安装：https://ffmpeg.org/download.html

### 2. 配置

在 `~/.nanobot/config.json` 中配置：

```json
{
  "tools": {
    "local_whisper": {
      "enabled": true,
      "model": "base",
      "device": "auto",
      "compute_type": "int8"
    }
  }
}
```

### Python 虚拟环境路径

**重要**: Whisper 安装在 nanobot 项目的虚拟环境中：
- **路径**: `/Users/likang/geminicode/Agent/nanobot/.venv`
- **Python**: `/Users/likang/geminicode/Agent/nanobot/.venv/bin/python`

使用时请用以下方式激活：
```bash
source /Users/likang/geminicode/Agent/nanobot/.venv/bin/activate
python nanobot/skills/local-whisper-asr/scripts/whisper_transcribe.py <音频文件>
```

### 配置选项

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `enabled` | 是否启用本地 Whisper | true |
| `model` | 模型大小: tiny, base, small, medium, large | base |
| `device` | 运行设备: auto, cpu, cuda | auto |
| `compute_type` | 计算类型: int8, float16, float32 | int8 |

### 模型大小对比

| 模型 | 大小 | 速度 | 准确率 | 显存需求 |
|------|------|------|--------|----------|
| tiny | 39 MB | 最快 | 一般 | ~1 GB |
| base | 74 MB | 快 | 较好 | ~1 GB |
| small | 244 MB | 中等 | 好 | ~2 GB |
| medium | 769 MB | 较慢 | 很好 | ~5 GB |
| large | 1550 MB | 最慢 | 最佳 | ~10 GB |

**推荐**: `base` 模型在准确率和速度之间平衡最好。

## Usage

### 基本用法

```bash
# 转录音频文件
python scripts/whisper_transcribe.py <audio_file>

# 指定语言（中文）
python scripts/whisper_transcribe.py <audio_file> --language zh

# 输出 SRT 字幕文件
python scripts/whisper_transcribe.py <audio_file> --format srt
```

### 配合 Bilibili 音频提取使用

```bash
# 提取音频并转录
python ../bilibili-audio-extractor/scripts/bilibili_audio_extract.py <url> --transcribe --local-whisper
```

### Python API

```python
from scripts.whisper_transcribe import transcribe_audio

result = transcribe_audio(
    audio_path="audio.mp3",
    language="zh",
    output_format="txt",
    model="base"
)
print(result["text"])
```

## Output Formats

### TXT (默认)
纯文本格式，包含元数据头部：
```
Title: 视频标题
Duration: 123 seconds
Model: whisper-base
Language: zh
--------------------------------------------------

这里是转录的文字内容...
```

### SRT
字幕格式，带时间戳：
```
1
00:00:00,000 --> 00:00:05,000
这里是第一句转录

2
00:00:05,000 --> 00:00:10,000
这里是第二句转录
```

### LRC
歌词格式，适合音乐播放器：
```
[00:00.00]这里是第一句
[00:05.00]这里是第二句
```

## First Run

首次运行时会自动：
1. 安装依赖包到项目虚拟环境 (openai-whisper, torch, numpy)
2. 下载指定的 Whisper 模型

这个过程可能需要几分钟，取决于网络速度。

## Troubleshooting

### 依赖安装失败
```bash
# 手动安装依赖到项目虚拟环境
cd /Users/likang/geminicode/Agent/nanobot
source .venv/bin/activate
pip install openai-whisper torch numpy
```

### 模型下载慢
```bash
# 手动下载模型并放到目录
~/.nanobot/whisper-models/
```

### 显存不足
- 使用更小的模型（tiny 或 base）
- 设置 `compute_type` 为 `int8`
- 使用 CPU 运行：设置 `device` 为 `cpu`

### FFmpeg 错误
确保 FFmpeg 已安装并在 PATH 中：
```bash
ffmpeg -version
```

## Integration with Bilibili Audio Extractor

这个 skill 可以与 bilibili-audio-extractor 配合使用：

```bash
# 修改 bilibili_audio_extract.py 中的转录配置
# 使用本地 Whisper 替代 DashScope API

config = {
    "asr_provider": "local_whisper",  # 改为本地 Whisper
    "local_whisper": {
        "model": "base",
        "language": "zh"
    }
}
```

## Privacy

- 所有音频处理都在本地完成
- 不会上传任何数据到云端
- 模型文件保存在本地磁盘

## License

MIT License - 与 Whisper 项目保持一致
