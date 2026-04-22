"""
hub/llm_router.py — Multi-Model LLM Router for Saathi Cloud Hub

Implements a tiered routing strategy using FREE open-weight models:

  Tier 1 (Primary):      Google Gemma 7B/27B via HF Inference API
  Tier 2 (Heavy/Fallback): Llama 3 / Mixtral via Groq Free API or HF
  Tier 3 (Edge/Offline):  Gemma 2B via local Ollama (daemon-side)

The router classifies incoming requests by complexity and routes them
to the most appropriate (and cheapest) model tier.
"""

import json
import logging
import os
import re
import time
from enum import Enum
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("saathi.llm_router")

# ── Configuration ──────────────────────────────────────────────────────────────

HF_API_KEY = os.getenv("HF_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

# Model identifiers
GEMMA_MODEL = os.getenv("GEMMA_MODEL", "google/gemma-3-12b-it")
GEMMA_FALLBACK = os.getenv("GEMMA_FALLBACK", "google/gemma-2-9b-it")
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "meta-llama/Llama-3.3-70B-Instruct")
MIXTRAL_MODEL = os.getenv("MIXTRAL_MODEL", "mistralai/Mixtral-8x7B-Instruct-v0.1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "gemma2:2b")  # Ollama model name
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

TIMEOUT = httpx.Timeout(120.0, connect=15.0)
MAX_RETRIES = 2


# ── Task Complexity Classification ─────────────────────────────────────────────

class TaskTier(str, Enum):
    """Route requests to the appropriate model tier based on complexity."""
    SIMPLE = "simple"         # Tier 1: Gemma — greetings, intents, simple Q&A
    STANDARD = "standard"     # Tier 1: Gemma — RAG, command gen, classification
    COMPLEX = "complex"       # Tier 2: Llama/Mixtral — multi-step planning
    EDGE = "edge"             # Tier 3: Local Gemma 2B — offline fallback


# Complexity heuristics
_COMPLEX_PATTERNS = [
    r"(plan|design|architect|refactor|debug|analyze)\s+(a |the |this )?",
    r"(step[- ]by[- ]step|multi[- ]step|chain of thought)",
    r"(traceback|error|exception|stack trace)\s*:",
    r"(compare|contrast|evaluate)\s+(multiple|several|different)",
    r"write\s+(a )?(complete|full|comprehensive|detailed)",
]

_SIMPLE_PATTERNS = [
    r"^(hi|hello|hey|thanks|bye|ok|yes|no|good)\b",
    r"^what (is|are|was|were) ",
    r"^(open|run|execute|start|stop|list|show|check)\b",
    r"^(remind|set|create|send|reply)\b",
]


def classify_complexity(message: str) -> TaskTier:
    """Classify the complexity of a user message to determine routing tier."""
    lower = message.lower().strip()

    # Check for complex patterns first
    for pattern in _COMPLEX_PATTERNS:
        if re.search(pattern, lower):
            return TaskTier.COMPLEX

    # Check for simple patterns
    for pattern in _SIMPLE_PATTERNS:
        if re.search(pattern, lower):
            return TaskTier.SIMPLE

    # Default to standard
    return TaskTier.STANDARD


# ── LLM Provider Implementations ──────────────────────────────────────────────

async def _call_hf_inference(
    model: str,
    system_prompt: str,
    user_message: str,
    history: list[dict[str, Any]] | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> dict[str, Any]:
    """Call Hugging Face Inference API with chat completion format."""
    if not HF_API_KEY:
        raise RuntimeError("HF_API_KEY not configured")

    url = f"https://router.huggingface.co/hf-inference/models/{model}/v1/chat/completions"

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for item in history:
            role = "assistant" if item.get("role") == "assistant" else "user"
            messages.append({"role": role, "content": item.get("text", "")})
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(url, json=payload, headers=headers)

    if response.status_code == 429:
        raise RuntimeError(f"HF Rate Limited (429) on {model}")
    if response.status_code == 503:
        raise RuntimeError(f"HF Model Loading (503) on {model} — try again in 30s")
    if response.status_code >= 400:
        raise RuntimeError(f"HF Error {response.status_code}: {response.text[:300]}")

    data = response.json()

    # Parse response
    try:
        text = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError):
        text = str(data)

    return {"text": text, "model": model, "provider": "huggingface"}


async def _call_groq(
    system_prompt: str,
    user_message: str,
    history: list[dict[str, Any]] | None = None,
    max_tokens: int = 8192,
    temperature: float = 0.1,
) -> dict[str, Any]:
    """Call Groq API for heavy reasoning with Llama 3."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not configured")

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for item in history:
            role = "assistant" if item.get("role") == "assistant" else "user"
            messages.append({"role": role, "content": item.get("text", "")})
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
        )

    if response.status_code == 429:
        raise RuntimeError("Groq Rate Limited (429)")
    if response.status_code >= 400:
        raise RuntimeError(f"Groq Error {response.status_code}: {response.text[:300]}")

    data = response.json()
    text = data["choices"][0]["message"]["content"].strip()
    return {"text": text, "model": GROQ_MODEL, "provider": "groq"}


async def _call_ollama(
    system_prompt: str,
    user_message: str,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Call local Ollama instance for edge/offline inference."""
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for item in history:
            role = "assistant" if item.get("role") == "assistant" else "user"
            messages.append({"role": role, "content": item.get("text", "")})
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": LOCAL_MODEL,
        "messages": messages,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
        response = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)

    if response.status_code >= 400:
        raise RuntimeError(f"Ollama Error {response.status_code}: {response.text[:200]}")

    data = response.json()
    text = data.get("message", {}).get("content", "").strip()
    return {"text": text, "model": LOCAL_MODEL, "provider": "ollama"}


