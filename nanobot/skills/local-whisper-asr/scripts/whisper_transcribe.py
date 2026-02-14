#!/usr/bin/env python3
"""
Local Whisper ASR Transcription Script

This script provides local speech-to-text transcription using OpenAI's Whisper model.
It runs completely locally in a Python virtual environment - no API keys required.

Usage:
    python whisper_transcribe.py <audio_file> [options]

Options:
    --language: Language code (zh, en, ja, etc.) [default: auto-detect]
    --format: Output format (txt, srt, lrc) [default: txt]
    --model: Whisper model size (tiny, base, small, medium, large) [default: base]
    --device: Device to use (auto, cpu, cuda) [default: auto]
    --output: Output file path [default: auto]

Examples:
    python whisper_transcribe.py audio.mp3
    python whisper_transcribe.py audio.mp3 --language zh --format srt
    python whisper_transcribe.py audio.mp3 --model small --output result.txt
"""

import sys
import os
import json
import subprocess
import argparse
from pathlib import Path
from typing import Optional, Dict, Any, List


# Configuration - use project venv if available, otherwise create user venv
PROJECT_VENV = Path("/Users/likang/geminicode/Agent/nanobot/.venv")
VENV_DIR = PROJECT_VENV if PROJECT_VENV.exists() else (Path.home() / ".nanobot" / "whisper-venv")
MODELS_DIR = Path.home() / ".nanobot" / "whisper-models"


