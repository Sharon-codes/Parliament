# Saathi Remote — How to Open on Your Phone

## What's Built

| File | Purpose |
|---|---|
| `saathi-api/remote_server.py` | WebSocket server (port 8765) — runs on your laptop |
| `saathi-remote/index.html` | Phone PWA — open this in your phone's browser |
| `saathi-remote/manifest.json` | Install prompt for home-screen icon |
| `saathi-remote/sw.js` | Service worker for offline caching |

---

## Step 1 — Start the Laptop Server

The remote server starts **automatically** when you run `main.py`. Standalone:

```powershell
cd saathi-api
python remote_server.py
```

Output:
```
  Local:  ws://192.168.1.42:8765
  Default PIN: 1234
```

---

## Step 2 — Find Your Laptop IP

```powershell
ipconfig
```
Look for **IPv4 Address** under your WiFi adapter.

---

## Step 3 — Open on Phone

### Option A — Same WiFi (LAN)

```powershell
cd saathi-remote
python -m http.server 5500
```

Open in phone browser: `http://YOUR_LAPTOP_IP:5500`

Enter WebSocket URL: `ws://YOUR_LAPTOP_IP:8765` + PIN `1234`

### Option B — Remote via ngrok

```powershell
ngrok tcp 8765
```
Use the `tcp://X.tcp.ngrok.io:PORT` URL as `ws://X.tcp.ngrok.io:PORT` in the PWA.

### Option C — Remote via Cloudflare Tunnel

```powershell
cloudflared tunnel --url tcp://localhost:8765
```

---

## Step 4 — Install as Home Screen App

**Android Chrome**: menu -> Add to Home screen

**iOS Safari**: Share -> Add to Home Screen

---

## Commands

| Action | How |
|---|---|
| Run active project | Run Code button |
| Open VS Code | VS Code button |
| List processes | Processes button |
| Focus timer | Pomodoro button |
| Lock screen | Lock button |
| Schedule shutdown | Shutdown button |
| Download file | Download button + URL |
| Change PIN | `set_pin XXXX` in chat |
| Change project | Project button (top bar) |
| Voice command | Mic button in Chat tab |

---

## Code Streaming

Run Code finds the project entry point, runs it with venv Python, and streams stdout/stderr line-by-line to the Terminal tab. If exit code != 0, the error traceback is surfaced automatically.

---

## Security

PIN stored as SHA-256 hash. Default is `1234`. Change immediately: type `set_pin YOURNEWPIN` in the Chat tab.
