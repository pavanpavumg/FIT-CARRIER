# app.py
import os
import io
import base64
import uuid
import shutil
import json
from datetime import datetime, timedelta
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException, Header, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn
import cv2
import numpy as np
import sqlite3
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext

from measure import estimate_waist_width_px, analyze_body
from exercise_database import get_recommended_workouts
from anomaly_detector import check_anomaly
import mediapipe as mp
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from AdvancedSquatAnalyzer import AdvancedSquatAnalyzer


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
DB_PATH = os.path.join(BASE_DIR, "fitness_history.db")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

# JWT Configuration
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security
security = HTTPBearer()

app = FastAPI(title="AI Fitness Backend (auth + segmentation)")

# Global exception handler to ensure JSON errors (but not HTTPExceptions)
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


def _is_corrupt_db_error(exc: sqlite3.DatabaseError) -> bool:
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "database disk image is malformed",
            "file is encrypted or is not a database",
            "malformed database schema",
        )
    )


def _handle_corrupt_db(exc: sqlite3.DatabaseError) -> bool:
    if not _is_corrupt_db_error(exc):
        return False
    # Move the corrupted DB aside so we can recreate a clean file.
    if os.path.exists(DB_PATH):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = f"fitness_history_corrupt_{ts}.db"
        backup_path = os.path.join(BACKUP_DIR, backup_name)
        try:
            shutil.move(DB_PATH, backup_path)
        except Exception:
            # If move fails, try to unlink to avoid reusing the corrupt file.
            try:
                os.remove(DB_PATH)
            except Exception:
                pass
    # Immediately rebuild the schema so the retry operates on a valid DB.
    try:
        init_db()
    except Exception:
        # If rebuild fails here, let the retry logic surface the error.
        pass
    return True


def _with_db_retry(fn):
    try:
        return fn()
    except sqlite3.IntegrityError:
        # Let integrity errors bubble up—they are expected (e.g., duplicate usernames).
        raise
    except sqlite3.DatabaseError as exc:
        if not _handle_corrupt_db(exc):
            raise
        return fn()

# serve static and templates
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# JWT helpers
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# DB helpers - cache for schema check
_db_initialized = False

def init_db(force=False):
    """Initialize database schema. Only runs once unless force=True."""
    global _db_initialized
    if _db_initialized and not force:
        return
    
    def _op():
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            # Enable foreign keys
            cur.execute("PRAGMA foreign_keys = ON")
            
            # Check if users table exists
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            users_table_exists = cur.fetchone() is not None
            
            if not users_table_exists:
                # Create users table from scratch
                cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT,
                    token TEXT UNIQUE,
                    streak_count INTEGER DEFAULT 0,
                    last_activity_date TEXT,
                    total_reps_all_time INTEGER DEFAULT 0,
                    badges_earned TEXT DEFAULT '[]'
                );
                """)
            else:
                # Table exists - check if password_hash column exists
                cur.execute("PRAGMA table_info(users)")
                columns = [row[1] for row in cur.fetchall()]
                if "password_hash" not in columns:
                    try:
                        cur.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
                    except sqlite3.OperationalError:
                        pass  # Column might already exist
            
            # Ensure gamification columns exist (for existing DBs if migration script wasn't run)
            # We trust migration for now or simple manual checks, but for app logic integrity:
            cur.execute("PRAGMA table_info(users)")
            user_cols = [row[1] for row in cur.fetchall()]
            new_cols = {
                "streak_count": "INTEGER DEFAULT 0",
                "last_activity_date": "TEXT",
                "total_reps_all_time": "INTEGER DEFAULT 0",
                "badges_earned": "TEXT DEFAULT '[]'"
            }
            for col, defn in new_cols.items():
                if col not in user_cols:
                    try:
                        cur.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
                    except sqlite3.OperationalError:
                        pass


            # Create workout_logs table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS workout_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                timestamp TEXT NOT NULL,
                reps INTEGER DEFAULT 0,
                workout_type TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_workout_logs_timestamp ON workout_logs(timestamp DESC);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_workout_logs_user_id ON workout_logs(user_id);")

            # Create measurements table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                filename TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                waist_px REAL,
                waist_cm REAL,
                recommended_workouts TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            """)

            # Ensure recommended_workouts column exists
            cur.execute("PRAGMA table_info(measurements)")
            measurement_columns = [row[1] for row in cur.fetchall()]
            if "recommended_workouts" not in measurement_columns:
                try:
                    cur.execute("ALTER TABLE measurements ADD COLUMN recommended_workouts TEXT")
                except sqlite3.OperationalError:
                    pass
            
            # Create indexes for faster queries
            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_measurements_user_id ON measurements(user_id);
            """)
            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_measurements_timestamp ON measurements(timestamp DESC);
            """)
            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
            """)
            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_token ON users(token);
            """)
            
            conn.commit()
        finally:
            conn.close()
    
    _with_db_retry(_op)
    _db_initialized = True

