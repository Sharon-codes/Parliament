import base64
import difflib
import email.utils
import os
import re
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
GOOGLE_API_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

GOOGLE_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/contacts.readonly",
]

DOC_URL_RE = re.compile(r"https://docs\.google\.com/document/d/([a-zA-Z0-9_-]+)")


class GoogleWorkspaceError(RuntimeError):
    pass


def oauth_enabled() -> bool:
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


def build_google_oauth_url(redirect_uri: str, state: str, prompt: str = "consent") -> str:
    if not oauth_enabled():
        raise GoogleWorkspaceError("Google OAuth is not configured.")
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "access_type": "offline",
        "prompt": prompt,
        "include_granted_scopes": "true",
        "scope": " ".join(GOOGLE_SCOPES),
        "state": state,
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


async def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict[str, Any]:
    payload = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=GOOGLE_API_TIMEOUT) as client:
        response = await client.post("https://oauth2.googleapis.com/token", data=payload)
    if response.status_code >= 400:
        raise GoogleWorkspaceError(f"Google token exchange failed: {response.text[:300]}")
    data = response.json()
    expiry = datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", 3600)))
    data["token_expiry"] = expiry.isoformat()
    return data


async def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    payload = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    async with httpx.AsyncClient(timeout=GOOGLE_API_TIMEOUT) as client:
        response = await client.post("https://oauth2.googleapis.com/token", data=payload)
    if response.status_code >= 400:
        raise GoogleWorkspaceError(f"Google token refresh failed: {response.text[:300]}")
    data = response.json()
    expiry = datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", 3600)))
    data["token_expiry"] = expiry.isoformat()
    return data


async def fetch_google_userinfo(access_token: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=GOOGLE_API_TIMEOUT) as client:
        response = await client.get("https://openidconnect.googleapis.com/v1/userinfo", headers=headers)
    if response.status_code >= 400:
        raise GoogleWorkspaceError(f"Google userinfo failed: {response.text[:300]}")
    return response.json()


def _token_expired(token_expiry: Optional[str]) -> bool:
    if not token_expiry:
        return True
    try:
        expiry = datetime.fromisoformat(token_expiry.replace("Z", "+00:00"))
    except ValueError:
        return True
    return expiry <= datetime.now(timezone.utc) + timedelta(minutes=2)


async def ensure_valid_tokens(connection: dict[str, Any]) -> dict[str, Any]:
    access_token = connection.get("access_token")
    refresh_token = connection.get("refresh_token")
    if access_token and not _token_expired(connection.get("token_expiry")):
        return connection
    if not refresh_token:
        raise GoogleWorkspaceError("Google Workspace needs to be reconnected.")
    refreshed = await refresh_access_token(refresh_token)
    connection["access_token"] = refreshed["access_token"]
    connection["token_expiry"] = refreshed["token_expiry"]
    if refreshed.get("refresh_token"):
        connection["refresh_token"] = refreshed["refresh_token"]
    return connection


def _parse_headers(payload: dict[str, Any]) -> dict[str, str]:
    headers = {}
    for item in payload.get("headers", []) or []:
        name = (item.get("name") or "").lower()
        if name:
            headers[name] = item.get("value") or ""
    return headers


def _decode_body(data: str) -> str:
    if not data:
        return ""
    padded = data + "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _extract_payload_text(payload: dict[str, Any]) -> str:
    mime_type = payload.get("mimeType", "")
    body = payload.get("body", {}) or {}
    text = _decode_body(body.get("data", ""))
    if mime_type in {"text/plain", "text/html"} and text:
        return text

    parts = payload.get("parts", []) or []
    chunks: list[str] = []
    for part in parts:
        nested = _extract_payload_text(part)
        if nested:
            chunks.append(nested)
    return "\n".join(chunks)


def extract_google_doc_links(text: str) -> list[str]:
    if not text:
        return []
    return list(dict.fromkeys(match.group(0) for match in DOC_URL_RE.finditer(text)))


