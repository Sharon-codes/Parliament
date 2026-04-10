"""
remote_server.py — Saathi Module 7: Phone-to-Laptop Remote Control
WebSocket server on port 8765. Phone PWA connects over LAN or via
Cloudflare Tunnel / ngrok for remote access.

Run standalone:
    python remote_server.py

Or import start_remote_server() and call it from main.py in a thread.
"""

import asyncio
import json
import os
import re
import sys
import subprocess
import threading
import time
import datetime
import platform
import hashlib
import secrets
import psutil
import websockets
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────────
WS_PORT       = 8765
PIN_HASH_FILE = Path(__file__).parent / ".saathi_pin_hash"

# Map of project-name → (root_path, entry_point)
# Saathi will populated this from active context; you can seed it here too.
KNOWN_PROJECTS: dict[str, dict] = {
    "saathi-api":   {"root": str(Path(__file__).parent), "entry": "main.py"},
    "saathi-web":   {"root": str(Path(__file__).parent.parent / "saathi-web"), "entry": "src/main.jsx"},
}
active_project: str = "saathi-api"   # updated at runtime by chat context

# Research download folder
RESEARCH_DIR = Path.home() / "Desktop" / "Saathi_Research"
RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

# ── PIN management ─────────────────────────────────────────────────────────────

def _hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.strip().encode()).hexdigest()

def get_or_create_pin() -> str:
    """Return the current saved PIN hash, creating a default one if absent."""
    if PIN_HASH_FILE.exists():
        return PIN_HASH_FILE.read_text().strip()
    default = "1234"
    h = _hash_pin(default)
    PIN_HASH_FILE.write_text(h)
    print(f"[Saathi Remote] Default PIN is 1234 — change it via the phone app.")
    return h

def verify_pin(pin: str) -> bool:
    expected = get_or_create_pin()
    return _hash_pin(pin) == expected

def set_pin(new_pin: str):
    PIN_HASH_FILE.write_text(_hash_pin(new_pin))

# ── Authenticated sessions ─────────────────────────────────────────────────────
# Maps websocket → auth token string; only authenticated sockets can run commands.
authed: dict = {}

# ── Command Handlers ───────────────────────────────────────────────────────────

async def cmd_ping(_args: str, _ws) -> str:
    return json.dumps({"type": "pong", "ts": datetime.datetime.now().isoformat()})


async def cmd_processes(_args: str, _ws) -> str:
    procs = []
    for p in sorted(psutil.process_iter(['pid','name','cpu_percent','memory_info']), key=lambda x: x.info['cpu_percent'] or 0, reverse=True)[:15]:
        try:
            procs.append({
                "pid":  p.info['pid'],
                "name": p.info['name'],
                "cpu":  round(p.info['cpu_percent'] or 0, 1),
                "mem":  round((p.info['memory_info'].rss if p.info['memory_info'] else 0) / 1_048_576, 1)
            })
        except Exception:
            pass
    return json.dumps({"type": "processes", "data": procs})


async def cmd_sysinfo(_args: str, _ws) -> str:
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    cpu = psutil.cpu_percent(interval=0.5)
    return json.dumps({
        "type": "sysinfo",
        "cpu_pct":   cpu,
        "mem_used":  round(mem.used / 1_073_741_824, 2),
        "mem_total": round(mem.total / 1_073_741_824, 2),
        "disk_used": round(disk.used / 1_073_741_824, 1),
        "disk_total":round(disk.total / 1_073_741_824, 1),
        "platform":  platform.platform(),
    })


async def cmd_open_vscode(args: str, _ws) -> str:
    """Open a file or folder in VS Code."""
    target = args.strip() or str(Path(__file__).parent)
    subprocess.Popen(f'code "{target}"', shell=True)
    return json.dumps({"type": "ok", "msg": f"Opened VS Code → {target}"})


