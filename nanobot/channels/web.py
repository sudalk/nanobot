"""Web channel for browser-based chat interface."""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel

from nanobot.channels.base import BaseChannel
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import WebConfig
from nanobot.tasks.manager import task_manager, TaskInfo, TaskStatus

# Static files directory
STATIC_DIR = Path(__file__).parent.parent / "web" / "static"


class ChatRequest(BaseModel):
    """Request model for chat API."""
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    """Response model for chat API."""
    response: str
    session_id: str


class SessionInfo(BaseModel):
    """Session information."""
    key: str
    created_at: str
    updated_at: str
    message_count: int


class TaskCreateRequest(BaseModel):
    """Request to create a task."""
    task_type: str
    title: str
    description: str = ""


class TaskUpdateRequest(BaseModel):
    """Request to update a task."""
    model_config = {"extra": "ignore"}  # Ignore extra fields for forward compatibility

    status: str | None = None
    progress: int | None = None
    result: Any = None
    error: str = ""
    description: str = ""


class WebChannel(BaseChannel):
    """
    Web channel for browser-based chat interface.

    Provides:
    - HTTP API for chat and session management
    - WebSocket for real-time bidirectional communication
    - Task progress notifications for long-running operations
    - Static file serving for the frontend
    """

    name = "web"

    def __init__(
        self,
        config: WebConfig,
        bus: MessageBus,
        agent: Any = None,
        session_manager: Any = None,
    ):
        """
        Initialize the web channel.

        Args:
            config: Web channel configuration.
            bus: Message bus for communication.
            agent: Agent loop for processing messages.
            session_manager: Session manager for conversation history.
        """
        super().__init__(config, bus)
        self.config = config
        self.agent = agent
        self.session_manager = session_manager
        self.app = FastAPI(title=config.title)
        self._websocket_connections: dict[str, WebSocket] = {}
        self._session_to_client: dict[str, str] = {}  # session_id -> client_id mapping
        self._setup_middleware()
        self._setup_routes()
        self._setup_task_callbacks()

    def _setup_middleware(self) -> None:
        """Setup CORS middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_task_callbacks(self) -> None:
        """Register task update callbacks."""
        task_manager.register_callback(self._on_task_update)
        logger.info("Task callbacks registered")

    async def _on_task_update(self, task: TaskInfo) -> None:
        """Handle task status updates and push to frontend.

        Args:
            task: The updated task information.
        """
        logger.info(f"[_on_task_update] Task update: {task.task_id} - {task.status.value} ({task.progress}%)")

        # Find the client for this session
        client_id = self._session_to_client.get(task.session_id)
        if not client_id:
            logger.warning(f"[_on_task_update] No client found for session {task.session_id}")
            logger.debug(f"[_on_task_update] Available sessions: {list(self._session_to_client.keys())}")
            return

        websocket = self._websocket_connections.get(client_id)
        if not websocket:
            logger.warning(f"[_on_task_update] WebSocket not found for client {client_id}")
            return

        try:
            # Send task update to frontend
            message = {
                "type": "task_update",
                "task": {
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "title": task.title,
                    "description": task.description,
                    "status": task.status.value,
                    "progress": task.progress,
                    "error": task.error,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                    "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                },
                "session_id": task.session_id,
            }
            await websocket.send_json(message)
            logger.info(f"[_on_task_update] Task update sent via WebSocket: {task.task_id} - {task.status.value}")
        except Exception as e:
            logger.error(f"[_on_task_update] Failed to send task update: {e}")

    def _setup_routes(self) -> None:
        """Setup API routes."""

        @self.app.get("/")
        async def root() -> HTMLResponse:
            """Serve the main page."""
            index_file = STATIC_DIR / "index.html"
            if index_file.exists():
                content = index_file.read_text()
                return HTMLResponse(content=content)
            return HTMLResponse(content=self._get_default_html())

        @self.app.get("/api/health")
        async def health() -> dict[str, Any]:
            """Health check endpoint."""
            return {"status": "ok", "channel": "web"}

        @self.app.get("/api/sessions")
        async def list_sessions() -> list[SessionInfo]:
            """List all sessions."""
            if not self.session_manager:
                return []
            sessions = self.session_manager.list_sessions()
            return [
                SessionInfo(
                    key=s["key"],
                    created_at=s.get("created_at", ""),
                    updated_at=s.get("updated_at", ""),
                    message_count=len(
                        self.session_manager.get_or_create(s["key"]).messages
                    ),
                )
                for s in sessions
            ]

        @self.app.get("/api/sessions/{session_id}/history")
        async def get_session_history(session_id: str) -> list[dict[str, Any]]:
            """Get session history."""
            if not self.session_manager:
                return []
            key = f"web:{session_id}"
            session = self.session_manager.get_or_create(key)
            return session.messages

        @self.app.delete("/api/sessions/{session_id}")
        async def delete_session(session_id: str) -> dict[str, bool]:
            """Delete a session."""
            if not self.session_manager:
                return {"success": False}
            key = f"web:{session_id}"
            success = self.session_manager.delete(key)
            return {"success": success}

        @self.app.post("/api/chat")
        async def chat(request: ChatRequest) -> ChatResponse:
            """Send a message and get a response."""
            session_id = request.session_id or str(uuid.uuid4())[:8]
            session_key = f"web:{session_id}"

            if not self.agent:
                raise Exception("Agent not initialized")

            response = await self.agent.process_direct(
                content=request.message,
                session_key=session_key,
                channel="web",
                chat_id=session_id,
            )

            return ChatResponse(
                response=response,
                session_id=session_id,
            )

        # Task management endpoints
        @self.app.post("/api/sessions/{session_id}/tasks")
        async def create_task(session_id: str, request: TaskCreateRequest) -> dict[str, Any]:
            """Create a new task for tracking."""
            task_id = task_manager.create_task(
                session_id=session_id,
                task_type=request.task_type,
                title=request.title,
                description=request.description,
            )
            return {"task_id": task_id, "session_id": session_id}

        @self.app.get("/api/sessions/{session_id}/tasks")
        async def list_session_tasks(session_id: str) -> list[dict[str, Any]]:
            """List all tasks for a session."""
            tasks = task_manager.get_session_tasks(session_id)
            return [
                {
                    "task_id": t.task_id,
                    "task_type": t.task_type,
                    "title": t.title,
                    "description": t.description,
                    "status": t.status.value,
                    "progress": t.progress,
                    "error": t.error,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                }
                for t in tasks
            ]

        @self.app.get("/api/tasks/{task_id}")
        async def get_task(task_id: str) -> dict[str, Any] | None:
            """Get task information."""
            task = task_manager.get_task(task_id)
            if not task:
                return None
            return {
                "task_id": task.task_id,
                "session_id": task.session_id,
                "task_type": task.task_type,
                "title": task.title,
                "description": task.description,
                "status": task.status.value,
                "progress": task.progress,
                "error": task.error,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            }

        @self.app.patch("/api/tasks/{task_id}")
        async def update_task(task_id: str, request: TaskUpdateRequest) -> dict[str, Any]:
            """Update task status."""
            logger.info(f"[API] Task update request: {task_id} -> status={request.status}, progress={request.progress}")
            status = None
            if request.status:
                try:
                    status = TaskStatus(request.status)
                except ValueError:
                    logger.warning(f"[API] Invalid status: {request.status}")
                    pass

            task = task_manager.update_task(
                task_id=task_id,
                status=status,
                progress=request.progress,
                result=request.result,
                error=request.error,
                description=request.description,
            )
            if not task:
                logger.warning(f"[API] Task not found: {task_id}")
                return {"error": "Task not found"}
            logger.info(f"[API] Task updated successfully: {task_id}")
            return {"success": True, "task_id": task_id}

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket) -> None:
            """WebSocket endpoint for real-time communication."""
            await websocket.accept()
            client_id = str(uuid.uuid4())[:8]
            self._websocket_connections[client_id] = websocket
            logger.info(f"WebSocket client connected: {client_id}")

            try:
                while True:
                    # Receive message from client
                    data = await websocket.receive_text()
                    try:
                        msg_data = json.loads(data)
                        logger.info(f"[WebChannel] Received WebSocket data: {msg_data}")
                    except json.JSONDecodeError:
                        await websocket.send_json(
                            {"type": "error", "message": "Invalid JSON"}
                        )
                        continue

                    msg_type = msg_data.get("type", "chat")

                    if msg_type == "chat":
                        await self._handle_chat_message(websocket, msg_data, client_id)
                    elif msg_type == "ping":
                        await websocket.send_json({"type": "pong"})
                    elif msg_type == "get_models":
                        await self._handle_get_models(websocket)
                    else:
                        await websocket.send_json(
                            {"type": "error", "message": f"Unknown type: {msg_type}"}
                        )

            except WebSocketDisconnect:
                logger.info(f"WebSocket client disconnected: {client_id}")
            except Exception as e:
                logger.error(f"WebSocket error for client {client_id}: {e}")
            finally:
                # Clean up session mapping
                sessions_to_remove = [
                    sid for sid, cid in self._session_to_client.items()
                    if cid == client_id
                ]
                for sid in sessions_to_remove:
                    del self._session_to_client[sid]
                self._websocket_connections.pop(client_id, None)

        # Mount static files if directory exists
        if STATIC_DIR.exists():
            self.app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    async def _handle_get_models(self, websocket: WebSocket) -> None:
        """Handle get available models request."""
        models = [
            {"id": "qwen", "name": "Qwen 3.5 (多模态)", "description": "支持视觉理解的统一多模态模型"},
            {"id": "minimax", "name": "MiniMax", "description": "支持搜索和视觉理解工具"},
        ]
        await websocket.send_json({
            "type": "models_list",
            "models": models
        })

    async def _handle_chat_message(
        self, websocket: WebSocket, data: dict[str, Any], client_id: str
    ) -> None:
        """
        Handle a chat message from WebSocket.

        Args:
            websocket: The WebSocket connection.
            data: The message data.
            client_id: The client identifier.
        """
        logger.info(f"[WebChannel] Received chat message from client {client_id}: {data}")

        if not self.agent:
            logger.error(f"[WebChannel] Agent not initialized")
            await websocket.send_json(
                {"type": "error", "message": "Agent not initialized"}
            )
            return

        message = data.get("message", "")
        image = data.get("image")  # Base64 encoded image
        session_id = data.get("session_id") or str(uuid.uuid4())[:8]
        session_key = f"web:{session_id}"

        logger.info(f"[WebChannel] Processing message for session {session_key}: {message[:50]}...")
        if image:
            logger.info(f"[WebChannel] Message includes image ({len(image)} chars)")

        # Allow empty message if there's an image
        if not message and not image:
            await websocket.send_json(
                {"type": "error", "message": "Empty message"}
            )
            return

        # Register session to client mapping for task notifications
        self._session_to_client[session_id] = client_id

        # Send acknowledgment
        await websocket.send_json(
            {
                "type": "ack",
                "session_id": session_id,
            }
        )

        try:
            # Process message through agent
            logger.info(f"[WebChannel] Calling agent.process_direct for session {session_key}")

            # Prepare media/images for the agent
            media = []
            if image:
                # Store image temporarily and get a URL, or pass as base64 in metadata
                media.append(image)  # Base64 data URL

            # Get model selection from client
            model = data.get("model", "qwen")  # Default to qwen
            logger.info(f"[WebChannel] Received model from client: {data.get('model')}")
            logger.info(f"[WebChannel] Using model: {model}")

            response = await self.agent.process_direct(
                content=message or "[图片]",  # Use placeholder if only image
                session_key=session_key,
                channel="web",
                chat_id=session_id,
                media=media if media else None,
                model=model,
            )
            logger.info(f"[WebChannel] Got response from agent: {response[:50]}...")

            # Send response in chunks for streaming effect
            chunk_size = 10  # Characters per chunk
            for i in range(0, len(response), chunk_size):
                chunk = response[i:i + chunk_size]
                await websocket.send_json(
                    {
                        "type": "chunk",
                        "content": chunk,
                        "session_id": session_id,
                    }
                )
                await asyncio.sleep(0.01)  # Small delay for streaming effect

            # Send completion
            await websocket.send_json(
                {
                    "type": "complete",
                    "session_id": session_id,
                    "full_response": response,
                }
            )
            logger.info(f"[WebChannel] Response sent successfully for session {session_key}")

        except Exception as e:
            logger.error(f"[WebChannel] Error processing message: {e}", exc_info=True)
            await websocket.send_json(
                {
                    "type": "error",
                    "message": str(e),
                    "session_id": session_id,
                }
            )

    def _get_default_html(self) -> str:
        """Get default HTML when static file is not found."""
        return """<!DOCTYPE html>
