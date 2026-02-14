"""
Task reporter for async operations.

This module provides a simple way for scripts to report task progress
to the nanobot Web Channel via HTTP API.
"""

import os
import json
import urllib.request
import urllib.error
from typing import Optional


class TaskReporter:
    """Reporter for task progress updates."""

    def __init__(self, task_id: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize task reporter.

        Args:
            task_id: The task ID to report progress for. If None, reads from NANOBOT_TASK_ID env var.
            base_url: The base URL of the nanobot web server. If None, reads from NANOBOT_API_BASE env var.
        """
        self.task_id = task_id or os.environ.get("NANOBOT_TASK_ID")
        self.base_url = base_url or os.environ.get("NANOBOT_API_BASE", "http://localhost:18790")

    def _make_request(self, endpoint: str, data: dict) -> bool:
        """Make HTTP request to update task."""
        if not self.task_id:
            print(f"[TaskReporter] No task_id, skipping update")
            return False

        try:
            url = f"{self.base_url}{endpoint}"
            headers = {"Content-Type": "application/json"}
            payload = json.dumps(data).encode("utf-8")

            print(f"[TaskReporter] Sending update to {url}: {data}")

            req = urllib.request.Request(
                url,
                data=payload,
                headers=headers,
                method="PATCH"
            )

            with urllib.request.urlopen(req, timeout=5) as response:
                response_body = response.read().decode('utf-8')
                print(f"[TaskReporter] Response: {response.status} - {response_body}")
                return response.status == 200

        except Exception as e:
            # Don't let task reporting break the main functionality
            print(f"[TaskReporter] Failed to update task: {e}")
            return False

    def update(
        self,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        result: Optional[str] = None,
        error: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        """
        Update task status.

        Args:
            status: Task status (pending, running, completed, failed, cancelled).
            progress: Progress percentage (0-100).
            result: Task result data.
            error: Error message if failed.
            description: Task description.

        Returns:
            True if update was successful, False otherwise.
        """
        if not self.task_id:
            return False

        data = {}
        if status is not None:
            data["status"] = status
        if progress is not None:
            data["progress"] = progress
        if result is not None:
            data["result"] = result
        if error is not None:
            data["error"] = error
        if description is not None:
            data["description"] = description

        return self._make_request(f"/api/tasks/{self.task_id}", data)

    def start(self, description: Optional[str] = None) -> bool:
        """Mark task as running."""
        return self.update(status="running", progress=0, description=description)

    def progress(self, percent: int, description: Optional[str] = None) -> bool:
        """Update task progress."""
        return self.update(status="running", progress=percent, description=description)

    def complete(self, result: Optional[str] = None) -> bool:
        """Mark task as completed."""
        return self.update(status="completed", progress=100, result=result)

    def fail(self, error: str) -> bool:
        """Mark task as failed."""
        return self.update(status="failed", error=error)


# Global reporter instance (can be imported and used across modules)
_global_reporter: Optional[TaskReporter] = None


def init_reporter(task_id: Optional[str] = None, base_url: Optional[str] = None) -> TaskReporter:
    """Initialize global task reporter.

    Args:
        task_id: Task ID. If None, reads from NANOBOT_TASK_ID env var.
        base_url: API base URL. If None, reads from NANOBOT_API_BASE env var.
    """
    global _global_reporter
    _global_reporter = TaskReporter(task_id, base_url)
    return _global_reporter


def get_reporter() -> Optional[TaskReporter]:
    """Get global task reporter instance."""
    return _global_reporter


def report_progress(percent: int, description: Optional[str] = None) -> bool:
    """Report progress using global reporter."""
    if _global_reporter:
        return _global_reporter.progress(percent, description)
    return False


def report_complete(result: Optional[str] = None) -> bool:
    """Report completion using global reporter."""
    if _global_reporter:
        return _global_reporter.complete(result)
    return False


def report_error(error: str) -> bool:
    """Report error using global reporter."""
    if _global_reporter:
        return _global_reporter.fail(error)
    return False
