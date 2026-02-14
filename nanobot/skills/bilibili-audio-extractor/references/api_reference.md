# Bilibili Audio Extraction API Reference

## Overview

This document provides detailed technical reference for the Bilibili Audio Extraction skill, including API specifications, error codes, format options, and troubleshooting guides.

## Core Functionality

### URL Validation

The system validates Bilibili video URLs using regular expression patterns:

```python
VALID_PATTERNS = [
    r'https?://(?:www\.)?bilibili\.com/video/[\w\.\-]+',
    r'https?://b23\.tv/[\w\.\-]+',
    r'https?://(?:www\.)?bilibili\.com/blackboard/topic/list',
]
```

**Supported URL Formats:**
- Standard video: `https://www.bilibili.com/video/BV1xx411c7mD`
- Short link: `https://b23.tv/abc123`
- Topic page: `https://www.bilibili.com/blackboard/topic/list`

### Audio Format Specifications

#### Supported Formats

| Format | Extension | Bitrate Range | Compatibility | Use Case |
|--------|-----------|---------------|---------------|----------|
| **MP3** | .mp3 | 128k-320k | Universal | General purpose, best compatibility |
| **M4A** | .m4a | 128k-320k | Apple/iOS optimized | iPhone, iPad, Mac users |
| **WAV** | .wav | Uncompressed | Professional | Audio editing, archival |
| **FLAC** | .flac | Lossless compressed | Audiophiles | Highest quality, larger files |

#### Quality Settings

| Setting | Bitrate | File Size (per hour) | Recommended For |
|---------|---------|---------------------|-----------------|
| **High** | 320k | ~40-60 MB | Music, important content |
| **Medium** | 192k | ~25-35 MB | General listening, podcasts |
| **Low** | 128k | ~15-25 MB | Mobile devices, storage constraints |

### Video Metadata Extraction

The system extracts the following metadata from Bilibili videos:

```json
{
    "title": "Video Title",
    "duration": 3600,
    "uploader": "Channel Name",
    "view_count": 1500000,
    "upload_date": "2024-01-15",
    "description": "Video description...",
    "thumbnail": "https://example.com/thumb.jpg"
}
```

**Metadata Fields:**
- `title`: Video title (cleaned for safe filenames)
- `duration`: Duration in seconds
- `uploader`: Channel/uploader name
- `view_count`: Total view count
- `upload_date`: Upload date (YYYY-MM-DD format)
- `description`: Video description (truncated for display)

## Error Handling

### Error Categories

#### 1. URL Validation Errors

| Error Code | Message | Cause | Solution |
|------------|---------|-------|----------|
| **URL_INVALID_FORMAT** | Invalid Bilibili video URL | URL doesn't match expected patterns | Check URL format, ensure it's a valid Bilibili link |
| **URL_PRIVATE** | Video is private or requires login | Video access restricted | Use public videos only |
| **URL_NOT_FOUND** | Video does not exist | BV ID doesn't exist | Verify video URL is correct |

#### 2. Extraction Errors

| Error Code | Message | Cause | Solution |
|------------|---------|-------|----------|
| **EXTRACTION_FAILED** | Audio extraction failed | yt-dlp processing error | Check video availability, update yt-dlp |
| **NETWORK_TIMEOUT** | Request timed out | Network connectivity issues | Check internet connection, retry later |
| **STORAGE_FULL** | Insufficient storage space | Disk space insufficient | Free up disk space or choose smaller format |
| **CONVERSION_ERROR** | Format conversion failed | Audio codec issues | Try different output format |

#### 3. System Errors

| Error Code | Message | Cause | Solution |
|------------|---------|-------|----------|
| **YTDLP_NOT_FOUND** | yt-dlp not installed | Missing dependency | Install: `pip install yt-dlp` |
| **PERMISSION_DENIED** | Cannot write to output directory | File system permissions | Check directory permissions |
| **MEMORY_INSUFFICIENT** | Insufficient memory | Large video processing | Use lower quality setting |

### Error Response Format

All errors return a consistent JSON structure:

```json
{
    "success": false,
    "error": {
        "code": "EXTRACTION_FAILED",
        "message": "Detailed error description",
        "suggestion": "Recommended action to resolve",
        "context": {
            "video_url": "...",
            "timestamp": "2024-01-15T10:30:00Z"
        }
    }
}
```

## Technical Implementation

### yt-dlp Integration

The extraction process uses yt-dlp with the following command structure:

```bash
yt-dlp \
    --extract-audio \
    --audio-format {format} \
    --audio-quality {bitrate} \
    -o {output_path} \
    {video_url}
```

**Parameters:**
- `--extract-audio`: Extract audio only
- `--audio-format`: Target format (mp3, m4a, wav, flac)
- `--audio-quality`: Bitrate setting (128k, 192k, 320k)
- `-o`: Output file path template

### Filename Sanitization

Filenames are automatically cleaned to ensure compatibility:

```python
def sanitize_filename(title: str, max_length: int = 50) -> str:
    # Remove special characters
    clean_title = re.sub(r'[^\w\-\.]', '_', title)
    # Truncate to max length
    clean_title = clean_title[:max_length]
    # Remove multiple underscores
    clean_title = re.sub(r'_+', '_', clean_title)
    # Trim underscores
    clean_title = clean_title.strip('_')
    return clean_title
```

