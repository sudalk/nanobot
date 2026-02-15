#!/usr/bin/env python3
"""Test MCP tool integration."""

import asyncio
import sys

# Add nanobot to path
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))

from nanobot.agent.tools.mcp import MiniMaxMCPTool


async def test_minimax_mcp():
    """Test MiniMax MCP tool."""
    print("Testing MiniMax MCP tool...")

    # Create tool
    tool = MiniMaxMCPTool()

    print(f"Tool name: {tool.name}")
    print(f"Tool description: {tool.description}")
    print(f"Tool parameters: {tool.parameters}")

    # Try to execute
    print("\nTrying to execute tool...")
    try:
        result = await tool.execute(prompt="Hello, this is a test")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_minimax_mcp())