def create_user(username: str, password: str = None):
    """Create a new user. If password is provided, use password auth. Otherwise use token auth."""
    init_db()  # Ensure DB is initialized
    def _op():
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        try:
            if password:
                password_hash = get_password_hash(password)
                try:
                    cur.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
                    conn.commit()
                    user_id = cur.lastrowid
                except sqlite3.IntegrityError:
                    conn.rollback()
                    raise ValueError("Username already exists")
            else:
                # Legacy token-based auth
                token = uuid.uuid4().hex
            try:
                cur.execute("INSERT INTO users (username, token) VALUES (?, ?)", (username, token))
                conn.commit()
                user_id = cur.lastrowid
            except sqlite3.IntegrityError:
                conn.rollback()
                cur.execute("SELECT id, token FROM users WHERE username = ?", (username,))
                r = cur.fetchone()
                if r:
                    user_id, token_val = r[0], r[1]
                    token = token_val
                else:
                    raise
        finally:
            conn.close()
        if password:
            return {"id": user_id, "username": username}
        else:
            return {"id": user_id, "username": username, "token": token}
    return _with_db_retry(_op)

def get_user_by_username(username: str):
    init_db()  # Ensure DB is initialized
    def _op():
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            # Check if password_hash column exists
            cur.execute("PRAGMA table_info(users)")
            columns = [row[1] for row in cur.fetchall()]
            has_password_hash = "password_hash" in columns
            
            # Select columns - use COALESCE to handle NULL values
            if has_password_hash:
                # Try to select password_hash and token
                try:
                    cur.execute("SELECT id, username, password_hash, token FROM users WHERE username = ?", (username,))
                except sqlite3.OperationalError:
                    # If token column doesn't exist, select without it
                    cur.execute("SELECT id, username, password_hash FROM users WHERE username = ?", (username,))
            else:
                cur.execute("SELECT id, username, token FROM users WHERE username = ?", (username,))
            r = cur.fetchone()
        finally:
            conn.close()
        if not r:
            return None
        
        # Build user dict
        user = {"id": r[0], "username": r[1]}
        if has_password_hash:
            if len(r) >= 3:
                user["password_hash"] = r[2]  # Can be None if NULL in DB
            if len(r) >= 4 and r[3] is not None:
                user["token"] = r[3]
        else:
            if len(r) >= 3 and r[2] is not None:
                user["token"] = r[2]
        
        return user
    return _with_db_retry(_op)

def get_user_by_token(token: str):
    init_db()  # Ensure DB is initialized
    def _op():
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, username FROM users WHERE token = ?", (token,))
            r = cur.fetchone()
        finally:
            conn.close()
        if not r:
            return None
        return {"id": r[0], "username": r[1]}
    return _with_db_retry(_op)

def save_measurement_record(user_id: int, filename: str, waist_px: Optional[float], waist_cm: Optional[float], recommended_workouts: Optional[list] = None):
    init_db()  # Ensure DB is initialized
    def _op():
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO measurements (user_id, filename, timestamp, waist_px, waist_cm, recommended_workouts) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    filename,
                    datetime.now().isoformat(),
                    waist_px,
                    waist_cm,
                    json.dumps(recommended_workouts) if recommended_workouts else None,
                )
            )
            conn.commit()
            rowid = cur.lastrowid
        finally:
            conn.close()
        return rowid
    return _with_db_retry(_op)

