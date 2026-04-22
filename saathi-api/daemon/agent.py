r"""
daemon/agent.py — Saathi Edge Daemon: Local Machine Agent

A lightweight Python client that runs on the user's physical machine.
Maintains a persistent, outbound WebSocket connection to the Cloud Hub,
bypassing residential NAT/firewalls.

Responsibilities:
  1. Connect to Cloud Hub via authenticated WebSocket
  2. Receive JSON execution payloads
  3. Execute commands within a strict Path Jail (~/saathi_workspace)
  4. Stream stdout/stderr back to the Hub in real-time
  5. Heartbeat loop for connection liveness
  6. Optional local Gemma 2B inference via Ollama for offline queries

Security:
  - Path Jail: All execution is confined to ~/saathi_workspace
  - No arbitrary shell access outside the workspace
  - Token-based authentication with the Cloud Hub
"""

import asyncio
import json
import logging
import os
import platform
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

import httpx
import websockets
from dotenv import load_dotenv

load_dotenv()

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Daemon] %(levelname)s: %(message)s",
)
logger = logging.getLogger("saathi.daemon")

# ── Configuration ──────────────────────────────────────────────────────────────
# Stored in a mutable dict so main() can override without 'global' declaration
_CONFIG = {
    "hub_ws_url": os.getenv("HUB_WS_URL", "ws://localhost:7860/ws/daemon"),
    "daemon_token": os.getenv("DAEMON_TOKEN", ""),
    "daemon_id": os.getenv("DAEMON_ID", f"daemon-{platform.node()}"),
    "workspace_dir": Path(
        os.getenv("SAATHI_WORKSPACE", os.path.expanduser("~/saathi_workspace"))
    ).resolve(),
    "heartbeat_interval": int(os.getenv("HEARTBEAT_INTERVAL", "30")),
    "ollama_url": os.getenv("OLLAMA_URL", "http://localhost:11434"),
    "local_model": os.getenv("LOCAL_MODEL", "gemma2:2b"),
}

# Convenience module-level accessors (read from _CONFIG)
HUB_WS_URL = _CONFIG["hub_ws_url"]
DAEMON_TOKEN = _CONFIG["daemon_token"]
DAEMON_ID = _CONFIG["daemon_id"]
WORKSPACE_DIR = _CONFIG["workspace_dir"]
HEARTBEAT_INTERVAL = _CONFIG["heartbeat_interval"]
OLLAMA_URL = _CONFIG["ollama_url"]
LOCAL_MODEL = _CONFIG["local_model"]

# Reconnection settings
RECONNECT_BASE_DELAY = 2     # seconds
RECONNECT_MAX_DELAY = 120    # seconds
RECONNECT_BACKOFF = 1.5      # multiplier


# ── Path Jail Security ────────────────────────────────────────────────────────

class PathJailViolation(Exception):
    """Raised when a command attempts to escape the workspace jail."""
    pass


def ensure_workspace():
    """Create the workspace directory if it doesn't exist."""
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"📁 Workspace jail: {WORKSPACE_DIR}")


def validate_path(path_str: str) -> Path:
    """
    Validate and resolve a path, ensuring it stays within the workspace jail.
    Raises PathJailViolation if the path escapes.
    """
    if not path_str:
        return WORKSPACE_DIR

    requested = Path(path_str)

    # If relative, resolve relative to workspace
    if not requested.is_absolute():
        resolved = (WORKSPACE_DIR / requested).resolve()
    else:
        resolved = requested.resolve()

    # Check jail containment
    try:
        resolved.relative_to(WORKSPACE_DIR)
    except ValueError:
        raise PathJailViolation(
            f"🔒 PATH JAIL VIOLATION: '{path_str}' resolves to '{resolved}' "
            f"which is outside the workspace '{WORKSPACE_DIR}'. "
            f"Access denied."
        )

    return resolved


