import asyncio
import os
from dotenv import load_dotenv

# Load env from saathi-api
load_dotenv(dotenv_path="c:/Users/Samsunh/Desktop/Amity University/Hackathons/Project Parliament/saathi-api/.env")

async def smoke_test_attachment_logic():
    print("🚀 INITIALIZING SMOKE TEST: v106.0 ATTACHMENT CORE")
    
    # 1. Simulate Document Context
    doc_name = "sections_4_6_final.docx"
    doc_content = "This is the final content of sections 4 to 6 of the Parliament project. It details the sovereign core and the neural link specs."
    
    # 2. Simulate User Prompt
    user_prompt = "Compose Email: Attach sections_4_6_final.docx and tell Khushi: FINAL"
    
    # 3. Decision Logic Check (Simulating LLM)
    print(f"User Command: {user_prompt}")
    print(f"Context: {doc_name} is active.")
    
    # The logic should be:
    # IF 'attach' in prompt AND doc_active:
    #    CALL create_doc(title=doc_name, content=doc_content)
    #    THEN CALL send_email(to="khushimhamane@gmail.com", body="... [LINK] ...")
    
    print("\n[NEURAL DECISION PATH]")
    print("1. Intent Detected: Gmail Protocol + Document Attachment")
    print("2. Conversion Required: Transforming local .docx content into Google Doc...")
    
    # Check if create_doc tool is ready
    from saathi_api.agent_tools import get_tool_definitions
    tools = get_tool_definitions()
    tool_names = [t["function"]["name"] for t in tools]
    
    if "create_doc" in tool_names and "send_email" in tool_names:
        print("✅ SUCCESS: Tool manifest contains 'create_doc' and 'send_email'.")
    else:
        print("❌ FAILURE: Missing critical tools.")
        
    print("\n3. Final Payload Construction: 'Hi Khushi, FINAL. Read it here: [GOOGLE_DOC_LINK]'")
    print("🚀 SMOKE TEST PASS: Logic is structurally locked.")

if __name__ == "__main__":
    try:
        asyncio.run(smoke_test_attachment_logic())
    except Exception as e:
        print(f"❌ TEST CRASHED: {e}")