def get_history_for_user(user_id: int):
    init_db()  # Ensure DB is initialized
    def _op():
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, filename, timestamp, waist_px, waist_cm, recommended_workouts FROM measurements WHERE user_id = ? ORDER BY timestamp DESC LIMIT 100",
                (user_id,)
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        result = []
        for r in rows:
            workouts_payload = []
            if len(r) >= 6 and r[5]:
                try:
                    workouts_payload = json.loads(r[5])
                except json.JSONDecodeError:
                    workouts_payload = []
            result.append({
                "id": r[0],
                "filename": r[1],
                "timestamp": r[2],
                "waist_px": r[3],
                "waist_cm": r[4],
                "recommended_workouts": workouts_payload,
            })
        return result
    return _with_db_retry(_op)

def delete_history_item_for_user(user_id: int, item_id: int):
    init_db()  # Ensure DB is initialized
    def _op():
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute("SELECT filename FROM measurements WHERE id = ? AND user_id = ?", (item_id, user_id))
            row = cur.fetchone()
            if not row:
                return False
            filename = row[0]
            cur.execute("DELETE FROM measurements WHERE id = ? AND user_id = ?", (item_id, user_id))
            conn.commit()
        finally:
            conn.close()
        # remove file
        fp = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(fp):
            try:
                os.remove(fp)
            except Exception:
                pass
        return True
    return _with_db_retry(_op)

# Gamification Logic
# Gamification Logic

def check_login_streak(user_id: int):
    """Updates login streak based on last_login_date."""
    init_db()
    
    today = datetime.now().date()
    today_str = today.isoformat()
    yesterday = today - timedelta(days=1)
    yesterday_str = yesterday.isoformat()
    
    current_streak = 0
    last_login = None
    
    def _read():
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute("SELECT current_login_streak, last_login_date FROM users WHERE id = ?", (user_id,))
            return cur.fetchone()
        finally:
            conn.close()
            
    row = _with_db_retry(_read)
    if row:
        current_streak = row[0] or 0
        last_login = row[1]
    
    new_streak = current_streak
    
    if last_login == today_str:
        pass # Already logged in today
    elif last_login == yesterday_str:
        new_streak += 1
    else:
        new_streak = 1 # Reset or Start
        
    if new_streak != current_streak or last_login != today_str:
        def _write():
            conn = sqlite3.connect(DB_PATH)
            try:
                cur = conn.cursor()
                cur.execute("UPDATE users SET current_login_streak = ?, last_login_date = ? WHERE id = ?", 
                           (new_streak, today_str, user_id))
                conn.commit()
            finally:
                conn.close()
        _with_db_retry(_write)
        
    return new_streak

def check_workout_streak(user_id: int):
    """Updates workout streak based on last_workout_date (called on valid workout)."""
    init_db()
    
    today = datetime.now().date()
    today_str = today.isoformat()
    yesterday = today - timedelta(days=1)
    yesterday_str = yesterday.isoformat()
    
    current_streak = 0
    last_workout = None
    
    def _read():
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute("SELECT current_workout_streak, last_workout_date FROM users WHERE id = ?", (user_id,))
            return cur.fetchone()
        finally:
            conn.close()
            
    row = _with_db_retry(_read)
    if row:
        current_streak = row[0] or 0
        last_workout = row[1]
    
    new_streak = current_streak
    updated = False
    
    if last_workout == today_str:
        pass # Already worked out today
    elif last_workout == yesterday_str:
        new_streak += 1
        updated = True
    else:
        new_streak = 1 # Reset or Start
        updated = True
        
    if updated or last_workout != today_str:
        def _write():
            conn = sqlite3.connect(DB_PATH)
            try:
                cur = conn.cursor()
                cur.execute("UPDATE users SET current_workout_streak = ?, last_workout_date = ? WHERE id = ?", 
                           (new_streak, today_str, user_id))
                conn.commit()
            finally:
                conn.close()
        _with_db_retry(_write)
        
    return new_streak