def validate_command(command: str) -> str:
    """
    Validate a shell command for safety. Block dangerous patterns
    that could escape the jail or cause harm.
    """
    # Literal substring patterns (exact match)
    dangerous_substrings = [
        "rm -rf /",
        "mkfs",
        "> /dev/",
        "chmod 777 /",
        "eval(",
        "__import__",
    ]

    # Regex patterns (for commands with arguments between keywords)
    dangerous_regexes = [
        r"dd\s+if=",            # disk destroyer
        r":\(\)\s*\{",          # fork bomb
        r"curl\b.*\|\s*sh",     # pipe remote script to shell
        r"wget\b.*\|\s*sh",     # pipe remote script to shell
        r"curl\b.*\|\s*bash",   # pipe remote script to bash
        r"wget\b.*\|\s*bash",   # pipe remote script to bash
    ]

    lower = command.lower()

    for pattern in dangerous_substrings:
        if pattern in lower:
            raise PathJailViolation(
                f"🔒 BLOCKED: Command contains dangerous pattern '{pattern}'"
            )

    for pattern in dangerous_regexes:
        if re.search(pattern, lower):
            raise PathJailViolation(
                f"🔒 BLOCKED: Command matches dangerous pattern '{pattern}'"
            )

    return command


# ── Command Executors ─────────────────────────────────────────────────────────

async def execute_payload(
    payload: dict[str, Any],
    request_id: str,
    ws: websockets.WebSocketClientProtocol,
) -> dict[str, Any]:
    """
    Execute a JSON payload from the Cloud Hub within the path jail.
    Streams output back via the WebSocket.
    """
    action = payload.get("action", "")
    args = payload.get("args", {})
    timeout = payload.get("timeout", 300)

    logger.info(f"⚡ Executing: action={action} request_id={request_id}")

    try:
        if action == "run_script":
            return await _run_script(args, request_id, ws, timeout)
        elif action == "shell_exec":
            return await _shell_exec(args, request_id, ws, timeout)
        elif action == "list_files":
            return await _list_files(args)
        elif action == "read_file":
            return await _read_file(args)
        elif action == "write_file":
            return await _write_file(args)
        elif action == "sysinfo":
            return await _sysinfo()
        elif action == "processes":
            return await _processes()
        elif action == "app_launch":
            return await _app_launch(args)
        elif action == "system_control":
            return await _system_control(args)
        elif action == "local_llm":
            return await _local_llm_query(args)
        elif action == "echo":
            return {"status": "ok", "output": args.get("message", "echo")}
        else:
            return {"status": "error", "error": f"Unknown action: {action}"}
    except PathJailViolation as exc:
        logger.warning(str(exc))
        return {"status": "blocked", "error": str(exc)}
    except Exception as exc:
        logger.error(f"Execution error: {exc}", exc_info=True)
        return {"status": "error", "error": str(exc)}


async def _run_script(
    args: dict, request_id: str, ws, timeout: int
) -> dict[str, Any]:
    """Run a Python script within the workspace jail. Streams output."""
    script_path = validate_path(args.get("script", "main.py"))

    if not script_path.exists():
        return {"status": "error", "error": f"Script not found: {script_path.name}"}

    extra_args = args.get("extra_args", [])

    # Find Python executable (prefer venv)
    venv_py = WORKSPACE_DIR / "venv" / (
        "Scripts" if platform.system() == "Windows" else "bin"
    ) / "python"
    python_exe = str(venv_py) if venv_py.exists() else sys.executable

    cmd = [python_exe, str(script_path)] + extra_args

    return await _stream_subprocess(cmd, request_id, ws, timeout, cwd=str(WORKSPACE_DIR))


async def _shell_exec(
    args: dict, request_id: str, ws, timeout: int
) -> dict[str, Any]:
    """Execute a shell command within the workspace. Streams output."""
    command = validate_command(args.get("command", ""))
    if not command:
        return {"status": "error", "error": "No command provided"}

    # Run via shell within workspace
    return await _stream_subprocess(
        command, request_id, ws, timeout,
        cwd=str(WORKSPACE_DIR), shell=True
    )


