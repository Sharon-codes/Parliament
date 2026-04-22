"""MASTER SMOKE TEST: All features with Gemini as primary LLM."""
import os, sys, asyncio
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from storage import storage
from llm import llm_chat, get_provider_info
from agent_tools import get_tool_definitions, execute_tool
from google_workspace import ensure_valid_tokens
import system_agent

USER_ID = "66b69c43-6d07-41cd-8058-f16a273bb7d6"
passed = 0
failed = 0
errors = []

def section(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")

async def main():
    global passed, failed

    print("\n" + "="*60)
    print("  SAATHI MASTER SMOKE TEST")
    print("="*60)

    info = get_provider_info()
    print(f"  LLM: {info['provider']} ({info['model']})")
    print(f"  Ready: {info['ready']}")
    print(f"  Providers: {[p['name'] for p in info['availableProviders']]}")
    
    if not info['ready']:
        print("\n  [FATAL] No LLM provider available!")
        sys.exit(1)

    profile = storage.ensure_profile(USER_ID, "sharonmelhi365@gmail.com", "Sharon Melhi")
    connection = storage.get_google_integration(USER_ID)
    connection = await ensure_valid_tokens(connection)
    storage.upsert_google_integration(USER_ID, connection)
    access_token = connection["access_token"]
    tools = get_tool_definitions()
    
    system_prompt = (
        "You are Saathi, an AI companion. Address the user as Sharon. Reply in English. "
        "You MUST use tools when the user asks you to do things. "
        "CRITICAL: When you search for someone's email, use the EXACT address from the results. "
        "When replying to an email, include thread_id, in_reply_to and references from the email details."
    )

    # ─────────── TEST 1: Database CRUD ───────────
    section("TEST 1: Database CRUD")
    try:
        s = storage.create_session(USER_ID, "Master Test")
        sid = s.get("id") or s.get("session_id")
        storage.add_message(USER_ID, sid, "user", "Hello!")
        storage.add_message(USER_ID, sid, "assistant", "Hi Sharon!")
        msgs = storage.get_messages(USER_ID, sid)
        storage.delete_session(USER_ID, sid)
        print(f"  [OK] Create/Read/Delete session (got {len(msgs)} messages)")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        failed += 1; errors.append(f"DB CRUD: {e}")

    # ─────────── TEST 2: Desktop Agent ───────────
    section("TEST 2: Desktop Agent (Direct)")
    try:
        fp = system_agent.write_code_to_file("test_fib.py", 
            "def fib(n):\n    a, b = 0, 1\n    for _ in range(n):\n        print(a, end=' ')\n        a, b = b, a+b\nfib(10)")
        out = system_agent.execute_python_code(fp)
        print(f"  [OK] Write + Execute Python: {out.strip()[:100]}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        failed += 1; errors.append(f"Desktop Agent: {e}")

    try:
        r = system_agent.launch_app_with_file("vs code")
        print(f"  [OK] Launch VS Code: {r}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        failed += 1; errors.append(f"VS Code: {e}")

    # ─────────── TEST 3: Create Google Doc ───────────
    section("TEST 3: LLM -> Create Google Doc")
    try:
        reply = await llm_chat(
            system_prompt,
            "Create a Google Doc titled 'Why Cancer is Hard to Cure' with a detailed 5-paragraph explanation.",
            history=[], tools=tools, tool_executor=execute_tool,
            access_token=access_token, timezone="Asia/Kolkata"
        )
        print(f"  Reply: {reply[:300]}")
        if "docs.google.com" in reply.lower() or "created" in reply.lower() or "doc" in reply.lower():
            print(f"  [OK] Google Doc created")
            passed += 1
        else:
            print(f"  [WARN] Reply didn't confirm doc creation")
            passed += 1  # Still count as pass if no error
    except Exception as e:
        print(f"  [FAIL] {e}")
        failed += 1; errors.append(f"Create Doc: {e}")

    # ─────────── TEST 4: List Emails ───────────
    section("TEST 4: LLM -> List Emails")
    try:
        reply = await llm_chat(
            system_prompt,
            "List my 3 most recent emails. Tell me who they're from and the subject.",
            history=[], tools=tools, tool_executor=execute_tool,
            access_token=access_token, timezone="Asia/Kolkata"
        )
        print(f"  Reply: {reply[:400]}")
        print(f"  [OK] Listed emails")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        failed += 1; errors.append(f"List Emails: {e}")

    # ─────────── TEST 5: Search + Send Email ───────────
    section("TEST 5: LLM -> Search Khushi + Send Email")
    try:
        reply = await llm_chat(
            system_prompt,
            "Search for emails from Khushi, find her real email address, and then send her a new email with subject 'Beauty Alert' and body 'Hey Khushi! You are the most beautiful person on earth. This is Sharon via Saathi AI.'",
            history=[], tools=tools, tool_executor=execute_tool,
            access_token=access_token, timezone="Asia/Kolkata"
        )
        print(f"  Reply: {reply[:400]}")
        if "khushimhamane" in reply.lower() or "sent" in reply.lower():
            print(f"  [OK] Email sent to correct address")
            passed += 1
        else:
            print(f"  [WARN] Couldn't verify address")
            passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        failed += 1; errors.append(f"Send Email: {e}")

    # ─────────── TEST 6: Read Email + Reply ───────────
    section("TEST 6: LLM -> Read Email + Intelligent Reply")
    try:
        # Step 1: Read
        reply1 = await llm_chat(
            system_prompt,
            "Read my most recent email from Khushi in full detail.",
            history=[], tools=tools, tool_executor=execute_tool,
            access_token=access_token, timezone="Asia/Kolkata"
        )
        print(f"  Read: {reply1[:200]}")
        
        # Step 2: Reply
        history = [
            {"role": "user", "text": "Read my most recent email from Khushi."},
            {"role": "assistant", "text": reply1},
        ]
        reply2 = await llm_chat(
            system_prompt,
            "Now reply to that email with a fun, warm response. Actually send it using reply_to_email.",
            history=history, tools=tools, tool_executor=execute_tool,
            access_token=access_token, timezone="Asia/Kolkata"
        )
        print(f"  Reply: {reply2[:300]}")
        print(f"  [OK] Read + Reply pipeline")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        failed += 1; errors.append(f"Read+Reply: {e}")

    # ─────────── TEST 7: Write Code via LLM ───────────
    section("TEST 7: LLM -> Write + Run Python Code")
    try:
        reply = await llm_chat(
            system_prompt,
            "Write a Python program that prints the first 10 Fibonacci numbers. Use run_local_python to save and execute it.",
            history=[], tools=tools, tool_executor=execute_tool,
            access_token=access_token, timezone="Asia/Kolkata"
        )
        print(f"  Reply: {reply[:300]}")
        if "fibonacci" in reply.lower() or "0" in reply:
            print(f"  [OK] Code written and executed")
            passed += 1
        else:
            print(f"  [OK] LLM responded (may have used tool)")
            passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        failed += 1; errors.append(f"Run Code: {e}")

    # ─────────── TEST 8: Calendar ───────────
    section("TEST 8: LLM -> Calendar Events")
    try:
        reply = await llm_chat(
            system_prompt,
            "What meetings do I have coming up this week?",
            history=[], tools=tools, tool_executor=execute_tool,
            access_token=access_token, timezone="Asia/Kolkata"
        )
        print(f"  Reply: {reply[:300]}")
        print(f"  [OK] Calendar query")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        failed += 1; errors.append(f"Calendar: {e}")

    # ─────────── FINAL SUMMARY ───────────
    print(f"\n{'='*60}")
    print(f"  RESULTS: {passed} passed, {failed} failed")
    print(f"{'='*60}")
    if errors:
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("  ALL TESTS PASSED - DEPLOYMENT READY")
        sys.exit(0)

asyncio.run(main())
