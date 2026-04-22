import asyncio, os
from storage import storage
from google_workspace import ensure_valid_tokens, create_google_doc, send_new_email, send_reply, list_recent_emails
import system_agent

USER_ID = "66b69c43-6d07-41cd-8058-f16a273bb7d6"

async def manual_smoke_test():
    print("--- STARTING MANUAL TOOL VERIFICATION (SMOKE TEST) ---")
    
    # Auth
    conn = storage.get_google_integration(USER_ID)
    conn = await ensure_valid_tokens(conn)
    token = conn["access_token"]
    
    # 1. Create Poem Doc
    poem = (
        "In the garden of life, a bloom so rare,\n"
        "Khushi, with beauty beyond compare.\n"
        "Eyes like stars and a smile like dawn,\n"
        "A vision of grace to look upon."
    )
    doc = await create_google_doc(token, "Poem for Khushi", poem)
    print(f"[OK] Created Poem Doc: {doc['url']}")
    
    # 2. Send Email
    khushi_email = "khushimhamane@gmail.com"
    flirty_quote = "If I had a flower for every time I thought of you, I could walk in my garden forever. Check out what I wrote for you: " + doc['url']
    await send_new_email(token, to=khushi_email, subject="A little something for you", body=flirty_quote)
    print(f"[OK] Sent Poem Link to Khushi")
    
    # 3. Reply to her last email
    emails = await list_recent_emails(token, 1)
    if emails:
        last = emails[0]
        await send_reply(token, to=khushi_email, subject=f"Re: {last['subject']}", body="I'm thinking of you... and your philosophical questions.", thread_id=last['threadId'])
        print(f"[OK] Replied to her last email: {last['subject']}")
    
    # 4. Open VS Code and write Sum of Evens
    code = (
        "def sum_evens(n):\n"
        "    return sum(i for i in range(2, n + 1, 2))\n\n"
        "result = sum_evens(100)\n"
        "print(f'Sum of even numbers till 100 is: {result}')"
    )
    fp = system_agent.write_code_to_file('sum_evens.py', code)
    out = system_agent.execute_python_code(fp)
    print(f"[OK] Executed Sum of Evens: {out}")
    print(system_agent.launch_app_with_file('vs code', fp))
    
    print("--- MANUAL SMOKE TEST COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(manual_smoke_test())
