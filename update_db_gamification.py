
import sqlite3
import os

DB_PATH = "fitness_history.db"

def update_schema():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    print("Checking 'users' table schema...")
    cur.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cur.fetchall()]
    
    # Columns to add
    new_columns = {
        "streak_count": "INTEGER DEFAULT 0",
        "last_activity_date": "TEXT",
        "total_reps_all_time": "INTEGER DEFAULT 0",
        "badges_earned": "TEXT DEFAULT '[]'"  # Store as JSON list string
    }
    
    for col, definition in new_columns.items():
        if col not in columns:
            print(f"Adding column '{col}'...")
            try:
                cur.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
                print(f"Successfully added '{col}'.")
            except sqlite3.OperationalError as e:
                print(f"Error adding '{col}': {e}")
        else:
            print(f"Column '{col}' already exists. Skipping.")
            
    conn.commit()
    conn.close()
    print("Database schema update complete.")

if __name__ == "__main__":
    update_schema()
