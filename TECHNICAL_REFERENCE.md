# Saathi — Technical Reference & Handover Document

> **For:** The next developer, contributor, or judge looking at this codebase.  
> **Written by:** The team that built this.  
> **Date:** April 2026  
> **Repo:** Project Parliament / Sharon-codes/Parliament

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Repository Layout](#2-repository-layout)
3. [Environment Setup — Step by Step](#3-environment-setup)
4. [Module Inventory](#4-module-inventory)
   - [M1: Core Chat Interface](#m1-core-chat-interface)
   - [M2: System Agent](#m2-system-agent)
   - [M3: Web Search & Research Feed](#m3-web-search--research-feed)
   - [M4: Calendar & Event Awareness](#m4-calendar--event-awareness)
   - [M5: Knowledge Base / Database](#m5-knowledge-base--database)
   - [M6: Conversational Memory & Gentle Nudges](#m6-conversational-memory--gentle-nudges)
   - [M7: Phone-to-Laptop Remote Control](#m7-phone-to-laptop-remote-control)
   - [M8: LLM Provider Layer](#m8-llm-provider-layer)
   - [M9: Wabi-Sabi Dashboard UI](#m9-wabi-sabi-dashboard-ui)
   - [M10: Session History](#m10-session-history)
   - [M11: Settings & Personalization](#m11-settings--personalization)
   - [M12: Voice Interface](#m12-voice-interface)
   - [M13: Mobile Sync (QR + Internet Tunnel)](#m13-mobile-sync-qr--internet-tunnel)
5. [What Is Fully Working](#5-what-is-fully-working)
6. [Placeholders & Incomplete Features](#6-placeholders--incomplete-features)
7. [Known Bottlenecks & Gotchas](#7-known-bottlenecks--gotchas)
8. [Testing Guide — Every Module](#8-testing-guide)
9. [Deployment Notes](#9-deployment-notes)
10. [Future Roadmap](#10-future-roadmap)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  PHONE (mobile browser)                                          │
│  saathi-remote/index.html  ←── WebSocket ──→  /ws/sync          │
└─────────────────────────────────────────────────────────────────┘
                                    │
                          Cloudflare Tunnel
                     (wss://xxx.trycloudflare.com)
                                    │
┌─────────────────────────────────────────────────────────────────┐
│  LAPTOP                                                          │
│                                                                  │
│  saathi-web/ (React, Vite, port 5173)                           │
│    └── Dashboard.jsx (main UI, all panels)                       │
│          ↕ HTTP/WS                                               │
│  saathi-api/ (FastAPI + uvicorn, port 8000)                     │
│    ├── main.py           API router, WebSocket endpoints         │
│    ├── llm.py            LLM provider (Gemini/Claude/OpenAI)     │
│    ├── memory.py         Episodic memory + nudge engine          │
│    ├── database.py       SQLite via raw SQL                      │
│    ├── system_agent.py   OS-level commands (clipboard, windows)  │
│    ├── remote_server.py  Phone WebSocket remote control (8765)   │
│    ├── voice_engine.py   STT + TTS + wake word + dictation       │
│    ├── tunnel_manager.py Cloudflare/ngrok auto-tunnel + QR       │
│    └── scrapers.py       arXiv + DuckDuckGo search               │
│                                                                  │
│  saathi-remote/ (static, served at /remote by FastAPI)          │
└─────────────────────────────────────────────────────────────────┘
```

**Data stores:**
- `saathi-api/saathi.db` — SQLite for chat sessions, settings, memory, nudges
- `saathi-api/.saathi_pin_raw` — raw PIN for mobile sync (created on first run)

---

## 2. Repository Layout

```
Project Parliament/
├── saathi-api/                  Python FastAPI backend
│   ├── main.py                  All HTTP + WebSocket endpoints
│   ├── llm.py                   Unified LLM provider layer
│   ├── memory.py                Episodic memory, facts, nudge engine
│   ├── database.py              SQLite wrapper (sessions, settings)
│   ├── system_agent.py          Clipboard, window title, shell exec
│   ├── remote_server.py         WebSocket server port 8765 (phone remote)
│   ├── voice_engine.py          Whisper STT, pyttsx3/ElevenLabs TTS, VAD, wake word
│   ├── tunnel_manager.py        Cloudflare/ngrok tunnel + QR code gen
│   ├── scrapers.py              DuckDuckGo + arXiv scrapers
│   ├── requirements.txt         Python dependencies
│   ├── .env.example             All env vars documented
│   └── .env                     Your actual keys (gitignored)
│
├── saathi-web/                  React 18 + Vite frontend
│   └── src/
│       └── pages/
│           └── Dashboard.jsx    Entire frontend (single large component)
│       └── index.css            All styling (wabi-sabi design system)
│
├── saathi-remote/               Mobile companion PWA (static HTML)
│   ├── index.html               Full mobile app (QR scan, chat, nudges)
│   ├── manifest.json            PWA manifest (installable)
│   └── sw.js                    Service worker (offline shell)
│
├── README.md                    Quick start (original)
└── TECHNICAL_REFERENCE.md       This file
```

---

## 3. Environment Setup

### Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.10+ | Tested on 3.11 |
| Node.js | 18+ | For React frontend |
| Git | any | |
| cloudflared | optional | For internet tunnel (free) |

### Step 1 — Clone & install Python deps

```bash
cd saathi-api
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

> ⚠️ `openai-whisper` pulls in PyTorch (~2GB). First install will take 5–15 minutes depending on connection.

### Step 2 — Configure API keys

```bash
cp .env.example .env
```

Open `.env` and fill in **at least one** of:

```env
# RECOMMENDED — 100% free, no credit card
GEMINI_API_KEY=AIza...   # https://aistudio.google.com/app/apikey
```

Other optional keys (voice features):
```env
ELEVENLABS_API_KEY=...   # High-quality voice (free tier: 10k chars/month)
PICOVOICE_KEY=...        # Accurate wake word (free tier)
NGROK_AUTHTOKEN=...      # If using ngrok instead of cloudflared
```

### Step 3 — Start the API

```bash
cd saathi-api
python main.py
# Server runs on http://localhost:8000
```

Expected startup output:
```
[Saathi LLM] Provider: GEMINI — gemini-2.0-flash
[Saathi] Remote server started on port 8765
[Voice] TTS: pyttsx3 (local)
[Sync] LAN fallback: http://192.168.x.x:8000
INFO:     Application startup complete.
```

### Step 4 — Start the frontend

```bash
cd saathi-web
npm install
npm run dev
# Opens at http://localhost:5173
```

### Step 5 — (Optional) Enable internet tunnel

Install cloudflared once:
```bash
winget install Cloudflare.cloudflared    # Windows
brew install cloudflared                  # Mac
```

Then just restart `main.py` — the tunnel auto-starts on boot.

---

## 4. Module Inventory

---

### M1: Core Chat Interface

**Files:** `saathi-web/src/pages/Dashboard.jsx`, `saathi-api/main.py` (`/api/chat`)

**What it does:**  
Three-panel layout (sidebar / chat / right panel) with a wabi-sabi Japanese aesthetic (rice-paper palette, Cormorant Garamond serif). Chat messages render markdown+code blocks inline. Three modes: Chat, Agent, Search.

**Status:** ✅ Fully working

**How it works:**
- `POST /api/chat` receives `{message, mode, session_id}`
- In `agent` mode: calls `agentic_execute()` to run OS commands
- In `search` mode: calls `search_web()` before LLM
- System prompt includes user name, language, memory context, nudges

**Placeholders:**
- Agent mode has a fixed list of commands; complex chained tasks aren't supported yet
- No streaming responses (full reply arrives at once — noticeable on long answers)

**Bottleneck:** Response latency = Gemini API round-trip (~1–2s). No streaming implemented.

---

### M2: System Agent

**Files:** `saathi-api/system_agent.py`, `saathi-api/remote_server.py`

**What it does:**  
Saathi can read the active window title, read clipboard, and execute shell commands. The `agentic_execute()` function parses natural language and maps to OS primitives.

**Status:** ✅ Partially working

**Works:**
- `get_clipboard()` — reads current clipboard
- `get_active_window_context()` — window title via `pygetwindow`
- Basic file open, browser URL launch, notepad commands
- Subprocess execution with output capture

**Placeholders / Won't Work:**
- `pygetwindow` may fail on some Windows configurations — it silently returns `None`
- No sandboxing: Saathi can run arbitrary shell commands. **Do not expose port 8000 publicly without auth.**
- Complex intent parsing for agent mode is keyword-based regex, not true NLU

---

### M3: Web Search & Research Feed

**Files:** `saathi-api/scrapers.py`, `main.py` (`/api/research`, search in `/api/chat`)

**What it does:**  
- DuckDuckGo HTML scraper for web search (no API key needed)
- arXiv RSS feed scraper for recent papers in user's interest area
- Research feed displayed in right panel of dashboard

**Status:** ✅ Working (fragile — depends on DuckDuckGo HTML structure)

**Bottleneck / Risk:**  
DuckDuckGo HTML scraping breaks if they change their markup. ~20% chance of silent failure. When it fails, search mode falls back to LLM-only response without warning the user.

**Placeholder:**  
arXiv topic is hardcoded to `"machine learning"` unless the user changes it in Settings → Interests. The mapping from free-text interest to arXiv category is not implemented; it uses the raw string as a search query.

---

### M4: Calendar & Event Awareness

**Files:** `main.py` (`/api/calendar`), `database.py`

**What it does:**  
Returns events stored in SQLite within a 7-day window. Events are manually added; there's no calendar sync (no Google Calendar, no iCal).

**Status:** ⚠️ Scaffold only

**What actually works:**
- `/api/calendar` endpoint returns rows from `events` table
- Events panel renders in right sidebar with date/time
- Memory module can surface events in LLM context

**What doesn't work / is missing:**
- **No way to add events from the UI** — must insert directly into SQLite or add an endpoint
- **No Google Calendar / iCal integration** — was planned, not built
- No reminder/alarm functionality

**How to add events manually:**
```bash
cd saathi-api
python -c "
import sqlite3, datetime
db = sqlite3.connect('saathi.db')
db.execute(\"INSERT INTO events (title, start_time, end_time) VALUES (?,?,?)\",
           ('ICCAIML deadline', '2026-05-01 23:59', '2026-05-01 23:59'))
db.commit()
"
```

---

### M5: Knowledge Base / Database

**Files:** `saathi-api/database.py`

**What it does:**  
SQLite database with tables for: `settings`, `chat_sessions`, `chat_messages`, `events`.

**Status:** ✅ Working

**Schema:**
```sql
settings     (key TEXT PK, value TEXT)
chat_sessions (session_id TEXT PK, title TEXT, created_at, updated_at)
chat_messages (id INT PK, session_id TEXT, role TEXT, content TEXT, created_at)
events        (id INT PK, title TEXT, start_time TEXT, end_time TEXT, created_at)
```

**Bottleneck:**  
No migrations system. If you add columns, you must `ALTER TABLE` manually or delete `saathi.db` and let it recreate (losing all data).

---

### M6: Conversational Memory & Gentle Nudges

**Files:** `saathi-api/memory.py`, `main.py` (nudge endpoints)

**What it does:**  
This is Saathi's "soul" — the feature that makes it feel like a real companion rather than a chat window.

**Memory system:**
- Every user message stored as an "episode" with timestamp + topic classification
- Named facts stored separately (`store_named_fact("ICCAIML deadline is May 1")`)
- `get_relevant_memory_context(query)` uses keyword overlap to retrieve related episodes (no vector embeddings — pure keyword matching)
- Memory search: `POST /api/memory/search`
- Episodes condense over time (but the condense call is manual — no background scheduler)

**Nudge engine:**
- Time-triggered nudges: if deadline-related word mentioned + enough time passes without progress check
- Worry nudges: if words like "worried", "stressed", "overwhelmed" appear
- Progress nudges: if topic silently drops for 7+ days
- Nudges are stored in `nudges` table, surfaced in the chat system prompt and right panel

**Status:** ✅ Core working; advanced features partial

**Works:**
- Episode storage and retrieval
- Named fact CRUD
- Basic nudge creation (worry + time-based)
- Nudge acknowledgment UI
- Memory search UI with display

**Placeholders / Missing:**
- **No vector embeddings.** Memory retrieval is keyword overlap, not semantic similarity. "Deadline stress" won't retrieve "feeling anxious about proposal due date."
- `condense_old_episodes()` is never called automatically — must be triggered manually via `/api/memory/condense`
- Topic classification is a simple keyword list, not ML-based
- Memory panel in UI only shows latest 6 episodes and 5 facts — no pagination

**How to manually trigger condensation:**
```bash
curl -X POST http://localhost:8000/api/memory/condense
```

---

### M7: Phone-to-Laptop Remote Control

**Files:** `saathi-api/remote_server.py`

**What it does:**  
A separate WebSocket server on port 8765 that lets a phone control the laptop. Authenticated with SHA-256 PIN hash.

**Status:** ✅ Working (LAN only without tunnel)

**Supported commands (natural language → action):**
| Command phrase | Action |
|---|---|
| "run", "execute" | Runs active project script via subprocess |
| "open", "launch" | Opens file/URL with OS shell |
| "clipboard" | Returns clipboard contents |
| "screenshot" | Takes screenshot (requires Pillow) |
| "volume up/down/mute" | System volume via nircmd |
| "pomodoro" | Starts 25-min timer in background thread |
| "list files" | Lists current directory |
| "system info" | CPU/RAM/disk via psutil |
| "kill process" | Terminates named process |
| "what is", "search" | Routes to LLM |

**PIN default:** `1234` (change in `.env` or via Mobile Sync panel)

**Bottleneck:**
- Port 8765 is a separate server — not tunneled through Cloudflare by default. For remote phone control (not on same WiFi), you need to either also tunnel port 8765 or route commands through the `/ws/sync` endpoint (port 8000) instead.
- Screenshot requires `Pillow` — not in default requirements
- `nircmd` for volume control is Windows-only freeware (not installed by pip)

**Screenshot install:**
```bash
pip install Pillow
```

---

### M8: LLM Provider Layer

**Files:** `saathi-api/llm.py`

**What it does:**  
Single `llm_chat(system, user, context)` coroutine that automatically routes to the best available provider based on `.env` API keys.

**Status:** ✅ Fully working

**Provider priority:**
1. **Google Gemini** (if `GEMINI_API_KEY` set) — `gemini-2.0-flash` — FREE tier, recommended
2. **Anthropic Claude** (if `ANTHROPIC_API_KEY` set) — `claude-3-5-haiku`
3. **OpenAI** (if `OPENAI_API_KEY` set) — `gpt-4o-mini`
4. **Offline fallback** — rule-based, canned responses for common queries

**`/api/llm-status` response:**
```json
{ "provider": "gemini", "model": "gemini-2.0-flash", "ready": true }
```

**Rate limits (Gemini free tier):**
- 15 requests/minute
- 1,000,000 tokens/minute  
- 1,500 requests/day

For heavy demo use (many rapid-fire messages), Gemini free tier rate limits may kick in (HTTP 429). The code does not automatically retry or switch provider on rate limit — it just returns an error string.

---

### M9: Wabi-Sabi Dashboard UI

**Files:** `saathi-web/src/pages/Dashboard.jsx`, `saathi-web/src/index.css`

**What it does:**  
Complete React dashboard with Japanese wabi-sabi aesthetic — rice-paper palette (#F5F1EA), Cormorant Garamond serif, DM Sans sans-serif, muted sage green accent. Three-panel layout: left sidebar / center chat / right panel.

**Status:** ✅ Working

**Components (all inline in Dashboard.jsx):**
- `Msg` — inline markdown renderer (code blocks, inline code)
- `NudgeCard` — animated nudge toast with dismiss/suppress
- `FactEntry` — named fact chip
- `MemoryEntry` — episodic memory entry with topic color dot
- `RPSection` — collapsible right-panel section
- `Waveform` — animated audio level bars (Module 12)
- `VoiceOverlay` — voice mode panel (Module 12)

**Placeholder:**
- Dashboard.jsx is **720+ lines** — it's monolithic. Should be split into separate component files for maintainability.
- Dark mode uses CSS class toggle (`document.documentElement.classList.toggle('dark')`) — not a React context. Means dark mode resets on hard refresh unless persisted.
- No mobile-responsive layout for the main dashboard (it's laptop-only; phone users use saathi-remote)

---

### M10: Session History

**Files:** `main.py` (`/api/sessions`, `/api/sessions/{id}`), `database.py`

**What it does:**  
Chat sessions are created with a UUID, stored in SQLite, and can be reloaded from the left sidebar History section.

**Status:** ✅ Working

**Session title:** auto-generated from first message (first 40 chars). No smart summarization.

**Placeholder:** Loading an old session restores messages to the UI but does NOT restore the conversation context to the LLM — old messages aren't re-injected as context. The LLM always starts fresh. This means continuing an old session feels disconnected.

---

### M11: Settings & Personalization

**Files:** `main.py` (`/api/settings`), `database.py`, Dashboard settings modal

**Settings stored:**
| Key | Default | Effect |
|-----|---------|--------|
| `name` | "Guest" | Injected into all LLM system prompts |
| `interests` | "machine learning" | Used for arXiv feed search |
| `language` | "English" | LLM responds in this language |
| `theme` | "light" | light/dark mode |
| `nudge_sensitivity` | "balanced" | Controls nudge trigger frequency: low/balanced/high |

**Status:** ✅ Working

---

### M12: Voice Interface

**Files:** `saathi-api/voice_engine.py`, `main.py` (voice endpoints), `Dashboard.jsx` (VoiceOverlay)

**What it does:**  
Complete voice stack — wake word detection, speech-to-text, text-to-speech, dictation mode, ambient mode.

**Status:** ⚠️ Installed but needs mic to be tested

**Component chain:**
```
Microphone → VAD (webrtcvad) → Whisper STT → LLM → pyttsx3/ElevenLabs TTS
                    ↑
          Wake word detection
          (Whisper text-match or Porcupine)
```

**Voice modes:**
| Mode | Behaviour |
|------|-----------|
| `off` | Disabled |
| `push_to_talk` | Browser holds mic while button pressed |
| `wake_word` | Always listening for "Hey Saathi" |
| `ambient` | Passive listening; only interrupts for urgent nudges |
| `dictation` | Continuous transcription → fills chat input |

**STT:** OpenAI Whisper `tiny` model (local, ~150MB, downloads on first use)

**TTS options:**
- `pyttsx3` — local, robotic but always-available
- ElevenLabs — cloud, natural voice, set `ELEVENLABS_API_KEY` in `.env`

**Wake word options:**
- Default: Whisper text-match — scans 3-second chunks for the phrase "hey saathi" or "saathi"
- Better: Porcupine — set `PICOVOICE_KEY` in `.env` (free at picovoice.ai)

**WebSocket:** `ws://localhost:8000/ws/voice` — browser connects for real-time events

**Bottlenecks:**
- `sounddevice` on Windows sometimes requires VC++ redistributables — if mic fails to open, install [VC++ 2019](https://aka.ms/vs/17/release/vc_redist.x64.exe)
- Whisper `tiny` model has ~80% accuracy on clear English speech. Use `base` model (`WHISPER_MODEL=base` in `.env`) for better accuracy at the cost of ~2x latency
- Wake word with Whisper fallback uses CPU for constant transcription — can cause ~30% CPU load on older machines. Porcupine is ~1% CPU.
- `webrtcvad` may fail to build on some systems — if it does, VAD is silently disabled and recording uses fixed 3s chunks

**Frontend voice (push-to-talk in browser):** Uses Web Speech API as a convenience layer (browser API, no mic streaming to backend). Set voice mode to `push_to_talk` in the VoiceOverlay panel.

**Placeholders:**
- Ambient mode "only interrupt for urgent nudges" is partially implemented — the distinction between urgent and non-urgent responses needs to be wired to the nudge system
- System-level voice (wake word) runs as a background thread but browser must also have the VoiceOverlay open to receive transcript events real-time. Voice-only (no browser) does work for full conversations; the browser just won't show the transcript.

---

### M13: Mobile Sync (QR + Internet Tunnel)

**Files:** `saathi-api/tunnel_manager.py`, `main.py` (sync endpoints), `saathi-remote/index.html`

**What it does:**  
Connects your phone to your laptop over the internet (not just same WiFi) using a Cloudflare Quick Tunnel. Phone scans a QR code → loads the mobile site → auto-connects via WebSocket → full Saathi chat from phone.

**Status:** ✅ Working (needs cloudflared for internet; LAN works immediately)

**Connection flow:**
1. `main.py` starts → calls `start_tunnel_background()` → tries `cloudflared tunnel --url http://localhost:8000`
2. Gets a URL like `https://abc-def-123.trycloudflare.com`
3. `GET /api/sync/session` generates QR code encoding `{url}/remote#ws={wsUrl}&pin={pin}&name={name}`
4. Dashboard "Sync Mobile" button shows QR modal
5. Phone camera scans → loads `https://abc-def-123.trycloudflare.com/remote`
6. Page reads URL fragment → auto-connects to `/ws/sync`
7. Backend authenticates via PIN → routes `/ws/sync chat messages to LLM → responses back

**Mobile site features:**
- QR scanner (`html5-qrcode` library from CDN)
- Manual fallback: enter URL + PIN digits
- Chat with full LLM access
- Quick action buttons (8 preset queries)
- Nudges tab (shows pending nudges, allows acknowledgment)
- Profile tab with disconnect + PIN change
- Auto-reconnects on disconnect (5s backoff)
- Installable as PWA (works on iOS and Android)

**Endpoints:**
```
GET  /api/sync/session    → {qr_image, qr_url, pin, public_url, tunnel_type}
GET  /api/sync/status     → {tunnel_active, tunnel_type, public_url}
POST /api/sync/pin        → {pin: "1234"}  — change PIN
WS   /ws/sync             → authenticated WebSocket (auth → chat → nudges)
GET  /remote              → serves saathi-remote/index.html
```

**Tunnel priority (auto-detected):**
```
cloudflared → ngrok → LAN IP
```

**Bottlenecks / Issues:**
- `trycloudflare.com` URLs expire when the process restarts — new QR needed each session
- Without `cloudflared` installed, only LAN works — phone must be on same WiFi
- QR code embedded PIN is in plain text in URL fragment — safe for local use but not production-grade
- `qrcode` library requires `Pillow` for PNG generation
- The `/ws/sync` endpoint does one async LLM call per message but holds the WebSocket open — concurrent users sharing the same laptop API could queue

---

## 5. What Is Fully Working

| Feature | Works? | Notes |
|---------|--------|-------|
| Chat with LLM (Gemini) | ✅ | Fast, reliable |
| Session history | ✅ | Create/reload sessions |
| Named fact storage | ✅ | "Remember that…" |
| Memory search | ✅ | Keyword-based |
| Time nudges | ✅ | Deadline words trigger |
| Worry nudges | ✅ | "stressed" etc. |
| Nudge acknowledge | ✅ | From UI and mobile |
| arXiv research feed | ✅ | Updates per interests |
| Web search mode | ✅ | DuckDuckGo scraper |
| Dark mode | ✅ | Toggle in topbar |
| Settings persistence | ✅ | SQLite backed |
| Remote WebSocket (port 8765) | ✅ | PIN auth, 16 commands |
| Pomodoro timer | ✅ | Via remote/chat |
| Voice TTS (pyttsx3) | ✅ | Local, no key needed |
| Voice STT (Whisper) | ✅ | Local, first load ~30s |
| Mobile site QR scan | ✅ | Opens and connects |
| Mobile chat | ✅ | Full LLM responses |
| Mobile nudge display | ✅ | With acknowledge |
| Mobile quick actions | ✅ | 8 preset queries |
| LAN tunnel fallback | ✅ | Always works |
| Cloudflare tunnel | ✅ | If cloudflared installed |
| PWA install | ✅ | Add to home screen |
| LLM offline fallback | ✅ | Rule-based responses |

---

## 6. Placeholders & Incomplete Features

| Feature | Status | What's missing |
|---------|--------|---------------|
| Calendar sync (Google/iCal) | ❌ Scaffold | API integration not built |
| Add calendar events from UI | ❌ Missing | No form, must use SQL |
| Vector memory search | ❌ Not implemented | Uses keyword overlap |
| Memory auto-condensation | ❌ Manual only | No background scheduler |
| Session context continuity | ❌ Missing | Old sessions lose LLM context |
| LLM streaming | ❌ Not implemented | Full response at once |
| Agent complex chaining | ❌ Basic only | Keyword regex, not NLU |
| Porcupine wake word | ⚠️ Optional | Needs `PICOVOICE_KEY` |
| ElevenLabs TTS | ⚠️ Optional | Needs `ELEVENLABS_API_KEY` |
| Ambient mode fine-grained | ⚠️ Partial | Urgent-only not wired to nudge type |
| Screenshot in remote | ⚠️ Needs Pillow | Not in default requirements |
| Volume control | ⚠️ Windows only | Needs nircmd |
| nircmd volume control | ⚠️ Manual install | Not pip-installable |
| Rate limit retry | ❌ Missing | Gemini 429 = error string |
| Dashboard mobile layout | ❌ Not responsive | Laptop display only |
| Dashboard component split | ❌ Monolithic | 700+ line single component |
| Auth on main API (port 8000) | ❌ None | Do not expose publicly |
| Dark mode persistence | ⚠️ Session only | Resets on hard refresh |

---

## 7. Known Bottlenecks & Gotchas

### 1. No Authentication on Main API
Port 8000 has zero authentication. Anyone who can reach it can read your memory, impersonate you to the LLM, and run shell commands. **Do not run this on a public network without adding auth middleware.**

### 2. SQLite Concurrency
Multiple concurrent WebSocket connections (e.g., browser + mobile + voice) all hit SQLite. SQLite handles this fine in WAL mode but can timeout under very heavy load. The code does not set `PRAGMA journal_mode=WAL`.

### 3. Whisper First Load
First time Whisper is invoked, it downloads the model (~150MB for `tiny`, ~290MB for `base`). This takes 30–120 seconds on a slow connection. The server will appear frozen during this time — it's not crashed.

### 4. Cloudflare Tunnel URL Expiry
`trycloudflare.com` gives a new random URL every time `cloudflared` starts. If you restart `main.py`, you get a new URL and must re-scan the QR code. This is by design (ephemeral tunnels). Use ngrok with a static domain if you need a persistent URL.

### 5. DuckDuckGo Scraper Fragility
The web search scraper parses DuckDuckGo HTML. If DuckDuckGo's HTML structure changes, it silently fails. Check `scrapers.py` if search results are empty.

### 6. pygetwindow on Windows
`pygetwindow` can crash on Windows 11 if run as an unprivileged user without UI access. The `get_active_window_context()` function wraps this in a try/except and returns empty string silently.

### 7. Voice CPU load (Whisper wake word)
Whisper-based wake word detection transcribes 3-second audio chunks continuously. On a laptop without GPU, this uses ~25–40% CPU. For production use, switch to Porcupine (set `PICOVOICE_KEY` in `.env`).

### 8. Port 8765 Not Tunneled
The remote server (Module 7) runs on port 8765 separately from the main API on port 8000. Cloudflare/ngrok only tunnels port 8000. Remote control from outside LAN via port 8765 won't work unless you also tunnel 8765. **Workaround:** route all remote commands through `/ws/sync` on port 8000 instead.

---

## 8. Testing Guide

### Prerequisites for testing
```bash
# Make sure API is running:
cd saathi-api && python main.py

# Make sure frontend is running:
cd saathi-web && npm run dev
# Open http://localhost:5173
```

---

### Test M1: Core Chat

1. Open `http://localhost:5173`
2. Type any message, press Enter
3. ✅ Expect: typesetting animation, AI reply within 2–3s
4. Type: `"What's 2+2?"` → expect direct answer (Gemini)
5. Check LLM status badge in bottom dock — should show `GEMINI · gemini-2.0-flash`

---

### Test M2: Agent Mode

1. Switch mode pill to **Agent**
2. Type: `"what's in my clipboard"`
3. ✅ Expect: clipboard text read and returned
4. Type: `"open notepad"`
5. ✅ Expect: Notepad opens on your desktop

---

### Test M3: Search Mode

1. Switch mode pill to **Search**
2. Type: `"what is the latest news about GPT-5"`
3. ✅ Expect: Response includes scraped context (may mention DDG results)
4. Check **Insight Feed** in right panel for arXiv papers

---

### Test M6: Memory & Nudges

```bash
# Directly test memory API
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Remember that my ICCAIML paper is due May 15", "mode": "chat"}'
```

1. Type: `"Remember that my dissertation defence is June 5"`
2. ✅ Expect: Saathi confirms the fact
3. Click **Memory** in sidebar → see the episode and named fact
4. Type: `"I'm really stressed about the defence date"`
5. ✅ Expect: A worry nudge appears in the right panel within a few seconds
6. Click ✓ on the nudge to acknowledge

---

### Test M7: Remote Control (WebSocket 8765)

Using a WebSocket client (e.g., browser dev tools, Postman, or wscat):
```bash
# Install wscat if needed:
npm install -g wscat

wscat -c ws://localhost:8765
# After connecting, send:
{"type": "auth", "pin_hash": "<sha256 of '1234'>"}
# Then:
{"command": "system info"}
```

SHA-256 of `1234`:
```
03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4
```

✅ Expect: CPU/RAM/disk info returned

---

### Test M8: LLM Status

```bash
curl http://localhost:8000/api/llm-status
```
✅ Expect: `{"provider":"gemini","model":"gemini-2.0-flash","ready":true}`

**Test offline fallback:**
1. Temporarily remove `GEMINI_API_KEY` from `.env`
2. Restart `main.py`
3. Send a chat message
4. ✅ Expect: rule-based response mentioning offline mode

---

### Test M12: Voice Interface

1. Click the **microphone icon** in the topbar (next to the volume icon)
2. Voice Overlay panel slides up
3. Click **Wake Word** mode button
4. Say: **"Hey Saathi, what time is it?"**
5. ✅ Expect:
   - Recording indicator (red dot) appears
   - After ~2s silence: transcript appears in overlay
   - Saathi speaks the response via TTS
   - Transcript also added as a bubble in chat

**Push-to-talk test:**
1. Select **Push** mode in Voice Overlay
2. In the Voice Overlay, the waveform shows as soon as you speak (uses Web Speech API in browser)
3. ✅ Expect: transcript captured and sent as message

**Dictation test:**
1. Select **Dictation** mode
2. Start speaking continuously
3. ✅ Expect: text accumulates in "Dictation buffer" section
4. Click **Done** → text fills chat input
5. Press Enter to send

**If voice doesn't work:**
```bash
python -c "import sounddevice; print(sounddevice.query_devices())"
# Should list your microphone
```

---

### Test M13: Mobile Sync

#### LAN test (always works):
1. Open Dashboard → sidebar → **Sync Mobile**
2. ✅ Expect: QR modal opens, shows QR code with LAN IP
3. On your phone (same WiFi): scan QR with camera
4. ✅ Expect: mobile site opens, auto-connects, PIN auto-filled
5. Type a message in mobile chat
6. ✅ Expect: reply from Saathi within 2–3s

#### Internet test (needs cloudflared):
```bash
winget install Cloudflare.cloudflared
# Restart main.py — you'll see:
# [Sync] Cloudflare tunnel: https://xxx.trycloudflare.com
```
1. Open Sync QR modal → QR now shows `trycloudflare.com` URL
2. Scan from phone **on any network** (4G, different WiFi)
3. ✅ Expect: same connection, works globally

**Manual connection test (no QR scanner):**
1. In mobile site → click "Or enter details manually"
2. Enter: `http://192.168.x.x:8000` + PIN `1234`
3. ✅ Expect: connects and shows auth OK

---

### Test API directly

```bash
# Full set of API endpoints:
curl http://localhost:8000/api/settings
curl http://localhost:8000/api/sessions
curl http://localhost:8000/api/memory/episodes
curl http://localhost:8000/api/memory/facts
curl http://localhost:8000/api/nudges
curl http://localhost:8000/api/llm-status
curl http://localhost:8000/api/voice/status
curl http://localhost:8000/api/sync/status
curl http://localhost:8000/api/sync/session    # generates QR

# FastAPI auto-docs (interactive):
open http://localhost:8000/docs
```

---

## 9. Deployment Notes

### Running the backend as a persistent service

**Windows Task Scheduler:**
```
Action: Start a program
Program: C:\...\saathi-api\venv\Scripts\python.exe
Arguments: C:\...\saathi-api\main.py
Start in: C:\...\saathi-api\
```

**Linux systemd:**
```ini
[Service]
WorkingDirectory=/path/to/saathi-api
ExecStart=/path/to/venv/bin/python main.py
Restart=always
```

### Making the frontend accessible over the tunnel

The FastAPI server serves `saathi-remote/` at `/remote`. The main dashboard (React) runs on port 5173 separately.

To serve the React app through the API server too (so it's accessible at the tunnel URL):
```bash
cd saathi-web
npm run build
# Then copy dist/ contents to a new /static folder and mount in FastAPI
```

This is not set up yet — a future improvement.

### ngrok persistent URL

```env
NGROK_AUTHTOKEN=your_token
# Get a static domain at: https://dashboard.ngrok.com/cloud-edge/domains
```

Then add `--domain=your-name.ngrok-free.app` to the ngrok command in `tunnel_manager.py`.

---

## 10. Future Roadmap

These are in rough priority order for what would be most impactful to implement next:

1. **Google Calendar integration** — OAuth flow → read real events → time-aware nudges
2. **Vector memory search** — replace keyword overlap with sentence-transformers embeddings → semantic retrieval
3. **LLM streaming** — stream tokens to frontend using FastAPI `StreamingResponse` → eliminates perceived latency
4. **Auth middleware** — FastAPI `Depends` with Bearer token or session cookie on all endpoints
5. **Background scheduler** — APScheduler for: memory condensation, nudge checks, arXiv refresh (runs even when chat is idle)
6. **Dashboard component split** — break `Dashboard.jsx` into `ChatPanel`, `MemoryPanel`, `VoiceOverlay`, `SyncModal`, etc.
7. **Persistent ngrok / custom domain** — so mobile doesn't need re-scan after restart
8. **Progress nudge wiring** — currently `maybe_create_nudge()` is called but progress nudges need topic tracking across sessions
9. **Resume session with context** — inject last N messages as history when loading old session
10. **Dark mode persistence** — store preference in localStorage, apply before React hydrates

---

## Quick Reference: All Environment Variables

```env
# ── LLM (pick one) ──
GEMINI_API_KEY=          # https://aistudio.google.com/app/apikey  (FREE)
ANTHROPIC_API_KEY=       # https://console.anthropic.com/
OPENAI_API_KEY=          # https://platform.openai.com/api-keys
GEMINI_MODEL=gemini-2.0-flash     # optional override
ANTHROPIC_MODEL=claude-3-5-haiku-20241022
OPENAI_MODEL=gpt-4o-mini

# ── Voice ──
WHISPER_MODEL=tiny       # tiny | base | small | medium
VOICE_WAKE_WORDS=hey saathi,saathi
ELEVENLABS_API_KEY=      # https://elevenlabs.io/ (10k chars/month free)
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM   # Rachel voice ID
PICOVOICE_KEY=           # https://console.picovoice.ai/ (free tier)

# ── Mobile Sync ──
NGROK_AUTHTOKEN=         # optional; cloudflared is preferred (no token needed)
API_PORT=8000            # override if 8000 is taken
```

---

*This document was auto-generated with assistance from Antigravity (Google DeepMind) during the Project Parliament hackathon sprint, April 2026.*
