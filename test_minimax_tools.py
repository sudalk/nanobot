#!/usr/bin/env python3
"""Test and list all MiniMax MCP tools."""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from nanobot.config.loader import load_config
from nanobot.agent.tools.mcp import MiniMaxMCPTool


def list_tools():
    """List all available MiniMax MCP tools."""
    print("=" * 70)
    print("MiniMax MCP Server - Available Tools")
    print("=" * 70)

    config = load_config()
    if not config.providers.minimax.api_key:
        print("\n❌ No MiniMax API key configured!")
        return

    # Create tool and discover available tools
    print("\n🔌 Connecting to MiniMax MCP server...\n")

    tool = MiniMaxMCPTool(
        api_key=config.providers.minimax.api_key,
        api_base=config.providers.minimax.api_base,
    )

    # Trigger initialization
    import asyncio
    async def discover():
        try:
            # Initialize to get tool list
            await asyncio.get_event_loop().run_in_executor(None, tool._initialize)

            print(f"✅ Connected successfully!")
            print(f"\n{'=' * 70}")
            print(f"Found {len(tool._tools_list)} tool(s):")
            print(f"{'=' * 70}\n")

            for i, t in enumerate(tool._tools_list, 1):
                name = t.get('name', 'unknown')
                desc = t.get('description', 'No description')
                params = t.get('parameters', {})

                print(f"{i}. 🔧 {name}")
                print(f"   {'─' * 60}")

                # Format description
                if desc:
                    # Truncate very long descriptions
                    if len(desc) > 200:
                        desc = desc[:200] + "..."
                    print(f"   📝 {desc}")

                # Show parameters
                if params and params.get('properties'):
                    print(f"\n   📋 Parameters:")
                    required = params.get('required', [])
                    for param_name, param_info in params['properties'].items():
                        param_type = param_info.get('type', 'any')
                        is_required = param_name in required
                        req_mark = " ✓" if is_required else " ○"
                        param_desc = param_info.get('description', '')
                        print(f"      {req_mark} {param_name}: {param_type}")
                        if param_desc:
                            short_desc = param_desc[:50] + "..." if len(param_desc) > 50 else param_desc
                            print(f"        └─ {short_desc}")
                else:
                    print(f"\n   📋 No parameters")

                print()

            print(f"{'=' * 70}")
            print("💡 Usage Example:")
            print(f"{'=' * 70}")
            print(f"   nanobot agent -m '用 minimax 搜索 Python 教程'")
            print(f"   nanobot agent -m '使用 web_search 查找最新的 AI 新闻'")
            print(f"{'=' * 70}")

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(discover())


if __name__ == "__main__":
    list_tools()