def update_weekly_consistency(user_id: int):
    """Updates weekly consistency score (workouts in last 7 days)."""
    init_db()
    
    def _op():
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            # Count distinct days with measurements in last 7 days
            seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
            cur.execute("""
                SELECT COUNT(DISTINCT substr(timestamp, 1, 10)) 
                FROM measurements 
                WHERE user_id = ? AND timestamp >= ?
            """, (user_id, seven_days_ago))
            count = cur.fetchone()[0]
            
            # Update score
            cur.execute("UPDATE users SET weekly_consistency_score = ? WHERE id = ?", (count, user_id))
            conn.commit()
            return count
        finally:
            conn.close()
            
    return _with_db_retry(_op)

def check_gamification(user_id: int):
    """
    Check and update streaks and badges.
    Now handles Login vs Workout streaks separately.
    Called AFTER a workout logic.
    """
    init_db()
    
    # Update Workout Streak explicit call
    workout_streak = check_workout_streak(user_id)
    
    # Update Consistency
    consistency_score = update_weekly_consistency(user_id)
    
    # Get Stats for Badges
    stats = {}
    def _get_stats():
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute("SELECT total_reps_all_time, badges_earned FROM users WHERE id = ?", (user_id,))
            return cur.fetchone()
        finally:
            conn.close()
            
    row = _with_db_retry(_get_stats)
    if not row: return None
    
    total_reps = row[0] or 0
    badges_json = row[1] or '[]'
    try:
        badges_list = json.loads(badges_json)
    except:
        badges_list = []
        
    new_badges = []
    
    # "Hot Streak": Workout Streak >= 3 (Low bar for demo) or 7
    if workout_streak >= 3:
        if "hot_streak" not in badges_list:
            badges_list.append("hot_streak")
            new_badges.append("hot_streak")
            
    # "Consistent": 3+ days a week
    if consistency_score >= 3:
         if "consistent" not in badges_list:
            badges_list.append("consistent")
            new_badges.append("consistent")

    # "Early Riser": 5AM - 8AM (Check current time)
    now_hour = datetime.now().hour
    if 5 <= now_hour < 8:
        if "early_riser" not in badges_list:
            badges_list.append("early_riser")
            new_badges.append("early_riser")

    # "Centurion"
    if total_reps > 100:
        if "centurion" not in badges_list:
            badges_list.append("centurion")
            new_badges.append("centurion")
            
    # Save Badges
    if new_badges:
        def _save_badges():
            conn = sqlite3.connect(DB_PATH)
            try:
                cur = conn.cursor()
                cur.execute("UPDATE users SET badges_earned = ? WHERE id = ?", (json.dumps(badges_list), user_id))
                conn.commit()
            finally:
                conn.close()
        _with_db_retry(_save_badges)
        
    return {
        "streak_count": workout_streak, # For backward compat in UI response
        "workout_streak": workout_streak,
        "consistency_score": consistency_score,
        "badges_earned": badges_list,
        "new_badges": new_badges
    }

def update_user_reps(user_id: int, reps: int):
    """Increment total reps for user."""
    init_db()
    def _op():
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            # Simple increment
            cur.execute("UPDATE users SET total_reps_all_time = total_reps_all_time + ? WHERE id = ?", (reps, user_id))
            conn.commit()
        finally:
            conn.close()
    _with_db_retry(_op)

class WeeklyReportRequest(BaseModel):
    username: str
    token: str