def _document_id_from_url(url: str) -> Optional[str]:
    match = DOC_URL_RE.search(url)
    return match.group(1) if match else None


async def _google_get(path: str, access_token: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=GOOGLE_API_TIMEOUT) as client:
        response = await client.get(path, headers=headers, params=params)
    if response.status_code >= 400:
        raise GoogleWorkspaceError(f"Google request failed ({response.status_code}): {response.text[:300]}")
    return response.json()


async def _google_post(
    path: str,
    access_token: str,
    json_body: Optional[dict[str, Any]] = None,
    params: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=GOOGLE_API_TIMEOUT) as client:
        response = await client.post(path, headers=headers, json=json_body, params=params)
    if response.status_code >= 400:
        raise GoogleWorkspaceError(f"Google request failed ({response.status_code}): {response.text[:300]}")
    return response.json()


async def list_recent_emails(access_token: str, max_results: int = 6, query: str = "in:inbox newer_than:30d") -> list[dict[str, Any]]:
    data = await _google_get(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages",
        access_token,
        params={"maxResults": max_results, "q": query},
    )
    messages = data.get("messages", []) or []
    results: list[dict[str, Any]] = []
    for item in messages:
        detail = await _google_get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{item['id']}",
            access_token,
            params={"format": "full"},
        )
        payload = detail.get("payload", {}) or {}
        headers = _parse_headers(payload)
        body_text = _extract_payload_text(payload)
        results.append(
            {
                "id": detail.get("id"),
                "threadId": detail.get("threadId"),
                "subject": headers.get("subject") or "(No subject)",
                "from": headers.get("from") or "Unknown sender",
                "snippet": detail.get("snippet") or body_text[:180],
                "receivedAt": headers.get("date"),
                "messageIdHeader": headers.get("message-id"),
                "references": headers.get("references"),
                "inReplyTo": headers.get("in-reply-to"),
                "labels": detail.get("labelIds", []) or [],
                "docLinks": extract_google_doc_links(body_text),
            }
        )
    return results


async def get_email_detail(access_token: str, message_id: str) -> dict[str, Any]:
    detail = await _google_get(
        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
        access_token,
        params={"format": "full"},
    )
    payload = detail.get("payload", {}) or {}
    headers = _parse_headers(payload)
    body_text = _extract_payload_text(payload)
    return {
        "id": detail.get("id"),
        "threadId": detail.get("threadId"),
        "subject": headers.get("subject") or "(No subject)",
        "from": headers.get("from") or "Unknown sender",
        "to": headers.get("to"),
        "snippet": detail.get("snippet") or body_text[:180],
        "body": body_text,
        "messageIdHeader": headers.get("message-id"),
        "references": headers.get("references"),
        "inReplyTo": headers.get("in-reply-to"),
        "docLinks": extract_google_doc_links(body_text),
    }


async def send_new_email(
    access_token: str,
    *,
    to: str,
    subject: str,
    body: str,
) -> dict[str, Any]:
    mime = MIMEText(body, _charset="utf-8")
    mime["To"] = to
    mime["Subject"] = subject
    mime["From"] = "me"

    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("utf-8")
    payload: dict[str, Any] = {"raw": raw}
    return await _google_post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send", access_token, payload)


