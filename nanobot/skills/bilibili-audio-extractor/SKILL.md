---
name: bilibili-audio-extractor
description: This skill should be used when users want to extract audio files from Bilibili (哔哩哔哩) video links, or transcribe video audio to text using local Whisper ASR. It handles video URL validation, audio extraction with multiple format support, speech-to-text transcription using local Whisper, and provides detailed progress feedback. Use this skill for tasks like downloading educational video audio, extracting podcast content, saving music from video links, or converting video speech to text.
always: true
---

# Bilibili Audio Extractor

## Overview

This skill enables extraction of high-quality audio files from Bilibili videos and optional speech-to-text transcription using local Whisper. It validates video URLs, extracts audio in multiple formats (MP3, M4A, WAV, FLAC), transcribes audio to text locally, and provides comprehensive progress feedback. Perfect for educational content, podcasts, music preservation, and content accessibility.

## Quick Start

### Supported Video URLs
- Standard Bilibili links: `https://www.bilibili.com/video/BVxxxxxxxx`
- Short links: `https://b23.tv/xxxxxxxx`
- Topic pages: `https://www.bilibili.com/blackboard/topic/list`

### Configuration

To use the ASR transcription feature, add local Whisper configuration to `~/.nanobot/config.json`:

```json
{
  "tools": {
    "local_whisper": {
      "enabled": true,
      "model": "base",
      "device": "auto",
      "language": "auto"
    }
  }
}
```

### Setup Local Whisper

Run the setup script to install dependencies:

```bash
python nanobot/skills/local-whisper-asr/scripts/setup_whisper.py
```

**Requirements:**
- FFmpeg installed (`brew install ffmpeg` on macOS)
- ~3GB disk space for virtual environment and model
- No API key required

### Basic Audio Extraction
To extract audio from a Bilibili video:

1. **Validate the video URL** - Ensure the link points to a public Bilibili video
2. **Choose audio format** - Select from MP3, M4A, WAV, or FLAC
3. **Set quality level** - High (320k), Medium (192k), or Low (128k)
4. **Execute extraction** - Download audio file with progress tracking

## Task Categories

### 1. Video Information Retrieval

Use when you need to preview video details before extraction:

**Get Video Metadata:**
```bash
# Example workflow for checking video information
# 1. User provides Bilibili video link
# 2. Extract video title, duration, uploader, view count
# 3. Display formatted information
# 4. Confirm with user before proceeding to extraction
```

**Information Provided:**
- Video title and description
- Uploader/channel name
- Duration and file size estimates
- View count and engagement metrics
- Available audio formats

### 2. Audio File Extraction

Use for the main audio extraction functionality:

**Format Options:**
- **MP3**: Universal compatibility, compressed (recommended for most users)
- **M4A**: Apple-optimized, good quality
- **WAV**: Uncompressed, highest quality (larger files)
- **FLAC**: Lossless compression, archival quality

**Quality Settings:**
- **High**: 320kbps (best quality, larger files)
- **Medium**: 192kbps (balanced quality/size)
- **Low**: 128kbps (smaller files, mobile-friendly)

**Common Extraction Workflows:**

**Educational Content Extraction:**
```bash
# For online course videos
1. Validate video URL
2. Extract audio in MP3 format at high quality
3. Generate clean filename based on video title
4. Provide file size and duration information
```

**Podcast/Music Preservation:**
```bash
# For podcast episodes or music videos
1. Check video availability and duration
2. Extract in FLAC format for best quality
3. Include metadata in filename
4. Provide technical specifications
```

**Mobile-Friendly Extraction:**
```bash
# For portable listening
1. Validate video accessibility
2. Extract in M4A format at medium quality
3. Optimize filename for mobile systems
4. Report compression efficiency
```

### 3. Progress Tracking and Error Handling

Use for monitoring extraction progress and handling issues:

**Progress Reporting:**
- Real-time download progress
- Phase indicators (validation, download, conversion)
- Estimated time remaining
- File size updates

**Common Error Scenarios:**
- **Invalid URL**: Guide user to correct Bilibili link format
- **Private/Protected Video**: Explain access restrictions
- **Network Issues**: Suggest retry strategies
- **Storage Problems**: Recommend cleanup or alternative locations

### 4. File Management

Use for organizing and managing extracted audio files:

**Filename Optimization:**
- Clean video titles for safe filenames
- Include metadata when appropriate
- Avoid special characters and path issues

**Storage Recommendations:**
- Temporary file handling guidance
- Space management suggestions
- Cleanup procedures for old files

### 5. Speech-to-Text Transcription (Local Whisper ASR)

Use for converting video audio to text using local Whisper:

**Prerequisites:**
- FFmpeg installed
- ~3GB disk space
- No API Key required
- Local Whisper enabled in config

**Configuration:**
```json
{
  "tools": {
    "local_whisper": {
      "enabled": true,
      "model": "base",
      "device": "auto",
      "compute_type": "int8",
      "language": "auto"
    }
  }
}
```

**Setup:**
```bash
python nanobot/skills/local-whisper-asr/scripts/setup_whisper.py
```

