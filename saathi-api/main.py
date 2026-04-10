import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path
from llm import llm_chat, get_provider_info

from scrapers import search_web, get_latest_arxiv
from database import init_db, get_settings, update_settings, get_chat_sessions, create_chat_session, get_chat_messages, add_chat_message
from system_agent import get_active_window_context, get_clipboard, agentic_execute
from memory import (
    init_memory_db,
    store_episode,
    get_episodes,
    search_episodes,
    condense_old_episodes,
    get_all_facts,
    store_named_fact,
    delete_named_fact,
    get_pending_nudges,
    acknowledge_nudge,
    suppress_nudge_topic,
    get_all_nudges_history,
    maybe_create_nudge,
    maybe_create_worry_nudge,
    get_relevant_memory_context,
    parse_memory_command,
)
from remote_server import start_remote_server
from voice_engine import init_voice_engine, get_voice_engine, VoiceMode
from tunnel_manager import start_tunnel_background, get_sync_session, set_session_pin, get_session_pin

init_db()
init_memory_db()

# Start WebSocket remote-control server in background
try:
    start_remote_server()
except Exception as _e:
    print(f"[Saathi] Remote server failed to start: {_e}")

# ── Voice engine async command handler ─────────────────────────────────────────
async def _voice_command_handler(text: str, mode: str):
    """Called by voice engine when a spoken command is ready."""
    settings = get_settings()
    user_name = settings.get("name", "Friend")
    language  = settings.get("language", "English")
    mem_ctx   = get_relevant_memory_context(text)
    system_prompt = (
        f"You are Saathi, an elegant personal AI companion. The user's name is {user_name}. "
        f"Answer in {language}. Keep voice responses concise (1–3 sentences). "
        f"The user spoke this via voice, so reply naturally as if speaking."
    )
    reply = await llm_chat(system_prompt, text, mem_ctx)
    store_episode(text)
    store_episode(f"Saathi replied: {reply[:200]}", source="ai")
    engine = get_voice_engine()
    if engine:
        engine.speak(reply)