async def cmd_lock_screen(_args: str, _ws) -> str:
    sys_name = platform.system()
    if sys_name == "Windows":
        subprocess.Popen("rundll32.exe user32.dll,LockWorkStation", shell=True)
    elif sys_name == "Darwin":
        subprocess.Popen("pmset displaysleepnow", shell=True)
    else:
        subprocess.Popen("gnome-screensaver-command --lock", shell=True)
    return json.dumps({"type": "ok", "msg": "Screen locked."})


async def cmd_shutdown(args: str, _ws) -> str:
    """Schedule shutdown in N minutes (default 30)."""
    m = re.search(r"(\d+)", args)
    minutes = int(m.group(1)) if m else 30
    sys_name = platform.system()
    if sys_name == "Windows":
        subprocess.Popen(f"shutdown /s /t {minutes * 60}", shell=True)
    elif sys_name == "Darwin":
        subprocess.Popen(f"sudo shutdown -h +{minutes}", shell=True)
    else:
        subprocess.Popen(f"shutdown -h +{minutes}", shell=True)
    return json.dumps({"type": "ok", "msg": f"Shutdown scheduled in {minutes} minutes."})


async def cmd_cancel_shutdown(_args: str, _ws) -> str:
    sys_name = platform.system()
    if sys_name == "Windows":
        subprocess.Popen("shutdown /a", shell=True)
    else:
        subprocess.Popen("sudo shutdown -c", shell=True)
    return json.dumps({"type": "ok", "msg": "Shutdown cancelled."})


async def cmd_play_focus(_args: str, _ws) -> str:
    url = "https://www.youtube.com/watch?v=jfKfPfyJRdk"  # lofi hip hop
    if platform.system() == "Windows":
        subprocess.Popen(f'start {url}', shell=True)
    elif platform.system() == "Darwin":
        subprocess.Popen(f'open {url}', shell=True)
    else:
        subprocess.Popen(f'xdg-open {url}', shell=True)
    return json.dumps({"type": "ok", "msg": "▶ Focus music launched."})


async def cmd_download_paper(args: str, ws) -> str:
    """Download a URL to the research folder and stream progress."""
    url = args.strip()
    if not url.startswith("http"):
        return json.dumps({"type": "error", "msg": "Please provide a valid URL."})
    try:
        import urllib.request
        filename = url.split("/")[-1].split("?")[0] or "paper.pdf"
        dest = RESEARCH_DIR / filename
        await ws.send(json.dumps({"type": "stream", "line": f"⬇ Downloading {filename}…"}))
        urllib.request.urlretrieve(url, dest)
        return json.dumps({"type": "ok", "msg": f"Saved to {dest}"})
    except Exception as e:
        return json.dumps({"type": "error", "msg": str(e)})


async def cmd_pomodoro(args: str, ws) -> str:
    """Start a Pomodoro timer (focus_mins work, 5 min break)."""
    m = re.search(r"(\d+)", args)
    focus_mins = int(m.group(1)) if m else 25
    secs = focus_mins * 60

    async def _run():
        await ws.send(json.dumps({"type": "stream", "line": f"🍅 Pomodoro started — {focus_mins} min focus block. Get to work!"}))
        await asyncio.sleep(secs)
        # Desktop notification
        _desktop_notify("Saathi Pomodoro", f"⏰ {focus_mins}-min focus block complete! Take a 5-min break.")
        await ws.send(json.dumps({"type": "stream", "line": "✅ Pomodoro complete! Time for a 5-min break."}))

    asyncio.create_task(_run())
    return json.dumps({"type": "ok", "msg": f"🍅 Pomodoro timer started ({focus_mins} min)"})


def _desktop_notify(title: str, body: str):
    try:
        if platform.system() == "Windows":
            from win10toast import ToastNotifier
            t = ToastNotifier()
            t.show_toast(title, body, duration=8, threaded=True)
        elif platform.system() == "Darwin":
            subprocess.Popen(f'osascript -e \'display notification "{body}" with title "{title}"\'', shell=True)
        else:
            subprocess.Popen(f'notify-send "{title}" "{body}"', shell=True)
    except Exception:
        pass