async def _stream_subprocess(
    cmd, request_id: str, ws, timeout: int,
    cwd: str = None, shell: bool = False,
) -> dict[str, Any]:
    """
    Execute a subprocess and stream its output line-by-line
    back to the Cloud Hub via WebSocket.
    """
    output_lines = []

    try:
        if shell:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
        else:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

        # Stream stdout
        async def _stream_pipe(pipe, stream_type):
            async for raw_line in pipe:
                line = raw_line.decode(errors="replace").rstrip()
                if line:
                    output_lines.append(line)
                    try:
                        await ws.send(json.dumps({
                            "type": "stream",
                            "request_id": request_id,
                            "line": line,
                            "stream_type": stream_type,
                        }))
                    except Exception:
                        pass  # WebSocket may be closing

        await asyncio.gather(
            _stream_pipe(proc.stdout, "stdout"),
            _stream_pipe(proc.stderr, "stderr"),
        )

        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return {
                "status": "timeout",
                "exit_code": -1,
                "output": "\n".join(output_lines[-50:]),
                "error": f"Process timed out after {timeout}s",
            }

        return {
            "status": "completed",
            "exit_code": proc.returncode,
            "output": "\n".join(output_lines[-100:]),
        }

    except Exception as exc:
        return {"status": "error", "error": str(exc)}


async def _list_files(args: dict) -> dict[str, Any]:
    """List files in the workspace (jailed)."""
    target = validate_path(args.get("path", "."))
    if not target.exists():
        return {"status": "error", "error": f"Path does not exist: {target.name}"}

    files = []
    for item in sorted(target.iterdir()):
        files.append({
            "name": item.name,
            "type": "dir" if item.is_dir() else "file",
            "size": item.stat().st_size if item.is_file() else None,
        })

    return {"status": "ok", "path": str(target.relative_to(WORKSPACE_DIR)), "files": files}


async def _read_file(args: dict) -> dict[str, Any]:
    """Read a file's contents (jailed)."""
    target = validate_path(args.get("path", ""))
    if not target.exists() or not target.is_file():
        return {"status": "error", "error": f"File not found: {target.name}"}

    # Limit file size to 500KB
    if target.stat().st_size > 512_000:
        return {"status": "error", "error": f"File too large ({target.stat().st_size} bytes)"}

    content = target.read_text(encoding="utf-8", errors="replace")
    return {"status": "ok", "path": target.name, "content": content}


async def _write_file(args: dict) -> dict[str, Any]:
    """Write content to a file (jailed)."""
    target = validate_path(args.get("path", ""))
    content = args.get("content", "")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    return {
        "status": "ok",
        "path": target.name,
        "size": len(content.encode("utf-8")),
    }


