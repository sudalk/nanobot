#!/usr/bin/env python3
"""
Batch Bilibili Audio Extractor with Local Whisper ASR Transcription

This script handles batch processing of multiple Bilibili videos for audio extraction
and optional speech-to-text transcription using local Whisper.

Usage:
    python batch_bilibili_extract.py <urls_file> [options]

Options:
    --format: Audio format for all videos (mp3, m4a, wav, flac)
    --quality: Audio quality for all videos (high, medium, low)
    --output: Base output directory
    --parallel: Number of parallel downloads (default: 1)
    --delay: Delay between downloads in seconds (default: 2)
    --transcribe: Enable speech-to-text transcription with local Whisper
    --language: Language for transcription (zh, en, ja, etc.)
    --text-format: Text output format (txt, srt, lrc)
"""

import sys
import os
import json
import time
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import transcribe functions from single video extractor
sys.path.insert(0, str(Path(__file__).parent))
from bilibili_audio_extract import (
    load_config,
    get_local_whisper_config,
    transcribe_audio_local,
    format_transcription,
    save_transcription,
)


def load_video_urls(file_path: str) -> List[str]:
    """Load video URLs from file (supports JSON, TXT, CSV)."""
    urls = []

    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found")
        return urls

    try:
        if file_path.endswith('.json'):
            # JSON format
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    urls = data
                elif isinstance(data, dict) and 'urls' in data:
                    urls = data['urls']
        else:
            # Text file (one URL per line)
            with open(file_path, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip()]

        print(f"Loaded {len(urls)} video URLs from {file_path}")
        return urls

    except Exception as e:
        print(f"Error loading URLs from {file_path}: {e}")
        return []


def validate_url(url: str) -> bool:
    """Validate if URL is a valid Bilibili video link."""
    import re
    bilibili_patterns = [
        r'https?://(?:www\.)?bilibili\.com/video/[\w\.\-]+',
        r'https?://b23\.tv/[\w\.\-]+',
    ]
    return any(re.match(pattern, url.strip()) for pattern in bilibili_patterns)


def get_video_metadata(url: str) -> Dict[str, Any]:
    """Extract metadata from a single video without downloading."""
    try:
        cmd = [
            'yt-dlp',
            '--dump-json',
            '--no-download',
            url
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
            'url': url,
            'title': video_info.get('title', 'Unknown Title'),
            'duration': video_info.get('duration', 0),
            'uploader': video_info.get('uploader', 'Unknown Uploader'),
            'view_count': video_info.get('view_count', 0),
            'upload_date': video_info.get('upload_date', 'Unknown Date'),
            'status': 'ready'
        }

    except Exception as e:
        return {
            'url': url,
            'title': 'Error',
            'duration': 0,
            'uploader': 'Unknown',
            'view_count': 0,
            'upload_date': 'Unknown',
            'status': f'error: {str(e)}'
        }


def extract_single_audio(url: str, output_dir: str, format: str, quality: str, index: int, total: int) -> Dict[str, Any]:
    """Extract audio from a single video with progress tracking."""
    try:
        print(f"[{index}/{total}] Processing: {url}")

        # Get metadata first
        metadata = get_video_metadata(url)

        if metadata['status'] != 'ready':
            return metadata

        # Create safe filename
        import re
        title = metadata['title']
        safe_title = re.sub(r'[^\w\-\.]', '_', title)[:40]
        filename = f"{index:03d}_{safe_title}.{format}"
        output_path = os.path.join(output_dir, filename)

        # yt-dlp command
        quality_settings = {
            'high': '320k',
            'medium': '192k',
            'low': '128k'
        }

        cmd = [
            'yt-dlp',
            '--extract-audio',
            '--audio-format', format,
            '--audio-quality', quality_settings[quality],
            '-o', output_path,
            url
        ]

        start_time = time.time()

        subprocess.run(cmd, check=True, capture_output=True)

        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            duration = time.time() - start_time

            return {
                'url': url,
                'title': metadata['title'],
                'output_path': output_path,
                'file_size': file_size,
                'duration': duration,
                'status': 'success'
            }
        else:
            return {
                'url': url,
                'title': metadata['title'],
                'status': 'error',
                'message': 'Output file not created'
            }

    except Exception as e:
        return {
            'url': url,
            'title': 'Unknown',
            'status': 'error',
            'message': str(e)
        }


def create_playlist_file(video_urls: List[str], output_path: str):
    """Create a playlist file for easy reference."""
    playlist_content = "# Bilibili Audio Extraction Playlist\n"
    playlist_content += f"# Generated on {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    playlist_content += f"# Total videos: {len(video_urls)}\n\n"

    for i, url in enumerate(video_urls, 1):
        playlist_content += f"{i}. {url}\n"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(playlist_content)

    print(f"Created playlist file: {output_path}")


