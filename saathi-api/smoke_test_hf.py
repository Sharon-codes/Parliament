"""HF MASTER SMOKE TEST: Multi-step pipeline with Hugging Face."""
import asyncio, os, sys, json
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from storage import storage
from llm import llm_chat, get_provider_info
from agent_tools import get_tool_definitions, execute_tool
from google_workspace import ensure_valid_tokens

USER_ID = "66b69c43-6d07-41cd-8058-f16a273bb7d6"

async def main():
    print("\n" + "="*60)
    print("  SAATHI HF AGENT SMOKE TEST")
    print("="*60)

    info = get_provider_info()
    print(f"  LLM: {info['provider']} ({info['model']})")
    
    profile = storage.ensure_profile(USER_ID, "sharonmelhi365@gmail.com", "Sharon Melhi")
    connection = storage.get_google_integration(USER_ID)
    connection = await ensure_valid_tokens(connection)
    access_token = connection["access_token"]
    tools = get_tool_definitions()

    prompt = (
        "You are Saathi. Address the user as Sharon. "
        "You MUST use tools to do things. The format is <call:tool_name>{json_args}</call>\n"
        "Wait for the result before proceeding."
    )

    # USER'S COMPLEX REQUEST
    request = (
        "1. Create a Google Doc titled 'Poem for Khushi' with a beautiful poem about how stunning she is. "
        "2. Find Khushi's email and send her that document link along with a flirty quote. "
        "3. Reply to her last email saying I'm thinking of her. "
        "4. Open VS Code and write a Python program that calculates the sum of even numbers until 100, then show me the output."
    )

    print(f"\n[STARTING MULTI-STEP PIPELINE]\nRequest: {request[:100]}...")
    
    try:
        reply = await llm_chat(
            prompt,
            request,
            history=[],
            tools=tools,
            tool_executor=execute_tool,
            access_token=access_token,
            timezone="Asia/Kolkata"
        )
        print("\n" + "-"*40)
        print(f"HF FINAL REPLY:\n{reply}")
        print("-"*40)
        print("\n[SUCCESS] Pipeline completed.")
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(main())
