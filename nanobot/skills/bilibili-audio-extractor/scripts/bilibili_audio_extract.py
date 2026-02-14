#!/usr/bin/env python3
"""
Bilibili Audio Extractor with Local Whisper ASR Transcription

This script provides functionality to extract audio from Bilibili videos
using yt-dlp, and optionally transcribe audio to text using local Whisper.

Usage:
    # Only extract audio
    python bilibili_audio_extract.py <video_url> [options]

    # Extract audio and transcribe with local Whisper
    python bilibili_audio_extract.py <video_url> --transcribe [options]

Options:
    --format: Audio format (mp3, m4a, wav, flac)
    --quality: Audio quality (high, medium, low)
    --output: Output directory
    --filename: Custom filename (without extension)
    --transcribe: Enable speech-to-text transcription with local Whisper
    --language: Language for transcription (zh, en, ja, etc.)
    --text-format: Text output format (txt, srt, lrc)
"""

import sys
import os
import subprocess
import tempfile
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any

# Import task reporter for progress tracking
try:
    from task_reporter import TaskReporter, init_reporter
except ImportError:
    TaskReporter = None
    init_reporter = None


def validate_bilibili_url(url: str) -> bool:
    """Validate if the URL is a valid Bilibili video link."""
    bilibili_patterns = [
        r'https?://(?:www\.)?bilibili\.com/video/[\w\.\-]+',
        r'https?://b23\.tv/[\w\.\-]+',
        r'https?://(?:www\.)?bilibili\.com/blackboard/topic/list',
    ]
    return any(re.match(pattern, url.strip()) for pattern in bilibili_patterns)