async def cmd_run_code(args: str, ws) -> str:
    """
    Run the active project's entry point (or a specified script).
    Streams stdout/stderr line-by-line back to the phone.
    """
    global active_project

    # Determine which file to run
    project_info = KNOWN_PROJECTS.get(active_project, {})
    root   = project_info.get("root", str(Path.cwd()))
    entry  = project_info.get("entry", "main.py")

    # Allow override: "run train.py --epochs 10"
    extra_args = []
    if args.strip():
        parts = args.strip().split()
        if parts[0].endswith(".py"):
            entry = parts[0]
            extra_args = parts[1:]
        else:
            extra_args = parts

    script_path = Path(root) / entry
    if not script_path.exists():
        return json.dumps({"type": "error", "msg": f"Script not found: {script_path}"})

    # Prefer venv python if present
    venv_python = Path(root) / "venv" / ("Scripts" if platform.system() == "Windows" else "bin") / "python"
    python_exe  = str(venv_python) if venv_python.exists() else sys.executable

    cmd = [python_exe, str(script_path)] + extra_args
    await ws.send(json.dumps({"type": "stream", "line": f"▶ Running: {' '.join(cmd)}"}))
    await ws.send(json.dumps({"type": "stream", "line": f"  cwd: {root}"}))
    await ws.send(json.dumps({"type": "stream", "line": "─" * 40}))

    error_lines = []
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=root,
        )

        async for raw_line in proc.stdout:
            line = raw_line.decode(errors="replace").rstrip()
            if line:
                await ws.send(json.dumps({"type": "stream", "line": line}))
                if "error" in line.lower() or "traceback" in line.lower():
                    error_lines.append(line)

        await proc.wait()
        rc = proc.returncode
        await ws.send(json.dumps({"type": "stream", "line": "─" * 40}))
        await ws.send(json.dumps({"type": "stream", "line": f"✔ Exit code: {rc}"}))

        if rc != 0 and error_lines:
            tb_snippet = "\n".join(error_lines[-8:])
            await ws.send(json.dumps({
                "type": "error_analysis",
                "msg": f"Detected errors. Traceback snippet:\n{tb_snippet}\n\n💡 Ask Saathi: 'Analyze this error' to get a fix suggestion."
            }))
        return json.dumps({"type": "done", "rc": rc})

    except Exception as e:
        return json.dumps({"type": "error", "msg": str(e)})


async def cmd_set_project(args: str, _ws) -> str:
    global active_project
    name = args.strip()
    if name in KNOWN_PROJECTS:
        active_project = name
        return json.dumps({"type": "ok", "msg": f"Active project set to '{name}'"})
    # Auto-register a path
    if os.path.isdir(name):
        pname = Path(name).name
        entry = "main.py"
        for candidate in ["main.py", "train.py", "app.py", "run.py", "index.py"]:
            if (Path(name) / candidate).exists():
                entry = candidate
                break
        KNOWN_PROJECTS[pname] = {"root": name, "entry": entry}
        active_project = pname
        return json.dumps({"type": "ok", "msg": f"Registered new project '{pname}' → {entry}"})
    return json.dumps({"type": "error", "msg": f"Unknown project: {name}. Known: {list(KNOWN_PROJECTS.keys())}"})


async def cmd_list_projects(_args: str, _ws) -> str:
    data = [{"name": k, "root": v["root"], "entry": v["entry"], "active": k == active_project}
            for k, v in KNOWN_PROJECTS.items()]
    return json.dumps({"type": "projects", "data": data, "active": active_project})


async def cmd_open_file(args: str, _ws) -> str:
    path = args.strip()
    if not path:
        return json.dumps({"type": "error", "msg": "Please specify a file path."})
    # Try OS open first, then VS Code
    if platform.system() == "Windows":
        subprocess.Popen(f'code "{path}"', shell=True)
    elif platform.system() == "Darwin":
        subprocess.Popen(f'open -a "Visual Studio Code" "{path}"', shell=True)
    else:
        subprocess.Popen(f'code "{path}"', shell=True)
    return json.dumps({"type": "ok", "msg": f"Opened: {path}"})


