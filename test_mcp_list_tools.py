#!/usr/bin/env python3
"""List all tools available from MiniMax MCP server."""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from nanobot.config.loader import load_config


def list_minimax_tools():
    """Connect to MiniMax MCP server and list available tools."""
    print("=" * 60)
    print("MiniMax MCP Server - Tool Discovery")
    print("=" * 60)

    # Load config to get API key
    config = load_config()
    api_key = config.providers.minimax.api_key

    if not api_key:
        print("\n❌ ERROR: No MiniMax API key found in config!")
        print("Please add it to ~/.nanobot/config.json:")
        print('  "providers": { "minimax": { "api_key": "your-key" } }')
        return

    print(f"\n✓ API Key found: {'*' * 10}")
    print(f"  API Base: {config.providers.minimax.api_base or 'default'}")

    # Start MCP server
    print("\n" + "-" * 60)
    print("Starting MiniMax MCP server...")
    print("-" * 60)

    env = {
        **subprocess.os.environ,
        "MINIMAX_API_KEY": api_key,
    }
    if config.providers.minimax.api_base:
        env["MINIMAX_API_BASE"] = config.providers.minimax.api_base

    try:
        process = subprocess.Popen(
            ["uvx", "minimax-coding-plan-mcp", "-y"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )

        request_id = 1

        # Send initialize
        print("\n📤 Sending initialize...")
        init_request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "nanobot-test", "version": "0.1.0"},
            },
        }
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()

        init_response = json.loads(process.stdout.readline())
        print(f"📥 Initialize response: {json.dumps(init_response, indent=2, ensure_ascii=False)[:500]}")

        if "error" in init_response:
            print(f"\n❌ Initialize failed: {init_response['error']}")
            process.terminate()
            return

        # Send tools/list
        request_id += 1
        print("\n📤 Sending tools/list...")
        list_request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/list",
            "params": {},
        }
        process.stdin.write(json.dumps(list_request) + "\n")
        process.stdin.flush()

        list_response = json.loads(process.stdout.readline())

        if "error" in list_response:
            print(f"\n❌ tools/list failed: {list_response['error']}")
            process.terminate()
            return

        # Parse tools
        tools = list_response.get("result", {}).get("tools", [])

        print("\n" + "=" * 60)
        print(f"✓ Found {len(tools)} tool(s):")
        print("=" * 60)

        for i, tool in enumerate(tools, 1):
            print(f"\n{i}. {tool.get('name', 'unknown')}")
            print(f"   Description: {tool.get('description', 'N/A')}")
            print(f"   Parameters:")
            params = tool.get('parameters', {})
            if params and params.get('properties'):
                for param_name, param_info in params['properties'].items():
                    param_type = param_info.get('type', 'any')
                    param_desc = param_info.get('description', '')
                    required = param_name in params.get('required', [])
                    req_mark = " (required)" if required else ""
                    print(f"     - {param_name}: {param_type}{req_mark}")
                    if param_desc:
                        print(f"       {param_desc}")
            else:
                print("     (no parameters)")

        # Cleanup
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

        print("\n" + "=" * 60)
        print("Tool discovery complete!")
        print("=" * 60)

    except FileNotFoundError:
        print("\n❌ ERROR: 'uvx' command not found!")
        print("Please install uv: pip install uv")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    list_minimax_tools()
