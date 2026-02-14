# Local Whisper ASR Skill

本地 Whisper 语音识别 Skill - 完全本地运行的语音转文字解决方案

## 快速开始

### 1. 安装 FFmpeg

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

### 2. 配置

编辑 `~/.nanobot/config.json`：

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

### 3. 运行安装脚本

```bash
cd nanobot/skills/local-whisper-asr/scripts
python setup_whisper.py
```

### 4. 使用

```bash
# 转录音频文件
python scripts/whisper_transcribe.py audio.mp3 --language zh

# 配合 Bilibili 音频提取使用
python ../bilibili-audio-extractor/scripts/bilibili_audio_extract.py <url> --transcribe --local-whisper
```

## 文件结构

```
local-whisper-asr/
├── SKILL.md              # 详细文档
├── README.md             # 本文件
└── scripts/
    ├── setup_whisper.py      # 安装脚本
    └── whisper_transcribe.py # 转录脚本
```

## 模型选择

| 模型 | 大小 | 速度 | 准确率 |
|------|------|------|--------|
| tiny | 39 MB | 最快 | 一般 |
| base | 74 MB | 快 | 较好 |
| small | 244 MB | 中等 | 好 |
| medium | 769 MB | 较慢 | 很好 |
| large | 1550 MB | 最慢 | 最佳 |

推荐 `base` 模型在准确率和速度之间取得平衡。

## 注意事项

- 首次使用时会自动下载模型文件（约 150MB for base）
- 所有处理在本地完成，不发送数据到云端
- 需要约 3GB 磁盘空间（虚拟环境 + 模型）