**Model Options:**
| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| tiny | 39 MB | Fastest | Basic |
| base | 74 MB | Fast | Good (recommended) |
| small | 244 MB | Medium | Better |
| medium | 769 MB | Slow | Very Good |
| large | 1550 MB | Slowest | Best |

**Language Support:**
- **zh**: Chinese (default)
- **en**: English
- **ja**: Japanese
- **ko**: Korean
- **es**: Spanish
- **fr**: French
- **de**: German
- And 90+ more languages...

**Text Output Formats:**
- **txt**: Plain text with metadata header
- **srt**: Subtitle format with timestamps
- **lrc**: Lyrics format for music players

**Transcription Workflows:**

**重要 - 脚本路径说明:**
- 脚本位置: `nanobot/skills/bilibili-audio-extractor/scripts/bilibili_audio_extract.py`
- 从项目根目录执行: `python nanobot/skills/bilibili-audio-extractor/scripts/bilibili_audio_extract.py`

**Single Video with Transcription:**
```bash
cd /Users/likang/geminicode/Agent/nanobot
python nanobot/skills/bilibili-audio-extractor/scripts/bilibili_audio_extract.py <url> --transcribe --language zh --text-format txt
```

**Batch Processing with Transcription:**
```bash
python batch_bilibili_extract.py urls.txt --transcribe --language zh --text-format srt
```

**Workflow Steps:**
1. Extract audio from video using yt-dlp
2. Load local Whisper model
3. Transcribe audio locally
4. Format output (txt/srt/lrc)
5. Save to file alongside audio

**Transcription Use Cases:**
- **Educational Content**: Create transcripts of lectures for note-taking
- **Accessibility**: Provide text alternatives for hearing-impaired users
- **Content Analysis**: Searchable text from video content
- **Translation**: Base text for translation workflows
- **Subtitle Creation**: Generate SRT files for video subtitles

## Implementation Patterns

### Workflow Decision Tree

**Audio Extraction Only:**
```
User Request → Validate URL → Check Video →
├─ Success → Choose Format/Quality → Extract Audio → Provide Results
└─ Error → Provide Clear Guidance → Suggest Alternatives
```

**With ASR Transcription:**
```
User Request → Validate URL → Check Video →
├─ Success → Extract Audio → Validate Whisper Config → Transcribe → Format Output → Provide Results
└─ Error → Provide Clear Guidance → Suggest Alternatives
```

### Error Handling Patterns

**URL Validation Errors:**
```
Invalid Format → Explain supported formats → Provide examples
Access Denied → Explain privacy settings → Suggest public videos
Network Issues → Recommend retry → Suggest alternative approaches
```

**Extraction Process Errors:**
```
Download Failed → Check video availability → Retry with different settings
Conversion Error → Try alternative format → Check system compatibility
Storage Full → Suggest cleanup → Recommend smaller quality settings
```

## Best Practices

### User Experience
1. **Always validate URLs first** - Provide clear error messages for invalid links
2. **Preview video information** - Show title, duration, and size estimates
3. **Offer format recommendations** - Suggest appropriate settings based on use case
4. **Provide progress feedback** - Keep users informed during extraction
5. **Handle cleanup gracefully** - Manage temporary files and storage

### Technical Considerations
1. **Respect rate limits** - Don't overwhelm Bilibili's servers
2. **Handle large files** - Provide progress updates for long videos
3. **Support interruption recovery** - Allow users to retry failed extractions
4. **Validate outputs** - Ensure downloaded files are complete and valid

### Legal and Ethical Use
1. **Public content only** - Respect privacy and access controls
2. **Personal use focus** - Emphasize educational and personal applications
3. **Copyright awareness** - Remind users about content rights
4. **Terms compliance** - Follow Bilibili's terms of service

## Common Use Cases

### Educational Applications
- **Online Course Audio**: Extract lecture audio for offline study
- **Tutorial Content**: Save instructional videos as audio references
- **Language Learning**: Extract pronunciation and conversation content

### Content Creation
- **Podcast Backup**: Preserve favorite podcast episodes
- **Music Collection**: Save music videos as audio files
- **Interview Content**: Extract audio from discussion videos

### Accessibility and Convenience
- **Offline Listening**: Convert videos to audio for commute listening
- **Storage Optimization**: Reduce file sizes for mobile storage
- **Multi-tasking**: Enable audio consumption while multitasking

## Integration with Other Tools

This skill works well with:
- **File management tools** - Organize downloaded audio files
- **Media players** - Integration with music library software
- **Cloud storage** - Upload extracted files to cloud services
- **Note-taking apps** - Use transcripts for study notes

## Resources

This skill includes supporting scripts and documentation for audio extraction workflows.

### scripts/
- `bilibili_audio_extract.py` - Single video audio extraction with transcription
- `batch_bilibili_extract.py` - Batch processing multiple videos

### local-whisper-asr/scripts/
- `setup_whisper.py` - Setup script for local Whisper ASR
- `whisper_transcribe.py` - Standalone transcription script

---

**This skill focuses on user-friendly audio extraction with comprehensive error handling and progress tracking. All operations respect Bilibili's terms of service and focus on publicly accessible content.**
