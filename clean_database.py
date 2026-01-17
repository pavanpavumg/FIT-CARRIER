
import sqlite3
import os
import glob

DB_PATH = "fitness_history.db"
BACKUP_DIR = "backups"

def clean_db():
    print("Connecting to database...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # 1. Drop unused tables
    print("Dropping unused table 'workout_logs'...")
    cur.execute("DROP TABLE IF EXISTS workout_logs")
    
    # 2. Wipe Activity Data
    print("Wiping 'workouts' and 'measurements'...")
    cur.execute("DELETE FROM workouts")
    cur.execute("DELETE FROM measurements")
    
    # 3. Reset User Stats (Keep the user account!)
    print("Resetting user stats for 'pavan'...")
    # Reset stats to defaults: 0 streaks, empty badges
    cur.execute("""
        UPDATE users 
        SET current_streak = 0,
            last_active_date = NULL,
            total_workouts = 0,
            streak_count = 0,
            last_activity_date = NULL,
            total_reps_all_time = 0,
            badges_earned = '[]',
            current_login_streak = 0,
            current_workout_streak = 0,
            total_reps_all_time = 0,
            weekly_consistency_score = 0
    """)
    
    conn.commit()
    conn.close()
    
    # 4. Delete junk backup files
    print("Deleting corrupt backup files...")
    patterns = [os.path.join(BACKUP_DIR, "*.db")]
    for p in patterns:
        for f in glob.glob(p):
            try:
                os.remove(f)
                print(f"Deleted: {f}")
            except Exception as e:
                print(f"Failed to delete {f}: {e}")
                
    print("\nDATABASE CLEAN COMPLETE.")
    print("All fake data removed. User 'pavan' preserved for Auto-Login.")

if __name__ == "__main__":
    clean_db()