def _voice_command_handler_sync(text: str, mode: str):
    """Thread-safe wrapper — schedules the async handler on the event loop."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(_voice_command_handler(text, mode), loop)
    except Exception as e:
        print(f"[Voice] Command handler error: {e}")

# Initialise voice engine
try:
    init_voice_engine(on_command=_voice_command_handler_sync)
except Exception as _ve:
    print(f"[Saathi] Voice engine init failed: {_ve}")

# Start Cloudflare/ngrok tunnel in background (Module 13 — Mobile Sync)
try:
    start_tunnel_background()
except Exception as _te:
    print(f"[Saathi] Tunnel start failed: {_te}")

app = FastAPI(title="Saathi API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# LLM provider is configured in llm.py via .env (Gemini / Anthropic / OpenAI)

# Serve the mobile companion site at /remote
_remote_dir = Path(__file__).parent.parent / "saathi-remote"
if _remote_dir.exists():
    app.mount("/remote", StaticFiles(directory=str(_remote_dir), html=True), name="remote")

# ── Request Models ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    mode: str = "chat"
    session_id: str = None

class SettingsRequest(BaseModel):
    name: str = None
    role: str = None
    interests: str = None
    language: str = None
    theme: str = None
    proactive_level: str = None
    nudge_sensitivity: str = None

class FactRequest(BaseModel):
    content: str
    key_phrase: str = ""

class NudgeAckRequest(BaseModel):
    nudge_id: int

class SuppressRequest(BaseModel):
    topic: str

class DeleteMemoryRequest(BaseModel):
    query: str

# ── Settings ──────────────────────────────────────────────────────────────────

@app.get("/api/settings")
def get_user_settings():
    return get_settings()

@app.post("/api/settings")
def save_user_settings(req: SettingsRequest):
    return update_settings(req.dict(exclude_none=True))

# ── Sessions ─────────────────────────────────────────────────────────────────

@app.get("/api/sessions")
def fetch_sessions():
    return {"sessions": get_chat_sessions()}

@app.get("/api/sessions/{session_id}")
def fetch_session_messages(session_id: str):
    return {"messages": get_chat_messages(session_id)}

@app.post("/api/sessions")
def create_session():
    return {"session_id": create_chat_session()}

# ── Chat (with memory integration) ───────────────────────────────────────────

@app.post("/api/chat")
async def chat_with_saathi(req: ChatRequest):
    settings = get_settings()
    user_name = settings.get("name", "Friend")
    language = settings.get("language", "English")
    nudge_sensitivity = settings.get("nudge_sensitivity", "balanced")

    session_id = req.session_id
    if not session_id:
        session_id = create_chat_session()

    add_chat_message(session_id, "user", req.message)

    # ── Check memory commands first ────────────────────────────────────────
    mem_cmd = parse_memory_command(req.message)
    if mem_cmd.handled:
        add_chat_message(session_id, "ai", mem_cmd.reply)
        return {"reply": mem_cmd.reply, "session_id": session_id}

    # ── Store this message as an episodic memory ──────────────────────────
    store_episode(req.message)

    # ── Nudge scheduling ──────────────────────────────────────────────────
    maybe_create_nudge(req.message)
    maybe_create_worry_nudge(req.message)

    # ── Build context for LLM ─────────────────────────────────────────────
    context = ""
    past_messages = get_chat_messages(session_id)
    if past_messages:
        memory_str = "\n".join([
            f"{msg['role'].capitalize()}: {msg['text']}"
            for msg in past_messages[-6:]
        ])
        context += f"-- Session history:\n{memory_str}\n--\n"

    # Inject long-term memory context
    mem_context = get_relevant_memory_context(req.message)
    if mem_context:
        context += f"\n-- Long-term memory:\n{mem_context}\n--\n"

    # Inject active nudges as context hints
    due_nudges = get_pending_nudges(nudge_sensitivity)
    if due_nudges:
        nudge_lines = "\n".join(f"• {n['message']}" for n in due_nudges[:2])
        context += f"\n-- Gentle reminders you may surface if relevant:\n{nudge_lines}\n--\n"

    if req.mode == "search":
        try:
            search_results = search_web(req.message)
            context += f"Here are live internet results to answer the user: {search_results}\n"
        except Exception as e:
            context += f"[Live search failed: {e}]\n"

    if req.mode == "agent":
        try:
            active_app = get_active_window_context()
            clipboard_data = get_clipboard()
            context += f"SYSTEM CONTEXT: The user is currently looking at window '{active_app}'. Current clipboard text: '{clipboard_data[:200]}...'\n"
        except:
            pass

    system_prompt = (
        f"You are Saathi, an elegant, serene personal AI companion with conversational memory. "
        f"The user's name is {user_name}. You must answer in {language}. "
        f"You remember past conversations and gently surface relevant memories when useful. "
        f"If the user expresses worry or stress, offer a calm, supportive response and ask if they'd like help making a plan. "
        f"Be warm, insightful, and non-intrusive. Never repeat yourself unnecessarily."
    )

    # ── Call LLM (Gemini / Claude / OpenAI — configured in .env) ───────────
    ai_reply = await llm_chat(system_prompt, req.message, context)

    # Store AI reply as an episode
    store_episode(f"Saathi responded: {ai_reply[:200]}", source="ai")

    sys_action_result = agentic_execute(req.message, llm_response=ai_reply, mode=req.mode)
    if sys_action_result and "no immediate desktop tools" not in sys_action_result:
        ai_reply += f"\n\n*(System Note: {sys_action_result})*"

    add_chat_message(session_id, "ai", ai_reply)
    return {"reply": ai_reply, "session_id": session_id}

# ── Research & Calendar ───────────────────────────────────────────────────────

@app.get("/api/research")
def get_daily_briefing():
    settings = get_settings()
    user_interests = settings.get("interests", "machine learning robotics")
    try:
        papers = get_latest_arxiv(user_interests, max_results=5)
        return {"papers": papers, "topic": user_interests}
    except Exception as e:
        return {"papers": [], "error": str(e), "topic": user_interests}

@app.get("/api/calendar")
def get_real_calendar():
    now = datetime.now()
    events = [
        {"id": "1", "title": "Review latest research in your field", "time": (now + timedelta(minutes=15)).strftime("%I:%M %p"), "type": "deadline"},
        {"id": "2", "title": "Hackathon Check-in Sync", "time": (now + timedelta(hours=2)).strftime("%I:%M %p"), "type": "meeting"}
    ]
    return {"events": events}

# ── Memory API ────────────────────────────────────────────────────────────────

@app.get("/api/memory/episodes")
def api_get_episodes(topic: str = None, days: int = 7):
    return {"episodes": get_episodes(topic=topic, since_days=days, limit=30)}

@app.get("/api/memory/search")
def api_search_memory(q: str):
    episodes = search_episodes(q, limit=8)
    facts = get_all_facts()
    q_lower = q.lower()
    relevant_facts = [f for f in facts if q_lower in f["content"].lower() or q_lower in f["key_phrase"].lower()]
    return {"episodes": episodes, "facts": relevant_facts}

@app.get("/api/memory/facts")
def api_get_facts(topic: str = None):
    return {"facts": get_all_facts(topic=topic)}

@app.post("/api/memory/facts")
def api_store_fact(req: FactRequest):
    store_named_fact(req.content, req.key_phrase)
    return {"ok": True}

@app.delete("/api/memory/facts")
def api_delete_fact(req: DeleteMemoryRequest):
    deleted = delete_named_fact(req.query)
    return {"deleted": deleted}

@app.post("/api/memory/condense")
def api_condense():
    condense_old_episodes(days_ago=3)
    return {"ok": True}

# ── Nudge API ─────────────────────────────────────────────────────────────────

@app.get("/api/nudges")
def api_get_nudges():
    settings = get_settings()
    sensitivity = settings.get("nudge_sensitivity", "balanced")
    return {"nudges": get_pending_nudges(sensitivity)}

@app.get("/api/nudges/history")
def api_get_nudge_history():
    return {"nudges": get_all_nudges_history()}

@app.post("/api/nudges/acknowledge")
def api_ack_nudge(req: NudgeAckRequest):
    acknowledge_nudge(req.nudge_id)
    return {"ok": True}

@app.post("/api/nudges/suppress")
def api_suppress_nudge(req: SuppressRequest):
    suppress_nudge_topic(req.topic)
    return {"ok": True}

# ── LLM status endpoint ──────────────────────────────────────────────────────

@app.get("/api/llm-status")
def llm_status():
    return get_provider_info()


# ── VOICE ENDPOINTS (Module 12) ───────────────────────────────────────────────

class VoiceModeRequest(BaseModel):
    mode: str   # off | push_to_talk | wake_word | ambient | dictation

class VoiceSpeakRequest(BaseModel):
    text: str
    urgent: bool = False

@app.get("/api/voice/status")
def voice_status():
    eng = get_voice_engine()
    if not eng:
        return {"available": False, "reason": "Voice engine not initialised"}
    return {"available": True, **eng.get_status()}

@app.post("/api/voice/mode")
def voice_set_mode(req: VoiceModeRequest):
    eng = get_voice_engine()
    if not eng:
        return {"ok": False, "error": "Voice engine not available"}
    try:
        eng.set_mode(VoiceMode(req.mode))
        return {"ok": True, "mode": req.mode}
    except ValueError:
        return {"ok": False, "error": f"Unknown mode '{req.mode}'"}

@app.post("/api/voice/speak")
async def voice_speak(req: VoiceSpeakRequest):
    eng = get_voice_engine()
    if not eng:
        return {"ok": False}
    if req.urgent:
        eng.speak_urgent(req.text)
    else:
        eng.speak(req.text)
    return {"ok": True}

@app.post("/api/voice/dictation/stop")
def voice_stop_dictation():
    eng = get_voice_engine()
    if not eng:
        return {"text": "", "ok": False}
    text = eng.stop_dictation()
    return {"text": text, "ok": True}


@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    """
    Browser WebSocket for the voice interface.

    Browser → Server (JSON):
      {"type": "set_mode",       "mode": "wake_word"|"ambient"|...}
      {"type": "audio",          "data": "<base64 PCM16 mono 16kHz>"}
      {"type": "dictation_start"}
      {"type": "dictation_stop"}
      {"type": "ping"}

    Server → Browser (JSON):
      {"type": "hello",          "mode", "tts", "stt", "mic_available"}
      {"type": "mode",           "mode", "msg"}
      {"type": "wake",           "msg"}
      {"type": "recording_start"}
      {"type": "transcript",     "text", "final"}
      {"type": "tts",            "text"}
      {"type": "tts_urgent",     "text"}
      {"type": "dictation_chunk","text"}
      {"type": "dictation_done", "text"}
      {"type": "error",          "msg"}
    """
    await websocket.accept()
    eng = get_voice_engine()
    if not eng:
        await websocket.send_json({"type": "error", "msg": "Voice engine unavailable"})
        await websocket.close()
        return

    eng.register_client(websocket)
    try:
        while True:
            msg = await websocket.receive_json()
            mtype = msg.get("type", "")

            if mtype == "ping":
                await websocket.send_json({"type": "pong"})

            elif mtype == "set_mode":
                try:
                    eng.set_mode(VoiceMode(msg.get("mode", "off")))
                except ValueError:
                    await websocket.send_json({"type": "error", "msg": "Unknown mode"})

            elif mtype == "audio":
                import base64
                raw = base64.b64decode(msg.get("data", ""))
                if raw:
                    loop = asyncio.get_event_loop()
                    text = await loop.run_in_executor(None, eng.stt.transcribe, raw)
                    if text:
                        await websocket.send_json({"type": "transcript", "text": text, "final": True})
                        await _voice_command_handler(text, "push_to_talk")

            elif mtype == "dictation_start":
                eng.start_dictation()

            elif mtype == "dictation_stop":
                text = eng.stop_dictation()
                await websocket.send_json({"type": "dictation_done", "text": text})

    except WebSocketDisconnect:
        pass
    finally:
        eng.unregister_client(websocket)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


# ── SYNC / MOBILE ENDPOINTS ──────────────────────────────────────────────────────

class PinRequest(BaseModel):
    pin: str

@app.get("/api/sync/session")
def sync_session():
    settings = get_settings()
    return get_sync_session(settings)

@app.get("/api/sync/status")
def sync_status():
    from tunnel_manager import _public_url, _tunnel_type, _local_ip
    return {
        "tunnel_active": bool(_public_url),
        "public_url":    _public_url,
        "tunnel_type":   _tunnel_type,
        "lan_ip":        _local_ip(),
        "mobile_url":    f"{_public_url}/remote" if _public_url else None,
    }

@app.post("/api/sync/pin")
def sync_update_pin(req: PinRequest):
    if not req.pin or len(req.pin) < 4:
        return {"ok": False, "error": "PIN must be at least 4 characters"}
    set_session_pin(req.pin)
    return {"ok": True}

# Sync WebSocket — bridges mobile ↔ desktop chat
# Mobile sends {type:"auth", pin:"..."} then {type:"chat", message:"..."}
# Server replies with {type:"reply", text:"..."} from LLM

_sync_clients: set = set()

@app.websocket("/ws/sync")
async def sync_websocket(websocket: WebSocket):
    await websocket.accept()
    settings = get_settings()

    # ── Auth ──
    try:
        raw = await asyncio.wait_for(websocket.receive_json(), timeout=15)
    except asyncio.TimeoutError:
        await websocket.send_json({"type": "error", "msg": "Auth timeout"})
        await websocket.close()
        return

    if raw.get("type") != "auth":
        await websocket.send_json({"type": "error", "msg": "Expected auth message"})
        await websocket.close()
        return

    provided = raw.get("pin", "").strip()
    if provided != get_session_pin():
        await websocket.send_json({"type": "auth_failed", "msg": "Incorrect PIN"})
        await websocket.close()
        return

    await websocket.send_json({
        "type":    "auth_ok",
        "name":    settings.get("name", "Saathi"),
        "msg":     "Connected to Saathi on your laptop.",
    })
    _sync_clients.add(websocket)

    # ── Message loop ──
    try:
        while True:
            msg = await websocket.receive_json()
            mtype = msg.get("type", "")

            if mtype == "ping":
                await websocket.send_json({"type": "pong"})

            elif mtype == "chat":
                text    = msg.get("message", "").strip()
                mode    = msg.get("mode", "chat")
                if not text:
                    continue

                # Broadcast "thinking" indicator
                await websocket.send_json({"type": "thinking"})

                # Build context + call LLM
                settings = get_settings()
                user_name = settings.get("name", "Friend")
                language  = settings.get("language", "English")
                mem_ctx   = get_relevant_memory_context(text)

                nudge_sensitivity = settings.get("nudge_sensitivity", "balanced")
                due_nudges = get_pending_nudges(nudge_sensitivity)
                nudge_ctx  = ""
                if due_nudges:
                    nudge_ctx = "\n-- Pending reminders:\n" + "\n".join(f"• {n['message']}" for n in due_nudges[:2])

                if mode == "search":
                    try:
                        sr = search_web(text)
                        mem_ctx += f"\nLive search results: {sr}"
                    except Exception:
                        pass

                system_prompt = (
                    f"You are Saathi, {user_name}'s personal AI companion. "
                    f"Answer in {language}. The user is on their phone — keep replies concise."
                )

                reply = await llm_chat(system_prompt, text, mem_ctx + nudge_ctx)

                # Store memory
                store_episode(text)
                store_episode(f"Saathi replied: {reply[:200]}", source="ai")
                maybe_create_nudge(text)

                await websocket.send_json({"type": "reply", "text": reply})

            elif mtype == "nudges":
                nudges = get_pending_nudges(settings.get("nudge_sensitivity", "balanced"))
                await websocket.send_json({"type": "nudges", "data": nudges[:5]})

            elif mtype == "ack_nudge":
                acknowledge_nudge(msg.get("nudge_id", 0))

    except WebSocketDisconnect:
        pass
    finally:
        _sync_clients.discard(websocket)
