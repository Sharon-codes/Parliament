import json
import re
from typing import Any, Optional
from urllib.parse import quote_plus

import httpx

import system_agent
from google_workspace import (
    create_calendar_event,
    create_google_doc,
    delete_spam_messages,
    get_email_detail,
    list_calendar_events_range,
    list_recent_emails,
    list_upcoming_events,
    parse_email_address,
    read_google_doc_from_url,
    resolve_contact_email,
    search_google_contacts,
    send_new_email,
    send_reply,
)


async def search_web(query: str) -> str:
    normalized = (query or "").strip()
    if not normalized:
        return "Search query is empty."

    url = f"https://duckduckgo.com/html/?q={quote_plus(normalized)}"
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": "Saathi/2.0"})
    if response.status_code >= 400:
        return f"Search is unavailable right now ({response.status_code})."

    matches = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', response.text)
    if not matches:
        return "No search results found."

    cleaned = []
    for href, title in matches[:5]:
        title_text = re.sub(r"<.*?>", "", title)
        cleaned.append(f"- {title_text}: {href}")
    return "\n".join(cleaned)


def _tool_catalog() -> list[dict[str, Any]]:
    return [
        {
            "name": "search_web",
            "description": "Search the web for up-to-date public information.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
        {
            "name": "open_url",
            "description": "Open a URL in the default browser.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
        {
            "name": "launch_app",
            "description": "Open an installed desktop application on this computer.",
            "parameters": {
                "type": "object",
                "properties": {"app_name": {"type": "string"}},
                "required": ["app_name"],
            },
        },
        {
            "name": "play_youtube_video",
            "description": "Open YouTube directly for a video or search query.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
        {
            "name": "send_email",
            "description": "Compose and send a professional Gmail. As Saathi, you must write the full email body yourself based on user intent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
        },
        {
            "name": "reply_to_email",
            "description": "Draft and send a professional Gmail reply. You must compose the full reply body yourself.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "thread_id": {"type": "string"},
                    "message_id_header": {"type": "string"},
                    "references": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
        },
        {
            "name": "create_doc",
            "description": "Create a rich Google Doc. As Saathi, you must compose the full document content (300+ words if needed) yourself.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["title", "content"],
            },
        },
        {
            "name": "create_calendar_event",
            "description": "Create a Google Calendar event.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                    "timezone": {"type": "string"},
                    "attendees": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "start", "end"],
            },
        },
        {
            "name": "schedule_meeting_with_meet",
            "description": "Create a Google Calendar event with a Google Meet link.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                    "timezone": {"type": "string"},
                    "attendees": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "start", "end"],
            },
        },
        {
            "name": "list_calendar_events",
            "description": "List upcoming Google Calendar events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"},
                    "timezone": {"type": "string"},
                },
            },
        },
        {
            "name": "search_calendar_for_day",
            "description": "List Google Calendar events within a date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "time_min": {"type": "string"},
                    "time_max": {"type": "string"},
                    "timezone": {"type": "string"},
                },
                "required": ["time_min", "time_max"],
            },
        },
        {
            "name": "search_emails",
            "description": "List recent Gmail messages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"},
                    "query": {"type": "string"},
                },
            },
        },
        {
            "name": "read_email",
            "description": "Read a Gmail message in detail.",
            "parameters": {
                "type": "object",
                "properties": {"message_id": {"type": "string"}},
                "required": ["message_id"],
            },
        },
        {
            "name": "read_doc_from_url",
            "description": "Read the text from a Google Doc URL.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
        {
            "name": "find_contact",
            "description": "Search Google Contacts for a person name or email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "empty_spam",
            "description": "Delete spam messages from Gmail.",
            "parameters": {"type": "object", "properties": {}},
        },
    ]


def get_tool_definitions(selected_names: Optional[list[str]] = None) -> list[dict[str, Any]]:
    catalog = _tool_catalog()
    if selected_names:
        allowed = set(selected_names)
        catalog = [item for item in catalog if item["name"] in allowed]
    return [{"function_declarations": catalog}]


def get_mini_tool_definitions(selected_names: Optional[list[str]] = None) -> list[dict[str, Any]]:
    mini = []
    for item in get_tool_definitions(selected_names)[0]["function_declarations"]:
        mini.append(
            {
                "name": item["name"],
                "description": item["description"][:120],
                "parameters": item["parameters"],
            }
        )
    return [{"function_declarations": mini}]


