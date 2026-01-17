import sqlite3
import os
import datetime
import uuid

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fitness_history.db")

def seed_data():
    if not os.path.exists(DB_PATH):
        print("DB not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    try:
        # 1. Get or Create Pavan
        username = "pavan"
        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        
        if row:
            user_id = row[0]
        else:
            token = uuid.uuid4().hex
            cur.execute("INSERT INTO users (username, token, current_login_streak) VALUES (?, ?, ?)", (username, token, 1))
            user_id = cur.lastrowid
            
        # 2. Clear recent workouts
        logs = []
        today = datetime.datetime.now()
        
        for i in range(6):
            d = today - datetime.timedelta(days=i)
            ts = d.isoformat()
            logs.append((user_id, ts, 15, "squat")) 
            
        cur.executemany("INSERT INTO workout_logs (user_id, timestamp, reps, workout_type) VALUES (?, ?, ?, ?)", logs)
        
        # 3. Update Stats
        cur.execute("UPDATE users SET current_workout_streak = 6, last_workout_date = ?, weekly_consistency_score = 6 WHERE id = ?", 
                    (today.date().isoformat(), user_id))
        
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
