"""Shell execution tool."""

import asyncio
import os
import re
import uuid
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.tasks.manager import task_manager, TaskStatus


class ExecTool(Tool):
    """Tool to execute shell commands."""

    def __init__(
        self,
        timeout: int = 60,
        working_dir: str | None = None,
        deny_patterns: list[str] | None = None,
        allow_patterns: list[str] | None = None,
        restrict_to_workspace: bool = False,
        session_id: str | None = None,
    ):
        self.timeout = timeout
        self.working_dir = working_dir
        self.deny_patterns = deny_patterns or [
            r"\brm\s+-[rf]{1,2}\b",          # rm -r, rm -rf, rm -fr
            r"\bdel\s+/[fq]\b",              # del /f, del /q
            r"\brmdir\s+/s\b",               # rmdir /s
            r"\b(format|mkfs|diskpart)\b",   # disk operations
            r"\bdd\s+if=",                   # dd
            r">\s*/dev/sd",                  # write to disk
            r"\b(shutdown|reboot|poweroff)\b",  # system power
            r":\(\)\s*\{.*\};\s*:",          # fork bomb
        ]
        self.allow_patterns = allow_patterns or []
        self.restrict_to_workspace = restrict_to_workspace
        self._session_id = session_id

    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the context for task tracking."""
        if channel == "web":
            self._session_id = chat_id

    @property
    def name(self) -> str:
        return "exec"

    @property
    def description(self) -> str:
        return "Execute a shell command and return its output. Use with caution."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                },
                "working_dir": {
                    "type": "string",
                    "description": "Optional working directory for the command"
                }
            },
            "required": ["command"]
        }

    def _is_long_running_task(self, command: str) -> tuple[bool, str | None]:
        """
        Check if command is a long-running task that should be tracked.

        Returns:
            Tuple of (is_long_running, task_title)
        """
        cmd_lower = command.lower()

        # Check for bilibili audio extraction
        if "bilibili" in cmd_lower and "extract" in cmd_lower:
            return True, "Bilibili 音频提取"

        # Check for whisper transcription
        if "whisper" in cmd_lower and "transcribe" in cmd_lower:
            return True, "Whisper 语音转文字"

        # Check for batch operations
        if "batch" in cmd_lower:
            return True, "批量处理"

        # Check for yt-dlp operations
        if "yt-dlp" in cmd_lower:
            return True, "视频下载"

        return False, None

    async def execute(self, command: str, working_dir: str | None = None, **kwargs: Any) -> str:
        cwd = working_dir or self.working_dir or os.getcwd()
        guard_error = self._guard_command(command, cwd)
        if guard_error:
            return guard_error

        # Check if this is a long-running task
        is_long_running, task_title = self._is_long_running_task(command)
        task_id = None

        if is_long_running and self._session_id:
            # Create a task for tracking
            task_id = task_manager.create_task(
                session_id=self._session_id,
                task_type="exec",
                title=task_title or "执行命令",
                description=f"运行: {command[:100]}...",
            )
            task_manager.update_task(task_id, status=TaskStatus.RUNNING, progress=0)

        try:
            # Prepare environment with task info
            env = os.environ.copy()
            if task_id:
                env["NANOBOT_TASK_ID"] = task_id
                env["NANOBOT_SESSION_ID"] = self._session_id or ""
                env["NANOBOT_API_BASE"] = f"http://localhost:{os.environ.get('NANOBOT_WEB_PORT', '18790')}"

            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                if task_id:
                    task_manager.fail_task(task_id, f"Command timed out after {self.timeout} seconds")
                return f"Error: Command timed out after {self.timeout} seconds"

            output_parts = []

            if stdout:
                output_parts.append(stdout.decode("utf-8", errors="replace"))

            if stderr:
                stderr_text = stderr.decode("utf-8", errors="replace")
                if stderr_text.strip():
                    output_parts.append(f"STDERR:\n{stderr_text}")

            if process.returncode != 0:
                output_parts.append(f"\nExit code: {process.returncode}")

            result = "\n".join(output_parts) if output_parts else "(no output)"

            # Truncate very long output
            max_len = 10000
            if len(result) > max_len:
                result = result[:max_len] + f"\n... (truncated, {len(result) - max_len} more chars)"

            # Update task status
            if task_id:
                if process.returncode == 0:
                    task_manager.complete_task(task_id, result=result[:500])
                else:
                    task_manager.fail_task(task_id, error=f"Exit code: {process.returncode}")

            return result

        except Exception as e:
            if task_id:
                task_manager.fail_task(task_id, error=str(e))
            return f"Error executing command: {str(e)}"

    def _guard_command(self, command: str, cwd: str) -> str | None:
        """Best-effort safety guard for potentially destructive commands."""
        cmd = command.strip()
        lower = cmd.lower()

        for pattern in self.deny_patterns:
            if re.search(pattern, lower):
                return "Error: Command blocked by safety guard (dangerous pattern detected)"

        if self.allow_patterns:
            if not any(re.search(p, lower) for p in self.allow_patterns):
                return "Error: Command blocked by safety guard (not in allowlist)"

        if self.restrict_to_workspace:
            if "..\\" in cmd or "../" in cmd:
                return "Error: Command blocked by safety guard (path traversal detected)"

            cwd_path = Path(cwd).resolve()

            win_paths = re.findall(r"[A-Za-z]:\\[^\\\"']+", cmd)
            posix_paths = re.findall(r"/[^\s\"']+", cmd)

            for raw in win_paths + posix_paths:
                try:
                    p = Path(raw).resolve()
                except Exception:
                    continue
                if cwd_path not in p.parents and p != cwd_path:
                    return "Error: Command blocked by safety guard (path outside working dir)"

        return None