async def resolve_recipient_email(access_token: str, name: str) -> str:
    return await resolve_contact_email(access_token, name)


async def execute_tool(
    name: str,
    args: dict[str, Any],
    access_token: str | None = None,
    timezone: str = "UTC",
    profile_id: str | None = None,
    origin: str = "laptop",
) -> str:
    try:
        # 🧪 Device-Aware Routing (v113.0)
        if origin == "mobile":
            if name == "open_url":
                return f"DEVICE_REDIRECT:{args['url']}"
            if name == "play_youtube_video":
                query = args.get("query", "")
                if "youtube.com" in query or "youtu.be" in query:
                    return f"DEVICE_REDIRECT:{query}"
                return f"DEVICE_REDIRECT:https://www.youtube.com/results?search_query={quote_plus(query)}"

        if name == "search_web":
            return await search_web(args.get("query", ""))

        if name == "open_url":
            return system_agent.open_web_url(args["url"])

        if name == "launch_app":
            return system_agent.launch_app_with_file(args["app_name"], args.get("file_path"))

        if name == "play_youtube_video":
            return system_agent.play_youtube_video(args.get("query", ""))

        if not access_token:
            return "Google Workspace is not connected."

        if name == "find_contact":
            contacts = await search_google_contacts(access_token, args.get("query", ""), limit=int(args.get("limit", 5)))
            if not contacts:
                return "No matching Google Contacts found."
            return json.dumps(contacts[:5], ensure_ascii=True)

        if name == "send_email":
            recipient = await resolve_recipient_email(access_token, args["to"])
            await send_new_email(
                access_token,
                to=recipient,
                subject=args["subject"],
                body=args["body"],
            )
            return f"Sent email to {recipient}."

        if name == "reply_to_email":
            recipient = parse_email_address(args.get("to", ""))
            await send_reply(
                access_token,
                to=recipient,
                subject=args["subject"],
                body=args["body"],
                thread_id=args.get("thread_id"),
                in_reply_to=args.get("message_id_header"),
                references=args.get("references"),
            )
            return f"Sent reply to {recipient}."

        if name == "create_doc":
            title = args.get("title", "Untitled")
            content = args.get("content", "")
            document = await create_google_doc(access_token, title, content)
            return document["url"]

        if name in {"create_calendar_event", "schedule_meeting_with_meet"}:
            attendees = args.get("attendees") or []
            resolved_attendees = []
            for attendee in attendees:
                resolved_attendees.append(await resolve_recipient_email(access_token, attendee))
            event = await create_calendar_event(
                access_token,
                title=args["title"],
                description=args.get("description", ""),
                start_iso=args["start"],
                end_iso=args["end"],
                timezone_name=args.get("timezone") or timezone,
                attendees=resolved_attendees,
                generate_meet=name == "schedule_meeting_with_meet",
            )
            meet_link = event.get("hangoutLink")
            return f"Created calendar event '{event.get('summary', args['title'])}'.{' Meet link: ' + meet_link if meet_link else ''}"

        if name == "list_calendar_events":
            events = await list_upcoming_events(
                access_token,
                timezone_name=args.get("timezone") or timezone,
                max_results=max(1, min(int(args.get("limit", 8)), 20)),
            )
            return json.dumps(events, ensure_ascii=True)

        if name == "search_calendar_for_day":
            events = await list_calendar_events_range(
                access_token,
                args.get("timezone") or timezone,
                args["time_min"],
                args["time_max"],
            )
            return json.dumps(events, ensure_ascii=True)

        if name == "search_emails":
            emails = await list_recent_emails(
                access_token,
                max_results=max(1, min(int(args.get("limit", 6)), 12)),
                query=args.get("query", "in:inbox newer_than:30d"),
            )
            return json.dumps(emails, ensure_ascii=True)

        if name == "read_email":
            email = await get_email_detail(access_token, args["message_id"])
            return json.dumps(email, ensure_ascii=True)

        if name == "read_doc_from_url":
            document = await read_google_doc_from_url(access_token, args["url"])
            return json.dumps(document, ensure_ascii=True)

        if name == "empty_spam":
            return await delete_spam_messages(access_token)

        return f"Unknown tool: {name}"
    except Exception as exc:
        return f"Error: {exc}"