async def cmd_clipboard_get(_args: str, _ws) -> str:
    try:
        import pyperclip
        content = pyperclip.paste()
        return json.dumps({"type": "clipboard", "content": content[:1000]})
    except Exception as e:
        return json.dumps({"type": "error", "msg": str(e)})


async def cmd_clipboard_set(args: str, _ws) -> str:
    try:
        import pyperclip
        pyperclip.copy(args.strip())
        return json.dumps({"type": "ok", "msg": "Clipboard updated."})
    except Exception as e:
        return json.dumps({"type": "error", "msg": str(e)})


async def cmd_set_pin(args: str, _ws) -> str:
    new_pin = args.strip()
    if not new_pin or len(new_pin) < 4:
        return json.dumps({"type": "error", "msg": "PIN must be at least 4 characters."})
    set_pin(new_pin)
    return json.dumps({"type": "ok", "msg": "PIN updated successfully."})


async def cmd_help(_args: str, _ws) -> str:
    cmds = [
        ("ping",            "Check connection latency"),
        ("processes",       "List top CPU processes"),
        ("sysinfo",         "CPU / RAM / Disk stats"),
        ("run [args]",      "Run active project entry point"),
        ("set_project <name|path>", "Set or register active project"),
        ("list_projects",   "Show all known projects"),
        ("open_file <path>","Open file in VS Code"),
        ("open_vscode [path]","Open VS Code"),
        ("lock",            "Lock screen"),
        ("shutdown [N]",    "Shutdown in N minutes"),
        ("cancel_shutdown", "Cancel scheduled shutdown"),
        ("pomodoro [N]",    "Start Pomodoro timer (default 25 min)"),
        ("focus_music",     "Launch lofi focus music in browser"),
        ("download <url>",  "Download file to research folder"),
        ("clipboard_get",   "Read clipboard content"),
        ("clipboard_set <text>","Write to clipboard"),
        ("set_pin <new>",   "Change connection PIN"),
        ("help",            "Show this list"),
    ]
    return json.dumps({"type": "help", "commands": [{"cmd": c, "desc": d} for c, d in cmds]})


# ── Command Router ─────────────────────────────────────────────────────────────
COMMAND_MAP = {
    "ping":            cmd_ping,
    "processes":       cmd_processes,
    "sysinfo":         cmd_sysinfo,
    "run":             cmd_run_code,
    "set_project":     cmd_set_project,
    "list_projects":   cmd_list_projects,
    "open_file":       cmd_open_file,
    "open_vscode":     cmd_open_vscode,
    "lock":            cmd_lock_screen,
    "shutdown":        cmd_shutdown,
    "cancel_shutdown": cmd_cancel_shutdown,
    "pomodoro":        cmd_pomodoro,
    "focus_music":     cmd_play_focus,
    "download":        cmd_download_paper,
    "clipboard_get":   cmd_clipboard_get,
    "clipboard_set":   cmd_clipboard_set,
    "set_pin":         cmd_set_pin,
    "help":            cmd_help,
}

def _parse_command(raw: str) -> tuple[str, str]:
    """Split raw text into (command, args)."""
    parts = raw.strip().split(None, 1)
    cmd  = parts[0].lower() if parts else ""
    args = parts[1] if len(parts) > 1 else ""
    return cmd, args


# ── NL→Command mapper (lightweight, no LLM needed) ───────────────────────────
NL_PATTERNS = [
    (r"run.*code|execute.*code|start.*project",          "run"),
    (r"what'?s?\s+running|list.*process",                "processes"),
    (r"system info|cpu|ram|memory stats",                "sysinfo"),
    (r"open.*vscode|visual studio|code editor",          "open_vscode"),
    (r"lock.*screen|lock.*computer",                     "lock"),
    (r"shutdown|turn off",                               "shutdown"),
    (r"cancel.*shutdown|abort.*shutdown",                "cancel_shutdown"),
    (r"pomodoro|focus timer|start.*timer",               "pomodoro"),
    (r"focus music|lofi|play.*music|study music",        "focus_music"),
    (r"download.*paper|download.*file",                  "download"),
    (r"clipboard",                                       "clipboard_get"),
    (r"what.*deadline|next.*deadline",                   "sysinfo"),  # fallback
    (r"help|commands|what can you do",                   "help"),
]