def batch_extract_audio(
    urls_file: str,
    output_dir: str,
    audio_format: str = 'mp3',
    quality: str = 'high',
    parallel: int = 1,
    delay: float = 2.0,
    transcribe: bool = False,
    language: str = 'zh',
    text_format: str = 'txt',
    whisper_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Extract audio from multiple Bilibili videos in batch."""

    # Load URLs
    video_urls = load_video_urls(urls_file)

    if not video_urls:
        print("No valid URLs found")
        return {'success': False, 'error': 'No URLs loaded'}

    # Validate URLs
    valid_urls = [url for url in video_urls if validate_url(url)]
    invalid_count = len(video_urls) - len(valid_urls)

    if invalid_count > 0:
        print(f"Warning: {invalid_count} invalid URLs were skipped")

    if not valid_urls:
        print("No valid Bilibili URLs found")
        return {'success': False, 'error': 'No valid URLs'}

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Create playlist file
    playlist_path = os.path.join(output_dir, 'playlist.txt')
    create_playlist_file(valid_urls, playlist_path)

    # Create results log
    results_log = {
        'started_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_videos': len(valid_urls),
        'format': audio_format,
        'quality': quality,
        'parallel': parallel,
        'results': []
    }

    print(f"\n🎵 Starting batch extraction of {len(valid_urls)} videos")
    print(f"📁 Output directory: {output_dir}")
    print(f"🎛️ Format: {audio_format.upper()} ({quality} quality)")
    print(f"⚡ Parallel downloads: {parallel}")
    print(f"⏱️ Delay between downloads: {delay}s")
    if transcribe:
        print(f"🎯 ASR Transcription: Enabled ({language}, {text_format})")
    print("-" * 60)

    # Process videos
    if parallel == 1:
        # Sequential processing
        for i, url in enumerate(valid_urls, 1):
            result = extract_single_audio(url, output_dir, audio_format, quality, i, len(valid_urls))
            results_log['results'].append(result)

            if result['status'] == 'success':
                print(f"✅ [{i}/{len(valid_urls)}] Success: {result['title']}")
            else:
                print(f"❌ [{i}/{len(valid_urls)}] Failed: {result['title']} - {result.get('message', 'Unknown error')}")

            # Add delay between downloads
            if i < len(valid_urls) and delay > 0:
                time.sleep(delay)
    else:
        # Parallel processing
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            future_to_url = {
                executor.submit(extract_single_audio, url, output_dir, audio_format, quality, i, len(valid_urls)): url
                for i, url in enumerate(valid_urls, 1)
            }

            completed = 0
            for future in as_completed(future_to_url):
                completed += 1
                result = future.result()
                results_log['results'].append(result)

                if result['status'] == 'success':
                    print(f"✅ [{completed}/{len(valid_urls)}] Success: {result['title']}")
                else:
                    print(f"❌ [{completed}/{len(valid_urls)}] Failed: {result['title']} - {result.get('message', 'Unknown error')}")

                # Add delay between task starts
                if delay > 0:
                    time.sleep(delay)

    # Generate summary
    successful = [r for r in results_log['results'] if r['status'] == 'success']
    failed = [r for r in results_log['results'] if r['status'] != 'success']

    results_log['completed_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    results_log['successful'] = len(successful)
    results_log['failed'] = len(failed)

    # Save results log
    log_path = os.path.join(output_dir, 'extraction_log.json')
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(results_log, f, indent=2, ensure_ascii=False)

    # Print summary
    print("\n" + "=" * 60)
    print("📊 EXTRACTION SUMMARY")
    print("=" * 60)
    print(f"✅ Successful: {len(successful)}")
    print(f"❌ Failed: {len(failed)}")
    print(f"📁 Output directory: {output_dir}")
    print(f"📋 Log file: {log_path}")
    print(f"📝 Playlist: {playlist_path}")

    if successful:
        total_size = sum(r['file_size'] for r in successful)
        total_size_mb = total_size / (1024 * 1024)
        print(f"💾 Total size: {total_size_mb:.1f} MB")

    if failed:
        print("\n❌ Failed extractions:")
        for result in failed:
            print(f"  - {result['title']}: {result.get('message', 'Unknown error')}")

    # Transcription phase
    transcription_results = []
    if transcribe and successful and whisper_config:
        print("\n" + "=" * 60)
        print("🎯 ASR TRANSCRIPTION PHASE")
        print("=" * 60)

        for i, result in enumerate(successful, 1):
            audio_path = result['output_path']
            print(f"\n[{i}/{len(successful)}] Transcribing: {result['title']}")

            transcription = transcribe_audio_local(
                audio_path=audio_path,
                whisper_config=whisper_config,
                output_format=text_format
            )

            if transcription:
                formatted = format_transcription(
                    transcription=transcription,
                    output_format=text_format,
                    video_info={'title': result['title']}
                )
                text_path = save_transcription(formatted, audio_path, text_format)

                print(f"  ✅ Saved: {text_path}")
                transcription_results.append({
                    'audio_path': audio_path,
                    'text_path': text_path,
                    'title': result['title'],
                    'status': 'success'
                })
            else:
                print(f"  ❌ Failed to transcribe")
                transcription_results.append({
                    'audio_path': audio_path,
                    'title': result['title'],
                    'status': 'failed'
                })

        # Add transcription results to log
        results_log['transcriptions'] = transcription_results

        # Save updated log
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(results_log, f, indent=2, ensure_ascii=False)

        print(f"\n📝 Transcription Summary: {len([t for t in transcription_results if t['status'] == 'success'])}/{len(transcription_results)} successful")

    return {'success': True, 'successful': len(successful), 'failed': len(failed), 'transcriptions': transcription_results if transcribe else []}


def main():
    """Main function for batch processing."""
    if len(sys.argv) < 2:
        print("Usage: python batch_bilibili_extract.py <urls_file> [options]")
        print("\nOptions:")
        print("  --format: Audio format (mp3, m4a, wav, flac) [default: mp3]")
        print("  --quality: Audio quality (high, medium, low) [default: high]")
        print("  --output: Output directory [default: ./bilibili_audio]")
        print("  --parallel: Number of parallel downloads [default: 1]")
        print("  --delay: Delay between downloads in seconds [default: 2]")
        print("  --transcribe: Enable speech-to-text transcription with local Whisper")
        print("  --language: Language for transcription (zh, en, ja, etc.) [default: zh]")
        print("  --text-format: Text output format (txt, srt, lrc) [default: txt]")
        print("\nSupported URL file formats:")
        print("  - JSON: ['url1', 'url2', ...] or {'urls': ['url1', 'url2']}")
        print("  - TXT: One URL per line")
        print("\nExamples:")
        print("  python batch_bilibili_extract.py videos.txt")
        print("  python batch_bilibili_extract.py playlist.json --format flac --parallel 3")
        print("  python batch_bilibili_extract.py urls.txt --output ~/Music --delay 5")
        print("  python batch_bilibili_extract.py videos.txt --transcribe --language zh")
        print("\nNote: Local Whisper requires setup:")
        print("  python ../local-whisper-asr/scripts/setup_whisper.py")
        print("  Add to ~/.nanobot/config.json:")
        print('  { "tools": { "local_whisper": { "enabled": true, "model": "base" } } }')
        return

    urls_file = sys.argv[1]

    # Parse arguments
    audio_format = 'mp3'
    quality = 'high'
    output_dir = './bilibili_audio'
    parallel = 1
    delay = 2.0
    transcribe = False
    language = 'zh'
    text_format = 'txt'

    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--format' and i + 1 < len(sys.argv):
            audio_format = sys.argv[i + 1]
            i += 2
        elif arg == '--quality' and i + 1 < len(sys.argv):
            quality = sys.argv[i + 1]
            i += 2
        elif arg == '--output' and i + 1 < len(sys.argv):
            output_dir = sys.argv[i + 1]
            i += 2
        elif arg == '--parallel' and i + 1 < len(sys.argv):
            parallel = int(sys.argv[i + 1])
            i += 2
        elif arg == '--delay' and i + 1 < len(sys.argv):
            delay = float(sys.argv[i + 1])
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
        else:
            i += 1

    # Load Whisper config if transcription enabled
    whisper_config = None
    if transcribe:
        config = load_config()
        whisper_config = get_local_whisper_config(config)

        if not whisper_config:
            print("⚠️  Warning: Local Whisper not configured.")
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
            print("  python ../local-whisper-asr/scripts/setup_whisper.py")
            print("\nContinuing with audio extraction only (no transcription)...")
            transcribe = False

    # Run batch extraction
    results = batch_extract_audio(
        urls_file=urls_file,
        output_dir=output_dir,
        audio_format=audio_format,
        quality=quality,
        parallel=parallel,
        delay=delay,
        transcribe=transcribe,
        language=language,
        text_format=text_format,
        whisper_config=whisper_config
    )

    if results['success']:
        print(f"\n🎉 Batch extraction completed!")
        if transcribe:
            print(f"📝 Transcriptions: {len([t for t in results.get('transcriptions', []) if t['status'] == 'success'])}")
    else:
        print(f"\n💥 Batch extraction failed!")


if __name__ == "__main__":
    main()