@app.post("/api/weekly_report")
async def get_weekly_report(req: WeeklyReportRequest):
    user = get_user_by_token(req.token)
    if not user or user['username'] != req.username:
        raise HTTPException(status_code=401, detail="Invalid token or username")
    
    user_id = user['id']
    
    init_db()
    def _op():
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            # Get all measurements for this user, sorted by timestamp ASC
            cur.execute(
                "SELECT timestamp, waist_cm FROM measurements WHERE user_id = ? ORDER BY timestamp ASC",
                (user_id,)
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        return rows
    
    all_records = _with_db_retry(_op)
    
    # Filter for last 7 days
    now = datetime.now()
    seven_days_ago = now - timedelta(days=7)
    
    weekly_records = []
    for r in all_records:
        # Parse timestamp (ISO format)
        try:
            ts = datetime.fromisoformat(r[0])
        except ValueError:
            continue # Skip invalid dates
            
        if ts >= seven_days_ago:
            weekly_records.append({"timestamp": ts, "waist_cm": r[1]})
            
    # Calculate stats
    # NEW: Fetch workout logs for daily activity
    def _get_workouts():
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT timestamp, reps FROM workout_logs WHERE user_id = ? AND timestamp >= ?",
                (user_id, seven_days_ago.isoformat())
            )
            return cur.fetchall()
        finally:
            conn.close()
            
    workout_rows = _with_db_retry(_get_workouts)
    
    # Aggregate by day for the last 7 days
    daily_activity_map = { (now - timedelta(days=i)).date(): 0 for i in range(7) }
    for r in workout_rows:
        try:
            ts = datetime.fromisoformat(r[0]).date()
            if ts in daily_activity_map:
                daily_activity_map[ts] += r[1]
        except: continue
        
    # Sort by date
    sorted_dates = sorted(daily_activity_map.keys())
    daily_activity = [daily_activity_map[d] for d in sorted_dates]
    activity_labels = [d.strftime("%a") for d in sorted_dates]

    total_scans = len(weekly_records)
    
    latest_waist = 0.0
    start_waist = 0.0
    avg_waist = 0.0
    weekly_change = 0.0
    
    if total_scans > 0:
        # Filter out None values for waist_cm calculation
        valid_waists = [rec["waist_cm"] for rec in weekly_records if rec["waist_cm"] is not None]
        
        if valid_waists:
            avg_waist = sum(valid_waists) / len(valid_waists)
            latest_waist = valid_waists[-1]
            start_waist = valid_waists[0]
            weekly_change = latest_waist - start_waist
            
    return {
        "total_scans": total_scans,
        "avg_waist": round(avg_waist, 1),
        "latest_waist": round(latest_waist, 1),
        "start_waist": round(start_waist, 1),
        "weekly_change": round(weekly_change, 1),
        "daily_activity": daily_activity,
        "activity_labels": activity_labels
    }

# Init DB - lazy initialization (only when needed)
# Will be initialized on first database operation

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/users")
async def api_create_user(username: str = Form(...)):
    if not username or username.strip() == "":
        raise HTTPException(status_code=400, detail="username required")
    
    # Check if user exists
    existing_user = get_user_by_username(username.strip())
    if existing_user:
        return JSONResponse(
            status_code=409,
            content={"status": "exists", "message": "User already registered."}
        )
        
    u = create_user(username.strip())
    return JSONResponse(u)

def png_bytes_from_bgr(img_bgr):
    _, buf = cv2.imencode(".png", img_bgr)
    return buf.tobytes()

def estimate_body_fat_percentage(waist_cm: Optional[float], height_cm: Optional[int], age: int = 30, gender: str = "male") -> Optional[float]:
    """
    Estimate body fat percentage using waist circumference.
    Uses simplified formula based on waist-to-height ratio and age.
    """
    if waist_cm is None or height_cm is None or waist_cm <= 0 or height_cm <= 0:
        return None
    
    # Waist-to-height ratio
    waist_to_height = waist_cm / height_cm
    
    # Simplified body fat estimation (approximate)
    # This is a rough estimate - for more accuracy, use DEXA or other methods
    if gender.lower() == "male":
        # For men: approximate formula
        bf_percentage = 64 - (20 * height_cm / waist_cm) + (0.1 * age)
    else:
        # For women: approximate formula
        bf_percentage = 76 - (20 * height_cm / waist_cm) + (0.1 * age)
    
    # Clamp to reasonable range
    bf_percentage = max(5.0, min(50.0, bf_percentage))
    
    return round(bf_percentage, 1)

# Helper to get user - authentication is optional, defaults to anonymous user
async def get_current_user(request: Request):
    """Get user via JWT Bearer token, legacy X-API-KEY token, or return default anonymous user"""
    # Get Authorization header from request
    authorization = request.headers.get("Authorization")
    x_api_key = request.headers.get("X-API-KEY")
    
    # Try JWT Bearer token first
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
            if user_id is None:
                # Return default user if token invalid
                return {"id": 1, "username": "anonymous"}
            # Get user by ID
            init_db()  # Ensure DB is initialized
            def _op():
                conn = sqlite3.connect(DB_PATH)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT id, username FROM users WHERE id = ?", (int(user_id),))
                    r = cur.fetchone()
                finally:
                    conn.close()
                if not r:
                    return None
                return {"id": r[0], "username": r[1]}
            user = _with_db_retry(_op)
            if user:
                return user
        except JWTError:
            pass  # Fall through to default user
    
    # Fallback to legacy X-API-KEY token
    if x_api_key:
        user = get_user_by_token(x_api_key)
        if user:
            return user
    
    # Return default anonymous user if no authentication provided
    return {"id": 1, "username": "anonymous"}