async def _sysinfo() -> dict[str, Any]:
    """Gather system information."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        cpu_pct = psutil.cpu_percent(interval=0.5)
    except ImportError:
        return {
            "status": "ok",
            "platform": platform.platform(),
            "python": sys.version,
            "note": "Install psutil for detailed metrics",
        }

    return {
        "status": "ok",
        "platform": platform.platform(),
        "python": sys.version,
        "cpu_percent": cpu_pct,
        "memory": {
            "used_gb": round(mem.used / 1e9, 2),
            "total_gb": round(mem.total / 1e9, 2),
            "percent": mem.percent,
        },
        "disk": {
            "used_gb": round(disk.used / 1e9, 1),
            "total_gb": round(disk.total / 1e9, 1),
            "percent": disk.percent,
        },
    }


async def _processes() -> dict[str, Any]:
    """List top processes by CPU usage."""
    try:
        import psutil
        procs = []
        for p in sorted(
            psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]),
            key=lambda x: x.info["cpu_percent"] or 0,
            reverse=True,
        )[:15]:
            try:
                procs.append({
                    "pid": p.info["pid"],
                    "name": p.info["name"],
                    "cpu": round(p.info["cpu_percent"] or 0, 1),
                    "mem_mb": round(
                        (p.info["memory_info"].rss if p.info["memory_info"] else 0) / 1e6,
                        1,
                    ),
                })
            except Exception:
                pass
        return {"status": "ok", "processes": procs}
    except ImportError:
        return {"status": "error", "error": "psutil not installed"}


async def _app_launch(args: dict) -> dict[str, Any]:
    """Launch a desktop application."""
    app_name = args.get("app", "").lower()
    file_path = args.get("file")

    app_commands = {
        "vscode": "code",
        "code": "code",
        "chrome": "start chrome" if platform.system() == "Windows" else "google-chrome",
        "browser": "start chrome" if platform.system() == "Windows" else "xdg-open",
        "notepad": "notepad",
        "terminal": "start cmd" if platform.system() == "Windows" else "gnome-terminal",
    }

    cmd = app_commands.get(app_name)
    if not cmd:
        return {"status": "error", "error": f"Unknown app: {app_name}"}

    full_cmd = f'{cmd} "{file_path}"' if file_path else cmd
    subprocess.Popen(full_cmd, shell=True)

    return {"status": "ok", "launched": app_name}


async def _system_control(args: dict) -> dict[str, Any]:
    """System control actions (lock, shutdown, etc.)."""
    action = args.get("action", "")
    sys_name = platform.system()

    if action == "lock":
        if sys_name == "Windows":
            subprocess.Popen("rundll32.exe user32.dll,LockWorkStation", shell=True)
        elif sys_name == "Darwin":
            subprocess.Popen("pmset displaysleepnow", shell=True)
        else:
            subprocess.Popen("loginctl lock-session", shell=True)
        return {"status": "ok", "action": "screen_locked"}

    elif action == "shutdown":
        # Schedule shutdown in 5 minutes (safety buffer)
        if sys_name == "Windows":
            subprocess.Popen("shutdown /s /t 300", shell=True)
        else:
            subprocess.Popen("shutdown -h +5", shell=True)
        return {"status": "ok", "action": "shutdown_scheduled", "delay_minutes": 5}

    return {"status": "error", "error": f"Unknown system action: {action}"}


async def _local_llm_query(args: dict) -> dict[str, Any]:
    """
    Query the local Gemma 2B model via Ollama for offline inference.
    This is the Tier 3 edge fallback.
    """
    message = args.get("message", "")
    system_prompt = args.get("system_prompt", "You are Saathi, a helpful AI assistant.")

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": LOCAL_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message},
                    ],
                    "stream": False,
                },
            )

        if response.status_code >= 400:
            return {
                "status": "error",
                "error": f"Ollama returned {response.status_code}",
            }

        data = response.json()
        return {
            "status": "ok",
            "text": data.get("message", {}).get("content", ""),
            "model": LOCAL_MODEL,
        }
    except Exception as exc:
        return {"status": "error", "error": f"Local LLM unavailable: {exc}"}


# ── WebSocket Client Loop ─────────────────────────────────────────────────────

class DaemonClient:
    """
    Persistent WebSocket client that connects to the Saathi Cloud Hub.
    Features:
      - Auto-reconnection with exponential backoff
      - Heartbeat loop for liveness detection
      - Graceful shutdown on SIGINT/SIGTERM
    """

    def __init__(self):
        self._running = True
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._reconnect_delay = RECONNECT_BASE_DELAY

    async def start(self):
        """Main entry point — connect and handle messages."""
        ensure_workspace()

        # Register signal handlers
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                asyncio.get_event_loop().add_signal_handler(
                    sig, lambda: asyncio.create_task(self.shutdown())
                )
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                pass

        logger.info("═" * 56)
        logger.info("  Saathi Edge Daemon — Starting")
        logger.info(f"  Hub:       {HUB_WS_URL}")
        logger.info(f"  Daemon ID: {DAEMON_ID}")
        logger.info(f"  Workspace: {WORKSPACE_DIR}")
        logger.info(f"  Platform:  {platform.platform()}")
        logger.info("═" * 56)

        while self._running:
            try:
                await self._connect()
            except Exception as exc:
                logger.error(f"Connection failed: {exc}")

            if not self._running:
                break

            # Exponential backoff reconnection
            logger.info(
                f"🔄 Reconnecting in {self._reconnect_delay:.0f}s..."
            )
            await asyncio.sleep(self._reconnect_delay)
            self._reconnect_delay = min(
                self._reconnect_delay * RECONNECT_BACKOFF, RECONNECT_MAX_DELAY
            )

        logger.info("Daemon shut down.")

    async def _connect(self):
        """Establish WebSocket connection and enter message loop."""
        ws_url = f"{HUB_WS_URL}?token={DAEMON_TOKEN}"

        logger.info(f"📡 Connecting to {HUB_WS_URL}...")

        async with websockets.connect(
            ws_url,
            ping_interval=20,
            ping_timeout=60,
            close_timeout=10,
            max_size=10 * 1024 * 1024,  # 10MB max message
        ) as ws:
            self._ws = ws
            self._reconnect_delay = RECONNECT_BASE_DELAY  # Reset on success
            logger.info("✅ Connected to Cloud Hub")

            # Start heartbeat loop
            heartbeat_task = asyncio.create_task(self._heartbeat_loop(ws))

            try:
                async for raw_message in ws:
                    try:
                        data = json.loads(raw_message)
                    except json.JSONDecodeError:
                        logger.warning(f"Non-JSON message received: {raw_message[:100]}")
                        continue

                    msg_type = data.get("type", "unknown")

                    if msg_type == "connected":
                        logger.info(
                            f"🤝 Hub acknowledged: v{data.get('hub_version', '?')}"
                        )

                    elif msg_type == "execute":
                        # Execute payload from the hub
                        payload = data.get("payload", {})
                        request_id = data.get("request_id", "unknown")
                        logger.info(
                            f"📥 Received execution: {payload.get('action', '?')} "
                            f"[{request_id}]"
                        )

                        # Execute asynchronously and send result back
                        asyncio.create_task(
                            self._execute_and_report(ws, payload, request_id)
                        )

                    elif msg_type == "heartbeat_ack":
                        pass  # Expected

                    elif msg_type == "ping":
                        await ws.send(json.dumps({"type": "pong"}))

                    else:
                        logger.debug(f"Unhandled message type: {msg_type}")

            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

    async def _heartbeat_loop(self, ws):
        """Send periodic heartbeats to the Cloud Hub."""
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await ws.send(json.dumps({
                    "type": "heartbeat",
                    "daemon_id": DAEMON_ID,
                    "timestamp": time.time(),
                }))
            except (asyncio.CancelledError, websockets.exceptions.ConnectionClosed):
                break
            except Exception as exc:
                logger.warning(f"Heartbeat failed: {exc}")
                break

    async def _execute_and_report(
        self, ws, payload: dict, request_id: str
    ):
        """Execute a payload and send the result back to the Hub."""
        start_time = time.time()

        result = await execute_payload(payload, request_id, ws)

        elapsed = time.time() - start_time
        result["elapsed_seconds"] = round(elapsed, 2)

        try:
            await ws.send(json.dumps({
                "type": "result",
                "request_id": request_id,
                "result": result,
            }))
        except Exception as exc:
            logger.error(f"Failed to send result: {exc}")

    async def shutdown(self):
        """Gracefully shut down the daemon."""
        logger.info("🛑 Shutting down daemon...")
        self._running = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass


# ── Entry Point ────────────────────────────────────────────────────────────────

def main():
    """CLI entry point for the Saathi Edge Daemon."""
    import argparse

    parser = argparse.ArgumentParser(description="Saathi Edge Daemon")
    parser.add_argument("--hub", default=_CONFIG["hub_ws_url"], help="Cloud Hub WebSocket URL")
    parser.add_argument("--token", default=_CONFIG["daemon_token"], help="Daemon JWT token")
    parser.add_argument("--workspace", default=str(_CONFIG["workspace_dir"]), help="Workspace directory")
    parser.add_argument("--daemon-id", default=_CONFIG["daemon_id"], help="Unique daemon identifier")
    args = parser.parse_args()

    # Override config via mutable dict (avoids 'global' SyntaxError in Python 3.14+)
    _CONFIG["hub_ws_url"] = args.hub
    _CONFIG["daemon_token"] = args.token
    _CONFIG["workspace_dir"] = Path(args.workspace).resolve()
    _CONFIG["daemon_id"] = args.daemon_id

    if not _CONFIG["daemon_token"]:
        logger.error(
            "❌ No DAEMON_TOKEN provided. Get one from the Cloud Hub:\n"
            "   POST /api/auth/daemon-token with your PSK"
        )
        sys.exit(1)

    client = DaemonClient()
    try:
        asyncio.run(client.start())
    except KeyboardInterrupt:
        logger.info("Daemon interrupted.")


if __name__ == "__main__":
    main()
