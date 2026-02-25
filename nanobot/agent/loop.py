"""Agent loop: the core processing engine."""

import asyncio
import json
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger

from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider
from nanobot.agent.context import ContextBuilder
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.web import WebSearchTool, WebFetchTool
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.spawn import SpawnTool
from nanobot.agent.tools.cron import CronTool
from nanobot.agent.tools.mcp import MCPTool, MiniMaxMCPTool, discover_mcp_tools
from nanobot.agent.subagent import SubagentManager
from nanobot.session.manager import SessionManager


class AgentLoop:
    """
    The agent loop is the core processing engine.

    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """

    _log_callback: Optional[Callable] = None

    @classmethod
    def set_log_callback(cls, callback: Optional[Callable]):
        """Set a callback for sending logs to clients."""
        cls._log_callback = callback

    @classmethod
    def send_log(cls, level: str, category: str, message: str, details: str | None = None):
        """Send a log entry to clients if callback is set."""
        if cls._log_callback:
            cls._log_callback({
                "level": level,
                "category": category,
                "message": message,
                "details": details,
                "timestamp": asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0,
            })

    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 20,
        brave_api_key: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        cron_service: "CronService | None" = None,
        providers: dict[str, LLMProvider] | None = None,
    ):
        from nanobot.config.schema import ExecToolConfig
        from nanobot.cron.service import CronService
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service

        # Support multiple providers for model switching
        self._providers = providers or {"default": provider}

        self.context = ContextBuilder(workspace)
        self.sessions = SessionManager(workspace)
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            brave_api_key=brave_api_key,
            exec_config=self.exec_config,
        )

        self._running = False
        self._register_default_tools()

    def _get_provider_for_model(self, model: str | None) -> tuple[LLMProvider, str]:
        """Get the appropriate provider and model name for a given model alias."""
        if not model:
            return self.provider, self.model

        model_lower = model.lower()

        # Map aliases to full model names and select provider
        if model_lower == "qwen":
            # Use qwen provider if available, otherwise default
            if "qwen" in self._providers:
                provider = self._providers["qwen"]
                logger.info(f"[AgentLoop] Selected qwen provider: {provider.__class__.__name__}")
            else:
                provider = self.provider
                logger.warning(f"[AgentLoop] Qwen provider not configured, falling back to {provider.__class__.__name__}")
            return provider, "openai/qwen3.5-plus"
        elif model_lower == "minimax":
            # Use minimax provider if available, otherwise default
            if "minimax" in self._providers:
                provider = self._providers["minimax"]
                logger.info(f"[AgentLoop] Selected minimax provider: {provider.__class__.__name__}")
            else:
                provider = self.provider
                logger.warning(f"[AgentLoop] MiniMax provider not configured, falling back to {provider.__class__.__name__}")
            return provider, "minimax/MiniMax-M2.5"

        # Direct model name - use default provider
        return self.provider, model
    
    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        # File tools
        self.tools.register(ReadFileTool())
        self.tools.register(WriteFileTool())
        self.tools.register(EditFileTool())
        self.tools.register(ListDirTool())
        
        # Shell tool
        self.tools.register(ExecTool(
            working_dir=str(self.workspace),
            timeout=self.exec_config.timeout,
            restrict_to_workspace=self.exec_config.restrict_to_workspace,
        ))
        
        # Web tools
        self.tools.register(WebSearchTool(api_key=self.brave_api_key))
        self.tools.register(WebFetchTool())
        
        # Message tool
        message_tool = MessageTool(send_callback=self.bus.publish_outbound)
        self.tools.register(message_tool)
        
        # Spawn tool (for subagents)
        spawn_tool = SpawnTool(manager=self.subagents)
        self.tools.register(spawn_tool)
        
        # Cron tool (for scheduling)
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service))

        # MCP tools (for external MCP servers)
        self._register_mcp_tools()

    def _register_mcp_tools(self) -> None:
        """Register MCP tools from configuration."""
        from nanobot.config.loader import load_config

        try:
            config = load_config()
            mcp_config = config.tools.mcp

            # Check if MiniMax is configured via provider (auto-enable MCP)
            if config.providers.minimax.api_key:
                logger.info("Discovering MiniMax MCP tools...")

                # Build environment for MiniMax
                env = {
                    "MINIMAX_API_KEY": config.providers.minimax.api_key,
                }
                if config.providers.minimax.api_base:
                    # Remove trailing /v1 if present to avoid duplicate version in URL
                    api_host = config.providers.minimax.api_base.rstrip('/')
                    if api_host.endswith('/v1'):
                        api_host = api_host[:-3]
                    env["MINIMAX_API_HOST"] = api_host

                # Discover available tools from MCP server
                # Use direct command if available, fallback to uvx
                mcp_tools = discover_mcp_tools(
                    command="minimax-coding-plan-mcp",
                    args=[],
                    env=env,
                )

                if mcp_tools:
                    logger.info(f"Registering {len(mcp_tools)} MiniMax MCP tool(s)")
                    for tool_def in mcp_tools:
                        tool_name = tool_def.get("name", "unknown")
                        self.tools.register(MCPTool(
                            name=f"minimax_{tool_name}",
                            command="minimax-coding-plan-mcp",
                            args=[],
                            env=env,
                            tool_name=tool_name,
                            tool_schema=tool_def,
                        ))
                else:
                    # Fallback: register a single generic minimax tool
                    logger.info("Failed to discover MiniMax tools, registering generic tool")
                    self.tools.register(MiniMaxMCPTool(
                        api_key=config.providers.minimax.api_key,
                        api_base=config.providers.minimax.api_base,
                    ))
                return

            # Explicit MCP configuration (requires enabled=True)
            if not mcp_config.enabled:
                return

            if mcp_config.command:
                logger.info(f"Discovering MCP tools from {mcp_config.command}...")

                # Discover available tools
                mcp_tools = discover_mcp_tools(
                    command=mcp_config.command,
                    args=mcp_config.args,
                    env=mcp_config.env,
                )

                if mcp_tools:
                    logger.info(f"Registering {len(mcp_tools)} MCP tool(s)")
                    for tool_def in mcp_tools:
                        tool_name = tool_def.get("name", "unknown")
                        self.tools.register(MCPTool(
                            name=f"{mcp_config.alias}_{tool_name}",
                            command=mcp_config.command,
                            args=mcp_config.args,
                            env=mcp_config.env,
                            tool_name=tool_name,
                        ))
                else:
                    # Fallback: register a single generic tool
                    logger.info(f"Registering MCP tool: {mcp_config.alias}")
                    self.tools.register(MCPTool(
                        name=mcp_config.alias,
                        command=mcp_config.command,
                        args=mcp_config.args,
                        env=mcp_config.env,
                        tool_name=mcp_config.tool_name,
                    ))
        except Exception as e:
            logger.warning(f"Failed to register MCP tools: {e}")

    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        logger.info("Agent loop started")
        
        while self._running:
            try:
                # Wait for next message
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0
                )
                
                # Process it
                try:
                    response = await self._process_message(msg)
                    if response:
                        await self.bus.publish_outbound(response)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Send error response
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=f"Sorry, I encountered an error: {str(e)}"
                    ))
            except asyncio.TimeoutError:
                continue
    
    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")
    
    async def _process_message(
        self,
        msg: InboundMessage,
        override_model: str | None = None
    ) -> OutboundMessage | None:
        """
        Process a single inbound message.

        Args:
            msg: The inbound message to process.
            override_model: Optional model to use for this message (e.g., 'qwen', 'minimax')

        Returns:
            The response message, or None if no response needed.
        """
        # Handle system messages (subagent announces)
        # The chat_id contains the original "channel:chat_id" to route back to
        if msg.channel == "system":
            return await self._process_system_message(msg, override_model)

        logger.info(f"Processing message from {msg.channel}:{msg.sender_id}")
        self.send_log("info", "general", f"开始处理消息", f"Channel: {msg.channel}\nModel: {override_model or 'default'}")

        # Use override model if provided, otherwise use default
        provider, model = self._get_provider_for_model(override_model)
        logger.info(f"[AgentLoop] Using model: {model}, provider: {provider.__class__.__name__}")
        self.send_log("info", "llm", f"使用模型: {model}")

        # Check if using MiniMax model (for MCP tool routing)
        is_minimax = "minimax" in model.lower()

        # Get or create session
        session = self.sessions.get_or_create(msg.session_key)
        
        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)

        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(msg.channel, msg.chat_id)

        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(msg.channel, msg.chat_id)

        # Update exec tool context for task tracking
        exec_tool = self.tools.get("exec")
        if exec_tool and hasattr(exec_tool, 'set_context'):
            exec_tool.set_context(msg.channel, msg.chat_id)
        
        # Check if message contains images
        if msg.media:
            logger.info(f"[AgentLoop] Image detected, is_minimax={is_minimax}, has_tool={self.tools.has('minimax_understand_image')}")
            if is_minimax and self.tools.has("minimax_understand_image"):
                logger.info(f"[AgentLoop] Using MiniMax MCP to process image")
                # Build context with image
                image_data = msg.media[0] if msg.media else None
                if image_data:
                    try:
                        # Prepare image_source parameter (base64 or URL)
                        if image_data.startswith("data:"):
                            # For base64 data, pass directly
                            image_source = image_data
                        else:
                            # For URLs, pass as-is
                            image_source = image_data

                        result = await self.tools.execute("minimax_understand_image", {
                            "prompt": msg.content or "描述这张图片",
                            "image_source": image_source
                        })
                        # Save result to session and return
                        session.add_message("user", f"[图片] {msg.content}" if msg.content else "[图片]")
                        session.add_message("assistant", result)
                        self.sessions.save(session)
                        return OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content=result
                        )
                    except Exception as e:
                        logger.error(f"[AgentLoop] minimax_understand_image failed: {e}")
                        # Fall through to normal processing
            elif not is_minimax:
                # For Qwen and other multimodal models, let the LLM handle the image directly
                logger.info(f"[AgentLoop] Using {model} native multimodal capability for image")
                # Continue to normal processing - the provider will handle the image

        # Check if message looks like a search query
        search_keywords = ["搜索", "查找", "查询", "最新", "新闻", "search", "find", "look up", "latest"]
        is_search_query = any(kw in msg.content.lower() for kw in search_keywords)

        # Use MiniMax MCP search tool for search queries (better search capability)
        if is_search_query and self.tools.has("minimax_web_search"):
            logger.info(f"[AgentLoop] Auto-routing search query to minimax_web_search")
            try:
                result = await self.tools.execute("minimax_web_search", {
                    "query": msg.content
                })
                # Save result to session and return
                session.add_message("user", msg.content)
                session.add_message("assistant", result)
                self.sessions.save(session)
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=result
                )
            except Exception as e:
                logger.error(f"[AgentLoop] minimax_web_search failed: {e}")
                # Fall through to normal processing

        # Build initial messages (use get_history for LLM-formatted messages)
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            media=msg.media if msg.media else None,
            channel=msg.channel,
            chat_id=msg.chat_id,
        )

        # Agent loop
        iteration = 0
        final_content = None

        self.send_log("info", "general", f"开始 Agent 循环 (最多 {self.max_iterations} 轮)")

        while iteration < self.max_iterations:
            iteration += 1
            self.send_log("info", "llm", f"第 {iteration} 轮: 调用 LLM")

            # Call LLM with selected provider and model
            response = await provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=model
            )

            self.send_log("success", "llm", f"LLM 响应完成", f"工具调用: {len(response.tool_calls) if response.has_tool_calls else 0}")
            
            # Handle tool calls
            if response.has_tool_calls:
                # Add assistant message with tool calls
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)  # Must be JSON string
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts
                )
                
                # Execute tools
                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments)
                    logger.debug(f"Executing tool: {tool_call.name} with arguments: {args_str}")
                    self.send_log("tool", "tool", f"执行工具: {tool_call.name}", f"参数: {args_str[:200]}..." if len(args_str) > 200 else f"参数: {args_str}")
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    result_preview = str(result)[:150] + "..." if len(str(result)) > 150 else str(result)
                    self.send_log("success", "tool", f"工具完成: {tool_call.name}", f"结果: {result_preview}")
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                # No tool calls, we're done
                final_content = response.content
                self.send_log("success", "general", f"Agent 循环完成", f"共 {iteration} 轮")
                break

        if final_content is None:
            final_content = "I've completed processing but have no response to give."
            self.send_log("warning", "general", "Agent 达到最大迭代次数", f"{self.max_iterations} 轮")

        # Save to session
        session.add_message("user", msg.content)
        session.add_message("assistant", final_content)
        self.sessions.save(session)
        
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content
        )
    
    async def _process_system_message(
        self,
        msg: InboundMessage,
        override_model: str | None = None
    ) -> OutboundMessage | None:
        """
        Process a system message (e.g., subagent announce).

        The chat_id field contains "original_channel:original_chat_id" to route
        the response back to the correct destination.

        Args:
            msg: The system message.
            override_model: Optional model to use for this message.
        """
        logger.info(f"Processing system message from {msg.sender_id}")

        # Determine which provider and model to use
        provider, model = self.get_provider_for_model(override_model)

        # Parse origin from chat_id (format: "channel:chat_id")
        if ":" in msg.chat_id:
            parts = msg.chat_id.split(":", 1)
            origin_channel = parts[0]
            origin_chat_id = parts[1]
        else:
            # Fallback
            origin_channel = "cli"
            origin_chat_id = msg.chat_id
        
        # Use the origin session for context
        session_key = f"{origin_channel}:{origin_chat_id}"
        session = self.sessions.get_or_create(session_key)
        
        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(origin_channel, origin_chat_id)

        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(origin_channel, origin_chat_id)

        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(origin_channel, origin_chat_id)

        # Update exec tool context for task tracking
        exec_tool = self.tools.get("exec")
        if exec_tool and hasattr(exec_tool, 'set_context'):
            exec_tool.set_context(origin_channel, origin_chat_id)

        # Build messages with the announce content
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            channel=origin_channel,
            chat_id=origin_chat_id,
        )
        
        # Agent loop (limited for announce handling)
        iteration = 0
        final_content = None
        
        while iteration < self.max_iterations:
            iteration += 1
            
            response = await provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=model
            )
            
            if response.has_tool_calls:
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts
                )
                
                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments)
                    logger.debug(f"Executing tool: {tool_call.name} with arguments: {args_str}")
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                final_content = response.content
                break
        
        if final_content is None:
            final_content = "Background task completed."
        
        # Save to session (mark as system message in history)
        session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")
        session.add_message("assistant", final_content)
        self.sessions.save(session)
        
        return OutboundMessage(
            channel=origin_channel,
            chat_id=origin_chat_id,
            content=final_content
        )
    
    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        media: list[str] | None = None,
        model: str | None = None,
    ) -> str:
        """
        Process a message directly (for CLI or cron usage).

        Args:
            content: The message content.
            session_key: Session identifier.
            channel: Source channel (for context).
            chat_id: Source chat ID (for context).
            media: Optional list of media URLs or base64 data.
            model: Optional model to use (e.g., 'qwen', 'minimax').

        Returns:
            The agent's response.
        """
        # Pass model alias directly - _get_provider_for_model will handle mapping
        msg = InboundMessage(
            channel=channel,
            sender_id="user",
            chat_id=chat_id,
            content=content,
            media=media or [],
        )

        response = await self._process_message(msg, override_model=model)
        return response.content if response else ""
