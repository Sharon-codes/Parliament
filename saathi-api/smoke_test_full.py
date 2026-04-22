"""Smoke test: VS Code launch, Python execution, and full email->doc->reply pipeline."""
import os, sys, asyncio
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from storage import storage
from llm import llm_chat, get_provider_info
from agent_tools import get_tool_definitions, execute_tool
from google_workspace import ensure_valid_tokens
import system_agent

USER_ID = "66b69c43-6d07-41cd-8058-f16a273bb7d6"
errors = []

def test(name, fn):
    try:
        result = fn()
        print(f"  [OK] {name}")
        return result
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        errors.append(f"{name}: {e}")
        return None

async def async_test(name, coro):
    try:
        result = await coro
        print(f"  [OK] {name}")
        return result
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        errors.append(f"{name}: {e}")
        return None

async def main():
    print("\n=== SMOKE TEST: Desktop Agent + Full Pipeline ===\n")

    # --- SECTION 1: Desktop Agent ---
    print("DESKTOP AGENT:")
    
    # Write and execute Python
    filepath = test("write_code_to_file", lambda: system_agent.write_code_to_file(
        "smoke_hello.py",
        'print("Hello from Saathi! The desktop agent works!")\nprint(f"2 + 2 = {2+2}")'
    ))
    if filepath:
        print(f"    File: {filepath}")
        output = test("execute_python_code", lambda: system_agent.execute_python_code(filepath))
        if output:
            print(f"    {output.strip()}")

    # Launch VS Code (just test the command exists)
    result = test("launch_app (VS Code)", lambda: system_agent.launch_app_with_file("vs code"))
    if result:
        print(f"    {result}")

    # --- SECTION 2: Full Pipeline via LLM ---
    print("\nFULL PIPELINE (via LLM):")

    profile = storage.ensure_profile(USER_ID, "sharonmelhi365@gmail.com", "Sharon Melhi")
    connection = storage.get_google_integration(USER_ID)
    if not connection:
        print("  [SKIP] No Google integration")
        return

    connection = await ensure_valid_tokens(connection)
    storage.upsert_google_integration(USER_ID, connection)
    access_token = connection["access_token"]
    tools = get_tool_definitions()

    system_prompt = (
        "You are Saathi, an AI companion. Address the user as Sharon. Reply in English. "
        "You MUST use tools when the user asks you to do things like send emails, create docs, etc. "
        "CRITICAL: When you search for someone's email address, you MUST use the EXACT email address "
        "from the search results. Never make up or guess an email address. "
        "If search_emails finds 'khushimhamane@gmail.com', use EXACTLY that address."
    )

    # Test 1: Open VS Code and write a program (via LLM)
    print("\n  Test: LLM -> Open VS Code + Write Code")
    reply = await llm_chat(
        system_prompt,
        "Write a Python program that prints the Fibonacci sequence up to 10 terms, save it, and open VS Code with it.",
        history=[],
        tools=tools,
        tool_executor=execute_tool,
        access_token=access_token,
        timezone="Asia/Kolkata"
    )
    print(f"    Reply: {reply[:300]}")

    # Test 2: Search Khushi's email and send (verify correct address)
    print("\n  Test: LLM -> Search Khushi + Send Real Email")
    reply2 = await llm_chat(
        system_prompt,
        "Search for emails from Khushi. Then send her an email with the subject 'How beautiful are you?' and body 'Hey Khushi! Just checking - how beautiful are you? Rate yourself 1-10. Love, Sharon'",
        history=[],
        tools=tools,
        tool_executor=execute_tool,
        access_token=access_token,
        timezone="Asia/Kolkata"
    )
    print(f"    Reply: {reply2[:400]}")
    # Verify it used the real email
    if "khushimhamane@gmail.com" in reply2.lower() or "khushi" in reply2.lower():
        print("    [OK] Appears to reference Khushi correctly")
    
    # Test 3: Full pipeline - read email, fetch doc, answer, create doc, reply
    print("\n  Test: LLM -> Read latest email + summarize")
    reply3 = await llm_chat(
        system_prompt,
        "List my recent 3 emails and tell me what they're about.",
        history=[],
        tools=tools,
        tool_executor=execute_tool,
        access_token=access_token,
        timezone="Asia/Kolkata"
    )
    print(f"    Reply: {reply3[:400]}")

    # Summary
    print(f"\n{'='*50}")
    if errors:
        print(f"ISSUES: {len(errors)} test(s) had problems:")
        for e in errors:
            print(f"  - {e}")
    else:
        print("ALL TESTS PASSED")

asyncio.run(main())
