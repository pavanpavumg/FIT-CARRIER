import sqlite3
import os
import datetime
import uuid

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fitness_history.db")

def seed_pavan():
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
            print(f"Found user '{username}' (ID: {user_id})")
        else:
            print(f"User '{username}' not found. Creating...")
            token = uuid.uuid4().hex
            cur.execute("INSERT INTO users (username, token, current_login_streak) VALUES (?, ?, ?)", (username, token, 1))
            user_id = cur.lastrowid
            
        # 2. Clear recent workouts for cleaner stats (optional, but ensures "6" is exact if we want)
        # We will just add 6 workouts in the last 6 days.
        
        logs = []
        today = datetime.datetime.now()
        
        # 6 workouts: Today, Yesterday, ... Day-5
        for i in range(6):
            d = today - datetime.timedelta(days=i)
            ts = d.isoformat()
            logs.append((user_id, ts, 15, "squat")) # 15 reps, squat
            
        print(f"Seeding 6 workouts for user {user_id}...")
        cur.executemany("INSERT INTO workout_logs (user_id, timestamp, reps, workout_type) VALUES (?, ?, ?, ?)", logs)
        
        # 3. Update Stats
        # Workout Streak: If we worked out today, yesterday... etc, streak is 6.
        cur.execute("UPDATE users SET current_workout_streak = 6, last_workout_date = ? WHERE id = ?", 
                    (today.date().isoformat(), user_id))
                    
        # Weekly Consistency: 6
        cur.execute("UPDATE users SET weekly_consistency_score = 6 WHERE id = ?", (user_id,))
        
        conn.commit()
        print("Seeding complete. Pavan now has 6 workouts this week and a streak of 6.")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    seed_pavan()
