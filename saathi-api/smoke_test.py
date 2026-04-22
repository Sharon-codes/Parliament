import asyncio
import os
import json
from google_workspace import create_calendar_event, ensure_valid_tokens
from storage import storage

async def smoke_test():
    try:
        user_id = "demo-user"
        connection = storage.get_google_integration(user_id)
        if not connection:
            print(f"FAILURE: No Google Integration found for '{user_id}'.")
            return
        
        print("Refreshing tokens natively...")
        connection = await ensure_valid_tokens(connection)
        storage.upsert_google_integration(user_id, connection)
        token = connection["access_token"]
        
        title = "SMOKE TEST: Saathi Neural Alignment v77.5"
        start = "2026-04-20T18:00:00"
        end = "2026-04-20T19:00:00"
        tz = "Asia/Kolkata"
        
        print(f"Initializing Smoke Test for '{title}'...")
        event = await create_calendar_event(
            token,
            title=title,
            description="Verified via Antigravity Smoke Test v77.5",
            start_iso=start,
            end_iso=end,
            timezone_name=tz,
            attendees=["khushisinghverma05@gmail.com"],
            generate_meet=True
        )
        meet_link = event.get("hangoutLink")
        print(f"SUCCESS: Google Meet Link Generated: {meet_link}")
    except Exception as e:
        print(f"FAILURE: {str(e)}")

if __name__ == "__main__":
    asyncio.run(smoke_test())