**Sanitization Rules:**
- Allow: alphanumeric, hyphens, underscores, dots
- Replace: spaces and special characters with underscores
- Limit: maximum 50 characters
- Preserve: file extension

### Progress Tracking

The system provides real-time progress updates:

```json
{
    "phase": "extracting",
    "progress": 0.65,
    "message": "Converting audio format...",
    "estimated_time_remaining": "2m 30s",
    "file_size_mb": 35.2
}
```

**Progress Phases:**
- `validating`: Checking URL and video availability
- `downloading`: Downloading video content
- `extracting`: Extracting audio stream
- `converting`: Converting to target format
- `finalizing`: Saving file and cleanup

## Rate Limiting and Best Practices

### Recommended Limits

| Operation | Recommended Delay | Maximum Parallel |
|-----------|------------------|-----------------|
| Single extraction | 0 seconds | 1 |
| Batch processing | 2-5 seconds | 2-3 |
| Playlist processing | 5-10 seconds | 1-2 |

### Best Practices

1. **Respect Rate Limits**
   - Add delays between requests
   - Avoid overwhelming Bilibili's servers
   - Use parallel processing sparingly

2. **Error Recovery**
   - Implement retry logic with exponential backoff
   - Log failed URLs for manual review
   - Provide clear error messages to users

3. **Resource Management**
   - Monitor disk space before starting
   - Clean up temporary files regularly
   - Use appropriate quality settings for use case

4. **User Experience**
   - Provide progress updates
   - Validate URLs before processing
   - Offer format recommendations

## Configuration Options

### Environment Variables

```bash
# Default settings
BILIBILI_DEFAULT_FORMAT=mp3
BILIBILI_DEFAULT_QUALITY=high
BILIBILI_MAX_CONCURRENT=2
BILIBILI_DELAY_BETWEEN_DOWNLOADS=2.0
BILIBILI_TEMP_DIR=/tmp/bilibili_audio
```

### Configuration File

Create `~/.bilibili_audio_config.json`:

```json
{
    "default_format": "mp3",
    "default_quality": "high",
    "output_directory": "~/Downloads/Bilibili_Audio",
    "max_concurrent_downloads": 2,
    "delay_between_downloads": 2.0,
    "auto_cleanup": true,
    "filename_template": "{index}_{title}.{format}"
}
```

## Troubleshooting Guide

### Common Issues and Solutions

#### 1. "yt-dlp not found"

**Problem:** Command line tool not installed

**Solution:**
```bash
pip install --upgrade yt-dlp
# or
pip3 install --upgrade yt-dlp
```

#### 2. "Video is private"

**Problem:** Cannot access private or members-only videos

**Solution:**
- Use public videos only
- Check if login is required
- Verify video URL is correct

#### 3. "Network timeout"

**Problem:** Connection issues during download

**Solution:**
- Check internet connection
- Try using a VPN if in restricted region
- Retry with longer timeout settings

#### 4. "File size too large"

**Problem:** Generated files exceed storage capacity

**Solution:**
- Use lower quality settings (128k instead of 320k)
- Choose MP3 format instead of FLAC
- Process videos in smaller batches

#### 5. "Permission denied"

**Problem:** Cannot write to output directory

**Solution:**
```bash
# Check directory permissions
ls -la output_directory

# Fix permissions if needed
chmod 755 output_directory

# Or change to writable directory
cd ~/Downloads/
```

### Performance Optimization

#### For Single Videos
- Use high quality settings for important content
- Choose MP3 format for best compatibility
- Monitor progress during extraction

#### For Batch Processing
- Use medium quality to balance speed and quality
- Limit parallel downloads to 2-3
- Add 2-5 second delays between downloads
- Process shorter videos first

#### Storage Optimization
- Delete temporary files after extraction
- Use appropriate format for your use case
- Monitor disk space usage
- Compress completed batches

## API Usage Examples

### Python Integration

```python
import subprocess
import json
import os

def extract_bilibili_audio(video_url, format='mp3', quality='high'):
    """Extract audio from Bilibili video"""
    
    # Validate URL
    if not validate_bilibili_url(video_url):
        raise ValueError("Invalid Bilibili video URL")
    
    # Get video info
    video_info = get_video_info(video_url)
    
    # Create output filename
    safe_title = sanitize_filename(video_info['title'])
    output_file = f"{safe_title}.{format}"
    
    # Extract audio
    cmd = [
        'yt-dlp',
        '--extract-audio',
        '--audio-format', format,
        '--audio-quality', quality,
        '-o', output_file,
        video_url
    ]
    
    try:
        subprocess.run(cmd, check=True)
        
        return {
            'success': True,
            'output_file': output_file,
            'video_info': video_info,
            'file_size': os.path.getsize(output_file)
        }
        
    except subprocess.CalledProcessError as e:
        return {
            'success': False,
            'error': str(e),
            'video_info': video_info
        }
```

### Command Line Usage

```bash
# Basic extraction
python bilibili_audio_extract.py https://www.bilibili.com/video/BV1xx411c7mD

# Custom format and quality
python bilibili_audio_extract.py https://b23.tv/abc123 --format flac --quality high

# Batch processing
python batch_bilibili_extract.py urls.txt --parallel 3 --delay 2

# Custom output directory
python bilibili_audio_extract.py https://www.bilibili.com/video/BV1xx411c7mD --output ~/Music --filename my_audio
```

This reference guide provides comprehensive technical details for implementing and troubleshooting Bilibili audio extraction functionality.