def nl_to_command(text: str) -> tuple[str, str] | None:
    t = text.lower()
    for pattern, cmd in NL_PATTERNS:
        if re.search(pattern, t):
            # Try to extract an argument from the natural language
            # e.g. "download https://..." → args = URL
            url_m = re.search(r'https?://\S+', text)
            file_m = re.search(r'[\w/\\:]+\.\w{2,5}', text)
            mins_m = re.search(r'(\d+)\s*min', text)
            args = ""
            if cmd == "download" and url_m:
                args = url_m.group(0)
            elif cmd == "open_file" and file_m:
                args = file_m.group(0)
            elif cmd in ("shutdown", "pomodoro") and mins_m:
                args = mins_m.group(1)
            return cmd, args
    return None


# ── WebSocket Handler ──────────────────────────────────────────────────────────

async def handler(ws):
    """One connection = one phone session."""
    peer = ws.remote_address
    print(f"[Remote] Connection from {peer}")

    # Step 1: Send challenge, require PIN
    token = secrets.token_hex(16)
    await ws.send(json.dumps({
        "type": "auth_required",
        "msg":  "Saathi Remote — please enter your PIN.",
        "token": token
    }))

    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=30)
        msg = json.loads(raw)
        if msg.get("type") != "auth" or not verify_pin(msg.get("pin", "")):
            await ws.send(json.dumps({"type": "auth_failed", "msg": "Incorrect PIN."}))
            print(f"[Remote] Auth FAILED from {peer}")
            return
    except (asyncio.TimeoutError, Exception):
        return

    authed[id(ws)] = token
    await ws.send(json.dumps({
        "type": "auth_ok",
        "msg":  f"Authenticated ✓  Active project: {active_project}",
        "active_project": active_project,
    }))
    print(f"[Remote] Authenticated {peer}")

    # Step 2: Command loop
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except Exception:
                await ws.send(json.dumps({"type": "error", "msg": "Invalid JSON"}))
                continue

            msg_type = msg.get("type", "command")
            text     = msg.get("text", "").strip()

            if not text:
                continue

            # Natural language → command
            parsed = nl_to_command(text)
            if parsed:
                cmd, args = parsed
            else:
                cmd, args = _parse_command(text)

            handler_fn = COMMAND_MAP.get(cmd)
            if not handler_fn:
                await ws.send(json.dumps({
                    "type": "error",
                    "msg": f"Unknown command: '{cmd}'. Type 'help' for the list."
                }))
                continue

            try:
                result_raw = await handler_fn(args, ws)
                if result_raw:
                    await ws.send(result_raw)
            except Exception as e:
                await ws.send(json.dumps({"type": "error", "msg": str(e)}))

    except websockets.exceptions.ConnectionClosedOK:
        pass
    except Exception as e:
        print(f"[Remote] Error: {e}")
    finally:
        authed.pop(id(ws), None)
        print(f"[Remote] Disconnected {peer}")


# ── Entry point ────────────────────────────────────────────────────────────────

async def _serve():
    get_or_create_pin()
    # Get local IP for display
    import socket
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "127.0.0.1"

    print("=" * 52)
    print("  🌐 Saathi Remote Server — Module 7")
    print(f"  Local:  ws://{local_ip}:{WS_PORT}")
    print(f"  PIN:    stored at {PIN_HASH_FILE}")
    print(f"  PWA:    open saathi-remote/index.html on phone")
    print("=" * 52)

    async with websockets.serve(handler, "0.0.0.0", WS_PORT):
        await asyncio.Future()   # run forever


def start_remote_server():
    """Start the WebSocket server in a background thread (call from main.py)."""
    def _thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_serve())
    t = threading.Thread(target=_thread, daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    asyncio.run(_serve())
