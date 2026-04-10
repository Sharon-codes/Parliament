"""
llm.py — Saathi LLM Provider Layer
Supports Gemini (default/free), Anthropic Claude, and OpenAI.
Priority: whichever key is set in .env first wins.
No Ollama required.

Set ONE of these in saathi-api/.env:
    GEMINI_API_KEY=...       ← Google AI Studio (free) — https://aistudio.google.com/app/apikey
    ANTHROPIC_API_KEY=...    ← Claude API
    OPENAI_API_KEY=...       ← OpenAI GPT-4o

If none are set, Saathi falls back to a built-in rule-based responder so
the app still works without any API key during demos.
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

# ── Detect which provider to use ─────────────────────────────────────────────
_GEMINI_KEY    = os.getenv("GEMINI_API_KEY", "").strip()
_ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
_OPENAI_KEY    = os.getenv("OPENAI_API_KEY", "").strip()

if _GEMINI_KEY:
    PROVIDER = "gemini"
elif _ANTHROPIC_KEY:
    PROVIDER = "anthropic"
elif _OPENAI_KEY:
    PROVIDER = "openai"
else:
    PROVIDER = "fallback"

print(f"[Saathi LLM] Provider: {PROVIDER.upper()}")

# ── Model names (override via .env if needed) ─────────────────────────────────
GEMINI_MODEL    = os.getenv("GEMINI_MODEL",    "gemini-2.0-flash")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")
OPENAI_MODEL    = os.getenv("OPENAI_MODEL",    "gpt-4o-mini")

TIMEOUT = httpx.Timeout(120.0, connect=10.0)


# ── Gemini ────────────────────────────────────────────────────────────────────

async def _call_gemini(system_prompt: str, user_message: str, context: str) -> str:
    """
    Google Gemini via REST API.
    Free tier: 15 RPM / 1M TPM on gemini-2.0-flash.
    """
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={_GEMINI_KEY}"
    )

    # Gemini uses a `contents` array with roles. We merge system + context into
    # the first user turn since Gemini Flash supports a system_instruction field.
    payload = {
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"{context}\n\nUser: {user_message}"}]
            }
        ],
        "generationConfig": {
            "temperature": 0.75,
            "maxOutputTokens": 1024,
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
        ]
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


# ── Anthropic Claude ──────────────────────────────────────────────────────────

async def _call_anthropic(system_prompt: str, user_message: str, context: str) -> str:
    """
    Anthropic Messages API.
    claude-3-5-haiku is fast and low-cost.
    """
    headers = {
        "x-api-key": _ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 1024,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": f"{context}\n\nUser: {user_message}"}
        ]
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post("https://api.anthropic.com/v1/messages",
                                 headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"].strip()


# ── OpenAI ────────────────────────────────────────────────────────────────────

async def _call_openai(system_prompt: str, user_message: str, context: str) -> str:
    """OpenAI Chat Completions API (gpt-4o-mini is cheap and fast)."""
    headers = {
        "Authorization": f"Bearer {_OPENAI_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system",    "content": system_prompt},
            {"role": "user",      "content": f"{context}\n\nUser: {user_message}"}
        ],
        "max_tokens": 1024,
        "temperature": 0.75,
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post("https://api.openai.com/v1/chat/completions",
                                 headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


# ── Fallback (no API key) ─────────────────────────────────────────────────────

_FALLBACK_RESPONSES = {
    "hello": "Peace and welcome. I'm Saathi, your personal AI companion. To unlock my full capabilities, please add a GEMINI_API_KEY to saathi-api/.env",
    "help":  "I can help with research, reminders, memory, and remote control. Add a GEMINI_API_KEY to .env to enable AI responses.",
}

async def _call_fallback(system_prompt: str, user_message: str, context: str) -> str:
    msg_l = user_message.lower()
    for kw, resp in _FALLBACK_RESPONSES.items():
        if kw in msg_l:
            return resp
    return (
        "✦ Saathi is running in offline mode. To enable AI responses, add one of these to "
        "`saathi-api/.env`:\n\n"
        "```\nGEMINI_API_KEY=your_key_here\n```\n\n"
        "Get a **free** Gemini key at https://aistudio.google.com/app/apikey"
    )


# ── Public interface ──────────────────────────────────────────────────────────

async def llm_chat(system_prompt: str, user_message: str, context: str = "") -> str:
    """
    Call the configured LLM provider and return the text response.
    Falls back gracefully if the API call fails.
    """
    try:
        if PROVIDER == "gemini":
            return await _call_gemini(system_prompt, user_message, context)
        elif PROVIDER == "anthropic":
            return await _call_anthropic(system_prompt, user_message, context)
        elif PROVIDER == "openai":
            return await _call_openai(system_prompt, user_message, context)
        else:
            return await _call_fallback(system_prompt, user_message, context)
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 429:
            return "⚠ Rate limit reached. Please wait a moment and try again."
        if status in (401, 403):
            return f"⚠ API key error ({status}). Please check your `.env` file."
        return f"⚠ LLM API error {status}: {e.response.text[:200]}"
    except httpx.ConnectError:
        return "⚠ Could not reach the AI provider. Check your internet connection."
    except Exception as e:
        return f"⚠ Unexpected error: {str(e)}"


def get_provider_info() -> dict:
    """Returns current provider info for the settings/status endpoint."""
    model_map = {
        "gemini":    GEMINI_MODEL,
        "anthropic": ANTHROPIC_MODEL,
        "openai":    OPENAI_MODEL,
        "fallback":  "none (offline mode)",
    }
    return {
        "provider": PROVIDER,
        "model":    model_map.get(PROVIDER, "unknown"),
        "ready":    PROVIDER != "fallback",
    }
