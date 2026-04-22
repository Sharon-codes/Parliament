import os
import json
import re
import httpx
import asyncio
from typing import Any, Optional
from dotenv import load_dotenv

load_dotenv()

# CORE PROVIDER KEYS
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
HF_API_KEY = os.getenv("HF_API_KEY", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
HF_MODEL = os.getenv("HF_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4-turbo")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")

PROVIDER_ORDER = os.getenv("LLM_PROVIDER_ORDER", "groq,gemini,openai,anthropic").split(",")
TIMEOUT = 45.0

class LLMCallError(Exception): pass

async def _call_gemini(system_prompt: str, user_message: str, history: list[dict[str, Any]], tools: list[dict[str, Any]] = None) -> dict[str, Any]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    contents = []
    for item in history:
        contents.append({"role": "model" if item["role"] == "assistant" else "user", "parts": [{"text": item["text"]}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024}
    }
    if tools: payload["tools"] = tools

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(url, json=payload)
    
    if response.status_code >= 400:
        raise LLMCallError(f"Gemini {response.status_code}: {response.text}")
    
    data = response.json()
    parts = data["candidates"][0]["content"]["parts"]
    tool_calls = [p["functionCall"] for p in parts if "functionCall" in p]
    text = "".join([p["text"] for p in parts if "text" in p]).strip()
    return {"text": text, "tool_calls": tool_calls}

async def _call_groq(system_prompt: str, user_message: str, history: list[dict[str, Any]] = None, tools: list[dict[str, Any]] = None) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for itm in history:
            messages.append({"role": itm["role"], "content": itm["text"]})
    messages.append({"role": "user", "content": user_message})
    
    payload = {"model": GROQ_MODEL, "messages": messages, "temperature": 0.1, "max_tokens": 2048}
    
    if tools:
        GROQ_TOOL_ALLOWLIST = {
            "search_emails", "send_email", "create_doc", "search_web", 
            "launch_app", "run_local_python", "write_local_file",
            "list_emails", "read_email", "list_local_files", "read_local_file"
        }
        formatted = []
        for ts in tools:
            for d in ts.get("function_declarations", []):
                if d["name"] in GROQ_TOOL_ALLOWLIST:
                    desc = d["description"][:100] + "..." if len(d["description"]) > 100 else d["description"]
                    formatted.append({"type":"function","function":{"name":d["name"],"description":desc,"parameters":d["parameters"]}})
        payload["tools"] = formatted

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
    
    if response.status_code >= 400:
        raise LLMCallError(f"Groq {response.status_code}: {response.text}")
    
    data = response.json()
    msg = data["choices"][0]["message"]
    raw_calls = msg.get("tool_calls") or []
    return {
        "text": (msg.get("content") or "").strip(),
        "tool_calls": [{"name": rc["function"]["name"], "args": json.loads(rc["function"]["arguments"])} for rc in raw_calls if rc.get("type") == "function"]
    }

async def _call_huggingface(system_prompt: str, user_message: str, context: str) -> str:
    url = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {"inputs": f"<|system|>\n{system_prompt}\n<|user|>\n{context}\n{user_message}\n<|assistant|>\n", "parameters": {"max_new_tokens": 512, "temperature": 0.2}}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(url, headers=headers, json=payload)
    if response.status_code != 200: return "Offline."
    return response.json()[0]['generated_text'].split("<|assistant|>")[-1].strip()

def _provider_config(provider: str) -> dict[str, Any]:
    mapping = {
        "gemini": {"enabled": bool(GEMINI_API_KEY), "model": GEMINI_MODEL, "call": _call_gemini},
        "groq": {"enabled": bool(GROQ_API_KEY), "model": GROQ_MODEL, "call": _call_groq},
        "huggingface": {"enabled": False, "model": HF_MODEL, "call": _call_huggingface},
    }
    return mapping.get(provider, {"enabled": False, "model": "offline", "call": None})

def _available_providers() -> list[str]:
    return [p for p in PROVIDER_ORDER if _provider_config(p).get("enabled")]

async def llm_chat(system_prompt: str, user_message: str, history: list[dict[str, Any]] = None, tools: list[dict[str, Any]] = None, tool_executor=None, access_token: str = None, timezone: str = "UTC", profile_id: str = None, origin: str = "laptop", raw_mode: bool = False) -> str:
    INTERNAL_SYSTEM = (system_prompt or "")
    if not (raw_mode or tools is None):
        INTERNAL_SYSTEM += (
            "\n\nCRITICAL CORE DIRECTIVE:\n"
            "1. If the user asks to 'Create', 'Send', or 'Draft', you ARE THE AUTHOR. Compose the FULL content yourself. DO NOT echo instructions.\n"
            "2. CALL TOOLS IMMEDIATELY. Execute first, narrate second.\n"
            "3. You are a Sovereign OS Companion."
        )
    
    if tools is None and not raw_mode:
        INTERNAL_SYSTEM += "\n\nAUTHOR DIRECTIVE: You are an Expert Author. Write 300-800 words of professional content. Use Markdown for structure. author the content based on the prompt, DO NOT just echo it."
    
    available = _available_providers()
    optimized_order = [p for p in PROVIDER_ORDER if p in available]
    current_history = (history[-5:] if history else [])
    
    last_error = ""
    for primary in optimized_order:
        for attempt in range(2):
            try:
                if primary == "gemini":
                    try:
                        res = await _call_gemini(INTERNAL_SYSTEM, user_message, current_history, tools=tools)
                    except Exception as ge:
                        if "429" in str(ge): raise Exception("rate_limit")
                        raise ge
                    
                    for _ in range(5):
                        if not res.get("tool_calls"): return res["text"]
                        
                        tool_results = []
                        for call in res["tool_calls"]:
                            if tool_executor:
                                c_name = call.get("name") or call.get("function", {}).get("name")
                                c_args = call.get("args") or call.get("function", {}).get("arguments")
                                if isinstance(c_args, str): c_args = json.loads(c_args)
                                res_text = await tool_executor(c_name, c_args or {}, access_token, timezone, profile_id, origin=origin)
                                tool_results.append({"role": "function", "parts": [{"functionResponse": {"name": c_name, "response": {"name": c_name, "content": res_text}}}]})
                        
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
                        contents = []
                        for item in current_history: contents.append({"role": "model" if item["role"] == "assistant" else "user", "parts": [{"text": item["text"]}]})
                        contents.append({"role": "user", "parts": [{"text": user_message}]})
                        contents.append({"role": "model", "parts": [{"functionCall": {"name": c["name"], "args": c["args"]}} for c in res["tool_calls"]]})
                        contents.extend(tool_results)
                        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                            resp = await client.post(url, json={"system_instruction": {"parts": [{"text": INTERNAL_SYSTEM}]}, "contents": contents, "tools": tools, "generationConfig": {"maxOutputTokens": 2048}})
                        if resp.status_code >= 400: break
                        parts = resp.json()["candidates"][0]["content"]["parts"]
                        res = {"text": "".join([p["text"] for p in parts if "text" in p]).strip(), "tool_calls": [p["functionCall"] for p in parts if "functionCall" in p]}
                    return res["text"]

                elif primary == "groq":
                    try:
                        res = await _call_groq(INTERNAL_SYSTEM, user_message, current_history, tools=tools)
                    except Exception as e:
                        if "413" in str(e):
                            res = await _call_groq(INTERNAL_SYSTEM, user_message, history=[], tools=None)
                        else: raise e

                    accumulated_context = []
                    for _ in range(5):
                        if not res.get("tool_calls"):
                            return res["text"] or (f"Action complete. {accumulated_context[-1]}" if accumulated_context else "Done! ✨")
                        
                        tool_messages = []
                        for call in res["tool_calls"]:
                            if tool_executor:
                                result_text = await tool_executor(call["name"], call.get("args") or {}, access_token, timezone, profile_id, origin=origin)
                                tool_messages.append({"role": "tool", "content": result_text, "name": call["name"]})
                                accumulated_context.append(f"[{call['name']}] {result_text}")
                        
                        messages = [{"role": "system", "content": INTERNAL_SYSTEM}]
                        for itm in current_history: messages.append({"role": itm["role"], "content": itm["text"]})
                        messages.append({"role": "user", "content": user_message})
                        messages.append({"role": "assistant", "content": res.get("text") or "", "tool_calls": [{"id": f"c_{i}", "type": "function", "function": {"name": c["name"], "arguments": json.dumps(c.get("args") or {})}} for i, c in enumerate(res["tool_calls"])]})
                        for i, tm in enumerate(tool_messages): messages.append({"role": "tool", "tool_call_id": f"c_{i}", "content": tm["content"]})
                        
                        fmt = []
                        GROQ_TOOL_ALLOWLIST = {"search_emails", "list_emails", "send_email", "read_email", "create_doc", "search_web", "launch_app", "run_local_python", "read_local_file", "list_local_files", "create_calendar_event", "list_calendar_events", "open_url", "write_local_file"}
                        for ts in (tools or []):
                            for d in ts.get("function_declarations", []):
                                if d["name"] in GROQ_TOOL_ALLOWLIST:
                                    fmt.append({"type":"function","function":{"name":d["name"],"description":d["description"],"parameters":d["parameters"]}})
                        
                        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                            resp = await client.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {GROQ_API_KEY}"}, json={
                                "model": GROQ_MODEL, "messages": messages, "tools": fmt if fmt else None, "temperature": 0.1, "max_tokens": 1024
                            })
                        if resp.status_code >= 400: break
                        msg = resp.json()["choices"][0]["message"]
                        raw_calls = msg.get("tool_calls") or []
                        res = {"text": (msg.get("content") or "").strip(), "tool_calls": [{"name": rc["function"]["name"], "args": json.loads(rc["function"]["arguments"])} for rc in raw_calls]}
                    return res["text"]

            except Exception as e:
                err_msg = str(e)
                if "rate_limit" in err_msg.lower() or "429" in err_msg or "513" in err_msg:
                    wait_time = (attempt + 1) * 3.5 # 🦾 v121.5: Increased wait to 3.5-7s
                    print(f"DEBUG: Neural Throttling. Waiting {wait_time}s for attempt {attempt+1}...")
                    await asyncio.sleep(wait_time)
                    continue
                print(f"DEBUG: {primary} failed: {err_msg}")
                last_error = err_msg
                break

    raise LLMCallError(f"Neural Core Instability. Last Error: {last_error}")

def get_provider_info() -> dict[str, Any]:
    available = _available_providers()
    primary = available[0] if available else "fallback"
    config = _provider_config(primary)
    return {
        "provider": primary, "model": config["model"], "ready": bool(available),
        "availableProviders": [{"name": p, "model": _provider_config(p)["model"]} for p in available],
    }
