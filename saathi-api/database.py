import sqlite3
import json
import uuid
import datetime

DB_FILE = "saathi.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY,
            name TEXT,
            role TEXT,
            interests TEXT,
            language TEXT,
            theme TEXT,
            proactive_level TEXT,
            nudge_sensitivity TEXT
        )
    ''')
    # Migrate: add nudge_sensitivity if it doesn't exist yet
    try:
        c.execute("ALTER TABLE user_settings ADD COLUMN nudge_sensitivity TEXT")
    except Exception:
        pass
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id TEXT PRIMARY KEY,
            title TEXT,
            updated_at TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            text TEXT,
            timestamp TIMESTAMP
        )
    ''')
    
    # Create default user if not exists
    c.execute("SELECT id FROM user_settings WHERE id = 1")
    if not c.fetchone():
        c.execute('''
            INSERT INTO user_settings (id, name, role, interests, language, theme, proactive_level, nudge_sensitivity)
            VALUES (1, 'Guest', 'Researcher', 'artificial intelligence', 'English', 'light', 'balanced', 'balanced')
        ''')
    conn.commit()
    conn.close()

def get_settings():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM user_settings WHERE id = 1")
    row = dict(c.fetchone())
    conn.close()
    return row

def update_settings(data: dict):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    for key, value in data.items():
        if key in ['name', 'role', 'interests', 'language', 'theme', 'proactive_level', 'nudge_sensitivity']:
            c.execute(f"UPDATE user_settings SET {key} = ? WHERE id = 1", (value,))
    conn.commit()
    conn.close()
    return get_settings()

def get_chat_sessions():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM chat_sessions ORDER BY updated_at DESC")
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows

def create_chat_session(title="New Chat"):
    session_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.datetime.now().isoformat()
    c.execute("INSERT INTO chat_sessions (session_id, title, updated_at) VALUES (?, ?, ?)", (session_id, title, now))
    conn.commit()
    conn.close()
    return session_id

def get_chat_messages(session_id: str):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT role, text FROM chat_messages WHERE session_id = ? ORDER BY id ASC", (session_id,))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows

def add_chat_message(session_id: str, role: str, text: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.datetime.now().isoformat()
    c.execute("INSERT INTO chat_messages (session_id, role, text, timestamp) VALUES (?, ?, ?, ?)", (session_id, role, text, now))
    
    # Extract title from the first user message if it's new
    c.execute("SELECT COUNT(*) FROM chat_messages WHERE session_id = ?", (session_id,))
    if c.fetchone()[0] <= 2 and role == 'user':
        title = text[:30] + "..." if len(text) > 30 else text
        c.execute("UPDATE chat_sessions SET title = ?, updated_at = ? WHERE session_id = ?", (title, now, session_id))
    else:
        c.execute("UPDATE chat_sessions SET updated_at = ? WHERE session_id = ?", (now, session_id))
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
