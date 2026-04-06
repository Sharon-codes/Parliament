import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import uvicorn
from datetime import datetime, timedelta

from scrapers import search_web, get_latest_arxiv
from database import init_db, get_settings, update_settings, get_chat_sessions, create_chat_session, get_chat_messages, add_chat_message
from system_agent import get_active_window_context, get_clipboard, agentic_execute

init_db()
app = FastAPI(title="Saathi API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL = "http://localhost:11434/api/generate"

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

@app.get("/api/settings")
def get_user_settings():
    return get_settings()

@app.post("/api/settings")
def save_user_settings(req: SettingsRequest):
    return update_settings(req.dict(exclude_none=True))

@app.get("/api/sessions")
def fetch_sessions():
    return {"sessions": get_chat_sessions()}

@app.get("/api/sessions/{session_id}")
def fetch_session_messages(session_id: str):
    return {"messages": get_chat_messages(session_id)}

@app.post("/api/sessions")
def create_session():
    return {"session_id": create_chat_session()}

@app.post("/api/chat")
async def chat_with_saathi(req: ChatRequest):
    settings = get_settings()
    user_name = settings.get("name", "Friend")
    language = settings.get("language", "English")
    
    session_id = req.session_id
    if not session_id:
        session_id = create_chat_session()
        
    add_chat_message(session_id, "user", req.message)
    
    context = ""
    past_messages = get_chat_messages(session_id)
    if past_messages:
        memory_str = "\n".join([f"{msg['role'].capitalize()}: {msg['text']}" for msg in past_messages[-6:]])
        context += f"-- Past Memory:\n{memory_str}\n--\n"

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
        except: pass
        
    system_prompt = f"You are Saathi, an elegant, serene personal AI companion. You have deep system integration. The user's name is {user_name}. You must answer in {language}. If you are asked to write code and run/open an editor, write the code in standard markdown blocks so the background system can exact it. Be friendly, calm, and insightful."
    
    full_prompt = f"System: {system_prompt}\nContext: {context}\nUser: {req.message}\nSaathi:"
    
    timeout_client = httpx.Timeout(300.0, connect=10.0)
    
    async with httpx.AsyncClient(timeout=timeout_client) as client:
        try:
            response = await client.post(OLLAMA_URL, json={
                "model": "llama3:latest",
                "prompt": full_prompt,
                "stream": False
            })
            
            if response.status_code == 200:
                data = response.json()
                ai_reply = data.get("response", "").strip()
                
                sys_action_result = agentic_execute(req.message, llm_response=ai_reply, mode=req.mode)
                if sys_action_result and "no immediate desktop tools" not in sys_action_result:
                    ai_reply += f"\n\n*(System Note: {sys_action_result})*"
                
                add_chat_message(session_id, "ai", ai_reply)
                return {"reply": ai_reply, "session_id": session_id}
            else:
                return {"reply": f"Hmm. My internal engine returned an error: {response.text}", "session_id": session_id}
        except Exception as e:
            return {"reply": f"An unexpected connection error occurred: {str(e)}", "session_id": session_id}

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

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
