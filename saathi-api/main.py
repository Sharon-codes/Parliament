import base64
import hashlib
import hmac
import json
import mimetypes
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import pytz
import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent_tools import execute_tool, get_mini_tool_definitions
from document_pipeline import extract_document_payload, translate_document_blocks, translate_text_content
from google_workspace import (
    GoogleWorkspaceError,
    build_google_oauth_url,
    create_calendar_event,
    create_google_doc,
    create_google_doc_from_blocks,
    exchange_code_for_tokens,
    fetch_google_userinfo,
    get_email_detail,
    list_calendar_events_range,
    list_recent_emails,
    list_upcoming_events,
    oauth_enabled,
    parse_email_address,
    read_google_doc_from_url,
    search_google_contacts,
    send_new_email,
    send_reply,
    ensure_valid_tokens,
)
from llm import get_provider_info, llm_chat
from storage import StorageError, storage, supabase_enabled, verify_access_token
from system_agent import launch_app_with_file, parse_desktop_command, play_youtube_video, write_code_to_file

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

PUBLIC_WEB_URL = os.getenv("PUBLIC_WEB_URL", "http://localhost:5173").strip().rstrip("/")
PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "http://localhost:8000").strip().rstrip("/")
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Kolkata").strip() or "Asia/Kolkata"
STATE_SECRET = os.getenv("GOOGLE_OAUTH_STATE_SECRET", "replace-this-in-production").encode("utf-8")

REMOTE_DIR = Path(__file__).parent.parent / "saathi-remote"
PRIMARY_FE_DIST_DIR = Path(__file__).parent / "dist"
FALLBACK_FE_DIST_DIR = Path(__file__).parent.parent / "saathi-web" / "dist"
FE_DIST_DIR = FALLBACK_FE_DIST_DIR if FALLBACK_FE_DIST_DIR.exists() else PRIMARY_FE_DIST_DIR

app = FastAPI(title="Saathi API", version="2.1.0")


class ProfileRequest(BaseModel):
    full_name: Optional[str] = None
    language: Optional[str] = None
    voice_gender: Optional[str] = None
    onboarding_completed: Optional[bool] = None


class ChatRequest(BaseModel):
    text: Optional[str] = None
    message: Optional[str] = None
    session_id: Optional[str] = None
    mode: str = "chat"
    doc_context: Optional[dict] = None

    @property
    def prompt(self) -> str:
        return (self.text or self.message or "").strip()


class MemoryRequest(BaseModel):
    text: str


class CreateSessionRequest(BaseModel):
    title: Optional[str] = None


class ReplyEmailRequest(BaseModel):
    to: str
    subject: str
    body: str
    thread_id: Optional[str] = None
    message_id_header: Optional[str] = None
    references: Optional[str] = None


class SendEmailRequest(BaseModel):
    to: str
    subject: str
    body: str


class CalendarEventRequest(BaseModel):
    title: str
    description: str = ""
    start: str
    end: str
    timezone: str = APP_TIMEZONE
    attendees: list[str] = Field(default_factory=list)
    generate_meet: bool = False


class CreateDocRequest(BaseModel):
    title: str
    content: str = ""
    prompt: Optional[str] = None
    generate: bool = False


class TranslateRequest(BaseModel):
    name: str
    content: str
    target_lang: str = "hi"


class ReadDocFromEmailRequest(BaseModel):
    message_id: str
    url: Optional[str] = None


class OpenAppRequest(BaseModel):
    app_name: str


class OpenYouTubeRequest(BaseModel):
    query: str


@app.exception_handler(StorageError)
async def storage_exception_handler(_: Request, exc: StorageError):
    return JSONResponse(status_code=500, content={"ok": False, "detail": str(exc)})


@app.exception_handler(GoogleWorkspaceError)
async def google_exception_handler(_: Request, exc: GoogleWorkspaceError):
    return JSONResponse(status_code=400, content={"ok": False, "detail": str(exc)})


@app.exception_handler(Exception)
async def global_exception_handler(_: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"ok": False, "detail": str(exc)})


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://10.22.66.210:8000",
        "http://localhost:5173",
        "https://fuzzy-yaks-spend.loca.lt",
        "https://plain-areas-rest.loca.lt"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if REMOTE_DIR.exists():
    app.mount("/remote", StaticFiles(directory=str(REMOTE_DIR), html=True), name="remote")


