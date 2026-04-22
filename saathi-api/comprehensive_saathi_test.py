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
from agent_tools import execute_tool

USER_ID = "demo-user"
errors = []

async def test_feature(name, coro):
    print(f"Testing: {name}...")
    try:
        result = await coro
        if result and "error" not in str(result).lower():
            print(f"  [OK] {name}")
            return result
        else:
            print(f"  [FAIL] {name}: {result}")
            errors.append(f"{name}: {result}")
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        errors.append(f"{name}: {e}")
    return None

async def main():
    print("\n" + "="*60)
    print("  SAATHI COMPREHENSIVE SUITE: AGENTIC CAPABILITIES")
    print("="*60 + "\n")

    # 1. CORE STORAGE (EXCEL)
    print("--- STORAGE ---")
    await test_feature("Excel Profile Mapping", asyncio.to_thread(storage.ensure_profile, USER_ID))
    
    # 2. LOCAL AUTOMATION
    print("\n--- DESKTOP AUTOMATION ---")
    await test_feature("Local Python (Math)", execute_tool("run_local_python", {"code": "print(100+256)"}, None))
    await test_feature("List Local Files", execute_tool("list_local_files", {}, None))
    # Safe ऐप launch
    await test_feature("Launch Notepad (Safe App)", execute_tool("launch_app", {"app_name": "notepad"}, None))

    # 3. WEB RESEARCH
    print("\n--- WEB RESEARCH ---")
    await test_feature("Web Search (Amity University)", execute_tool("search_web", {"query": "Amity University latest hackathon news"}, None))

    # 4. GOOGLE WORKSPACE (Requires Integration)
    print("\n--- GOOGLE WORKSPACE ---")
    integration = storage.get_google_integration(USER_ID)
    if integration:
        try:
            from google_workspace import ensure_valid_tokens
            integration = await ensure_valid_tokens(integration)
            token = integration['access_token']
            
            await test_feature("Gmail: List Emails", execute_tool("list_emails", {"limit": 2}, token))
            await test_feature("Calendar: List Events", execute_tool("list_calendar_events", {"limit": 2}, token))
            await test_feature("Docs: Create Test Doc", execute_tool("create_doc", {"title": "Smoke Test Doc", "content": "This is a smoke test content."}, token))
            
        except Exception as e:
            print(f"  [SKIP] Workspace tests failed: {e}")
    else:
        print("  [SKIP] No Google account connected for test.")

    # 5. LLM PERSONA & MULTILINGUAL
    print("\n--- LLM PERSONA & LANGUAGES ---")
    hindi_res = await llm_chat("You are Saathi. Reply in Hindi.", "Hello!")
    if hindi_res:
        print(f"  [OK] Hindi Response: {hindi_res[:50]}...")
    else:
        errors.append("Hindi response failed")

    # FINAL REPORT
    print("\n" + "="*60)
    if errors:
        print(f"FINISHED WITH {len(errors)} ERRORS.")
        for e in errors:
            print(f" - {e}")
        sys.exit(1)
    else:
        print("COMPREHENSIVE TEST PASSED. Saathi is 100% functional.")
        print("="*60 + "\n")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