@app.post("/api/upload")
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
                       use_height: str = Form("false"),
                       height_cm: Optional[str] = Form(None),
                       age: Optional[str] = Form("30"),
    use_segmentation: str = Form("false")
):
    # authenticate
    user = await get_current_user(request)

    # read file bytes
    data = await file.read()
    npimg = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
    if img is None:
        return JSONResponse({"error": "Could not decode image"}, status_code=400)

    # flags
    use_height_bool = True if str(use_height).lower() in ("1", "true", "yes") else False
    use_seg_bool = True if str(use_segmentation).lower() in ("1", "true", "yes") else False
    height_input = None
    if use_height_bool and height_cm:
        try:
            height_input = int(height_cm)
        except ValueError:
            height_input = None
            
    age_input = 30
    if age:
        try:
            age_input = int(age)
        except ValueError:
            age_input = 30

    # Try scientific MediaPipe Pose method first if height is provided
    body_analysis_result = None
    if height_input and height_input > 0:
        try:
            body_analysis_result = analyze_body(img, height_input, gender="male", age=age_input)
            if body_analysis_result.get("landmarks_detected"):
                # Use the scientific method results
                debug_img = body_analysis_result["annotated_image"]
                waist_cm = body_analysis_result["waist_cm"]
                body_fat_pct = body_analysis_result["body_fat_percentage"]
                neck_cm = body_analysis_result["neck_cm"]
                torso_volume_index = body_analysis_result["torso_volume_index"]
                px_per_cm = body_analysis_result["pixel_to_cm_ratio"]
                waist_px = (waist_cm / px_per_cm) if (waist_cm and px_per_cm) else None
            else:
                # Pose detection failed, fall back to old method
                body_analysis_result = None
        except Exception as e:
            print(f"MediaPipe Pose analysis error: {e}")
            body_analysis_result = None
    
    # Fall back to classic method if Pose method wasn't used or failed
    if body_analysis_result is None or not body_analysis_result.get("landmarks_detected"):
        # call estimator (pass use_segmentation)
        waist_px, debug_img, px_per_cm = estimate_waist_width_px(img, use_segmentation=use_seg_bool, height_cm=height_input)
        waist_cm = (waist_px / px_per_cm) if (waist_px is not None and px_per_cm) else None
        # Estimate body fat percentage using simplified method
        body_fat_pct = estimate_body_fat_percentage(waist_cm, height_input)
        neck_cm = None
        torso_volume_index = None
    else:
        # Already set from MediaPipe method above
        pass

    # Save original image to uploads
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_name = f"user{user['id']}_img_{ts}_{file.filename}".replace(" ", "_")
    save_path = os.path.join(UPLOAD_DIR, safe_name)
    cv2.imwrite(save_path, img)
    
    # Get workout recommendations
    workouts = []
    if body_fat_pct is not None and waist_cm is not None:
        # try:
        workouts = get_recommended_workouts(body_fat_pct, waist_cm, plan_size=6, age=age_input)
        # except Exception as e:
        #     # If recommendation fails, continue without workouts
        #     print(f"Workout recommendation error: {e}")

    # Check for anomaly before saving
    # Fetch history for anomaly check
    history_data = get_history_for_user(user['id'])
    # history_data is a list of dicts from get_history_for_user (based on previous edits)
    
    anomaly_result = check_anomaly(float(waist_cm) if waist_cm is not None else 0.0, history_data)
    
    save_status = "success"
    warning_msg = None
    
    if not anomaly_result["is_safe"]:
        save_status = "warning"
        warning_msg = anomaly_result["message"]
        # Do NOT save to DB
    else:
        # Save record in DB
        save_measurement_record(
            user['id'],
            safe_name,
            float(waist_px) if waist_px is not None else None,
            float(waist_cm) if waist_cm is not None else None,
            recommended_workouts=workouts
        )

    # prepare debug PNG to return as base64
    debug_png = png_bytes_from_bgr(debug_img)
    debug_b64 = base64.b64encode(debug_png).decode("utf-8")

    response = {
        "filename": safe_name,
        "waist_px": int(waist_px) if waist_px is not None else None,
        "waist_cm": waist_cm,
        "body_fat_percentage": body_fat_pct,
        "neck_cm": neck_cm,
        "torso_volume_index": torso_volume_index,
        "workouts": workouts,
        "debug_png_b64": debug_b64,
        "method_used": "US Navy Method (AI)" if (body_analysis_result and body_analysis_result.get("landmarks_detected")) else "Contour Approximation",
        "status": save_status,
        "message": warning_msg
    }
    
    # Trigger Gamification if successful
    if save_status == "success":
        # Increment reps? Upload usually doesn't count "reps" unless analyzed.
        # But it counts as "activity" for streak.
        # Let's verify gamification updates streak.
        game_res = check_gamification(user['id'])
        if game_res:
            response.update({
                "streak_count": game_res['streak_count'],
                "new_badges": game_res['new_badges'],
                "badges_earned": game_res['badges_earned']
            })
    
    # Add new analysis features if available
    if body_analysis_result and body_analysis_result.get("landmarks_detected"):
        response.update({
            "body_morphotype": body_analysis_result.get("body_morphotype"),
            "morphotype_description": body_analysis_result.get("morphotype_description"),
            "shoulder_to_waist_ratio": body_analysis_result.get("shoulder_to_waist_ratio"),
            "posture_issues": body_analysis_result.get("posture_issues", []),
            "posture_good": body_analysis_result.get("posture_good", []),
            "waist_to_hip_ratio": body_analysis_result.get("waist_to_hip_ratio"),
            "health_risk_level": body_analysis_result.get("health_risk_level"),
            "hip_cm": body_analysis_result.get("hip_cm"),
            "scan_quality": body_analysis_result.get("scan_quality")
        })
    else:
        # Set defaults for classic method
        response.update({
            "body_morphotype": None,
            "morphotype_description": None,
            "shoulder_to_waist_ratio": None,
            "posture_issues": [],
            "posture_good": [],
            "waist_to_hip_ratio": None,
            "health_risk_level": None,
            "hip_cm": None,
            "scan_quality": None
        })
    
    return JSONResponse(response)

