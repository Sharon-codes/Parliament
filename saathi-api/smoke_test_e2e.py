"""End-to-end smoke test: simulate a real /api/chat request with tool execution."""
import os, sys, asyncio
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from storage import storage, _now_iso
from llm import llm_chat, get_provider_info
from agent_tools import get_tool_definitions, execute_tool
from google_workspace import ensure_valid_tokens

USER_ID = "66b69c43-6d07-41cd-8058-f16a273bb7d6"

async def main():
    print("\n=== END-TO-END CHAT + TOOL TEST ===\n")
    
    # 1. Check LLM status
    info = get_provider_info()
    print(f"LLM Provider: {info['provider']} ({info['model']})")
    print(f"Ready: {info['ready']}")
    if not info['ready']:
        print("NO LLM PROVIDER AVAILABLE - check your API keys in .env")
        sys.exit(1)
    
    # 2. Get access token
    profile = storage.ensure_profile(USER_ID, "sharonmelhi365@gmail.com", "Sharon Melhi")
    connection = storage.get_google_integration(USER_ID)
    if not connection:
        print("No Google integration. Connect workspace first.")
        sys.exit(1)
    
    connection = await ensure_valid_tokens(connection)
    storage.upsert_google_integration(USER_ID, connection)
    access_token = connection["access_token"]
    tools = get_tool_definitions()
    
    # 3. Test: Ask to create a doc
    print("\n--- Test 1: Create Google Doc ---")
    system_prompt = (
        "You are Saathi, a gentle AI companion. "
        "Address the user as Sharon. "
        "Reply in English. "
        "Be warm, practical, and clear. "
        "You have access to tools. USE THEM when the user asks you to create docs, send emails, etc. "
        "IMPORTANT: If the user gives you a name but no email, use search_emails to find their email address first."
    )
    
    reply = await llm_chat(
        system_prompt,
        "Create a Google Doc explaining why cancer is very hard to cure. Keep it brief.",
        history=[],
        tools=tools,
        tool_executor=execute_tool,
        access_token=access_token,
        timezone="Asia/Kolkata"
    )
    print(f"Reply: {reply[:500]}")
    
    # 4. Test: Send email
    print("\n--- Test 2: Send Email ---")
    reply2 = await llm_chat(
        system_prompt,
        "Search for Khushi's email and send her a mail saying she is the most beautiful person.",
        history=[],
        tools=tools,
        tool_executor=execute_tool,
        access_token=access_token,
        timezone="Asia/Kolkata"
    )
    print(f"Reply: {reply2[:500]}")
    
    print("\n=== DONE ===")

asyncio.run(main())
