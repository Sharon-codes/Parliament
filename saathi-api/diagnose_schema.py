"""Introspect the actual Supabase database schema so we stop guessing."""
import os, httpx, json
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

BASE = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

headers = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
}

TABLES = ["profiles", "chat_sessions", "chat_messages", "google_integrations"]

for table in TABLES:
    print(f"\n{'='*60}")
    print(f"TABLE: {table}")
    print(f"{'='*60}")
    # Use the PostgREST OPTIONS endpoint to get column info
    r = httpx.options(f"{BASE}/rest/v1/{table}", headers=headers)
    # Also try a SELECT with limit 0 to see what columns come back
    r2 = httpx.get(
        f"{BASE}/rest/v1/{table}",
        headers={**headers, "Prefer": "count=exact"},
        params={"limit": "0"},
    )
    print(f"  Status: {r2.status_code}")
    print(f"  Content-Range: {r2.headers.get('content-range', 'N/A')}")
    
    # Now fetch 1 row to see actual column names and types
    r3 = httpx.get(
        f"{BASE}/rest/v1/{table}",
        headers=headers,
        params={"limit": "1"},
    )
    rows = r3.json() if r3.status_code == 200 else r3.text
    if isinstance(rows, list) and rows:
        print(f"  Columns (from sample row):")
        for col, val in rows[0].items():
            print(f"    {col}: {type(val).__name__} = {repr(val)[:80]}")
    elif isinstance(rows, list):
        print(f"  (empty table, no sample row)")
    else:
        print(f"  Error: {rows}")

# Also get the OpenAPI definition for precise types
print(f"\n{'='*60}")
print("OPENAPI COLUMN DEFINITIONS")
print(f"{'='*60}")
r = httpx.get(f"{BASE}/rest/v1/", headers=headers)
if r.status_code == 200:
    spec = r.json()
    definitions = spec.get("definitions", {})
    for table in TABLES:
        if table in definitions:
            props = definitions[table].get("properties", {})
            print(f"\n  {table}:")
            for col, info in props.items():
                fmt = info.get("format", "")
                typ = info.get("type", "")
                desc = info.get("description", "")
                print(f"    {col}: type={typ} format={fmt} {desc}")
        else:
            print(f"\n  {table}: NOT FOUND in definitions")
