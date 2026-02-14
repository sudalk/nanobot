"""Task manager for async operations.

This module provides a centralized task management system for tracking
long-running operations like audio extraction and transcription.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine

from loguru import logger


class TaskStatus(Enum):
    """Task status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskInfo:
    """Task information."""
    task_id: str
    session_id: str
    task_type: str
    status: TaskStatus
    title: str
    description: str = ""
    progress: int = 0  # 0-100
    result: Any = None
    error: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None


class TaskManager:
    """Manager for async tasks.

    Provides centralized task tracking and progress notification.
    """

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        """Singleton pattern to ensure one task manager instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the task manager."""
        if self._initialized:
            return

        self._tasks: dict[str, TaskInfo] = {}
        self._callbacks: list[Callable[[TaskInfo], Coroutine]] = []
        self._initialized = True
        logger.info("TaskManager initialized")

    def register_callback(self, callback: Callable[[TaskInfo], Coroutine]) -> None:
        """Register a callback for task updates.

        Args:
            callback: Async callback function that receives TaskInfo updates.
        """
        self._callbacks.append(callback)
        logger.debug(f"Task callback registered, total: {len(self._callbacks)}")

    def unregister_callback(self, callback: Callable[[TaskInfo], Coroutine]) -> None:
        """Unregister a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            logger.debug(f"Task callback unregistered, total: {len(self._callbacks)}")

    def create_task(
        self,
        session_id: str,
        task_type: str,
        title: str,
        description: str = "",
    ) -> str:
        """Create a new task.

        Args:
            session_id: The session ID associated with this task.
            task_type: Type of task (e.g., 'audio_extract', 'transcribe').
            title: Human-readable task title.
            description: Optional task description.

        Returns:
            The task ID.
        """
        task_id = str(uuid.uuid4())[:8]
        task = TaskInfo(
            task_id=task_id,
            session_id=session_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            title=title,
            description=description,
        )
        self._tasks[task_id] = task
        logger.info(f"Task created: {task_id} ({title}) for session {session_id}")
        return task_id

    def get_task(self, task_id: str) -> TaskInfo | None:
        """Get task information.

        Args:
            task_id: The task ID.

        Returns:
            TaskInfo if found, None otherwise.
        """
        return self._tasks.get(task_id)

    def get_session_tasks(self, session_id: str) -> list[TaskInfo]:
        """Get all tasks for a session.

        Args:
            session_id: The session ID.

        Returns:
            List of tasks for the session.
        """
        return [t for t in self._tasks.values() if t.session_id == session_id]

    def update_task(
        self,
        task_id: str,
        status: TaskStatus | None = None,
        progress: int | None = None,
        result: Any = None,
        error: str = "",
        description: str = "",
    ) -> TaskInfo | None:
        """Update task status.

        Args:
            task_id: The task ID.
            status: New status (optional).
            progress: Progress percentage 0-100 (optional).
            result: Task result (optional).
            error: Error message (optional).
            description: Task description (optional).

        Returns:
            Updated TaskInfo if found, None otherwise.
        """
        task = self._tasks.get(task_id)
        if not task:
            logger.warning(f"Task not found: {task_id}")
            return None

        if status is not None:
            task.status = status
            if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                task.completed_at = datetime.now()

        if progress is not None:
            task.progress = max(0, min(100, progress))

        if result is not None:
            task.result = result

        if error:
            task.error = error

        if description:
            task.description = description

        task.updated_at = datetime.now()

        logger.debug(
            f"Task updated: {task_id} - {task.status.value} ({task.progress}%)"
        )

        # Notify callbacks
        asyncio.create_task(self._notify_callbacks(task))

        return task

    async def _notify_callbacks(self, task: TaskInfo) -> None:
        """Notify all registered callbacks of task update."""
        for callback in self._callbacks:
            try:
                await callback(task)
            except Exception as e:
                logger.error(f"Task callback error: {e}")

    def complete_task(self, task_id: str, result: Any = None) -> TaskInfo | None:
        """Mark task as completed.

        Args:
            task_id: The task ID.
            result: Task result.

        Returns:
            Updated TaskInfo if found, None otherwise.
        """
        return self.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100,
            result=result,
        )

    def fail_task(self, task_id: str, error: str) -> TaskInfo | None:
        """Mark task as failed.

        Args:
            task_id: The task ID.
            error: Error message.

        Returns:
            Updated TaskInfo if found, None otherwise.
        """
        return self.update_task(
            task_id,
            status=TaskStatus.FAILED,
            error=error,
        )

    def delete_task(self, task_id: str) -> bool:
        """Delete a task.

        Args:
            task_id: The task ID.

        Returns:
            True if deleted, False if not found.
        """
        if task_id in self._tasks:
            del self._tasks[task_id]
            logger.info(f"Task deleted: {task_id}")
            return True
        return False

    def cleanup_old_tasks(self, max_age_seconds: float = 3600) -> int:
        """Clean up old completed tasks.

        Args:
            max_age_seconds: Maximum age in seconds.

        Returns:
            Number of tasks cleaned up.
        """
        now = datetime.now()
        to_delete = []

        for task_id, task in self._tasks.items():
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                if task.completed_at:
                    age = (now - task.completed_at).total_seconds()
                    if age > max_age_seconds:
                        to_delete.append(task_id)

        for task_id in to_delete:
            del self._tasks[task_id]

        if to_delete:
            logger.info(f"Cleaned up {len(to_delete)} old tasks")

        return len(to_delete)


# Global task manager instance
task_manager = TaskManager()
