#!/usr/bin/env python3
"""Simple test for MiniMax MCP - with timeout."""

import json
import subprocess
import sys
import signal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from nanobot.config.loader import load_config


def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")


def test_mcp():
    print("=" * 60)
    print("MiniMax MCP Tool Discovery")
    print("=" * 60)

    config = load_config()
    api_key = config.providers.minimax.api_key

    if not api_key:
        print("\n❌ No MiniMax API key in config")
        return

    print(f"\n✓ API Key configured")
    print(f"  Base: {config.providers.minimax.api_base or 'default'}")

    # Set timeout
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(15)  # 15 second timeout

    try:
        env = {
            **subprocess.os.environ,
            "MINIMAX_API_KEY": api_key,
        }
        if config.providers.minimax.api_base:
            env["MINIMAX_API_BASE"] = config.providers.minimax.api_base

        print("\n📡 Starting uvx minimax-coding-plan-mcp...")
        print("   (timeout: 15s)")

        process = subprocess.Popen(
            ["uvx", "minimax-coding-plan-mcp", "-y"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )

        # Send initialize
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0.1"},
            },
        }
        process.stdin.write(json.dumps(init_req) + "\n")
        process.stdin.flush()

        print("\n⏳ Waiting for response...")
        response = process.stdout.readline()
        signal.alarm(0)  # Cancel timeout

        print(f"\n📥 Response received:")
        try:
            data = json.loads(response)
            print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
        except:
            print(f"Raw: {response[:500]}")

        # Try to get tools
        print("\n📤 Requesting tools/list...")
        tools_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        process.stdin.write(json.dumps(tools_req) + "\n")
        process.stdin.flush()

        signal.alarm(10)
        tools_response = process.stdout.readline()
        signal.alarm(0)

        try:
            data = json.loads(tools_response)
            tools = data.get("result", {}).get("tools", [])
            print(f"\n✓ Found {len(tools)} tool(s):")
            for tool in tools:
                print(f"\n  📌 {tool.get('name')}")
                print(f"     {tool.get('description', 'No description')[:100]}")
                params = tool.get('parameters', {})
                if params.get('properties'):
                    print(f"     Parameters: {list(params['properties'].keys())}")
        except Exception as e:
            print(f"Error parsing: {e}")
            print(f"Raw: {tools_response[:500]}")

        process.terminate()

    except TimeoutError:
        print("\n⏰ Timeout! The MCP server is not responding.")
        print("Possible causes:")
        print("  1. uvx is downloading the package (first run)")
        print("  2. The MCP server requires different parameters")
        print("  3. Network issues or API key invalid")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_mcp()