# ── Intent Classification ─────────────────────────────────────────────────────

# Intent taxonomy for daemon command routing
INTENT_LABELS = [
    "execute_script",       # run a script / code
    "file_operation",       # list / read / write files
    "system_info",          # sysinfo, processes
    "app_launch",           # open an application
    "system_control",       # lock, shutdown, restart
    "general_question",     # Q&A, chitchat
    "complex_reasoning",    # multi-step analysis
    "workspace_action",     # Google Workspace (email/cal/docs)
]


async def classify_intent(message: str) -> dict[str, Any]:
    """
    Use Gemma to classify the user's intent from natural language.
    Returns: {"intent": str, "confidence": float, "parameters": dict}
    """
    system = (
        "You are an intent classifier. Given a user message, classify it into "
        "exactly ONE of these intents:\n"
        + "\n".join(f"- {label}" for label in INTENT_LABELS)
        + "\n\nRespond ONLY with valid JSON: "
        '{\"intent\": \"<intent>\", \"confidence\": <0.0-1.0>, \"parameters\": {<extracted params>}}'
    )

    try:
        result = await _call_hf_inference(
            GEMMA_MODEL, system, message, temperature=0.1, max_tokens=256
        )
        text = result["text"]

        # Extract JSON from response
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            return {
                "intent": parsed.get("intent", "general_question"),
                "confidence": min(1.0, max(0.0, float(parsed.get("confidence", 0.5)))),
                "parameters": parsed.get("parameters", {}),
                "model": result.get("model", GEMMA_MODEL),
            }
    except Exception as exc:
        logger.warning(f"Intent classification failed: {exc}")

    # Fallback: rule-based classification
    return _rule_based_intent(message)


def _rule_based_intent(message: str) -> dict[str, Any]:
    """Fallback rule-based intent classifier when LLM is unavailable."""
    lower = message.lower()
    rules = [
        (r"(run|execute|start)\b.*(code|script|program|project)", "execute_script"),
        (r"(list|show|read|open|create|write|delete)\b.*(files?|folder|dir)", "file_operation"),
        (r"(cpu|ram|memory|disk|process|system\s+info)", "system_info"),
        (r"(open|launch|start)\b.*(app|chrome|vscode|code|browser)", "app_launch"),
        (r"(lock|shutdown|restart|sleep|hibernate)", "system_control"),
        (r"(email|mail|calendar|event|doc|document)", "workspace_action"),
        (r"(plan|design|architect|analyze|debug|refactor)", "complex_reasoning"),
    ]

    for pattern, intent in rules:
        if re.search(pattern, lower):
            return {
                "intent": intent,
                "confidence": 0.7,
                "parameters": {},
                "model": "rule_based",
            }

    return {
        "intent": "general_question",
        "confidence": 0.5,
        "parameters": {},
        "model": "rule_based",
    }


