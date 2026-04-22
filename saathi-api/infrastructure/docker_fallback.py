"""
infrastructure/docker_fallback.py — Saathi Cloud Workspace (Offline Fallback)

When the user's physical Edge Daemon is offline, this module provisions
an ephemeral Docker container to execute scripts in the cloud.

Flow:
  1. Hub detects daemon is offline (WebSocket dead)
  2. Hub calls CloudWorkspaceManager.execute()
  3. Manager spins up a lightweight Python 3.11 container
  4. Pulls user's project from GitHub (if configured)
  5. Executes the command, captures output
  6. Tears down the container
  7. Returns results to the Hub for user delivery

NOTE: This module uses Docker SDK when available. On environments
without Docker (e.g., HF Spaces without DinD), it falls back to
subprocess-based execution in an isolated temp directory.
"""

import asyncio
import json
import logging
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger("saathi.cloud_workspace")

# ── Configuration ──────────────────────────────────────────────────────────────

DOCKER_IMAGE = os.getenv("CLOUD_WORKSPACE_IMAGE", "python:3.11-slim")
WORKSPACE_TIMEOUT = int(os.getenv("CLOUD_WORKSPACE_TIMEOUT", "120"))  # seconds
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
MAX_OUTPUT_SIZE = 50_000  # characters


# ── Docker Manager ─────────────────────────────────────────────────────────────

