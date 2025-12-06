# create_db.py
import sqlite3, os
BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "fitness_history.db")
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    token TEXT UNIQUE
);
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    filename TEXT,
    timestamp TEXT,
    waist_px REAL,
    waist_cm REAL
);
""")
conn.commit()
conn.close()
print("Created new DB at:", DB)