async def send_reply(
    access_token: str,
    *,
    to: str,
    subject: str,
    body: str,
    thread_id: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    references: Optional[str] = None,
) -> dict[str, Any]:
    mime = MIMEText(body, _charset="utf-8")
    mime["To"] = to
    mime["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    mime["From"] = "me"
    if in_reply_to:
        mime["In-Reply-To"] = in_reply_to
    if references:
        mime["References"] = references

    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("utf-8")
    payload: dict[str, Any] = {"raw": raw}
    if thread_id:
        payload["threadId"] = thread_id
    return await _google_post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send", access_token, payload)


async def delete_spam_messages(access_token: str) -> str:
    async with httpx.AsyncClient(timeout=GOOGLE_API_TIMEOUT) as client:
        response = await client.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"labelIds": ["SPAM"], "maxResults": 100},
        )
        if response.status_code != 200:
            return f"Unable to list spam right now: {response.text[:200]}"

        data = response.json()
        messages = data.get("messages", []) or []
        if not messages:
            return "Spam folder is already clear."

        ids = [item["id"] for item in messages]
        delete_response = await client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/batchDelete",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"ids": ids},
        )
        if delete_response.status_code in {200, 204}:
            return f"Deleted {len(ids)} spam messages."

        deleted = 0
        for message_id in ids[:20]:
            single = await client.delete(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if single.status_code in {200, 204}:
                deleted += 1

        if deleted:
            return f"Deleted {deleted} spam messages in fallback mode."
        return f"Spam cleanup failed: {delete_response.text[:200]}"


async def list_calendar_events_range(access_token: str, timezone_name: str, time_min: str, time_max: str) -> list[dict[str, Any]]:
    params = {
        "calendarId": "primary",
        "singleEvents": "true",
        "orderBy": "startTime",
        "timeMin": time_min,
        "timeMax": time_max,
        "timeZone": timezone_name,
    }
    data = await _google_get("https://www.googleapis.com/calendar/v3/calendars/primary/events", access_token, params=params)
    results = []
    for event in data.get("items", []) or []:
        start = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
        end = event.get("end", {}).get("dateTime") or event.get("end", {}).get("date")
        results.append(
            {
                "id": event.get("id"),
                "title": event.get("summary") or "Untitled event",
                "description": event.get("description") or "",
                "start": start,
                "end": end,
                "hangoutLink": event.get("hangoutLink"),
            }
        )
    return results


async def list_upcoming_events(access_token: str, timezone_name: str, max_results: int = 8) -> list[dict[str, Any]]:
    params = {
        "calendarId": "primary",
        "singleEvents": "true",
        "orderBy": "startTime",
        "timeMin": datetime.now(timezone.utc).isoformat(),
        "maxResults": max_results,
        "timeZone": timezone_name,
    }
    data = await _google_get("https://www.googleapis.com/calendar/v3/calendars/primary/events", access_token, params=params)
    results = []
    for event in data.get("items", []) or []:
        start = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
        end = event.get("end", {}).get("dateTime") or event.get("end", {}).get("date")
        results.append(
            {
                "id": event.get("id"),
                "title": event.get("summary") or "Untitled event",
                "start": start,
                "end": end,
                "hangoutLink": event.get("hangoutLink"),
            }
        )
    return results


async def create_calendar_event(
    access_token: str,
    *,
    title: str,
    description: str,
    start_iso: str,
    end_iso: str,
    timezone_name: str,
    attendees: Optional[list[str]] = None,
    generate_meet: bool = False,
) -> dict[str, Any]:
    payload = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_iso, "timeZone": timezone_name},
        "end": {"dateTime": end_iso, "timeZone": timezone_name},
        "attendees": [{"email": email} for email in (attendees or []) if email],
    }

    params = {}
    if generate_meet:
        payload["conferenceData"] = {
            "createRequest": {
                "requestId": f"meet-{int(datetime.now().timestamp() * 1000)}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }
        params["conferenceDataVersion"] = 1

    return await _google_post(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        access_token,
        payload,
        params=params,
    )


def _flatten_document_content(content: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for element in content or []:
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        for item in paragraph.get("elements", []) or []:
            text_run = item.get("textRun")
            if text_run and text_run.get("content"):
                parts.append(text_run["content"])
    return "".join(parts).strip()


async def create_google_doc(access_token: str, title: str, content: str) -> dict[str, Any]:
    document = await _google_post("https://docs.googleapis.com/v1/documents", access_token, {"title": title})
    doc_id = document.get("documentId")
    if content and doc_id:
        await _google_post(
            f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
            access_token,
            {
                "requests": [
                    {
                        "insertText": {
                            "location": {"index": 1},
                            "text": content,
                        }
                    }
                ]
            },
        )
    return {"documentId": doc_id, "title": document.get("title"), "url": f"https://docs.google.com/document/d/{doc_id}/edit"}


def _parse_markdown_to_blocks(content: str) -> list[dict]:
    """🧬 SAATHI OUTLINE PARSER (v125.0): Converts markdown into Numbered/Alphabetical Doc Outlines."""
    blocks = []
    # Normalize line endings and split
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    
    h1_count = 0
    h2_count = 0
    h3_count = 0
    bullet_count = 0
    
    for line in lines:
        raw = line.strip()
        if not raw:
            # Reset sub-counts on empty lines/new sections if desired
            # But usually, numbering stays consistent
            continue
            
        # 1. Structural Numbering for Headings
        if raw.startswith("#### "):
            # We don't number level 4 usually, just clean it
            blocks.append({"text": f"    {raw[5:]}", "paragraphStyle": "HEADING_4"})
            
        elif raw.startswith("### "):
            h3_count += 1
            blocks.append({
                "text": f"{h1_count}.{h2_count}.{h3_count} {raw[4:]}", 
                "paragraphStyle": "HEADING_3"
            })
            
        elif raw.startswith("## "):
            h2_count += 1
            h3_count = 0 # Reset H3 below this H2
            blocks.append({
                "text": f"{h1_count}.{h2_count} {raw[3:]}", 
                "paragraphStyle": "HEADING_2"
            })
            
        elif raw.startswith("# "):
            h1_count += 1
            h2_count = 0 # Reset H2/H3 below this H1
            h3_count = 0
            blocks.append({
                "text": f"{h1_count}. {raw[2:]}", 
                "paragraphStyle": "HEADING_1"
            })
        
        # 2. Numbered / Alphabetical Point System for Bullets
        elif raw.startswith("- ") or raw.startswith("* "):
            blocks.append({
                "text": raw[2:], 
                "paragraphStyle": "NORMAL_TEXT",
                # Use Numbered Preset instead of Bullet discs
                "bulletPreset": "NUMBERED_DECIMAL_ALPHA_ROMAN"
            })
        
        # 3. Clean Normal Paragraph
        else:
            # Deep clean of Bold/Italic as before
            clean_text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", line)
            clean_text = re.sub(r"(\*|_)(.*?)\1", r"\2", clean_text)
            clean_text = clean_text.replace("**", "").replace("__", "").strip()
            blocks.append({"text": clean_text, "paragraphStyle": "NORMAL_TEXT"})
            
    return blocks


async def create_google_doc_from_markdown(access_token: str, title: str, markdown_text: str) -> dict[str, Any]:
    """🦾 v123.5: High-level entry point to creating formatted docs from AI markdown."""
    blocks = _parse_markdown_to_blocks(markdown_text)
    return await create_google_doc_from_blocks(access_token, title, blocks)


async def create_google_doc_from_blocks(access_token: str, title: str, blocks: list[dict[str, Any]]) -> dict[str, Any]:
    if not blocks:
        return await create_google_doc(access_token, title, "")

    document = await _google_post("https://docs.googleapis.com/v1/documents", access_token, {"title": title})
    doc_id = document.get("documentId")
    if not doc_id:
        raise GoogleWorkspaceError("Google Docs did not return a document id.")

    buffer: list[str] = []
    ranges: list[dict[str, Any]] = []
    cursor = 1

    for block in blocks:
        raw_text = (block.get("text") or "").replace("\r\n", "\n").replace("\r", "\n")
        block_text = raw_text.rstrip("\n")
        text_to_insert = f"{block_text}\n"
        buffer.append(text_to_insert)
        end_cursor = cursor + len(text_to_insert)
        ranges.append(
            {
                "startIndex": cursor,
                "endIndex": end_cursor,
                "namedStyleType": _normalize_named_style(block.get("paragraphStyle")),
                "alignment": block.get("alignment"),
                "bulletPreset": block.get("bulletPreset"),
            }
        )
        cursor = end_cursor

    await _google_post(
        f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
        access_token,
        {"requests": [{"insertText": {"location": {"index": 1}, "text": "".join(buffer)}}]},
    )

    requests: list[dict[str, Any]] = []
    for item in ranges:
        style_payload = {"namedStyleType": item["namedStyleType"]}
        fields = ["namedStyleType"]
        if item.get("alignment"):
            style_payload["alignment"] = item["alignment"]
            fields.append("alignment")
        requests.append(
            {
                "updateParagraphStyle": {
                    "range": {"startIndex": item["startIndex"], "endIndex": item["endIndex"]},
                    "paragraphStyle": style_payload,
                    "fields": ",".join(fields),
                }
            }
        )
        if item.get("bulletPreset") and item["endIndex"] > item["startIndex"] + 1:
            requests.append(
                {
                    "createParagraphBullets": {
                        "range": {"startIndex": item["startIndex"], "endIndex": item["endIndex"]},
                        "bulletPreset": item["bulletPreset"],
                    }
                }
            )

    if requests:
        await _google_post(
            f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
            access_token,
            {"requests": requests},
        )

    return {"documentId": doc_id, "title": document.get("title"), "url": f"https://docs.google.com/document/d/{doc_id}/edit"}


async def read_google_doc(access_token: str, document_id: str) -> dict[str, Any]:
    document = await _google_get(f"https://docs.googleapis.com/v1/documents/{document_id}", access_token)
    body = document.get("body", {}) or {}
    content = _flatten_document_content(body.get("content", []) or [])
    return {"documentId": document_id, "title": document.get("title"), "content": content}


async def read_google_doc_from_url(access_token: str, url: str) -> dict[str, Any]:
    document_id = _document_id_from_url(url)
    if not document_id:
        raise GoogleWorkspaceError("No Google Doc link was found in that email.")
    return await read_google_doc(access_token, document_id)


def _normalize_contact(person: dict[str, Any]) -> Optional[dict[str, Any]]:
    emails = person.get("emailAddresses") or []
    names = person.get("names") or []
    organizations = person.get("organizations") or []
    primary_email = ""
    for email in emails:
        value = (email.get("value") or "").strip()
        if value:
            primary_email = value
            break
    if not primary_email:
        return None
    display_name = ""
    for item in names:
        value = (item.get("displayName") or "").strip()
        if value:
            display_name = value
            break
    if not display_name:
        display_name = primary_email.split("@", 1)[0]
    organization = ""
    for item in organizations:
        value = (item.get("name") or "").strip()
        if value:
            organization = value
            break
    return {
        "name": display_name,
        "email": primary_email,
        "organization": organization,
        "resourceName": person.get("resourceName"),
        "source": "google-contacts",
    }


def _manual_contact(email_value: str, name: str = "", organization: str = "", source: str = "manual") -> dict[str, Any]:
    local_name = name.strip() or email_value.split("@", 1)[0]
    return {
        "name": local_name,
        "email": email_value.strip(),
        "organization": organization.strip(),
        "resourceName": None,
        "source": source,
    }


def _contact_score(contact: dict[str, Any], query: str) -> float:
    q = query.strip().lower()
    if not q:
        return 0.0
    
    name = (contact.get("name") or "").lower()
    email_val = (contact.get("email") or "").lower()
    org = (contact.get("organization") or "").lower()
    
    # Exact email match is highest priority
    if q == email_val:
        return 10.0
    
    # Exact name match is high priority
    if q == name:
        return 8.0
        
    haystack = f"{name} {email_val} {org}"
    
    # Prefix matches or contains matches
    if q in name:
        return 5.0 + (len(q) / max(len(name), 1))
    if q in email_val:
        return 4.0 + (len(q) / max(len(email_val), 1))
    if q in haystack:
        return 3.0
        
    return difflib.SequenceMatcher(None, q, haystack).ratio()


async def _fallback_contacts(access_token: str, query: str, limit: int) -> list[dict[str, Any]]:
    try:
        params = {
            "pageSize": 200,
            "personFields": "names,emailAddresses,organizations",
            "sortOrder": "LAST_MODIFIED_DESCENDING",
        }
        data = await _google_get("https://people.googleapis.com/v1/people/me/connections", access_token, params=params)
        contacts = []
        for person in data.get("connections", []) or []:
            normalized = _normalize_contact(person)
            if normalized:
                contacts.append(normalized)
        contacts.sort(key=lambda item: _contact_score(item, query), reverse=True)
        filtered = [item for item in contacts if _contact_score(item, query) > 0.1]
        if filtered:
            return filtered[:limit]
    except GoogleWorkspaceError:
        pass
    return await _gmail_history_contacts(access_token, query, limit)


def _extract_header_contacts(raw_header: str) -> list[dict[str, Any]]:
    contacts: list[dict[str, Any]] = []
    for display_name, email_value in email.utils.getaddresses([raw_header or ""]):
        clean_email = (email_value or "").strip()
        if not clean_email or "@" not in clean_email:
            continue
        contacts.append(_manual_contact(clean_email, name=display_name, source="gmail-history"))
    return contacts


async def _gmail_history_contacts(access_token: str, query: str, limit: int) -> list[dict[str, Any]]:
    query = (query or "").strip()
    if not query:
        return []

    if "@" in query:
        return [_manual_contact(query, source="manual")] if query.count("@") == 1 else []

    search_queries = [
        f'in:anywhere "{query}" newer_than:730d',
        f'in:anywhere {query} newer_than:730d',
    ]
    contact_map: dict[str, dict[str, Any]] = {}

    for gmail_query in search_queries:
        try:
            data = await _google_get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                access_token,
                params={"maxResults": 25, "q": gmail_query},
            )
        except GoogleWorkspaceError:
            continue

        for item in data.get("messages", []) or []:
            try:
                detail = await _google_get(
                    f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{item['id']}",
                    access_token,
                    params={"format": "metadata", "metadataHeaders": ["From", "To", "Cc", "Reply-To"]},
                )
            except GoogleWorkspaceError:
                continue

            headers = _parse_headers(detail.get("payload", {}) or {})
            for header_name in ("from", "to", "cc", "reply-to"):
                for contact in _extract_header_contacts(headers.get(header_name, "")):
                    key = contact["email"].lower()
                    existing = contact_map.get(key)
                    if not existing or len(contact.get("name", "")) > len(existing.get("name", "")):
                        contact_map[key] = contact

        if contact_map:
            break

    contacts = list(contact_map.values())
    contacts.sort(key=lambda item: _contact_score(item, query), reverse=True)
    filtered = [item for item in contacts if _contact_score(item, query) > 0.1]
    return filtered[:limit]


async def search_google_contacts(access_token: str, query: str, limit: int = 8) -> list[dict[str, Any]]:
    query = (query or "").strip()
    if not query:
        return []
    if "@" in query and query.count("@") == 1:
        return [_manual_contact(query, source="manual")]

    params = {
        "query": query,
        "readMask": "names,emailAddresses,organizations",
        "pageSize": max(1, min(limit, 20)),
    }
    try:
        data = await _google_get("https://people.googleapis.com/v1/people:searchContacts", access_token, params=params)
        contacts = []
        for item in data.get("results", []) or []:
            normalized = _normalize_contact(item.get("person") or {})
            if normalized:
                contacts.append(normalized)
        contacts.sort(key=lambda item: _contact_score(item, query), reverse=True)
        if contacts:
            return contacts[:limit]
    except GoogleWorkspaceError:
        pass
    return await _fallback_contacts(access_token, query, limit)


async def resolve_contact_email(access_token: str, raw_value: str) -> str:
    parsed = parse_email_address(raw_value)
    if "@" in parsed:
        return parsed
    contacts = await search_google_contacts(access_token, raw_value, limit=1)
    if not contacts:
        raise GoogleWorkspaceError(f"I could not find a Google Contact for '{raw_value}'.")
    return contacts[0]["email"]


def parse_email_address(raw_value: str) -> str:
    return email.utils.parseaddr(raw_value or "")[1] or raw_value
