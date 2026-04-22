import asyncio, os
from dotenv import load_dotenv
load_dotenv()
from storage import storage
from google_workspace import list_recent_emails, get_email_detail, ensure_valid_tokens

USER_ID = "66b69c43-6d07-41cd-8058-f16a273bb7d6"

async def main():
    conn = storage.get_google_integration(USER_ID)
    if not conn:
        print("No connection")
        return
    conn = await ensure_valid_tokens(conn)
    emails = await list_recent_emails(conn['access_token'], 1)
    if not emails:
        print("No emails found")
        return
    
    first = emails[0]
    print(f"ID: {first['id']}")
    try:
        detail = await get_email_detail(conn['access_token'], first['id'])
        print(f"Subject: {detail['subject']}")
        print("Success!")
    except Exception as e:
        print(f"Error reading {first['id']}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
