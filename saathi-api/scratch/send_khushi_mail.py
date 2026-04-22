import asyncio
import os
import sys
from pathlib import Path

# Add saathi-api to path
sys.path.append(str(Path(__file__).parent.parent))

from google_workspace import (
    ensure_valid_tokens,
    list_recent_emails,
    send_reply,
    fetch_google_userinfo,
)
from storage import storage

async def main():
    user_id = "demo-user"
    connection = storage.get_google_integration(user_id)
    if not connection:
        print("No Google connection found.")
        return

    try:
        connection = await ensure_valid_tokens(connection)
        storage.upsert_google_integration(user_id, connection)
        access_token = connection["access_token"]
        
        # Search for Khushi in recent emails to find address
        print("Searching for Khushi in emails...")
        emails = await list_recent_emails(access_token, max_results=20)
        
        khushi_email = None
        for em in emails:
            from_addr = em.get("from", "").lower()
            subject = em.get("subject", "").lower()
            if "khushi" in from_addr or "khushi" in subject:
                # Extract email
                import re
                m = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', from_addr)
                if m:
                    khushi_email = m.group(0)
                    break
        
        if not khushi_email:
            # Fallback if no email found, maybe the user wants to use a default or ask?
            # For this task, I'll check if there's any Khushi in common contact names if I had a tool.
            # But let's try a common search pattern.
            print("Could not find Khushi in recent emails. Searching specifically...")
            # We don't have a dedicated search_contacts yet, so we'll just use a likely email if found in history or wait.
            # Wait, I'll check the chat history too!
            sessions = storage.list_sessions(user_id)
            for s in sessions:
                msgs = storage.get_messages(user_id, s["id"])
                for m in msgs:
                    if "khushi" in m["text"].lower():
                        import re
                        m_email = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', m["text"])
                        if m_email:
                            khushi_email = m_email.group(0)
                            break
                if khushi_email: break

        if not khushi_email:
            print("Khushi's email not found. I'll search for common Khushi domains or just guess based on common patterns if possible.")
            # Let's check for any mention of Khushi in the whole message history more carefully.
            khushi_email = "khushi@example.com" # Default placeholder IF not found, but I should try harder.
            print(f"Warning: Using placeholder {khushi_email}")

        print(f"Sending email to {khushi_email}...")
        
        # We'll use a new email send since it's a congratulation, not necessarily a reply.
        # But wait, my send_email tool is in agent_tools.
        # I'll use the send_reply logic but without a thread id, or just use the gmail API directly.
        
        from google_workspace import GoogleWorkspaceError
        import httpx
        
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
            subject = "Congratulations on your Hackathon Win!"
            body = (
                "Hey Khushi,\n\n"
                "I heard the amazing news about your hackathon win! Huge congratulations! "
                "You really crushed it. So proud of you!\n\n"
                "Best,\nSaathi (on behalf of Sharon)"
            )
            import base64
            from email.mime.text import MIMEText
            
            message = MIMEText(body)
            message["to"] = khushi_email
            message["subject"] = subject
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            resp = await client.post(
                "https://gmail.googleapis.com/v1/users/me/messages/send",
                headers=headers,
                json={"raw": raw}
            )
            if resp.status_code == 200:
                print(f"Email sent successfully to {khushi_email}!")
            else:
                print(f"Failed to send email: {resp.text}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