def _sign_state(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(STATE_SECRET, raw, hashlib.sha256).digest()
    encoded_payload = base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
    encoded_sig = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
    return f"{encoded_payload}.{encoded_sig}"


def _unsign_state(token: str) -> dict:
    try:
        encoded_payload, encoded_sig = token.split(".", 1)
        raw = base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
        expected = hmac.new(STATE_SECRET, raw, hashlib.sha256).digest()
        actual = base64.urlsafe_b64decode(encoded_sig + "=" * (-len(encoded_sig) % 4))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid token format.") from exc
    if not hmac.compare_digest(expected, actual):
        raise HTTPException(status_code=400, detail="Token signature check failed.")
    return json.loads(raw.decode("utf-8"))


def _create_token(user_id: str, email: str, full_name: str) -> str:
    return _sign_state({"id": user_id, "email": email, "full_name": full_name, "type": "saathi_session"})


async def get_current_user(request: Request) -> dict:
    auth_header = request.headers.get("authorization", "").strip()
    token = auth_header.removeprefix("Bearer").strip() if auth_header.lower().startswith("bearer ") else ""

    if not token:
        raise HTTPException(status_code=401, detail="Please sign in to continue.")

    try:
        payload = _unsign_state(token)
        if payload.get("type") == "saathi_session":
            return {
                "id": payload["id"],
                "email": payload["email"],
                "user_metadata": {"full_name": payload.get("full_name", "Friend")},
                "app_metadata": {"provider": "google"},
            }
    except Exception:
        pass

    if supabase_enabled():
        user = await verify_access_token(token)
        if user:
            return user

    raise HTTPException(status_code=401, detail="Invalid session. Please sign in again.")


def _profile_from_identity(user: dict) -> dict:
    metadata = user.get("user_metadata") or {}
    return storage.ensure_profile(
        user["id"],
        email=user.get("email", ""),
        full_name=metadata.get("full_name") or metadata.get("name") or "Friend",
    )


async def _workspace_connection(user_id: str) -> dict:
    connection = storage.get_google_integration(user_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Google Workspace is not connected yet.")
    try:
        connection = await ensure_valid_tokens(connection)
    except GoogleWorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    storage.upsert_google_integration(user_id, connection)
    return connection


def _get_base_url(request: Request) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")

    if forwarded_host and "loca.lt" in forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}"
    if PUBLIC_API_URL and "localhost" not in PUBLIC_API_URL:
        return PUBLIC_API_URL
    return f"{forwarded_proto}://{forwarded_host}"


def _trim_doc_context(content: str, limit: int = 1800) -> str:
    if len(content) <= limit:
        return content
    return content[:limit] + "\n... [document context trimmed for faster routing]"


def _selected_tool_names(message: str, workspace_connected: bool) -> list[str]:
    msg = (message or "").lower()
    selected = {"search_web", "open_url", "launch_app", "play_youtube_video"}

    if workspace_connected:
        if any(keyword in msg for keyword in ["email", "mail", "reply", "inbox"]):
            selected.update({"send_email", "reply_to_email", "search_emails", "read_email", "find_contact"})
        if any(keyword in msg for keyword in ["meeting", "calendar", "event", "schedule"]):
            selected.update({"create_calendar_event", "schedule_meeting_with_meet", "list_calendar_events", "search_calendar_for_day", "find_contact"})
        if any(keyword in msg for keyword in ["doc", "document", "google doc", "notes", "write up"]):
            selected.update({"create_doc", "read_doc_from_url"})

    return sorted(selected)


async def _translate_to_google_doc(
    *,
    access_token: str,
    title: str,
    plain_text: str,
    target_lang: str,
    blocks: Optional[list[dict]] = None,
) -> dict:
    translated_blocks = None
    translated_text = ""

    if blocks:
        translated_blocks = await translate_document_blocks(blocks, target_lang)
        translated_text = "\n".join((block.get("text") or "") for block in translated_blocks).strip()
    else:
        translated_text = await translate_text_content(plain_text, target_lang)

    if translated_blocks:
        document = await create_google_doc_from_blocks(access_token, title, translated_blocks)
    else:
        document = await create_google_doc(access_token, title, translated_text)

    return {"document": document, "translated_text": translated_text}


async def _generate_document_content(title: str, prompt: str, seed_content: str = "") -> str:
    doc_prompt = (prompt or "").strip()
    seed = (seed_content or "").strip()
    if not doc_prompt and seed:
        doc_prompt = seed
    if not doc_prompt:
        return seed

    system_prompt = (
        "You are an Elite Workspace Author. You write structured, high-fidelity professional content for Google Docs. "
        "Your output must be the FULL document body. Use Markdown-like structure (Headings, Bullets, Paragraphs). "
        "The content must be detailed (300+ words if title warrants it), factual, and polished."
    )
    user_prompt = f"Create a document titled '{title}'.\n\nRequest:\n{doc_prompt}"
    if seed:
        user_prompt += f"\n\nStarting notes to incorporate and improve:\n{seed}"
    try:
        # 💨 NITRO INJECTION (v120.5): Use a minimal system prompt to save tokens
        lite_system = "Expert Author. Write a detailed professional document. Use Markdown. Produce 300+ words."
        generated = await llm_chat(lite_system, user_prompt, history=[], tools=None, raw_mode=True)
        
        if (generated or "").strip() and (generated.strip() != doc_prompt.strip()):
            return generated.strip()
        
        return seed or doc_prompt
    except Exception as e:
        print(f"DEBUG: Generation failed: {e}")
        return seed or doc_prompt


def _extract_json_payload(raw_text: str) -> dict:
    text = (raw_text or "").strip()
    if not text:
        return {}
    fenced = re.search(r"```(?:json)?\s*([\s\S]+?)```", text, re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except Exception:
        return {}


def _detect_code_request(instruction: str) -> Optional[dict]:
    normalized = re.sub(r"\s+", " ", (instruction or "").strip())
    if not normalized:
        return None
    if not re.search(r"\b(write|create|make|build|draft|generate|code|program)\b", normalized, re.IGNORECASE):
        return None
    # Optional program keyword or just language check
    has_program_kv = re.search(r"\b(program|script|file|code|game|app|application|tool|logic)\b", normalized, re.IGNORECASE)
    has_language = re.search(r"\b(python|javascript|node|js|html|css|cpp|java)\b", normalized, re.IGNORECASE)
    
    if not (has_program_kv or has_language):
        return None

    language = None
    extension = ".txt"
    if re.search(r"\bpython\b", normalized, re.IGNORECASE):
        language = "python"
        extension = ".py"
    elif re.search(r"\b(javascript|node|js)\b", normalized, re.IGNORECASE):
        language = "javascript"
        extension = ".js"
    elif re.search(r"\b(html)\b", normalized, re.IGNORECASE):
        language = "html"
        extension = ".html"

    if not language:
        return None

    summary = re.sub(r"^(?:and\s+)?(?:write|create|make|build|draft|generate)\s+", "", normalized, flags=re.IGNORECASE)
    return {"language": language, "extension": extension, "summary": summary}


def _fallback_code_payload(task: dict) -> dict:
    default_name = re.sub(r"[^a-z0-9]+", "_", task["summary"].lower()).strip("_") or "generated_code"
    
    # 🧬 SOVEREIGN STARTER (v121.5): High-fidelity boilerplate for presentation stability
    templates = {
        "python": "def main():\n    \"\"\"Calculates {summary}\"\"\"\n    print('Starting task...')\n    # TODO: Logic for {summary}\n\nif __name__ == '__main__':\n    main()",
        "javascript": "async function main() {\n    console.log('Task: {summary}');\n    // TODO: {summary}\n}\nmain();",
        "html": "<!DOCTYPE html>\n<html>\n<head><title>{summary}</title></head>\n<body>\n  <h1>{summary}</h1>\n</body>\n</html>"
    }
    code = templates.get(task["language"], "# {summary}")
    code = code.replace("{summary}", task["summary"])
    
    return {
        "filename": f"{default_name[:40]}{task['extension']}",
        "code": code,
    }


async def _build_code_file_from_request(instruction: str) -> Optional[dict]:
    task = _detect_code_request(instruction)
    if not task:
        return None

    fallback = _fallback_code_payload(task)
    filename = fallback["filename"]
    code = fallback["code"]

    try:
        # 🦾 SOVEREIGN ENGINEER (v121.8): Using robust Tag-Based Extraction
        res_text = await llm_chat(
            f"You are an Elite Software Engineer. Return the COMPLETE operational source code for the requested program. "
            f"Wrap your code EXACTLY between [SOURCE_START] and [SOURCE_END] markers. "
            f"Provide at least 30 lines of well-commented, functional {task['language']} code.",
            f"Task: {task['summary']}\nLanguage: {task['language']}",
            history=[],
            tools=None,
            raw_mode=False
        )
        
        # Robust Recovery Parser (v123.0)
        match = re.search(r"\[SOURCE_START\]([\s\S]+?)\[SOURCE_END\]", res_text)
        if not match:
            # Look for partial start tag (cutoff recovery)
            match = re.search(r"\[SOURCE_START\]([\s\S]+)$", res_text)
            
        if match:
            code = match.group(1).strip()
            # Clean up markdown fences
            code = re.sub(r"^```[\w]*\n|```$", "", code, flags=re.MULTILINE).strip()
            # If we recovered a partial, add a notice
            if "[SOURCE_END]" not in res_text:
                code += "\n\n# [AI NOTICE]: This file was recovered from a neural stream cutoff."
    except Exception as e:
        print(f"DEBUG: Code drafting failed: {e}")

    if not code.endswith("\n"):
        code += "\n"

    import system_agent
    file_path = system_agent.write_code_to_file(filename, code)
    return {"file_path": file_path, "filename": filename, "summary": task["summary"]}


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "storage": storage.mode,
        "auth": "supabase" if supabase_enabled() else "demo",
        "workspaceOAuth": oauth_enabled(),
        "webUrl": PUBLIC_WEB_URL,
        "apiUrl": PUBLIC_API_URL,
    }


@app.get("/api/llm-status")
def llm_status():
    status = get_provider_info()
    status["storage"] = storage.mode
    return status


@app.get("/api/profile")
async def get_profile(user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    return {
        **profile,
        "demo_mode": not supabase_enabled(),
        "available_languages": ["English", "Hindi", "Tamil", "Kannada", "Telugu"],
    }


@app.post("/api/profile")
async def update_profile(req: ProfileRequest, user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    return storage.update_profile(profile["id"], req.dict(exclude_none=True))


@app.get("/api/sessions")
async def list_sessions(user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    return storage.list_sessions(profile["id"])


@app.post("/api/sessions")
async def create_session(req: Optional[CreateSessionRequest] = None, user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    title = (req.title if req else None) or "New chat"
    return storage.create_session(profile["id"], title=title)


@app.get("/api/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    return storage.get_messages(profile["id"], session_id)


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    storage.delete_session(profile["id"], session_id)
    return {"ok": True}


@app.post("/api/extract-doc")
async def extract_doc_content(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    content = await file.read()
    payload = extract_document_payload(file.filename or "document.txt", content)
    return {"content": payload["plain_text"]}


@app.post("/api/sessions/{session_id}/translate")
async def translate_document(session_id: str, req: TranslateRequest, user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    connection = await _workspace_connection(profile["id"])
    if not req.content:
        raise HTTPException(status_code=400, detail="Document content is empty.")
    translated = await _translate_to_google_doc(
        access_token=connection["access_token"],
        title=f"Polyglot_{req.target_lang}_{req.name}",
        plain_text=req.content,
        target_lang=req.target_lang,
    )
    return {"link": translated["document"]["url"], "document": translated["document"]}


@app.get("/api/deadlines")
@app.get("/api/workspace/deadlines")
async def get_deadlines(user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    return storage.list_deadlines(profile["id"])


@app.get("/api/memory")
async def get_memory(user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    return storage.list_memory(profile["id"])


@app.post("/api/sessions/{session_id}/chat")
async def session_chat(session_id: str, req: ChatRequest, user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    msg = req.prompt
    if not msg:
        raise HTTPException(status_code=400, detail="Message is empty")

    storage.add_message(profile["id"], session_id, "user", msg)
    history = storage.get_messages(profile["id"], session_id)
    prior_messages = history[:-1][-6:]

    doc_directive = ""
    if req.doc_context:
        name = req.doc_context.get("name", "Document")
        content = _trim_doc_context(req.doc_context.get("content", ""))
        doc_directive = (
            f"\n\n[DOCUMENT CONTEXT]\n"
            f"Active document: {name}\n"
            f"Use this context only when the user is clearly referring to the attached document.\n"
            f"{content}"
        )

    connection = storage.get_google_integration(profile["id"])
    access_token = None
    if connection:
        try:
            connection = await ensure_valid_tokens(connection)
            storage.upsert_google_integration(profile["id"], connection)
            access_token = connection["access_token"]
        except Exception:
            access_token = None

    origin = request.headers.get("x-saathi-origin", "laptop").lower()
    tools = get_mini_tool_definitions(_selected_tool_names(msg, bool(access_token)))
    local_tz = pytz.timezone(APP_TIMEZONE)
    current_time_str = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S")
    system_prompt = (
        f"Saathi is an Elite Sovereign Assistant for Desktop and Google Workspace.\n"
        f"Current time: {current_time_str}\n"
        f"Timezone: {APP_TIMEZONE}\n"
        f"{doc_directive}\n"
        "SOVEREIGN RULES:\n"
        "1. You are the CONTENT AUTHOR. If asked to 'create' or 'send', compose full, rich, professional content yourself.\n"
        "2. CALL TOOLS IMMEDIATELY based on the request. Use tool outputs to provide a status update.\n"
        "3. If details are missing, proceed with high-confidence assumptions or ask precisely for the missing bit.\n"
        "4. You have direct agency over the user's workspace and hardware."
    )

    try:
        reply = await llm_chat(
            system_prompt,
            msg,
            history=prior_messages,
            tools=tools,
            tool_executor=execute_tool,
            access_token=access_token,
            timezone=APP_TIMEZONE,
            profile_id=profile["id"],
            origin=origin,
        )
    except Exception as exc:
        reply = f"Saathi hit a routing error: {exc}"

    storage.add_message(profile["id"], session_id, "assistant", reply)
    return {"id": str(uuid.uuid4()), "role": "assistant", "text": reply, "created_at": datetime.utcnow().isoformat()}


@app.post("/api/chat")
async def direct_chat(req: ChatRequest, user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    session_id = req.session_id or storage.create_session(profile["id"])["id"]
    return await session_chat(session_id, req, user)


@app.post("/api/workspace/sync")
async def sync_workspace(user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    connection = storage.get_google_integration(profile["id"])
    if not connection:
        return {"status": "skipped", "reason": "No Google connection"}

    connection = await ensure_valid_tokens(connection)
    storage.upsert_google_integration(profile["id"], connection)
    events = await list_upcoming_events(connection["access_token"], timezone_name=APP_TIMEZONE, max_results=20)
    return {"status": "success", "count": len(events)}


@app.get("/api/workspace/status")
async def workspace_status(user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    connection = storage.get_google_integration(profile["id"])
    return {
        "oauthConfigured": oauth_enabled(),
        "connected": bool(connection),
        "email": (connection or {}).get("google_email"),
        "scopes": (connection or {}).get("scopes") or [],
        "requiredFile": "Google OAuth Web Client JSON (client_id + client_secret)",
    }


@app.get("/api/workspace/connect")
async def connect_workspace(request: Request, mode: str = "workspace", user: dict = Depends(get_current_user)):
    if not oauth_enabled():
        raise HTTPException(status_code=400, detail="Google OAuth is not configured.")
    _profile_from_identity(user)
    state = _sign_state({"mode": mode, "ts": datetime.utcnow().isoformat()})
    redirect_uri = f"{_get_base_url(request)}/api/auth/google/callback"
    return {"url": build_google_oauth_url(redirect_uri, state, prompt="consent select_account")}


@app.delete("/api/workspace/connect")
async def disconnect_workspace(user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    storage.delete_google_integration(profile["id"])
    return {"ok": True}


@app.get("/api/auth/google/url")
async def get_google_auth_url(request: Request, mode: str = "signup"):
    if not oauth_enabled():
        raise HTTPException(status_code=400, detail="Google OAuth is not configured.")
    state = _sign_state({"mode": mode, "ts": datetime.utcnow().isoformat()})
    redirect_uri = f"{_get_base_url(request)}/api/auth/google/callback"
    return {"url": build_google_oauth_url(redirect_uri, state, prompt="consent select_account")}


@app.get("/api/auth/google/callback")
async def google_auth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    web_url = PUBLIC_WEB_URL
    if "localhost" in web_url and "loca.lt" in (request.url.hostname or ""):
        web_url = f"{request.url.scheme}://{request.url.hostname}"
        if request.url.port and request.url.port not in {80, 443}:
            web_url += f":{request.url.port}"

    if error:
        return RedirectResponse(url=f"{web_url}/auth?error={quote(error)}")
    if not code or not state:
        return RedirectResponse(url=f"{web_url}/auth?error=missing_auth_data")

    payload = _unsign_state(state)
    redirect_uri = f"{_get_base_url(request)}/api/auth/google/callback"

    try:
        tokens = await exchange_code_for_tokens(code, redirect_uri)
        userinfo = await fetch_google_userinfo(tokens["access_token"])
        email = userinfo.get("email")
        if not email:
            raise GoogleWorkspaceError("Failed to retrieve Google identity.")

        user_id = email.replace("@", "_").replace(".", "_")
        storage.upsert_google_integration(
            user_id,
            {
                "google_email": email,
                "access_token": tokens.get("access_token"),
                "refresh_token": tokens.get("refresh_token"),
                "token_expiry": tokens.get("token_expiry"),
                "scopes": (tokens.get("scope") or "").split(),
                "connected_at": datetime.utcnow().isoformat(),
            },
        )

        saathi_token = _create_token(user_id, email, userinfo.get("name", "Friend"))
        force_dashboard = payload.get("mode") == "login"
        is_returning = storage.profile_exists(user_id)
        if force_dashboard:
            storage.update_profile(user_id, {"onboarding_completed": True})
        target = "/dashboard" if (is_returning or force_dashboard) else "/welcome"
        return RedirectResponse(url=f"{web_url}{target}?token={saathi_token}")
    except Exception as exc:
        return RedirectResponse(url=f"{web_url}/auth?error={quote(str(exc))}")


@app.get("/api/workspace/contacts/search")
async def workspace_contact_search(query: str, limit: int = 8, user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    connection = await _workspace_connection(profile["id"])
    contacts = await search_google_contacts(connection["access_token"], query, limit=max(1, min(limit, 12)))
    return {"contacts": contacts, "bestMatch": contacts[0] if contacts else None}


@app.get("/api/workspace/emails")
async def workspace_emails(limit: int = 6, user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    connection = await _workspace_connection(profile["id"])
    emails = await list_recent_emails(connection["access_token"], max_results=max(1, min(limit, 12)))
    return {"emails": emails}


@app.get("/api/workspace/emails/{message_id}")
async def workspace_email_detail(message_id: str, user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    connection = await _workspace_connection(profile["id"])
    return await get_email_detail(connection["access_token"], message_id)


@app.post("/api/workspace/emails/send")
async def workspace_send_email(req: SendEmailRequest, user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    connection = await _workspace_connection(profile["id"])
    recipient = parse_email_address(req.to).strip()
    if not recipient and req.to.strip():
        matches = await search_google_contacts(connection["access_token"], req.to.strip(), limit=1)
        if matches:
            recipient = matches[0]["email"]
    if not recipient:
        raise HTTPException(status_code=400, detail="Choose or type a recipient email before sending.")
    result = await send_new_email(
        connection["access_token"],
        to=recipient,
        subject=req.subject,
        body=req.body,
    )
    return {"ok": True, "message": result}


@app.post("/api/workspace/emails/reply")
async def workspace_reply(req: ReplyEmailRequest, user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    connection = await _workspace_connection(profile["id"])
    result = await send_reply(
        connection["access_token"],
        to=parse_email_address(req.to),
        subject=req.subject,
        body=req.body,
        thread_id=req.thread_id,
        in_reply_to=req.message_id_header,
        references=req.references,
    )
    return {"ok": True, "message": result}


@app.get("/api/workspace/calendar")
async def workspace_calendar(limit: int = 8, timezone: str = APP_TIMEZONE, user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    connection = await _workspace_connection(profile["id"])
    events = await list_upcoming_events(connection["access_token"], timezone, max_results=max(1, min(limit, 12)))
    return {"events": events}


@app.post("/api/workspace/calendar/events")
async def workspace_create_event(req: CalendarEventRequest, user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    connection = await _workspace_connection(profile["id"])
    start_val = f"{req.start}:00" if req.start and req.start.count(":") == 1 else req.start
    end_val = f"{req.end}:00" if req.end and req.end.count(":") == 1 else req.end
    resolved_attendees: list[str] = []
    for attendee in req.attendees:
        candidate = parse_email_address(attendee).strip()
        if candidate and "@" in candidate:
            resolved_attendees.append(candidate)
            continue
        if attendee.strip():
            matches = await search_google_contacts(connection["access_token"], attendee, limit=1)
            if matches:
                resolved_attendees.append(matches[0]["email"])
    if req.attendees and not resolved_attendees:
        raise HTTPException(status_code=400, detail="Choose or type a valid attendee email before scheduling.")
    event = await create_calendar_event(
        connection["access_token"],
        title=req.title,
        description=req.description,
        start_iso=start_val,
        end_iso=end_val,
        timezone_name=req.timezone or APP_TIMEZONE,
        attendees=resolved_attendees,
        generate_meet=req.generate_meet,
    )
    return {"ok": True, "event": event}


@app.post("/api/workspace/docs")
async def workspace_create_doc(req: CreateDocRequest, user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    connection = await _workspace_connection(profile["id"])
    prompt = (req.prompt or "").strip()
    content = (req.content or "").strip()

    # 🧬 FORCE GENERATION (v119.0): Never echo prompts.
    if not content and prompt:
        content = await _generate_document_content(req.title, prompt, seed_content="")
    elif req.generate:
        content = await _generate_document_content(req.title, prompt or content, seed_content=content)

    if not content:
        raise HTTPException(status_code=400, detail="Document content or prompt is required.")

    document = await create_google_doc(connection["access_token"], req.title, content)
    return {"ok": True, "document": document, "generated_content": content}


@app.post("/api/workspace/translate")
async def workspace_translate_doc(request: Request, user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    connection = await _workspace_connection(profile["id"])
    data = await request.json()
    text = data.get("text", "")
    target_lang = data.get("target_lang", "hi")
    title = data.get("title", "Translated Document")

    if not text:
        raise HTTPException(status_code=400, detail="No content provided for translation.")

    translated = await _translate_to_google_doc(
        access_token=connection["access_token"],
        title=f"{title} [{target_lang}]",
        plain_text=text,
        target_lang=target_lang,
    )
    storage.add_memory(profile["id"], f"DOCUMENT SUMMARY [{title}]: {translated['translated_text'][:1000]}")
    return {"ok": True, "document": translated["document"], "translated_text": translated["translated_text"]}


@app.post("/api/workspace/translate-file")
async def workspace_translate_file(
    file: UploadFile = File(...),
    target_lang: str = Form("hi"),
    user: dict = Depends(get_current_user),
):
    profile = _profile_from_identity(user)
    connection = await _workspace_connection(profile["id"])
    content = await file.read()
    payload = extract_document_payload(file.filename or "document.txt", content)

    if not payload["plain_text"].strip():
        raise HTTPException(status_code=400, detail="Could not extract text from file.")

    title = f"Polyglot: {file.filename}"
    translated = await _translate_to_google_doc(
        access_token=connection["access_token"],
        title=f"{title} [{target_lang}]",
        plain_text=payload["plain_text"],
        target_lang=target_lang,
        blocks=payload.get("blocks"),
    )
    storage.add_memory(profile["id"], f"DOCUMENT SUMMARY [{title}]: {translated['translated_text'][:1000]}")
    return {"ok": True, "document": translated["document"], "translated_text": translated["translated_text"]}


@app.post("/api/workspace/docs/from-email")
async def workspace_read_doc_from_email(req: ReadDocFromEmailRequest, user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    connection = await _workspace_connection(profile["id"])
    doc_url = req.url
    if not doc_url:
        email_detail = await get_email_detail(connection["access_token"], req.message_id)
        links = email_detail.get("docLinks") or []
        if not links:
            raise HTTPException(status_code=404, detail="No Google Doc link was found in that email.")
        doc_url = links[0]
    document = await read_google_doc_from_url(connection["access_token"], doc_url)
    return {"document": document, "sourceUrl": doc_url}


@app.post("/api/memory")
async def add_memory(req: MemoryRequest, user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    return storage.add_memory(profile["id"], req.text)


@app.delete("/api/memory/{memory_id}")
async def delete_memory(memory_id: str, user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    storage.delete_memory(profile["id"], memory_id)
    return {"ok": True}


@app.post("/api/workspace/deadlines")
async def add_manual_deadline(req: dict, user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    title = req.get("title")
    due_date = req.get("date")
    if not title or not due_date:
        raise HTTPException(status_code=400, detail="Title and Date are required.")
    return storage.add_deadline(profile["id"], title, due_date, source_email_id="manual")


@app.delete("/api/workspace/deadlines/{deadline_id}")
async def delete_manual_deadline(deadline_id: str, user: dict = Depends(get_current_user)):
    profile = _profile_from_identity(user)
    storage.delete_deadline(profile["id"], deadline_id)
    return {"ok": True}


@app.post("/api/nudges/sync")
async def sync_nudges(user: dict = Depends(get_current_user)):
    import asyncio

    profile = _profile_from_identity(user)
    connection = await _workspace_connection(profile["id"])
    emails, calendar_events = await asyncio.gather(
        list_recent_emails(connection["access_token"], max_results=30, query="is:unread newer_than:7d"),
        list_upcoming_events(connection["access_token"], timezone_name=APP_TIMEZONE, max_results=15),
    )

    storage.delete_nudges_by_type(profile["id"], "email_unread")
    storage.delete_nudges_by_type(profile["id"], "calendar_alert")

    existing_deadlines = [item["title"] for item in storage.list_deadlines(profile["id"])]
    for event in calendar_events or []:
        storage.add_nudge(profile["id"], f"Cal: {event.get('title')}", f"Starts: {event.get('start')}", "calendar_alert")

    keywords = ["deadline", "assignment", "due", "submission", "exam", "quiz", "test", "urgent"]
    for email in emails or []:
        body = email.get("body", "")
        subject = email.get("subject", "")
        preview = f"{subject} {body[:200]}".lower()
        if any(keyword in preview for keyword in keywords) and subject not in existing_deadlines:
            storage.add_deadline(profile["id"], subject, "Soon", email.get("id", ""))
            storage.add_nudge(
                profile["id"],
                f"New Deadline: {subject}",
                "Detected in your Gmail. Manage in the Brain Room.",
                "email_unread",
            )

    return {"ok": True}


@app.post("/api/system/open-app")
async def system_open_app(req: OpenAppRequest, user: dict = Depends(get_current_user)):
    _profile_from_identity(user)
    
    # 🧪 ADVANCED ROUTING (v122.0): Disambiguate App Launching vs Code Drafting
    app_name, follow_up = parse_desktop_command(req.app_name)
    instruction = follow_up or req.app_name
    
    # Detect if user actually wants code drafting (proactive mode)
    code_intent = re.search(r"\b(write|create|make|code|program|script|develop)\b", instruction.lower())
    
    drafted_file = None
    if code_intent:
        drafted_file = await _build_code_file_from_request(instruction)

    if drafted_file:
        target_app = app_name or "vs code"
        if not app_name and "vs code" not in instruction.lower():
             target_app = "vs code" # Default to VS Code for drafting
             
        launch_message = launch_app_with_file(target_app, drafted_file["file_path"])
        return {
            "ok": True,
            "message": f"{launch_message} Drafted {drafted_file['filename']} for {drafted_file['summary']}.",
        }

    return {"ok": True, "message": launch_app_with_file(app_name or req.app_name)}


@app.post("/api/system/open-youtube")
async def system_open_youtube(req: OpenYouTubeRequest, user: dict = Depends(get_current_user)):
    _profile_from_identity(user)
    return {"ok": True, "message": play_youtube_video(req.query)}


@app.get("/api/logout")
@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("access_token")
    return response


@app.get("/{full_path:path}")
async def serve_spa_index(request: Request, full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")

    file_path = FE_DIST_DIR / full_path
    if file_path.exists() and file_path.is_file():
        mime_type, _ = mimetypes.guess_type(str(file_path))
        from fastapi.responses import FileResponse

        return FileResponse(file_path, media_type=mime_type or "application/octet-stream")

    index_path = FE_DIST_DIR / "index.html"
    if index_path.exists():
        from fastapi.responses import FileResponse

        return FileResponse(
            index_path,
            media_type="text/html",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )

    return JSONResponse({"error": "Frontend build not found."}, status_code=500)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
