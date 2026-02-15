#!/usr/bin/env python3
"""Test MiniMax MCP server and list available tools."""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from nanobot.config.loader import load_config


def test_mcp_tools():
    """Test MiniMax MCP server."""
    print("=" * 70)
    print("MiniMax MCP Server - Tool Discovery Test")
    print("=" * 70)

    # Load config
    config = load_config()
    api_key = config.providers.minimax.api_key
    api_base = config.providers.minimax.api_base or "https://api.minimaxi.com/v1"

    if not api_key:
        print("\n❌ No MiniMax API key found!")
        print("Add to ~/.nanobot/config.json:")
        print('  "providers": { "minimax": { "api_key": "your-key" } }')
        return

    print(f"\n✓ API Key: {'*' * 20} ({len(api_key)} chars)")
    print(f"✓ API Base: {api_base}")

    # Set environment
    env = {
        **os.environ,
        "MINIMAX_API_KEY": api_key,
        "MINIMAX_API_BASE": api_base,
    }

    print("\n" + "-" * 70)
    print("Starting minimax-coding-plan-mcp...")
    print("-" * 70)

    try:
        process = subprocess.Popen(
            ["minimax-coding-plan-mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )

        # Send initialize
        print("\n📤 Sending initialize...")
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "nanobot-test", "version": "0.1.0"},
            },
        }
        process.stdin.write(json.dumps(init_req) + "\n")
        process.stdin.flush()

        # Read response
        init_resp = process.stdout.readline()
        print(f"📥 Response: {init_resp[:300]}...")

        try:
            data = json.loads(init_resp)
            if "error" in data:
                print(f"\n❌ Initialize error: {data['error']}")
                process.terminate()
                return
            print("✓ Initialize successful")
        except json.JSONDecodeError:
            print(f"\n❌ Invalid JSON response: {init_resp[:200]}")
            process.terminate()
            return

        # Send tools/list
        print("\n📤 Sending tools/list...")
        tools_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        process.stdin.write(json.dumps(tools_req) + "\n")
        process.stdin.flush()

        tools_resp = process.stdout.readline()

        try:
            data = json.loads(tools_resp)
            if "error" in data:
                print(f"\n❌ tools/list error: {data['error']}")
                process.terminate()
                return

            tools = data.get("result", {}).get("tools", [])

            print("\n" + "=" * 70)
            print(f"✓ Discovered {len(tools)} tool(s) from MiniMax MCP:")
            print("=" * 70)

            for i, tool in enumerate(tools, 1):
                name = tool.get("name", "unknown")
                desc = tool.get("description", "No description available")
                params = tool.get("parameters", {})

                print(f"\n{i}. 🔧 {name}")
                print(f"   📝 {desc[:100]}{'...' if len(desc) > 100 else ''}")

                if params and params.get("properties"):
                    print(f"   📋 Parameters:")
                    required = params.get("required", [])
                    for param_name, param_info in params["properties"].items():
                        param_type = param_info.get("type", "any")
                        is_required = param_name in required
                        req_str = " (required)" if is_required else ""
                        param_desc = param_info.get("description", "")
                        print(f"      • {param_name}: {param_type}{req_str}")
                        if param_desc:
                            print(f"        {param_desc[:60]}{'...' if len(param_desc) > 60 else ''}")
                else:
                    print(f"   📋 No parameters")

            # Update our MCP tool with the correct schema
            if tools:
                print("\n" + "-" * 70)
                print("💡 Tool schema detected! You can now use:")
                print(f"   nanobot agent -m 'Use {tools[0]['name']} to help me...'")
                print("-" * 70)

        except json.JSONDecodeError:
            print(f"\n❌ Invalid tools/list response: {tools_resp[:200]}")

        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

    except FileNotFoundError:
        print("\n❌ minimax-coding-plan-mcp not found!")
        print("Install with: pip install minimax-coding-plan-mcp")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)


if __name__ == "__main__":
    test_mcp_tools()