@app.get("/api/history")
async def api_history(request: Request):
    user = await get_current_user(request)
    return JSONResponse(get_history_for_user(user['id']))


@app.post("/api/get_history")
async def api_get_history(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    username = (data.get("username") or "").strip()
    token = (data.get("token") or "").strip()

    if not username or not token:
        raise HTTPException(status_code=400, detail="Username and token required")

    user = get_user_by_username(username)
    if not user or user.get("token") != token:
        raise HTTPException(status_code=401, detail="Access Denied: Invalid Token")

    return JSONResponse(get_history_for_user(user["id"]))

class LogWorkoutRequest(BaseModel):
    user_id: int # Or token
    reps: int
    workout_type: str

@app.post("/api/log_workout")
async def api_log_workout(req: dict = None, request: Request = None):
    # Depending on how client sends it. Usually just check token.
    user = await get_current_user(request)
    if not user or user['username'] == 'anonymous':
        raise HTTPException(status_code=401, detail="Authentication required")
        
    try:
        data = await request.json()
        reps = data.get("reps", 0)
    except:
        reps = 0
        
    # Update total reps
    if reps > 0:
        update_user_reps(user['id'], reps)
        # NEW: Log individual session
        def _log_op():
            conn = sqlite3.connect(DB_PATH)
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO workout_logs (user_id, timestamp, reps, workout_type) VALUES (?, ?, ?, ?)",
                    (user['id'], datetime.now().isoformat(), reps, data.get("workout_type", "squat"))
                )
                conn.commit()
            finally:
                conn.close()
        _with_db_retry(_log_op)
        
    # Check gamification (streak, badges)
    game_res = check_gamification(user['id'])
    
    return JSONResponse({
        "status": "success",
        "logged_reps": reps,
        "streak_count": game_res['streak_count'] if game_res else 0,
        "new_badges": game_res['new_badges'] if game_res else [],
        "badges_earned": game_res['badges_earned'] if game_res else []
    })

