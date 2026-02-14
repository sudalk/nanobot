#!/usr/bin/env python3
"""
Setup script for Local Whisper ASR.

This script sets up the Python virtual environment and installs required dependencies.
Run this once before using the transcription feature.

Usage:
    python setup_whisper.py
"""

import sys
import os
import subprocess
from pathlib import Path

# Use project virtual environment or create one in ~/.nanobot
PROJECT_VENV = Path("/Users/likang/geminicode/Agent/nanobot/.venv")
if PROJECT_VENV.exists():
    VENV_DIR = PROJECT_VENV
    print(f"Using project virtual environment: {VENV_DIR}")
else:
    VENV_DIR = Path.home() / ".nanobot" / "whisper-venv"
    print(f"Using user virtual environment: {VENV_DIR}")


def check_python_version() -> bool:
    """Check if Python version is compatible."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python 3.8+ required, found {version.major}.{version.minor}")
        return False
    print(f"✅ Python version: {version.major}.{version.minor}.{version.micro}")
    return True


def check_ffmpeg() -> bool:
    """Check if FFmpeg is installed."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"✅ FFmpeg: {version_line}")
            return True
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    print("❌ FFmpeg not found")
    print("   Please install FFmpeg:")
    print("   - macOS: brew install ffmpeg")
    print("   - Ubuntu: sudo apt install ffmpeg")
    print("   - Windows: https://ffmpeg.org/download.html")
    return False


def create_venv() -> bool:
    """Create Python virtual environment."""
    if VENV_DIR.exists():
        print(f"✅ Virtual environment already exists: {VENV_DIR}")
        return True

    print(f"🔧 Creating virtual environment at {VENV_DIR}...")
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", str(VENV_DIR)],
            check=True,
            capture_output=True
        )
        print("✅ Virtual environment created")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create virtual environment: {e}")
        return False


def install_dependencies() -> bool:
    """Install required packages in virtual environment."""
    if os.name == 'nt':  # Windows
        pip_path = VENV_DIR / "Scripts" / "pip.exe"
    else:
        pip_path = VENV_DIR / "bin" / "pip"

    if not pip_path.exists():
        print(f"❌ pip not found in virtual environment")
        return False

    print("📦 Installing dependencies (this may take a few minutes)...")
    print("   - openai-whisper")
    print("   - torch")
    print("   - numpy")

    try:
        # Upgrade pip first
        subprocess.run(
            [str(pip_path), "install", "-q", "--upgrade", "pip"],
            check=True,
            capture_output=True
        )

        # Install packages - use openai-whisper instead of faster-whisper for better compatibility
        subprocess.run(
            [str(pip_path), "install", "-q", "openai-whisper", "torch", "numpy", "tqdm"],
            check=True
        )

        print("✅ Dependencies installed")
        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False


def test_installation() -> bool:
    """Test if whisper can be imported."""
    python_path = get_python_path()

    print("🧪 Testing installation...")

    test_script = """
import sys
try:
    import whisper
    print("✅ whisper imported successfully")
    sys.exit(0)
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)
"""

    try:
        result = subprocess.run(
            [python_path, "-c", test_script],
            capture_output=True,
            text=True,
            timeout=30
        )
        print(result.stdout.strip())
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def get_python_path() -> str:
    """Get Python executable path in virtual environment."""
    if os.name == 'nt':  # Windows
        return str(VENV_DIR / "Scripts" / "python.exe")
    else:  # Unix/Linux/macOS
        return str(VENV_DIR / "bin" / "python")


def download_model(model: str = "base") -> bool:
    """Pre-download a Whisper model."""
    python_path = get_python_path()

    print(f"📥 Downloading Whisper model: {model} (this may take a while)...")
    print("   Model will be cached for future use")

    script = f"""
import warnings
warnings.filterwarnings('ignore')
import whisper
print(f"Loading model: {model}")
model_obj = whisper.load_model("{model}")
print(f"✅ Model downloaded successfully")
"""

    try:
        result = subprocess.run(
            [python_path, "-c", script],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes for download
        )
        print(result.stdout.strip())
        if result.stderr:
            print(result.stderr.strip())
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("❌ Model download timed out")
        return False
    except Exception as e:
        print(f"❌ Model download failed: {e}")
        return False


def main():
    """Main setup function."""
    print("=" * 60)
    print("🔧 Local Whisper ASR Setup")
    print("=" * 60)
    print()

    # Check prerequisites
    print("1️⃣ Checking prerequisites...")
    if not check_python_version():
        sys.exit(1)
    if not check_ffmpeg():
        print("\n⚠️  Please install FFmpeg and run setup again")
        sys.exit(1)
    print()

    # Create virtual environment
    print("2️⃣ Creating virtual environment...")
    if not create_venv():
        sys.exit(1)
    print()

    # Install dependencies
    print("3️⃣ Installing dependencies...")
    if not install_dependencies():
        sys.exit(1)
    print()

    # Test installation
    print("4️⃣ Testing installation...")
    if not test_installation():
        print("\n⚠️  Installation test failed")
        sys.exit(1)
    print()

    # Ask to download model (auto-yes in non-interactive mode)
    print("5️⃣ Model download")
    import sys
    if not sys.stdin.isatty():
        # Non-interactive mode, auto download
        print("   Auto-downloading 'base' model (~150MB)...")
        if download_model("base"):
            print("   ✅ Model ready")
        else:
            print("   ⚠️  Model will be downloaded on first use")
    else:
        response = input("   Download 'base' model now? (recommended, ~150MB) [Y/n]: ").strip().lower()
        if response in ('', 'y', 'yes'):
            if download_model("base"):
                print("   ✅ Model ready")
            else:
                print("   ⚠️  Model will be downloaded on first use")
        else:
            print("   ⏭️  Model will be downloaded on first use")
    print()

    # Summary
    print("=" * 60)
    print("✅ Setup complete!")
    print("=" * 60)
    print()
    print("You can now use local Whisper for transcription:")
    print()
    print("  python whisper_transcribe.py <audio_file>")
    print()
    print("Available models (accuracy vs speed trade-off):")
    print("  - tiny:  Fastest, basic accuracy")
    print("  - base:  Fast, good accuracy (recommended)")
    print("  - small: Slower, better accuracy")
    print("  - medium: Slow, very good accuracy")
    print("  - large: Slowest, best accuracy")
    print()


if __name__ == "__main__":
    main()
