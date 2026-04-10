"""
tunnel_manager.py — Saathi Sync: Auto-tunnel + QR Code Manager
──────────────────────────────────────────────────────────────
Strategy (tried in order):
  1. Cloudflare Quick Tunnel (trycloudflare.com)
     - Zero config, no account, completely free
     - Run: cloudflared tunnel --url http://localhost:8000
  2. ngrok
     - Needs NGROK_AUTHTOKEN in .env (free tier)
     - Run: ngrok http 8000
  3. LAN fallback (same network only)

Mobile companion site is served at <public_url>/remote
QR code encodes: <public_url>/remote?ws=<ws_url>&pin=<pin>&name=<name>
Scanning QR → loads site → auto-connects, no manual input needed.
"""

import io
import json
import os
import re
import secrets
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

NGROK_TOKEN = os.getenv("NGROK_AUTHTOKEN", "").strip()
API_PORT    = int(os.getenv("API_PORT", "8000"))

# ── State ──────────────────────────────────────────────────────────────────────
_public_url:  Optional[str] = None
_tunnel_proc: Optional[subprocess.Popen] = None
_tunnel_type: str = "none"
_session_pin: str = "1234"          # loaded from or synced with remote_server PIN hash

# ── Helpers ────────────────────────────────────────────────────────────────────

def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _wait_for_url(proc: subprocess.Popen, pattern: str, timeout: int = 30) -> Optional[str]:
    """Read proc stderr/stdout line by line looking for a URL matching pattern."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = proc.stderr.readline()
        if not line:
            time.sleep(0.2)
            continue
        text = line.strip()
        if text:
            m = re.search(pattern, text)
            if m:
                return m.group(0)
        if proc.poll() is not None:
            break
    return None


# ── Tunnel backends ────────────────────────────────────────────────────────────

def _try_cloudflare() -> Optional[str]:
    """
    Cloudflare Quick Tunnel — no account, no dependency except cloudflared binary.
    Install: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/
    Or: winget install Cloudflare.cloudflared
    """
    import shutil
    if not shutil.which("cloudflared"):
        return None
    try:
        proc = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", f"http://localhost:{API_PORT}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        url = _wait_for_url(proc, r"https://[a-z0-9\-]+\.trycloudflare\.com", timeout=25)
        if url:
            global _tunnel_proc, _tunnel_type
            _tunnel_proc = proc
            _tunnel_type = "cloudflare"
            print(f"[Sync] Cloudflare tunnel: {url}")
            return url
        proc.kill()
    except Exception as e:
        print(f"[Sync] Cloudflare failed: {e}")
    return None


def _try_ngrok() -> Optional[str]:
    """ngrok — needs NGROK_AUTHTOKEN in .env and ngrok binary."""
    import shutil
    if not shutil.which("ngrok"):
        return None
    try:
        if NGROK_TOKEN:
            subprocess.run(["ngrok", "config", "add-authtoken", NGROK_TOKEN],
                           capture_output=True, timeout=5)
        proc = subprocess.Popen(
            ["ngrok", "http", str(API_PORT), "--log=stderr", "--log-format=json"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.time() + 20
        while time.time() < deadline:
            line = proc.stderr.readline()
            if not line:
                time.sleep(0.2)
                continue
            try:
                data = json.loads(line)
                if data.get("msg") == "started tunnel":
                    url = data.get("url", "")
                    if url.startswith("https://"):
                        global _tunnel_proc, _tunnel_type
                        _tunnel_proc = proc
                        _tunnel_type = "ngrok"
                        print(f"[Sync] ngrok tunnel: {url}")
                        return url
            except Exception:
                # Try regex fallback for non-JSON output
                m = re.search(r"https://[a-z0-9\-]+\.ngrok[\-a-z]*\.io", line)
                if m:
                    _tunnel_proc = proc
                    _tunnel_type = "ngrok"
                    return m.group(0)
            if proc.poll() is not None:
                break
        proc.kill()
    except Exception as e:
        print(f"[Sync] ngrok failed: {e}")
    return None


def _lan_fallback() -> str:
    ip = _local_ip()
    url = f"http://{ip}:{API_PORT}"
    global _tunnel_type
    _tunnel_type = "lan"
    print(f"[Sync] LAN fallback: {url}")
    return url


# ── QR Code generation ─────────────────────────────────────────────────────────

def generate_qr_data_url(content: str) -> str:
    """Return a base64 PNG data URL for a QR code. Falls back to text if qrcode not installed."""
    try:
        import qrcode
        import base64
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(content)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/png;base64,{b64}"
    except ImportError:
        return ""


# ── Session PIN ────────────────────────────────────────────────────────────────

def _get_current_pin() -> str:
    """Read PIN from the remote_server hash file, or use default."""
    pin_file = Path(__file__).parent / ".saathi_pin_hash"
    # We can't reverse the hash, so we store the raw PIN alongside for QR generation
    raw_file = Path(__file__).parent / ".saathi_pin_raw"
    if raw_file.exists():
        return raw_file.read_text().strip()
    return "1234"   # default


def set_session_pin(pin: str):
    """Update the session PIN (also updates remote_server PIN)."""
    global _session_pin
    _session_pin = pin
    raw_file = Path(__file__).parent / ".saathi_pin_raw"
    raw_file.write_text(pin)
    # Also update remote_server hash
    try:
        from remote_server import set_pin
        set_pin(pin)
    except Exception:
        pass


def get_session_pin() -> str:
    global _session_pin
    if _session_pin == "1234":
        _session_pin = _get_current_pin()
    return _session_pin


# ── Main API ───────────────────────────────────────────────────────────────────

def start_tunnel() -> str:
    """Try tunnel backends in priority order. Returns public URL."""
    global _public_url
    if _public_url:
        return _public_url

    url = _try_cloudflare() or _try_ngrok() or _lan_fallback()
    _public_url = url.rstrip("/")
    return _public_url


def get_sync_session(settings: dict) -> dict:
    """
    Returns the full sync session payload including QR code.
    Called by /api/sync/session endpoint.
    """
    public_url = _public_url or start_tunnel()
    ws_url = public_url.replace("https://", "wss://").replace("http://", "ws://")
    pin    = get_session_pin()
    name   = settings.get("name", "Saathi")

    mobile_url = f"{public_url}/remote"

    # QR content: mobile URL + auto-connect params embedded in fragment (not server-side)
    # Fragment is client-side only — pin never sent to server in plaintext
    qr_target = (
        f"{mobile_url}"
        f"#ws={ws_url}"
        f"&pin={pin}"
        f"&name={name}"
    )

    qr_data_url = generate_qr_data_url(qr_target)

    return {
        "public_url":  public_url,
        "ws_url":      ws_url,
        "mobile_url":  mobile_url,
        "qr_url":      qr_target,
        "qr_image":    qr_data_url,
        "pin":         pin,
        "tunnel_type": _tunnel_type,
        "lan_ip":      _local_ip(),
    }


def stop_tunnel():
    global _tunnel_proc, _public_url
    if _tunnel_proc:
        try:
            _tunnel_proc.kill()
        except Exception:
            pass
        _tunnel_proc = None
    _public_url = None


def start_tunnel_background():
    """Start tunnel in a background thread so it doesn't block API startup."""
    t = threading.Thread(target=start_tunnel, daemon=True)
    t.start()