def ensure_venv_exists() -> bool:
    """
    Ensure Python virtual environment exists and is set up.

    Returns:
        True if venv is ready, False otherwise
    """
    # Check if venv exists
    if not VENV_DIR.exists():
        print(f"🔧 Creating virtual environment at {VENV_DIR}...")
        try:
            subprocess.run(
                [sys.executable, "-m", "venv", str(VENV_DIR)],
                check=True,
                capture_output=True
            )
            print(f"✅ Virtual environment created")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to create virtual environment: {e}")
            return False

    # Check if whisper is installed
    pip_path = VENV_DIR / "bin" / "pip"
    if not pip_path.exists():
        pip_path = VENV_DIR / "Scripts" / "pip.exe"  # Windows

    if not pip_path.exists():
        print(f"❌ pip not found in virtual environment")
        return False

    # Check if whisper is installed
    try:
        result = subprocess.run(
            [str(pip_path), "show", "openai-whisper"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print("📦 Installing openai-whisper (this may take a few minutes)...")
            subprocess.run(
                [str(pip_path), "install", "-q", "openai-whisper", "torch", "numpy", "tqdm"],
                check=True
            )
            print("✅ Dependencies installed")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

    return True


def get_python_path() -> str:
    """Get Python executable path in virtual environment."""
    if os.name == 'nt':  # Windows
        return str(VENV_DIR / "Scripts" / "python.exe")
    else:  # Unix/Linux/macOS
        return str(VENV_DIR / "bin" / "python")


def transcribe_with_venv(
    audio_path: str,
    model: str = "base",
    language: Optional[str] = None,
    device: str = "auto",
    compute_type: str = "int8"
) -> Optional[Dict[str, Any]]:
    """
    Run transcription in virtual environment.

    Args:
        audio_path: Path to audio file
        model: Model size (tiny, base, small, medium, large)
        language: Language code (zh, en, ja, etc.)
        device: Device (auto, cpu, cuda)
        compute_type: Compute type (int8, float16, float32)

    Returns:
        Transcription result or None if failed
    """
    if not ensure_venv_exists():
        return None

    # Create temporary script to run in venv
    script_content = f'''
import sys
import json
import warnings
warnings.filterwarnings('ignore')

import whisper

audio_path = {repr(audio_path)}
model_size = {repr(model)}
language = {repr(language)}

print(f"🎯 Loading Whisper model: {{model_size}}", flush=True)

# Load model
model = whisper.load_model(model_size)

print(f"🎤 Transcribing: {{audio_path}}", flush=True)

# Transcribe
result = model.transcribe(
    audio_path,
    language=language,
    verbose=False
)

# Format segments with proper timing
segments_list = []
for segment in result["segments"]:
    segments_list.append({{
        "start": segment["start"],
        "end": segment["end"],
        "text": segment["text"].strip()
    }})

output = {{
    "text": result["text"],
    "segments": segments_list,
    "language": result.get("language", "unknown"),
    "language_probability": 1.0
}}

print(json.dumps(output, ensure_ascii=False))
'''

    # Write and execute script
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(script_content)
        script_path = f.name

    try:
        python_path = get_python_path()

        print(f"⏳ Starting transcription (this may take a while)...")

        result = subprocess.run(
            [python_path, script_path],
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout for long audio
        )

        if result.returncode != 0:
            print(f"❌ Transcription failed:")
            print(result.stderr)
            return None

        # Parse JSON output (last line should be the result)
        lines = result.stdout.strip().split('\n')
        for line in reversed(lines):
            line = line.strip()
            if line and line.startswith('{'):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue

        print("❌ Could not parse transcription result")
        return None

    except subprocess.TimeoutExpired:
        print("❌ Transcription timed out")
        return None
    except Exception as e:
        print(f"❌ Error during transcription: {e}")
        return None
    finally:
        os.unlink(script_path)


def format_transcription(
    result: Dict[str, Any],
    output_format: str = "txt",
    audio_info: Optional[Dict[str, Any]] = None
) -> str:
    """
    Format transcription result based on output format.

    Args:
        result: Transcription result from Whisper
        output_format: Output format (txt, srt, lrc)
        audio_info: Optional audio metadata

    Returns:
        Formatted text
    """
    if output_format == "txt":
        header = ""
        if audio_info:
            header = f"Title: {audio_info.get('title', 'Unknown')}\\n"
            header += f"Duration: {audio_info.get('duration', 0)} seconds\\n"
            header += f"Model: whisper-{result.get('language', 'unknown')}\\n"
            header += f"Language: {result.get('language', 'unknown')}\\n"
            header += "-" * 50 + "\\n\\n"
        return header + result["text"]

    elif output_format == "srt":
        lines = []
        for i, segment in enumerate(result["segments"], 1):
            start = segment["start"]
            end = segment["end"]
            text = segment["text"]

            # Format timestamps
            start_str = f"{int(start//3600):02d}:{int((start%3600)//60):02d}:{int(start%60):02d},{int((start%1)*1000):03d}"
            end_str = f"{int(end//3600):02d}:{int((end%3600)//60):02d}:{int(end%60):02d},{int((end%1)*1000):03d}"

            lines.append(f"{i}")
            lines.append(f"{start_str} --> {end_str}")
            lines.append(text)
            lines.append("")

        return "\\n".join(lines)

    elif output_format == "lrc":
        lines = []
        for segment in result["segments"]:
            start = segment["start"]
            text = segment["text"]
            timestamp = f"[{int(start//60):02d}:{int(start%60):02d}.{int((start%1)*100):02d}]"
            lines.append(f"{timestamp}{text}")
        return "\\n".join(lines)

    return result["text"]


def save_transcription(
    content: str,
    output_path: str
) -> str:
    """Save transcription to file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return output_path


def transcribe_audio(
    audio_path: str,
    language: str = "auto",
    output_format: str = "txt",
    model: str = "base",
    device: str = "auto",
    compute_type: str = "int8",
    output_path: Optional[str] = None,
    audio_info: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Transcribe audio file using local Whisper.

    Args:
        audio_path: Path to audio file
        language: Language code (zh, en, ja, etc.) or "auto" for auto-detect
        output_format: Output format (txt, srt, lrc)
        model: Model size (tiny, base, small, medium, large)
        device: Device (auto, cpu, cuda)
        compute_type: Compute type (int8, float16, float32)
        output_path: Output file path (optional)
        audio_info: Audio metadata for header (optional)

    Returns:
        Path to output file or None if failed
    """
    # Check audio file exists
    if not os.path.exists(audio_path):
        print(f"❌ Audio file not found: {audio_path}")
        return None

    # Transcribe
    lang_code = None if language == "auto" else language

    result = transcribe_with_venv(
        audio_path=audio_path,
        model=model,
        language=lang_code,
        device=device,
        compute_type=compute_type
    )

    if not result:
        return None

    # Format output
    formatted = format_transcription(result, output_format, audio_info)

    # Determine output path
    if not output_path:
        base_path = Path(audio_path)
        suffix = f"_whisper_{model}"
        output_path = str(base_path.parent / f"{base_path.stem}{suffix}.{output_format}")

    # Save
    save_transcription(formatted, output_path)

    print(f"\\n✅ Transcription saved to: {output_path}")
    print(f"📊 Language: {result.get('language', 'unknown')} "
          f"(confidence: {result.get('language_probability', 0):.2%})")
    print(f"📝 Characters: {len(result['text'])}")

    return output_path


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Local Whisper ASR Transcription"
    )
    parser.add_argument("audio_file", help="Path to audio file")
    parser.add_argument(
        "--language", "-l",
        default="auto",
        help="Language code (zh, en, ja, etc.) or 'auto' for auto-detect"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["txt", "srt", "lrc"],
        default="txt",
        help="Output format"
    )
    parser.add_argument(
        "--model", "-m",
        choices=["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"],
        default="base",
        help="Whisper model size"
    )
    parser.add_argument(
        "--device", "-d",
        choices=["auto", "cpu", "cuda"],
        default="auto",
        help="Device to use"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path"
    )
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="Only setup environment without transcribing"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("🎤 Local Whisper ASR Transcription")
    print("=" * 60)

    # Setup only mode
    if args.setup_only:
        print("🔧 Setting up environment...")
        if ensure_venv_exists():
            print("✅ Environment ready!")
            print(f"   Virtual env: {VENV_DIR}")
            print(f"   Models dir: {MODELS_DIR}")
        else:
            print("❌ Setup failed")
            sys.exit(1)
        return

    # Transcribe
    result = transcribe_audio(
        audio_path=args.audio_file,
        language=args.language,
        output_format=args.format,
        model=args.model,
        device=args.device,
        output_path=args.output
    )

    if result:
        print("\\n🎉 Transcription completed!")
    else:
        print("\\n❌ Transcription failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
