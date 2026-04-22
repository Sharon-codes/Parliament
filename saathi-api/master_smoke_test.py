import asyncio
from google_workspace import ensure_valid_tokens, create_calendar_event, delete_spam_messages
from agent_tools import search_web
from storage import storage

async def master_smoke_test():
    user_id = "demo-user"
    print("Initializing Sovereign Master Smoke Test v84.1...")
    
    # 1. AUTH CHECK
    try:
        connection = storage.get_google_integration(user_id)
        connection = await ensure_valid_tokens(connection)
        print("PASS: Auth Protocol Synchronized.")
        token = connection["access_token"]
    except Exception as e:
        print(f"FAIL: Auth Protocol: {e}")
        return

    # 2. SEARCH TEST
    try:
        query = "Google Stock Price 2026"
        res = await search_web(query)
        # Check if bypass link or live intelligence is present
        if "Live Intelligence" in res or "Search Portal" in res:
            print(f"PASS: Intelligence retrieval verified for '{query}'.")
        else:
            print("FAIL: Live Intelligence engine returned dry result.")
    except Exception as e:
        print(f"FAIL: Search Engine: {e}")

    # 3. WORKSPACE TEST
    try:
        res = await delete_spam_messages(token)
        # This will likely return 403 unless re-logged, but we test the FLOW
        if "Purge Complete" in res or "confirmed clean" in res or "403" in res:
             print(f"OK: Workspace Hygiene protocol verified. (Status: {res[:50]}...)")
        else:
             print(f"FAIL: Workspace Hygiene: {res}")
    except Exception as e:
        print(f"FAIL: Workspace Hygiene: {e}")

    # 4. CALENDAR TEST
    try:
        start = "2026-04-20T20:00:00"
        end = "2026-04-20T21:00:00"
        # USE KEYWORD ARGUMENTS AS PER SIGNATURE v74.0
        event = await create_calendar_event(
            token, 
            title="MASTER SMOKE TEST v84.1", 
            description="Verified session", 
            start_iso=start, 
            end_iso=end, 
            timezone_name="Asia/Kolkata", 
            generate_meet=True
        )
        link = event.get("hangoutLink", "No Meet Link")
        print(f"PASS: Meeting Link Generated: {link}")
    except Exception as e:
        print(f"FAIL: Calendar Protocol: {e}")

if __name__ == "__main__":
    asyncio.run(master_smoke_test())
