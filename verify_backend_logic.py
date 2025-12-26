import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.getcwd(), "fitness_app.db")

def verify_backend():
    print(f"Checking DB at: {DB_PATH}")
    
    # Initialize DB if missing
    if not os.path.exists(DB_PATH):
        print("Database not found. Initializing...")
        try:
            from app import init_db
            init_db()
            print("Database initialized.")
        except ImportError:
            print("Could not import app.py to init DB. Ensure in same dir.")
            return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Check Table Existence
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='workout_logs'")
        if cursor.fetchone():
            print("✅ 'workout_logs' table exists.")
        else:
            print("❌ 'workout_logs' table MISSING.")
            return
    except Exception as e:
        print(f"Error checking table: {e}")
        return

    # 2. Simulate User and Workout
    # Find or create a user
    cursor.execute("SELECT id FROM users LIMIT 1")
    user = cursor.fetchone()
    if not user:
        print("No users found. Creating dummy user for test.")
        cursor.execute("INSERT INTO users (username) VALUES ('test_verifier')")
        user_id = cursor.lastrowid
    else:
        user_id = user[0]
    
    print(f"Using User ID: {user_id}")

    # Insert a workout for today
    reps = 15
    now = datetime.now()
    try:
        cursor.execute(
            "INSERT INTO workout_logs (user_id, timestamp, reps, workout_type) VALUES (?, ?, ?, ?)",
            (user_id, now.isoformat(), reps, "test_squat")
        )
        conn.commit()
        print(f"✅ Logged test workout: {reps} reps at {now}")
    except Exception as e:
        print(f"❌ Failed to insert workout log: {e}")

    # 3. Verify Aggregation Query (Logic from get_weekly_report)
    seven_days_ago = now - timedelta(days=7)
    try:
        cursor.execute(
            "SELECT timestamp, reps FROM workout_logs WHERE user_id = ? AND timestamp >= ?",
            (user_id, seven_days_ago.isoformat())
        )
        rows = cursor.fetchall()
        
        # Aggregate
        daily_activity_map = { (now - timedelta(days=i)).date(): 0 for i in range(7) }
        found_today = False
        
        for r in rows:
            ts = datetime.fromisoformat(r[0]).date()
            if ts in daily_activity_map:
                daily_activity_map[ts] += r[1]
                if ts == now.date():
                    found_today = True

        today_reps = daily_activity_map[now.date()]
        if today_reps >= reps:
            print(f"✅ Aggregation Logic Verified. Reps for today: {today_reps}")
        else:
            print(f"❌ Aggregation Failed. Expected at least {reps}, got {today_reps}")

    except Exception as e:
        print(f"❌ Query logic failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    verify_backend()
