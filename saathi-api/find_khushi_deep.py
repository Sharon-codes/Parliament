import asyncio
from google_workspace import list_recent_emails, ensure_valid_tokens
from storage import storage

async def find_khushi_deep():
    try:
        user_id = "demo-user"
        connection = storage.get_google_integration(user_id)
        connection = await ensure_valid_tokens(connection)
        
        print("Deep searching Gmail for 'Khushi'...")
        # Broaden search to all messages
        emails = await list_recent_emails(connection["access_token"], query="Khushi", max_results=50)
        
        contacts = set()
        for em in strings_from_em(emails):
            if "Khushi" in em or "khushi" in em.lower():
                # Clean unicode
                msg = em.encode("ascii", "ignore").decode("ascii")
                contacts.add(msg)
        
        print("DETECTED:")
        for c in contacts:
            if c.strip():
                print(f"- {c}")
    except Exception as e:
        print(f"FAILURE: {str(e)}")

def strings_from_em(emails):
    res = []
    for e in emails:
        res.append(e.get("from", ""))
        res.append(e.get("to", ""))
        res.append(e.get("subject", ""))
    return res

if __name__ == "__main__":
    asyncio.run(find_khushi_deep())
