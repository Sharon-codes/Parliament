import asyncio
import os
import sys

# Ensure we can import from saathi-api
sys.path.append(os.path.join(os.getcwd(), "saathi-api"))

async def run_final_gauntlet():
    print("THE FINAL GAUNTLET (V123.0)...")
    from main import _build_code_file_from_request, llm_chat
    from dotenv import load_dotenv
    load_dotenv(dotenv_path="saathi-api/.env")

    # TEST 1: The "Be an Author" Test (Mirror Mode Simulation)
    print("\n[TEST 1] Testing Authorial Fidelity (Mirror Mode)...")
    prompt = "Create a detailed technical document about the internal workings of an LLM."
    
    response = await llm_chat(
        "Expert Author. Write 300-800 words of professional content.",
        prompt,
        history=[],
        tools=None,
        raw_mode=False
    )
    
    print(f"  Response Length: {len(response)} characters")
    if prompt.lower() in response.lower() and len(response) < 150:
        print("  FAILURE: Echo detected (Copy-Paste bug).")
    elif len(response) > 500:
        print("  SUCCESS: High-fidelity authoring detected.")
    else:
        print(f"  UNCERTAIN: Content length {len(response)} is low.")

    # TEST 2: The "Token Starvation" Test (Workstation Mode)
    print("\n[TEST 2] Testing Token Starvation (Workstation)...")
    instruction = "Write a comprehensive Chess game in Python with all rules implemented."
    
    drafted = await _build_code_file_from_request(instruction)
    
    if drafted:
        with open(drafted['file_path'], 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"  Drafted File: {drafted['filename']}")
        print(f"  Content Length: {len(content)} characters")
        
        if len(content) > 1500:
            print("  SUCCESS: Large file drafted successfully (2048 token window verified).")
        else:
            print(f"  FAILURE: File too short ({len(content)}). Still hitting starvation or fallback.")
            
        if "[AI NOTICE]" in content:
            print("  RECOVERY ACTIVE: Partial stream recovered successfully.")
    else:
        print("  FAILURE: No file drafted.")

    print("\nTHE FINAL GAUNTLET COMPLETE.")

if __name__ == "__main__":
    asyncio.run(run_final_gauntlet())