class CloudWorkspaceManager:
    """
    Manages ephemeral cloud workspaces for offline fallback execution.

    Supports two backends:
      1. Docker (preferred) — uses Docker SDK to create containers
      2. Subprocess (fallback) — uses isolated temp dirs when Docker isn't available
    """

    def __init__(self):
        self._docker_available = False
        self._docker_client = None
        self._active_workspaces: dict[str, dict] = {}
        self._init_docker()

    def _init_docker(self):
        """Try to initialize Docker client."""
        try:
            import docker
            self._docker_client = docker.from_env()
            self._docker_client.ping()
            self._docker_available = True
            logger.info("🐳 Docker backend available")
        except Exception as exc:
            logger.info(f"Docker unavailable ({exc}). Using subprocess fallback.")
            self._docker_available = False

    @property
    def backend(self) -> str:
        return "docker" if self._docker_available else "subprocess"

    async def execute(
        self,
        user_id: str,
        action: str,
        args: dict[str, Any],
        github_repo: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Execute a command in an ephemeral cloud workspace.

        Args:
            user_id: The user requesting execution
            action: The action type (run_script, shell_exec)
            args: Action-specific arguments
            github_repo: Optional GitHub repo URL to clone

        Returns:
            Execution result dict with status, output, etc.
        """
        workspace_id = f"ws-{uuid.uuid4().hex[:12]}"
        start_time = time.time()

        logger.info(
            f"☁️  Cloud workspace [{workspace_id}] for user {user_id}: "
            f"action={action}"
        )

        self._active_workspaces[workspace_id] = {
            "user_id": user_id,
            "action": action,
            "started_at": time.time(),
            "status": "running",
        }

        try:
            if self._docker_available:
                result = await self._execute_docker(
                    workspace_id, action, args, github_repo
                )
            else:
                result = await self._execute_subprocess(
                    workspace_id, action, args, github_repo
                )

            elapsed = time.time() - start_time
            result["workspace_id"] = workspace_id
            result["elapsed_seconds"] = round(elapsed, 2)
            result["backend"] = self.backend

            self._active_workspaces[workspace_id]["status"] = result.get("status", "done")
            return result

        except asyncio.TimeoutError:
            return {
                "workspace_id": workspace_id,
                "status": "timeout",
                "error": f"Execution timed out after {WORKSPACE_TIMEOUT}s",
                "backend": self.backend,
            }
        except Exception as exc:
            logger.error(f"Cloud workspace error: {exc}", exc_info=True)
            return {
                "workspace_id": workspace_id,
                "status": "error",
                "error": str(exc),
                "backend": self.backend,
            }
        finally:
            self._active_workspaces.pop(workspace_id, None)

    async def _execute_docker(
        self,
        workspace_id: str,
        action: str,
        args: dict,
        github_repo: Optional[str],
    ) -> dict[str, Any]:
        """Execute in a Docker container."""
        import docker

        container = None
        try:
            # Build the command
            if action == "run_script":
                script_content = args.get("content", "")
                script_name = args.get("script", "script.py")
                command = f"python /workspace/{script_name}"
            elif action == "shell_exec":
                command = args.get("command", "echo 'no command'")
            else:
                return {"status": "error", "error": f"Unsupported action: {action}"}

            # Prepare setup commands
            setup_cmds = []

            # Clone repo if configured
            if github_repo:
                clone_url = github_repo
                if GITHUB_TOKEN and "github.com" in github_repo:
                    clone_url = github_repo.replace(
                        "https://", f"https://{GITHUB_TOKEN}@"
                    )
                setup_cmds.append(
                    f"apt-get update -qq && apt-get install -y -qq git > /dev/null 2>&1 && "
                    f"git clone --depth 1 {clone_url} /workspace"
                )
            else:
                setup_cmds.append("mkdir -p /workspace")

            # Write script content if provided
            if action == "run_script" and script_content:
                # Escape the content for shell
                escaped = script_content.replace("'", "'\\''")
                setup_cmds.append(
                    f"echo '{escaped}' > /workspace/{script_name}"
                )

            # Install requirements if present
            setup_cmds.append(
                "cd /workspace && "
                "[ -f requirements.txt ] && pip install -q -r requirements.txt || true"
            )

            # Combine all commands
            full_command = " && ".join(setup_cmds + [f"cd /workspace && {command}"])

            # Run container
            container = self._docker_client.containers.run(
                DOCKER_IMAGE,
                command=["sh", "-c", full_command],
                detach=True,
                mem_limit="512m",
                cpu_period=100000,
                cpu_quota=50000,  # 50% CPU
                network_mode="bridge",
                remove=False,
                name=f"saathi-{workspace_id}",
            )

            # Wait for completion with timeout
            result = container.wait(timeout=WORKSPACE_TIMEOUT)
            logs = container.logs(stdout=True, stderr=True).decode(
                "utf-8", errors="replace"
            )

            # Truncate output
            if len(logs) > MAX_OUTPUT_SIZE:
                logs = logs[:MAX_OUTPUT_SIZE] + "\n... [output truncated]"

            return {
                "status": "completed",
                "exit_code": result.get("StatusCode", -1),
                "output": logs,
            }

        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

    async def _execute_subprocess(
        self,
        workspace_id: str,
        action: str,
        args: dict,
        github_repo: Optional[str],
    ) -> dict[str, Any]:
        """
        Fallback: Execute in an isolated temp directory using subprocess.
        Used when Docker is not available (e.g., HF Spaces).
        """
        tmpdir = tempfile.mkdtemp(prefix=f"saathi-ws-{workspace_id}-")

        try:
            # Clone repo if configured
            if github_repo:
                clone_url = github_repo
                if GITHUB_TOKEN and "github.com" in github_repo:
                    clone_url = github_repo.replace(
                        "https://", f"https://{GITHUB_TOKEN}@"
                    )
                clone_proc = await asyncio.create_subprocess_exec(
                    "git", "clone", "--depth", "1", clone_url, tmpdir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(clone_proc.wait(), timeout=60)

            # Write script content if provided
            if action == "run_script":
                script_content = args.get("content", "")
                script_name = args.get("script", "script.py")
                if script_content:
                    script_path = Path(tmpdir) / script_name
                    script_path.write_text(script_content, encoding="utf-8")

                # Install requirements
                req_file = Path(tmpdir) / "requirements.txt"
                if req_file.exists():
                    pip_proc = await asyncio.create_subprocess_exec(
                        sys.executable, "-m", "pip", "install",
                        "-q", "-r", str(req_file),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await asyncio.wait_for(pip_proc.wait(), timeout=120)

                cmd = [sys.executable, str(Path(tmpdir) / script_name)]

            elif action == "shell_exec":
                cmd = args.get("command", "echo 'no command'")
            else:
                return {"status": "error", "error": f"Unsupported action: {action}"}

            # Execute
            if isinstance(cmd, str):
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=tmpdir,
                )
            else:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=tmpdir,
                )

            try:
                stdout, _ = await asyncio.wait_for(
                    proc.communicate(), timeout=WORKSPACE_TIMEOUT
                )
            except asyncio.TimeoutError:
                proc.kill()
                return {
                    "status": "timeout",
                    "exit_code": -1,
                    "output": "",
                    "error": f"Timed out after {WORKSPACE_TIMEOUT}s",
                }

            output = stdout.decode("utf-8", errors="replace")
            if len(output) > MAX_OUTPUT_SIZE:
                output = output[:MAX_OUTPUT_SIZE] + "\n... [output truncated]"

            return {
                "status": "completed",
                "exit_code": proc.returncode,
                "output": output,
            }

        finally:
            # Clean up temp directory
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass

    async def list_active(self) -> list[dict]:
        """List currently running cloud workspaces."""
        return list(self._active_workspaces.values())


# Need sys import for subprocess fallback
import sys
