import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fitness_history.db")

def check_users():
    if not os.path.exists(DB_PATH):
        print("DB does not exist.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, username, token FROM users")
        rows = cur.fetchall()
        print(f"Total users: {len(rows)}")
        for r in rows:
            print(r)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_users()
