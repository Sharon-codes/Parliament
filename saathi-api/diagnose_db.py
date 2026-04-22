import sqlite3
import os

db_path = "saathi.db"
if not os.path.exists(db_path):
    print(f"DATABASE NOT FOUND: {db_path}")
else:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cur.fetchall()
    print(f"TABLES: {tables}")
    for table in tables:
        t_name = table[0]
        cur.execute(f"PRAGMA table_info({t_name});")
        info = cur.fetchall()
        print(f"COLUMNS {t_name}: {info}")
    conn.close()
