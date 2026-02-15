"""MCP (Model Context Protocol) tool integration."""

import asyncio
import json
import subprocess
from typing import Any

from loguru import logger

from nanobot.agent.tools.base import Tool


def discover_mcp_tools(command: str, args: list[str], env: dict[str, str]) -> list[dict]:
    """
    Discover available tools from an MCP server.

    Args:
        command: The command to launch the MCP server.
        args: Arguments for the command.
        env: Environment variables.

    Returns:
        List of tool definitions from the MCP server.
    """
    try:
        process = subprocess.Popen(
            [command, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env={**subprocess.os.environ, **env},
        )

        # Send initialize
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "nanobot", "version": "0.1.0"},
            },
        }
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()

        import select
        ready, _, _ = select.select([process.stdout], [], [], 30)
        if not ready:
            logger.warning("MCP server initialization timeout")
            process.terminate()
            return []

        response = process.stdout.readline()
        data = json.loads(response)
        if "error" in data:
            logger.warning(f"MCP initialize failed: {data['error']}")
            process.terminate()
            return []

        # Send tools/list
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        process.stdin.write(json.dumps(tools_request) + "\n")
        process.stdin.flush()

        ready, _, _ = select.select([process.stdout], [], [], 30)
        if not ready:
            logger.warning("MCP server tools/list timeout")
            process.terminate()
            return []

        response = process.stdout.readline()
        data = json.loads(response)
        if "error" in data:
            logger.warning(f"MCP tools/list failed: {data['error']}")
            process.terminate()
            return []

        tools = data.get("result", {}).get("tools", [])
        process.terminate()

        return tools

    except Exception as e:
        logger.warning(f"Failed to discover MCP tools: {e}")
        return []


class MCPTool(Tool):
    """
    Generic MCP tool that communicates with an MCP server via stdio.

    This tool launches an MCP server as a subprocess and communicates
    with it using JSON-RPC over stdio.
    """

    def __init__(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        tool_name: str | None = None,  # Specific tool name from MCP server
        tool_schema: dict | None = None,  # Pre-discovered tool schema
    ):
        """
        Initialize MCP tool.

        Args:
            name: The name to register this tool as.
            command: The command to launch the MCP server.
            args: Arguments for the command.
            env: Environment variables for the subprocess.
            tool_name: Specific tool name from MCP server (if None, uses first available).
            tool_schema: Pre-discovered tool schema (optional, avoids lazy loading).
        """
        self._name = name
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.tool_name = tool_name
        self._process: subprocess.Popen | None = None
        self._request_id = 0
        self._tools_list: list[dict] | None = None
        self._mcp_tool_name: str | None = tool_name
        self._mcp_tool_schema: dict | None = tool_schema

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        if self._mcp_tool_schema:
            return self._mcp_tool_schema.get("description", f"MCP tool: {self.name}")
        # Default description for MiniMax
        if self.name == "minimax":
            return "Use MiniMax AI to create coding plans, learning roadmaps, or solve programming tasks. Provide a detailed prompt describing what you need help with."
        return f"MCP tool: {self.name} - An external AI service that can help with various tasks"

    @property
    def parameters(self) -> dict[str, Any]:
        if self._mcp_tool_schema:
            return self._mcp_tool_schema.get("parameters", {"type": "object", "properties": {}})
        # Return a generic parameter schema before initialization
        # This allows LLM to call the tool with any parameters
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The prompt or task description to send to MiniMax"
                }
            },
            "required": ["prompt"]
        }

    def _start_server(self) -> subprocess.Popen:
        """Start the MCP server subprocess."""
        if self._process is None or self._process.poll() is not None:
            env = {**self.env}
            self._process = subprocess.Popen(
                [self.command, *self.args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env={**subprocess.os.environ, **env},
            )
        return self._process

    def _send_request(self, method: str, params: dict | None = None) -> dict:
        """Send a JSON-RPC request to the MCP server."""
        process = self._start_server()
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }

        request_line = json.dumps(request) + "\n"
        process.stdin.write(request_line)
        process.stdin.flush()

        # Read response
        response_line = process.stdout.readline()
        return json.loads(response_line)

    def _initialize(self) -> None:
        """Initialize connection and discover tools."""
        if self._tools_list is not None:
            return

        # Initialize MCP connection
        result = self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "nanobot", "version": "0.1.0"},
        })

        if "error" in result:
            raise RuntimeError(f"MCP initialize failed: {result['error']}")

        # List available tools
        result = self._send_request("tools/list")
        if "error" in result:
            raise RuntimeError(f"Failed to list MCP tools: {result['error']}")

        self._tools_list = result.get("result", {}).get("tools", [])

        # Select the tool to use
        if self.tool_name:
            for tool in self._tools_list:
                if tool.get("name") == self.tool_name:
                    self._mcp_tool_name = tool["name"]
                    self._mcp_tool_schema = tool
                    break
            if not self._mcp_tool_name:
                raise ValueError(f"Tool '{self.tool_name}' not found in MCP server. Available: {[t['name'] for t in self._tools_list]}")
        elif self._tools_list:
            # Use first available tool
            self._mcp_tool_name = self._tools_list[0]["name"]
            self._mcp_tool_schema = self._tools_list[0]
        else:
            raise RuntimeError("No tools available from MCP server")

    async def execute(self, **kwargs: Any) -> str:
        """Execute the MCP tool."""
        try:
            # Initialize if needed
            if self._tools_list is None:
                # Run initialization in thread pool
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._initialize)

            # Call the tool
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self._send_request,
                "tools/call",
                {"name": self._mcp_tool_name, "arguments": kwargs},
            )

            if "error" in result:
                return f"MCP Error: {result['error']}"

            # Extract result content
            content = result.get("result", {}).get("content", [])
            if not content:
                return "No result from MCP tool"

            # Concatenate text content
            texts = []
            for item in content:
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))

            return "\n".join(texts) if texts else json.dumps(result["result"])

        except Exception as e:
            return f"Error executing MCP tool: {str(e)}"

    def __del__(self):
        """Cleanup subprocess."""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()


class MiniMaxMCPTool(MCPTool):
    """Convenience class for MiniMax MCP server.

    Provides access to MiniMax AI capabilities including:
    - web_search: Search the web for information
    - understand_image: Analyze and understand images
    """

    def __init__(self, api_key: str | None = None, api_base: str | None = None):
        env = {}
        if api_key:
            env["MINIMAX_API_KEY"] = api_key
        if api_base:
            # Remove trailing /v1 if present to avoid duplicate version in URL
            api_host = api_base.rstrip('/')
            if api_host.endswith('/v1'):
                api_host = api_host[:-3]
            env["MINIMAX_API_HOST"] = api_host  # Note: MCP server uses MINIMAX_API_HOST, not MINIMAX_API_BASE

        super().__init__(
            name="minimax",
            command="uvx",
            args=["minimax-coding-plan-mcp", "-y"],
            env=env,
        )
