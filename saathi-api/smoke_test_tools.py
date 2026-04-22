import os
import sys
import asyncio
from pathlib import Path

# Add saathi-api to path
sys.path.append(os.path.dirname(__file__))

import system_agent

async def tool_smoke_test():
    print("\n" + "="*80)
    print("  SAATHI TOOL SMOKE TEST: APP LAUNCHING")
    print("="*80 + "\n")

    test_cases = [
        {"input": "open vs code", "expected": "Launched vs code"},
        {"input": "launch cursor", "expected": "Launched cursor"},
        {"input": "hey saathi open pycharm", "expected": "Launched pycharm"},
        {"input": "open notepad++", "expected": "Launched notepad++"},
        {"input": "open chrome", "expected": "Launched chrome"},
    ]

    for case in test_cases:
        print(f"[TESTING] Command: '{case['input']}'")
        # Simulate agentic_execute
        # Note: mode="agent" is required to trigger the parsing logic I updated
        result = system_agent.agentic_execute(case["input"], mode="agent")
        print(f"[RESULT] {result}")
        if case["expected"] in result:
            print(f"[OK] SUCCESS: Correct app command generated.")
        else:
            print(f"[FAIL] FAILURE: Expected '{case['expected']}' in result.")
        print("-" * 40)

    print("\n[VERIFYING WAKE WORD PARSING]")
    # Test the logic where I added (name == "cursor" and "cursor" in task_lower)
    result = system_agent.agentic_execute("cursor", mode="agent")
    print(f"[RESULT for 'cursor'] {result}")
    if "Launched cursor" in result:
        print("[OK] SUCCESS: Bare 'cursor' command now works.")
    else:
        print("[FAIL] FAILURE: Bare 'cursor' command failed.")

if __name__ == "__main__":
    asyncio.run(tool_smoke_test())
