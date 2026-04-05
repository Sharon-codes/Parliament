import sqlite3
import json

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
            proactive_level TEXT
        )
    ''')
    # Create default user if not exists
    c.execute("SELECT id FROM user_settings WHERE id = 1")
    if not c.fetchone():
        c.execute('''
            INSERT INTO user_settings (id, name, role, interests, language, theme, proactive_level)
            VALUES (1, 'Guest', 'Researcher', 'artificial intelligence', 'English', 'light', 'balanced')
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
    
    # We only have one user for this local personal AI
    for key, value in data.items():
        if key in ['name', 'role', 'interests', 'language', 'theme', 'proactive_level']:
            c.execute(f"UPDATE user_settings SET {key} = ? WHERE id = 1", (value,))
            
    conn.commit()
    conn.close()
    return get_settings()

if __name__ == "__main__":
    init_db()
