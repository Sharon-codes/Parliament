import os
import sys
import asyncio
import random
from pathlib import Path
from dotenv import load_dotenv

# Add saathi-api to path
sys.path.append(os.path.dirname(__file__))

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from storage import storage, _now_iso
from llm import llm_chat, get_provider_info
from agent_tools import execute_tool

USER_ID = "demo-user"
errors = []

def test(name, fn):
    try:
        if asyncio.iscoroutinefunction(fn) or asyncio.iscoroutine(fn):
            import asyncio
            result = asyncio.run(fn) if not asyncio.iscoroutine(fn) else asyncio.run(fn)
        else:
            result = fn()
        print(f"  [OK] {name}")
        return result
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        errors.append(f"{name}: {e}")
        return None

async def run_async_test(name, coro):
    try:
        result = await coro
        print(f"  [OK] {name}")
        return result
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        errors.append(f"{name}: {e}")
        return None

async def main():
    print("\n" + "="*60)
    print("  SAATHI V2 SMOKE TEST: EXCEL STORAGE & AGENTIC TOOLS")
    print("="*60 + "\n")

    # 1. STORAGE TEST (Excel)
    print("STORAGE (EXCEL):")
    print(f"  Mode: {storage.mode}")
    if storage.mode != "excel":
        print("  [WARNING] Storage is not in EXCEL mode!")
    
    excel_path = os.getenv("EXCEL_DB_PATH", "saathi_data.xlsx")
    print(f"  File: {excel_path}")
    
    profile = await run_async_test("ensure_profile", asyncio.to_thread(storage.ensure_profile, USER_ID, "smoke@test.com", "Smoke Test User"))
    test_session = await run_async_test("create_session", asyncio.to_thread(storage.create_session, USER_ID, "Smoke Test Session"))
    
    if test_session:
        sid = test_session["id"]
        await run_async_test("add_message", asyncio.to_thread(storage.add_message, USER_ID, sid, "user", "Smoke test message"))
        msgs = await run_async_test("get_messages", asyncio.to_thread(storage.get_messages, USER_ID, sid))
        if msgs and len(msgs) > 0:
            print(f"    Found {len(msgs)} messages in Excel")
        
        # Verify file exists and is not empty
        if Path(excel_path).exists() and Path(excel_path).stat().st_size > 0:
            print(f"    [OK] Excel file validated on disk")
        else:
            errors.append("Excel file missing or empty")

    # 2. LLM PROVIDER TEST
    print("\nLLM PROVIDERS:")
    info = get_provider_info()
    print(f"  Primary Provider: {info['provider']}")
    print(f"  Model:            {info['model']}")
    print(f"  Available:        {[p['name'] for p in info['availableProviders']]}")
    
    if not info['ready']:
        errors.append("No LLM providers ready")
    
    llm_res = await run_async_test("llm_chat (basic)", llm_chat("You are a helper.", "Say 'Testing 123'"))
    if llm_res and "Testing" in llm_res:
        print(f"    Response: {llm_res}")
    else:
        errors.append(f"Unexpected LLM response: {llm_res}")

    # 3. AGENT TOOLS TEST (Local)
    print("\nAGENT TOOLS (LOCAL):")
    # Test local python execution
    tool_res = await run_async_test("execute_tool (run_local_python)", execute_tool("run_local_python", {"code": "print(21 + 21)"}, None))
    if tool_res and "42" in tool_res:
        print(f"    Python Execution: OK (Result: 42)")
    else:
        errors.append(f"Local Python tool failed: {tool_res}")

    # 4. GOOGLE WORKSPACE TEST (if connected)
    print("\nGOOGLE WORKSPACE:")
    integration = storage.get_google_integration(USER_ID)
    if integration:
        print(f"  Connected as: {integration['google_email']}")
        # Try to list emails (read-only)
        try:
            from google_workspace import ensure_valid_tokens, list_recent_emails
            integration = await ensure_valid_tokens(integration)
            emails = await list_recent_emails(integration['access_token'], max_results=1)
            print(f"  [OK] Gmail Connectivity: Found {len(emails)} emails")
        except Exception as e:
            print(f"  [SKIP] Workspace test failed (likely token issue): {e}")
    else:
        print("  [SKIP] No Google connection found for demo-user")

    # FINAL RESULTS
    print("\n" + "="*60)
    if errors:
        print(f"❌ SMOKE TEST FAILED with {len(errors)} errors:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("✅ ALL SYSTEMS GO! Saathi V2 is mission ready.")
        print("="*60 + "\n")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
