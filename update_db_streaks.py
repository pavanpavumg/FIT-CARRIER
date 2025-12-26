import sqlite3
import os

DB_NAME = "fitness_history.db"

def migrate_db():
    if not os.path.exists(DB_NAME):
        print(f"Database {DB_NAME} not found. Migration skipped.")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    columns_to_add = [
        ("current_login_streak", "INTEGER DEFAULT 0"),
        ("last_login_date", "TEXT"),
        ("current_workout_streak", "INTEGER DEFAULT 0"),
        ("last_workout_date", "TEXT"),
        ("weekly_consistency_score", "INTEGER DEFAULT 0")
    ]

    print("Checking for new gamification columns...")
    
    # Get existing columns
    cursor.execute(f"PRAGMA table_info(users)")
    existing_columns = [info[1] for info in cursor.fetchall()]

    for col_name, col_type in columns_to_add:
        if col_name not in existing_columns:
            print(f"Adding column: {col_name} ({col_type})")
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError as e:
                print(f"Error adding {col_name}: {e}")
        else:
            print(f"Column '{col_name}' already exists.")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate_db()
