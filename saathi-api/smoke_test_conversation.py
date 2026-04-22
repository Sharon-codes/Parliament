import os
import sys
import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv

# Add saathi-api to path
sys.path.append(os.path.dirname(__file__))

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from storage import storage
from llm import llm_chat
from agent_tools import execute_tool, get_tool_definitions

USER_ID = "demo-user"

async def mock_tool_executor(name, args, access_token, timezone):
    print(f"\n[AGENT TOOL CALL] {name}({json.dumps(args)})")
    result = await execute_tool(name, args, access_token, timezone)
    print(f"[TOOL RESULT] {result}")
    return result

async def conversational_smoke_test():
    print("\n" + "="*80)
    print("  SAATHI CONVERSATIONAL SMOKE TEST: SENDING EMAIL TO KHUSHI")
    print("="*80 + "\n")

    # 1. Get Workspace Connection
    connection = storage.get_google_integration(USER_ID)
    if not connection:
        print("Error: No Google Workspace connection found in database.")
        return

    from google_workspace import ensure_valid_tokens
    try:
        connection = await ensure_valid_tokens(connection)
        access_token = connection['access_token']
        print(f"Connected as: {connection.get('google_email')}")
    except Exception as e:
        print(f"Error refreshing tokens: {e}")
        return

    # 2. Define the System Prompt (matching main.py)
    profile = storage.ensure_profile(USER_ID)
    system_prompt = (
        "You are Saathi, a gentle AI companion. "
        f"Address the user as {profile.get('full_name') or 'Friend'}. "
        f"Reply in {profile.get('language') or 'English'}. "
        "Be warm, practical, and clear. Keep answers grounded and helpful. "
        "--- AGENTIC CAPABILITIES (YOU MUST USE THESE TOOLS) ---\n"
        "RULE: ALWAYS use tools when the user asks you to DO something. NEVER give manual instructions instead.\n"
        "1. GOOGLE WORKSPACE:\n"
        "   - search_emails: Search emails by sender name or subject keyword\n"
        "   - list_emails: List recent inbox emails\n"
        "   - read_email: Read full content of a specific email by message_id\n"
        "   - send_email: Send a NEW email (to, subject, body)\n"
        "   - reply_to_email: Reply to an existing email thread\n"
        "   - create_doc: Create a Google Doc with title + content\n"
        "   - read_doc_from_url: Read a Google Doc from a URL found in an email\n"
        "   - list_calendar_events: List upcoming calendar events\n"
        "   - create_calendar_event: Create a new calendar event\n"
        "2. DESKTOP BRIDGE (you run on the user's COMPUTER):\n"
        "   - run_local_python: Write AND execute Python code on the user's computer.\n"
        "   - launch_app: Open desktop apps like 'VS Code', 'Chrome'.\n"
        "3. WEB: search_web for current information.\n"
    )

    user_message = "Mail Khushi congratulating her on her hackathon win"
    
    print(f"\n[USER PROMPT] {user_message}")
    print("\n--- AGENT THINKING ---")
    
    # Call Saathi's llm_chat which handles the multi-step tool logic
    try:
        reply = await llm_chat(
            system_prompt,
            user_message,
            history=[],
            tools=get_tool_definitions(),
            tool_executor=mock_tool_executor,
            access_token=access_token,
            timezone="Asia/Kolkata"
        )
        
        print("\n--- FINAL AGENT RESPONSE ---")
        print(reply)
        print("\n" + "="*80)
        
    except Exception as e:
        print(f"\n[CRITICAL ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(conversational_smoke_test())
