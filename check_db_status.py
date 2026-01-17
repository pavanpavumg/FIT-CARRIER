
import sqlite3
import datetime
from datetime import timedelta

DB_PATH = "fitness_history.db"

def check_status():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Get user
    username = 'pavan'
    cur.execute("SELECT id FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    if not row:
        print("User pavan NOT FOUND.")
        return
    
    user_id = row[0]
    print(f"Checking Data for User: {username} (ID: {user_id})")
    
    # 1. Check Workouts (Last 7 Days)
    print("\n--- Workouts (Last 7 Days) ---")
    end_date = datetime.datetime.utcnow()
    for i in range(6, -1, -1):
        d = end_date - timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        day_name = d.strftime("%a")
        
        cur.execute("SELECT SUM(duration) FROM workouts WHERE user_id = ? AND timestamp LIKE ?", (user_id, f"{d_str}%"))
        res = cur.fetchone()[0]
        minutes = round(res / 60, 1) if res else 0.0
        print(f"Date: {d_str} ({day_name}) | Duration Sum (sec): {res} | Graph Value (min): {minutes}")

    # 2. Check Waist Scans (Last 7)
    print("\n--- Waist Scans (Latest) ---")
    cur.execute("SELECT timestamp, waist_cm FROM measurements WHERE user_id = ? ORDER BY timestamp DESC LIMIT 7", (user_id,))
    rows = cur.fetchall()
    for r in rows:
        print(f"Time: {r[0]} | Waist: {r[1]} cm")
        
    conn.close()

if __name__ == "__main__":
    check_status()