<html>
<head>
    <title>nanobot</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            text-align: center;
        }
        h1 { color: #333; }
        p { color: #666; }
        .error { color: #e74c3c; }
    </style>
</head>
<body>
    <h1>nanobot</h1>
    <p class="error">Frontend not found. Please ensure static files are built.</p>
</body>
</html>"""

    async def start(self) -> None:
        """Start the web server."""
        import uvicorn

        self._running = True
        logger.info(
            f"Starting web channel on http://{self.config.host}:{self.config.port}"
        )

        config = uvicorn.Config(
            self.app,
            host=self.config.host,
            port=self.config.port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def stop(self) -> None:
        """Stop the web server."""
        self._running = False
        logger.info("Web channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """
        Send a message through the web channel.

        This is called when the agent sends a response.
        We forward it to the appropriate WebSocket connection.
        """
        # Find the WebSocket connection for this chat_id
        # For now, broadcast to all connected clients
        for client_id, ws in list(self._websocket_connections.items()):
            try:
                await ws.send_json(
                    {
                        "type": "agent_message",
                        "content": msg.content,
                        "chat_id": msg.chat_id,
                    }
                )
            except Exception as e:
                logger.error(f"Error sending to client {client_id}: {e}")
                self._websocket_connections.pop(client_id, None)