@app.delete("/api/history/{item_id}")
async def api_delete_history(item_id: int, request: Request):
    user = await get_current_user(request)
    ok = delete_history_item_for_user(user['id'], item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Item not found")
    return JSONResponse({"deleted": item_id})

@app.get("/.well-known/appspecific/com.chrome.devtools.json")
async def chrome_devtools_manifest():
    return JSONResponse({})


@app.get("/api/gamification")
async def get_gamification_stats(request: Request):
    """
    Get gamification stats for the current user.
    Also updates Login Streak.
    """
    user = await get_current_user(request)
    if user['username'] == "anonymous":
         # Return empty/default for anonymous
         return JSONResponse({
             "login_streak": 0,
             "workout_streak": 0,
             "weekly_consistency": 0,
             "badges_earned": [],
             "total_reps": 0
         })
         
    user_id = user['id']
    
    # Update Login Streak just by fetching this
    check_login_streak(user_id)
    
    # Fetch all stats
    def _get_full_stats():
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT current_login_streak, current_workout_streak, weekly_consistency_score, 
                       badges_earned, total_reps_all_time
                FROM users WHERE id = ?
            """, (user_id,))
            return cur.fetchone()
        finally:
            conn.close()
            
    row = _with_db_retry(_get_full_stats)
    if not row:
        return JSONResponse({"error": "User data not found"}, status_code=404)
        
    login_streak = row[0] or 0
    workout_streak = row[1] or 0
    consistency = row[2] or 0
    badges = json.loads(row[3]) if row[3] else []
    total_reps = row[4] or 0
    
    return JSONResponse({
        "login_streak": login_streak,
        "workout_streak": workout_streak,
        "weekly_consistency": consistency,
        "badges_earned": badges,
        "total_reps": total_reps
    })

@app.post("/api/reset_counter", dependencies=[Depends(get_current_user)])
async def reset_counter_api(request: Request):
    """
    Resets the session counter or stats.
    """
    return JSONResponse(content={"status": "success", "message": "Counter reset signal received"})

# --- Video Streaming Logic ---
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

def gen_frames():
    cap = cv2.VideoCapture(0)
    
    # Instantiate the analyzer OUTSIDE the while loop
    squat_analyzer = AdvancedSquatAnalyzer() 
    
    with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
        while True:
            success, frame = cap.read()
            if not success:
                break

            # ... existing MediaPipe processing ...
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(image)
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

            if results.pose_landmarks:
                landmarks = results.pose_landmarks.landmark
                
                # PASS LANDMARKS TO ANALYZER
                # This function draws the errors directly on the 'image'
                try:
                    image, current_feedback = squat_analyzer.analyze_frame(landmarks, image)
                except Exception as e:
                    print(f"Analyzer Error: {e}")
                
                # Draw standard landmarks (optional, if you still want the stick figure)
                mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

                # --- Visual Feedback Box (Dynamic Positioning) ---
                h, w, _ = image.shape
                
                # Draw Blue Rectangle at the bottom 15% (height 80px)
                # Color: Blue (255, 0, 0) for BGR
                cv2.rectangle(image, (0, h - 80), (w, h), (255, 0, 0), -1)
                
                # Text Settings
                # Use current_feedback from analyzer, default to "Form Analysis Active" if empty
                text = current_feedback if current_feedback else "Form Analysis Active"
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 1
                thickness = 2
                
                # Calculate text size for centering
                (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
                text_x = (w - text_width) // 2
                text_y = h - 20 # Approx padding from bottom
                
                # Draw Text (White)
                cv2.putText(image, text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
                # ---------------------------------------------

            ret, buffer = cv2.imencode('.jpg', image)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    
    cap.release()

@app.get("/video_feed")
def video_feed():
    return StreamingResponse(gen_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)