# ── Execution Payload Generator ───────────────────────────────────────────────

async def generate_execution_payload(
    message: str,
    intent: dict[str, Any],
    system_context: str = "",
) -> dict[str, Any]:
    """
    Convert a classified intent + natural language into a structured
    JSON execution payload for the Edge Daemon.
    """
    system = (
        "You are a command generator for the Saathi daemon. Convert user intent into "
        "a JSON execution payload.\n\n"
        "The payload MUST follow this schema:\n"
        "{\n"
        '  "action": "<daemon_command>",\n'
        '  "args": {<command-specific arguments>},\n'
        '  "cwd": "<working directory or null>",\n'
        '  "timeout": <seconds or null>,\n'
        '  "stream": <true for long-running commands>\n'
        "}\n\n"
        "Available daemon commands:\n"
        "- run_script: {args: {script: 'path.py', extra_args: []}}\n"
        "- list_files: {args: {path: '.'}}\n"
        "- read_file: {args: {path: 'file.py'}}\n"
        "- write_file: {args: {path: 'file.py', content: '...'}}\n"
        "- shell_exec: {args: {command: 'pip install ...'}}\n"
        "- sysinfo: {args: {}}\n"
        "- processes: {args: {}}\n"
        "- app_launch: {args: {app: 'vscode', file: null}}\n"
        "- system_control: {args: {action: 'lock|shutdown|restart'}}\n\n"
        f"Intent: {intent['intent']}\n"
        f"Parameters extracted: {json.dumps(intent.get('parameters', {}))}\n"
        f"Context: {system_context}\n\n"
        "Respond with ONLY the JSON payload, no other text."
    )

    try:
        result = await _call_hf_inference(
            GEMMA_MODEL, system, message, temperature=0.1, max_tokens=512
        )
        text = result["text"]
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as exc:
        logger.warning(f"Payload generation failed: {exc}")

    # Fallback: construct payload from intent directly
    return _fallback_payload(intent)


def _fallback_payload(intent: dict) -> dict[str, Any]:
    """Build a minimal payload from intent classification when LLM is down."""
    action_map = {
        "execute_script": {"action": "run_script", "args": {"script": "main.py"}},
        "file_operation": {"action": "list_files", "args": {"path": "."}},
        "system_info": {"action": "sysinfo", "args": {}},
        "app_launch": {"action": "app_launch", "args": {"app": "vscode"}},
        "system_control": {"action": "system_control", "args": {"action": "lock"}},
    }
    return action_map.get(
        intent["intent"],
        {"action": "echo", "args": {"message": "Unable to parse command"}},
    )


# ── Main Router Class ─────────────────────────────────────────────────────────