def get_video_info(video_url: str) -> Optional[Dict[str, Any]]:
    """Extract basic video information using yt-dlp."""
    try:
        cmd = [
            'yt-dlp',
            '--dump-json',
            '--no-download',
            video_url
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )

        video_info = json.loads(result.stdout)

        return {
            'title': video_info.get('title', 'Unknown Title'),
            'duration': video_info.get('duration', 0),
            'uploader': video_info.get('uploader', 'Unknown Uploader'),
            'view_count': video_info.get('view_count', 0),
            'upload_date': video_info.get('upload_date', 'Unknown Date')
        }

    except (subprocess.CalledProcessError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        print(f"Error extracting video info: {e}")
        return None


def extract_audio(
    video_url: str,
    output_format: str = 'mp3',
    quality: str = 'high',
    output_dir: Optional[str] = None,
    custom_filename: Optional[str] = None
) -> Optional[str]:
    """
    Extract audio from Bilibili video.

    Args:
        video_url: URL of the Bilibili video
        output_format: Audio format (mp3, m4a, wav, flac)
        quality: Audio quality (high, medium, low)
        output_dir: Directory to save the file (default: temp directory)
        custom_filename: Custom filename without extension

    Returns:
        Path to extracted audio file or None if failed
    """
    if not validate_bilibili_url(video_url):
        print(f"Error: Invalid Bilibili video URL: {video_url}")
        return None

    # Determine output directory
    if output_dir is None:
        output_dir = tempfile.gettempdir()

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Map quality to bitrate
    quality_map = {
        'high': '320k',
        'medium': '192k',
        'low': '128k'
    }
    bitrate = quality_map.get(quality, '192k')

    try:
        # Get video info for filename
        video_info = get_video_info(video_url)
        if video_info:
            safe_title = re.sub(r'[^\w\s-]', '', video_info['title']).strip().replace(' ', '_')
            if custom_filename:
                output_filename = f"{custom_filename}.{output_format}"
            else:
                output_filename = f"{safe_title}.{output_format}"
        else:
            output_filename = f"bilibili_audio.{output_format}"

        output_path = os.path.join(output_dir, output_filename)

        print(f"Extracting audio from: {video_url}")
        print(f"Output format: {output_format.upper()}")
        print(f"Quality: {quality} ({bitrate})")
        print(f"Destination: {output_path}")
        print("-" * 50)

        # Build yt-dlp command
        cmd = [
            'yt-dlp',
            '--extract-audio',
            '--audio-format', output_format,
            '--audio-quality', bitrate,
            '--output', output_path,
            '--no-playlist',
            '--progress',
            video_url
        ]

        # Execute extraction
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # Check if file was created
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            file_size_mb = file_size / (1024 * 1024)
            print(f"\n✅ Audio extracted successfully!")
            print(f"📁 File: {output_path}")
            print(f"💾 Size: {file_size_mb:.2f} MB")
            return output_path
        else:
            print("❌ Error: Output file was not created")
            return None

    except subprocess.CalledProcessError as e:
        print(f"❌ Error during extraction: {e}")
        print("Common issues:")
        print("- Video might be private or requires login")
        print("- Network connectivity issues")
        print("- yt-dlp might need updating: pip install --upgrade yt-dlp")
        return None


def load_config() -> Dict[str, Any]:
    """Load nanobot configuration from config file."""
    config_paths = [
        Path.home() / ".nanobot" / "config.json",
        Path.home() / ".config" / "nanobot" / "config.json",
    ]

    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load config from {config_path}: {e}")

    return {}


def get_local_whisper_config(config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract local Whisper configuration from nanobot config."""
    tools = config.get('tools', {})
    whisper_config = tools.get('local_whisper', {})

    if not whisper_config.get('enabled', False):
        return None

    return {
        'model': whisper_config.get('model', 'base'),
        'device': whisper_config.get('device', 'auto'),
        'compute_type': whisper_config.get('compute_type', 'int8'),
        'language': whisper_config.get('language', 'auto'),
    }


def transcribe_audio_local(
    audio_path: str,
    whisper_config: Dict[str, Any],
    output_format: str = 'txt'
) -> Optional[str]:
    """
    Transcribe audio using local Whisper in virtual environment.

    Args:
        audio_path: Path to audio file
        whisper_config: Whisper configuration dict
        output_format: Output format (txt, srt, lrc)

    Returns:
        Transcription text or None if failed
    """
    # Import here to avoid dependency issues
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'local-whisper-asr' / 'scripts'))

    try:
        from whisper_transcribe import transcribe_audio

        print(f"\n🎯 Using Local Whisper for transcription...")
        print(f"📝 Model: {whisper_config['model']}")
        print(f"🌐 Language: {whisper_config.get('language', 'auto')}")
        print("-" * 50)

        result_path = transcribe_audio(
            audio_path=audio_path,
            language=whisper_config.get('language', 'auto'),
            output_format=output_format,
            model=whisper_config.get('model', 'base')
        )

        if result_path:
            # Read the transcription result
            with open(result_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # If using txt format with header, extract just the text part
            if output_format == 'txt':
                # Split by the header separator
                parts = content.split('-' * 50 + '\n\n')
                if len(parts) > 1:
                    return parts[1]
                return content

            return content

        return None

    except ImportError:
        print("❌ Local Whisper not installed. Please run setup:")
        print(f"   python {Path(__file__).parent.parent.parent / 'local-whisper-asr' / 'scripts' / 'setup_whisper.py'}")
        return None
    except Exception as e:
        print(f"❌ Local transcription failed: {e}")
        return None


def format_transcription(
    transcription: str,
    output_format: str,
    video_info: Optional[Dict[str, Any]] = None
) -> str:
    """
    Format transcription based on output format.

    Args:
        transcription: Raw transcription text
        output_format: Desired format (txt, srt, lrc)
        video_info: Optional video metadata

    Returns:
        Formatted text
    """
    if output_format == 'txt':
        header = ""
        if video_info:
            header = f"Title: {video_info.get('title', 'Unknown')}\n"
            header += f"Uploader: {video_info.get('uploader', 'Unknown')}\n"
            header += f"Duration: {video_info.get('duration', 0)} seconds\n"
            header += "-" * 50 + "\n\n"
        return header + transcription

    elif output_format == 'srt':
        # Simple SRT format - would need timestamps for proper implementation
        lines = transcription.split('\n')
        srt_lines = []
        for i, line in enumerate(lines, 1):
            if line.strip():
                # Mock timestamps - in real implementation, ASR should return timestamps
                start_time = f"{i//3600:02d}:{(i//60)%60:02d}:{i%60:02d},000"
                end_time = f"{(i+1)//3600:02d}:{((i+1)//60)%60:02d}:{(i+1)%60:02d},000"
                srt_lines.append(f"{i}")
                srt_lines.append(f"{start_time} --> {end_time}")
                srt_lines.append(line.strip())
                srt_lines.append("")
        return "\n".join(srt_lines)

    elif output_format == 'lrc':
        # LRC format for lyrics
        lines = transcription.split('\n')
        lrc_lines = []
        for i, line in enumerate(lines):
            if line.strip():
                timestamp = f"[{i//60:02d}:{i%60:02d}.00]"
                lrc_lines.append(f"{timestamp}{line.strip()}")
        return "\n".join(lrc_lines)

    return transcription


def save_transcription(
    transcription: str,
    output_path: str,
    output_format: str = 'txt'
) -> str:
    """Save transcription to file."""
    # Determine output filename
    base_path = Path(output_path)
    text_filename = base_path.stem + f"_transcription.{output_format}"
    text_path = base_path.parent / text_filename

    with open(text_path, 'w', encoding='utf-8') as f:
        f.write(transcription)

    return str(text_path)


def main():
    """Main function for command-line usage."""
    if len(sys.argv) < 2:
        print("Usage: python bilibili_audio_extract.py <video_url> [options]")
        print("\nOptions:")
        print("  --format: Audio format (mp3, m4a, wav, flac) [default: mp3]")
        print("  --quality: Audio quality (high, medium, low) [default: high]")
        print("  --output: Output directory [default: system temp]")
        print("  --filename: Custom filename without extension")
        print("  --transcribe: Enable speech-to-text transcription with local Whisper")
        print("  --language: Language for transcription (zh, en, ja, etc.) [default: zh]")
        print("  --text-format: Text output format (txt, srt, lrc) [default: txt]")
        print("  --task-id: Task ID for progress reporting [optional]")
        print("  --api-base: API base URL for task reporting [default: http://localhost:18790]")
        print("\nExamples:")
        print("  python bilibili_audio_extract.py https://www.bilibili.com/video/BV1xx411c7mD")
        print("  python bilibili_audio_extract.py https://b23.tv/abc123 --format flac --quality high")
        print("  python bilibili_audio_extract.py https://www.bilibili.com/video/BV1xx411c7mD --output ~/Music --filename my_audio")
        print("  python bilibili_audio_extract.py <url> --transcribe --language zh --text-format txt")
        print("\nNote: Local Whisper requires setup:")
        print("  python ../local-whisper-asr/scripts/setup_whisper.py")
        print("  Add to ~/.nanobot/config.json:")
        print('  { "tools": { "local_whisper": { "enabled": true, "model": "base" } } }')
        return

    video_url = sys.argv[1]

    # Parse arguments
    output_format = 'mp3'
    quality = 'high'
    output_dir = None
    custom_filename = None
    transcribe = False
    language = 'zh'
    text_format = 'txt'
    # Task reporting: command line args override environment variables
    task_id = os.environ.get("NANOBOT_TASK_ID")
    api_base = os.environ.get("NANOBOT_API_BASE", "http://localhost:18790")

    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--format' and i + 1 < len(sys.argv):
            output_format = sys.argv[i + 1]
            i += 2
        elif arg == '--quality' and i + 1 < len(sys.argv):
            quality = sys.argv[i + 1]
            i += 2
        elif arg == '--output' and i + 1 < len(sys.argv):
            output_dir = sys.argv[i + 1]
            i += 2
        elif arg == '--filename' and i + 1 < len(sys.argv):
            custom_filename = sys.argv[i + 1]
            i += 2
        elif arg == '--transcribe':
            transcribe = True
            i += 1
        elif arg == '--language' and i + 1 < len(sys.argv):
            language = sys.argv[i + 1]
            i += 2
        elif arg == '--text-format' and i + 1 < len(sys.argv):
            text_format = sys.argv[i + 1]
            i += 2
        elif arg == '--task-id' and i + 1 < len(sys.argv):
            task_id = sys.argv[i + 1]
            i += 2
        elif arg == '--api-base' and i + 1 < len(sys.argv):
            api_base = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    # Initialize task reporter - will auto-read from environment if available
    reporter = None
    if init_reporter:
        reporter = init_reporter(task_id, api_base)
        if reporter.task_id:
            print(f"[Task {reporter.task_id}] Progress reporting enabled")

    # Validate URL
    if not validate_bilibili_url(video_url):
        print(f"Error: Please provide a valid Bilibili video URL")
        print("Supported formats:")
        print("- https://www.bilibili.com/video/BVxxxxxxxx")
        print("- https://b23.tv/xxxxxxxx")
        return

    # Create output directory if needed
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Report start
    if reporter:
        reporter.start("正在获取视频信息...")

    # Get video info for transcription
    video_info = get_video_info(video_url) if transcribe else None

    # Report progress - extracting audio
    if reporter:
        reporter.progress(10, "正在提取音频...")

    # Extract audio
    result = extract_audio(
        video_url=video_url,
        output_format=output_format,
        quality=quality,
        output_dir=output_dir,
        custom_filename=custom_filename
    )

    if result:
        # Report progress - extraction complete
        if reporter:
            if transcribe:
                reporter.progress(50, "音频提取完成，准备转录...")
            else:
                reporter.complete(f"音频已保存: {result}")

        print(f"\n🎵 Audio extraction completed successfully!")
        print(f"📂 Location: {result}")

        # Transcribe if requested
        if transcribe:
            print("\n" + "=" * 50)

            # Report progress - loading config
            if reporter:
                reporter.progress(55, "正在加载配置...")

            # Load config
            config = load_config()

            # Get local Whisper config
            whisper_config = get_local_whisper_config(config)

            if not whisper_config:
                if reporter:
                    reporter.fail("Local Whisper 未配置")
                print("⚠️  Local Whisper not enabled in config.")
                print("Please add the following to ~/.nanobot/config.json:")
                print()
                print('  {')
                print('    "tools": {')
                print('      "local_whisper": {')
                print('        "enabled": true,')
                print('        "model": "base",')
                print('        "language": "auto"')
                print('      }')
                print('    }')
                print('  }')
                print()
                print("Setup instructions:")
                print(f"  python {Path(__file__).parent.parent.parent / 'local-whisper-asr' / 'scripts' / 'setup_whisper.py'}")
                return

            # Report progress - starting transcription
            if reporter:
                reporter.progress(60, "正在转录音频，请稍候...")

            # Perform transcription with local Whisper
            transcription = transcribe_audio_local(
                audio_path=result,
                whisper_config=whisper_config,
                output_format=text_format
            )

            if transcription:
                # Format and save
                formatted = format_transcription(
                    transcription=transcription,
                    output_format=text_format,
                    video_info=video_info
                )

                text_path = save_transcription(formatted, result, text_format)

                # Report completion
                if reporter:
                    reporter.complete(f"转录完成! 文本已保存: {text_path}")

                print(f"\n📝 Transcription saved to: {text_path}")
                print(f"📊 Preview (first 200 chars):")
                print("-" * 50)
                print(transcription[:200] + "..." if len(transcription) > 200 else transcription)
            else:
                if reporter:
                    reporter.fail("转录失败")
                print("\n❌ Transcription failed.")
    else:
        if reporter:
            reporter.fail("音频提取失败")
        print(f"\n❌ Audio extraction failed. Please check the video URL and try again.")


if __name__ == "__main__":
    main()
