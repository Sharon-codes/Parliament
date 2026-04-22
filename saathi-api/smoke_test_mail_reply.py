"""Smoke test: Read unread emails, summarize them, and reply intelligently."""
import os, sys, asyncio
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from storage import storage
from llm import llm_chat, get_provider_info
from agent_tools import get_tool_definitions, execute_tool
from google_workspace import ensure_valid_tokens

USER_ID = "66b69c43-6d07-41cd-8058-f16a273bb7d6"

async def main():
    print("\n=== SMOKE TEST: Read Unread Mail -> Summarize -> Reply ===\n")

    info = get_provider_info()
    print(f"LLM: {info['provider']} ({info['model']})")

    profile = storage.ensure_profile(USER_ID, "sharonmelhi365@gmail.com", "Sharon Melhi")
    connection = storage.get_google_integration(USER_ID)
    if not connection:
        print("[FAIL] No Google integration")
        sys.exit(1)

    connection = await ensure_valid_tokens(connection)
    storage.upsert_google_integration(USER_ID, connection)
    access_token = connection["access_token"]
    tools = get_tool_definitions()

    system_prompt = (
        "You are Saathi, an AI companion. Address the user as Sharon. Reply in English. "
        "You MUST use tools when the user asks you to do things. "
        "CRITICAL: When you search for someone's email address, use the EXACT email address from results. "
        "When replying to an email, use reply_to_email with the correct to, subject, thread_id, in_reply_to, and references from the email details."
    )

    # STEP 1: List recent unread emails
    print("--- Step 1: List recent emails ---")
    reply1 = await llm_chat(
        system_prompt,
        "List my 5 most recent emails. For each one, tell me who it's from, the subject, and a brief summary.",
        history=[],
        tools=tools,
        tool_executor=execute_tool,
        access_token=access_token,
        timezone="Asia/Kolkata"
    )
    print(f"Saathi: {reply1}\n")

    # STEP 2: Read the first email in detail
    print("--- Step 2: Read the most interesting email ---")
    history_so_far = [
        {"role": "user", "text": "List my 5 most recent emails."},
        {"role": "assistant", "text": reply1},
    ]
    reply2 = await llm_chat(
        system_prompt,
        "Read the first email in full detail. Tell me exactly what it says and if it needs a reply.",
        history=history_so_far,
        tools=tools,
        tool_executor=execute_tool,
        access_token=access_token,
        timezone="Asia/Kolkata"
    )
    print(f"Saathi: {reply2}\n")

    # STEP 3: Reply to that email
    print("--- Step 3: Draft and send a reply ---")
    history_so_far.extend([
        {"role": "user", "text": "Read the first email in full detail."},
        {"role": "assistant", "text": reply2},
    ])
    reply3 = await llm_chat(
        system_prompt,
        "Now reply to that email with a warm, professional response. Keep it short and friendly. Actually send it using reply_to_email.",
        history=history_so_far,
        tools=tools,
        tool_executor=execute_tool,
        access_token=access_token,
        timezone="Asia/Kolkata"
    )
    print(f"Saathi: {reply3}\n")

    print("=" * 50)
    print("FULL PIPELINE COMPLETE")

asyncio.run(main())
