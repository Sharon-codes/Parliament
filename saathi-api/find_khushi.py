import asyncio
from google_workspace import list_recent_emails, ensure_valid_tokens
from storage import storage

async def find_khushi():
    try:
        user_id = "demo-user"
        connection = storage.get_google_integration(user_id)
        connection = await ensure_valid_tokens(connection)
        
        print("Searching Gmail for 'Khushi'...")
        # Search in sent and inbox
        emails = await list_recent_emails(connection["access_token"], query="Khushi", max_results=10)
        
        contacts = set()
        for em in emails:
            contacts.add(em.get("from", ""))
            contacts.add(em.get("to", ""))
        
        print("DETECTED CONTACTS:")
        for c in contacts:
            if "Khushi" in c:
                print(f"- {c}")
    except Exception as e:
        print(f"FAILURE: {str(e)}")

if __name__ == "__main__":
    asyncio.run(find_khushi())