class LLMRouter:
    """
    Multi-model router that selects the optimal free LLM based on task complexity.

    Routing Strategy:
      1. Classify message complexity → TaskTier
      2. Route SIMPLE/STANDARD → Gemma (HF Inference)
      3. Route COMPLEX → Llama 3/Mixtral (Groq or HF)
      4. On failure → cascade to next tier
      5. Final fallback → local Ollama (Gemma 2B) if available
    """

    def __init__(self):
        self.call_count = 0
        self.tier_stats = {tier: 0 for tier in TaskTier}
        self.errors: list[dict] = []
        self._last_hf_error_time = 0

    @property
    def stats(self) -> dict:
        return {
            "total_calls": self.call_count,
            "tier_distribution": {k.value: v for k, v in self.tier_stats.items()},
            "recent_errors": self.errors[-5:],
            "hf_available": HF_API_KEY != "",
            "groq_available": GROQ_API_KEY != "",
            "models": {
                "primary": GEMMA_MODEL,
                "fallback_hf": GEMMA_FALLBACK,
                "heavy": GROQ_MODEL,
                "local": LOCAL_MODEL,
            },
        }

    async def route(
        self,
        system_prompt: str,
        user_message: str,
        history: list[dict[str, Any]] | None = None,
        force_tier: TaskTier | None = None,
    ) -> dict[str, Any]:
        """
        Route a message to the appropriate model tier and return the response.

        Returns: {"text": str, "model": str, "provider": str, "tier": str}
        """
        self.call_count += 1
        tier = force_tier or classify_complexity(user_message)
        self.tier_stats[tier] += 1

        logger.info(f"Routing [{self.call_count}] tier={tier.value} msg='{user_message[:60]}...'")

        # Build the cascade based on tier
        if tier == TaskTier.COMPLEX:
            cascade = [
                ("groq", lambda: _call_groq(system_prompt, user_message, history)),
                ("hf_llama", lambda: _call_hf_inference(LLAMA_MODEL, system_prompt, user_message, history)),
                ("hf_mixtral", lambda: _call_hf_inference(MIXTRAL_MODEL, system_prompt, user_message, history)),
                ("hf_gemma", lambda: _call_hf_inference(GEMMA_MODEL, system_prompt, user_message, history)),
                ("ollama", lambda: _call_ollama(system_prompt, user_message, history)),
            ]
        elif tier == TaskTier.EDGE:
            cascade = [
                ("ollama", lambda: _call_ollama(system_prompt, user_message, history)),
                ("hf_gemma", lambda: _call_hf_inference(GEMMA_MODEL, system_prompt, user_message, history)),
            ]
        else:
            # SIMPLE and STANDARD → Gemma first
            cascade = [
                ("hf_gemma", lambda: _call_hf_inference(GEMMA_MODEL, system_prompt, user_message, history)),
                ("hf_gemma_fallback", lambda: _call_hf_inference(GEMMA_FALLBACK, system_prompt, user_message, history)),
                ("groq", lambda: _call_groq(system_prompt, user_message, history)),
                ("hf_mixtral", lambda: _call_hf_inference(MIXTRAL_MODEL, system_prompt, user_message, history)),
                ("ollama", lambda: _call_ollama(system_prompt, user_message, history)),
            ]

        last_err = ""
        for provider_name, call_fn in cascade:
            try:
                result = await call_fn()
                result["tier"] = tier.value
                result["routed_via"] = provider_name
                return result
            except Exception as exc:
                last_err = f"{provider_name}: {exc}"
                self.errors.append({
                    "provider": provider_name,
                    "error": str(exc),
                    "time": time.time(),
                })
                logger.warning(f"Provider {provider_name} failed: {exc}")
                continue

        # All providers exhausted
        return {
            "text": (
                "Saathi is temporarily running in offline mode. "
                f"All model providers are unavailable. Last error: {last_err}"
            ),
            "model": "offline",
            "provider": "none",
            "tier": tier.value,
            "routed_via": "fallback",
        }

    async def classify_and_route(
        self,
        message: str,
        system_context: str = "",
    ) -> dict[str, Any]:
        """
        Full pipeline: classify intent → generate payload → route to model.
        Returns the intent, payload, and natural-language response.
        """
        # Step 1: Classify intent
        intent = await classify_intent(message)

        # Step 2: If it's a daemon-actionable intent, generate an execution payload
        payload = None
        if intent["intent"] not in ("general_question", "complex_reasoning"):
            payload = await generate_execution_payload(message, intent, system_context)

        # Step 3: Generate a natural language response
        system_prompt = (
            "You are Saathi, a gentle and capable AI companion. "
            "Be warm, practical, and clear. "
            f"The user's intent has been classified as: {intent['intent']}. "
        )
        if payload:
            system_prompt += (
                f"A daemon execution payload has been generated: {json.dumps(payload)}. "
                "Confirm what action you're taking for the user."
            )

        response = await self.route(system_prompt, message)

        return {
            "intent": intent,
            "payload": payload,
            "response": response,
        }


# ── Singleton ──────────────────────────────────────────────────────────────────

router = LLMRouter()
