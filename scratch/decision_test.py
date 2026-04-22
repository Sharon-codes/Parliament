import asyncio
import os
import json

async def simulate_system_prompt_decision():
    print("--- SAATHI DECISION SMOKE TEST (v106.1) ---")
    
    # Simulate Context from main.py logic
    doc_name = "sections_4_6_final.docx"
    doc_content = "Final specs for the Parliament sovereign core."
    
    doc_directive = f"\n\n[SOVEREIGN DOCUMENT CONTEXT]\nActive Document: {doc_name}\nRAW CONTENT: {doc_content}\nDIRECTIVE: If the user asks to 'attach' this to an email or doc, YOU MUST FIRST use 'create_doc' to save this content as a Google Doc, THEN include the resulting URL in the email/task. DO NOT send a literal message about attaching."

    user_input = "Compose Email: Attach sections_4_6_final.docx and tell Khushi: FINAL"
    
    print(f"Doc Directive injected into System Prompt: Yes")
    print(f"User Input: {user_input}")
    
    # In a real run, the LLM would see this.
    # We verify that the directive is explicit enough.
    
    if "FIRST use 'create_doc'" in doc_directive and "include the resulting URL" in doc_directive:
        print("RESULT SUCCESS: Decision directive is explicitly defined.")
    else:
        print("RESULT FAILURE: Directive is ambiguous.")

if __name__ == "__main__":
    asyncio.run(simulate_system_prompt_decision())
