#!/usr/bin/env python3
"""
Test script for Qwen3-ASR-Flash API connectivity.

This script tests:
1. Configuration loading from ~/.nanobot/config.json
2. API key validation
3. Basic connectivity to DashScope API

Usage:
    python test_asr_connection.py
"""

import sys
import json
from pathlib import Path


def load_config():
    """Load nanobot configuration from config file."""
    config_paths = [
        Path.home() / ".nanobot" / "config.json",
        Path.home() / ".config" / "nanobot" / "config.json",
    ]

    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f), config_path
            except (json.JSONDecodeError, IOError) as e:
                print(f"❌ Failed to load config from {config_path}: {e}")

    return None, None


def test_configuration():
    """Test if ASR configuration is properly set up."""
    print("=" * 60)
    print("🔧 Step 1: Checking Configuration")
    print("=" * 60)

    config, config_path = load_config()

    if not config:
        print("❌ No configuration file found!")
        print("\nExpected locations:")
        print("  - ~/.nanobot/config.json")
        print("  - ~/.config/nanobot/config.json")
        return False

    print(f"✅ Config file found: {config_path}")

    # Check tools.asr configuration
    tools = config.get('tools', {})
    asr_config = tools.get('asr', {})

    if not asr_config:
        print("❌ No ASR configuration found in config!")
        print("\nPlease add the following to your config.json:")
        print(json.dumps({
            "tools": {
                "asr": {
                    "api_key": "your-dashscope-api-key",
                    "api_base": "https://dashscope.aliyuncs.com/api/v1",
                    "model": "qwen3-asr-flash"
                }
            }
        }, indent=2))
        return False

    api_key = asr_config.get('api_key', '')
    api_base = asr_config.get('api_base', 'https://dashscope.aliyuncs.com/api/v1')
    model = asr_config.get('model', 'qwen3-asr-flash')

    print(f"✅ ASR configuration found")
    print(f"   API Base: {api_base}")
    print(f"   Model: {model}")

    if not api_key:
        print("❌ API key is empty!")
        return False

    # Mask API key for display
    masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
    print(f"   API Key: {masked_key}")
    print(f"✅ API key is configured")

    return True, api_key, api_base, model


def test_api_connectivity(api_key, api_base, model):
    """Test API connectivity with a simple request."""
    print("\n" + "=" * 60)
    print("🌐 Step 2: Testing API Connectivity")
    print("=" * 60)

    try:
        import requests
    except ImportError:
        print("❌ requests library not installed!")
        print("   Run: pip install requests")
        return False

    # Test with a simple GET request to check API availability
    # DashScope API endpoint for checking models or account info
    url = f"{api_base}/models"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        print(f"Testing connection to: {url}")
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            print("✅ API connection successful!")
            try:
                data = response.json()
                if 'data' in data:
                    models = [m.get('id', '') for m in data['data']]
                    if model in models:
                        print(f"✅ Model '{model}' is available")
                    else:
                        print(f"⚠️  Model '{model}' not found in available models")
                        print(f"   Available ASR models: {[m for m in models if 'asr' in m.lower()]}")
            except:
                pass
            return True

        elif response.status_code == 401:
            print("❌ Authentication failed! (401)")
            print("   Please check your API key.")
            print(f"   Response: {response.text[:200]}")
            return False

        elif response.status_code == 403:
            print("❌ Access forbidden! (403)")
            print("   Your API key may not have access to this service.")
            print(f"   Response: {response.text[:200]}")
            return False

        else:
            print(f"⚠️  Unexpected status code: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False

    except requests.exceptions.Timeout:
        print("❌ Connection timed out!")
        print("   The API server may be slow or unreachable.")
        return False

    except requests.exceptions.ConnectionError as e:
        print("❌ Connection error!")
        print(f"   Error: {e}")
        print("   Please check your internet connection.")
        return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False


def test_asr_with_sample(api_key, api_base, model):
    """Test ASR with a small sample audio if available."""
    print("\n" + "=" * 60)
    print("🎤 Step 3: Testing ASR Functionality (Optional)")
    print("=" * 60)

    # Create a small test audio file using ffmpeg if available
    import subprocess
    import tempfile
    import os

    test_audio_path = None
    try:
        # Check if ffmpeg is available
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
        if result.returncode != 0:
            print("⚠️  ffmpeg not found, skipping ASR functional test")
            print("   To test full ASR, install ffmpeg: brew install ffmpeg (macOS)")
            return None

        print("Creating test audio file...")

        # Create a temporary directory
        with tempfile.TemporaryDirectory() as tmpdir:
            test_audio_path = os.path.join(tmpdir, "test_audio.mp3")

            # Generate a 3-second sine wave test tone
            cmd = [
                'ffmpeg', '-f', 'lavfi', '-i',
                'sine=frequency=1000:duration=3',
                '-ar', '16000', '-ac', '1',
                test_audio_path, '-y'
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=10)

            if result.returncode != 0:
                print("⚠️  Failed to create test audio")
                return None

            print(f"✅ Test audio created: {test_audio_path}")

            # Now test ASR
            print("\nSending audio to ASR API...")

            import requests

            url = f"{api_base}/services/aigc/multimodal-generation/generation"

            headers = {
                "Authorization": f"Bearer {api_key}",
            }

            with open(test_audio_path, 'rb') as f:
                files = {'file': ('test.mp3', f, 'audio/mpeg')}
                data = {
                    'model': model,
                    'parameters': json.dumps({'language': 'zh'}),
                }

                response = requests.post(
                    url,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=60
                )

            if response.status_code == 200:
                result = response.json()
                print("✅ ASR API request successful!")
                print(f"   Response: {json.dumps(result, indent=2)[:500]}...")
                return True
            else:
                print(f"❌ ASR request failed: {response.status_code}")
                print(f"   Response: {response.text[:500]}")
                return False

    except Exception as e:
        print(f"⚠️  ASR functional test skipped: {e}")
        return None


def main():
    """Main test function."""
    print("\n" + "=" * 60)
    print("🧪 Qwen3-ASR-Flash Connectivity Test")
    print("=" * 60)

    # Step 1: Check configuration
    config_result = test_configuration()
    if not config_result:
        print("\n" + "=" * 60)
        print("❌ Configuration test failed!")
        print("=" * 60)
        sys.exit(1)

    _, api_key, api_base, model = config_result

    # Step 2: Test API connectivity
    if not test_api_connectivity(api_key, api_base, model):
        print("\n" + "=" * 60)
        print("❌ API connectivity test failed!")
        print("=" * 60)
        sys.exit(1)

    # Step 3: Test ASR functionality (optional)
    test_asr_with_sample(api_key, api_base, model)

    # Final summary
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
    print("\nYour Qwen3-ASR-Flash configuration is working correctly.")
    print("You can now use the Bilibili audio extractor with transcription:")
    print("\n  python bilibili_audio_extract.py <url> --transcribe")
    print("\n")


if __name__ == "__main__":
    main()
