#!/usr/bin/env python3
"""Debug MCP tool registration and execution."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from nanobot.config.loader import load_config
from nanobot.agent.tools.mcp import MCPTool, MiniMaxMCPTool
from nanobot.agent.tools.registry import ToolRegistry


def test_config():
    """Test config loading."""
    print("=" * 50)
    print("1. Testing Config Loading")
    print("=" * 50)

    config = load_config()
    print(f"Config loaded: {type(config)}")
    print(f"Tools config: {config.tools}")
    print(f"MCP config: {config.tools.mcp}")
    print(f"  - enabled: {config.tools.mcp.enabled}")
    print(f"  - command: {config.tools.mcp.command}")
    print(f"  - args: {config.tools.mcp.args}")
    print(f"  - alias: {config.tools.mcp.alias}")

    # Check MiniMax provider
    print(f"\nMiniMax provider:")
    print(f"  - api_key: {'***' if config.providers.minimax.api_key else 'NOT SET'}")
    print(f"  - api_base: {config.providers.minimax.api_base}")

    return config


def test_tool_registration():
    """Test tool registration."""
    print("\n" + "=" * 50)
    print("2. Testing Tool Registration")
    print("=" * 50)

    registry = ToolRegistry()

    # Register MiniMax MCP tool
    config = load_config()
    if config.providers.minimax.api_key:
        print("Registering MiniMaxMCPTool...")
        tool = MiniMaxMCPTool(
            api_key=config.providers.minimax.api_key,
            api_base=config.providers.minimax.api_base,
        )
        registry.register(tool)
        print(f"  Registered: {tool.name}")
        print(f"  Description: {tool.description}")
        print(f"  Parameters: {tool.parameters}")
    else:
        print("No MiniMax API key, skipping MiniMaxMCPTool")

    # Register generic MCP if configured
    if config.tools.mcp.enabled and config.tools.mcp.command:
        print(f"\nRegistering generic MCPTool: {config.tools.mcp.alias}")
        tool = MCPTool(
            name=config.tools.mcp.alias,
            command=config.tools.mcp.command,
            args=config.tools.mcp.args,
            env=config.tools.mcp.env,
            tool_name=config.tools.mcp.tool_name,
        )
        registry.register(tool)
        print(f"  Registered: {tool.name}")

    # List all registered tools
    print(f"\nAll registered tools: {registry.tool_names}")

    # Get tool definitions
    definitions = registry.get_definitions()
    print(f"\nTool definitions for LLM:")
    for d in definitions:
        print(f"  - {d['function']['name']}: {d['function']['description'][:50]}...")

    return registry


async def test_tool_execution(registry: ToolRegistry):
    """Test tool execution (skipped - requires actual MCP server)."""
    print("\n" + "=" * 50)
    print("3. Testing Tool Execution (SKIPPED)")
    print("=" * 50)
    print("Note: Execution test skipped. Run manually with:")
    print("  nanobot agent -m 'use minimax tool to test'")


async def main():
    """Main test."""
    print("MCP Tool Debug Test")
    print("=" * 50)

    # Test 1: Config
    config = test_config()

    # Test 2: Registration
    registry = test_tool_registration()

    # Test 3: Execution (skipped)
    await test_tool_execution(registry)

    print("\n" + "=" * 50)
    print("Debug complete")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
