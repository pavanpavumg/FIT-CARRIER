# app_flask.py - Flask version with JWT Authentication
import os
import io
import base64
import shutil
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import cv2
import numpy as np
import sqlite3
from typing import Optional

from measure import estimate_waist_width_px

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
DB_PATH = os.path.join(BASE_DIR, "fitness_history.db")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
app.config['UPLOAD_FOLDER'] = UPLOAD_DIR
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

jwt = JWTManager(app)


# Custom JWT error handlers
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    # If it's an API request, return JSON; otherwise redirect to login
    if request.path.startswith('/api'):
        return jsonify({"error": "Token has expired"}), 401
    return redirect(url_for('login_page')), 302


@jwt.invalid_token_loader
def invalid_token_callback(error):
    # If it's an API request, return JSON; otherwise redirect to login
    if request.path.startswith('/api'):
        return jsonify({"error": "Invalid token"}), 401
    return redirect(url_for('login_page')), 302


@jwt.unauthorized_loader
def missing_token_callback(error):
    # If it's an API request, return JSON; otherwise redirect to login
    if request.path.startswith('/api'):
        return jsonify({"error": "Missing Authorization Header"}), 401
    return redirect(url_for('login_page')), 302


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
    if os.path.exists(DB_PATH):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = f"fitness_history_corrupt_{ts}.db"
        backup_path = os.path.join(BACKUP_DIR, backup_name)
        try:
            shutil.move(DB_PATH, backup_path)
        except Exception:
            try:
                os.remove(DB_PATH)
            except Exception:
                pass
    try:
        init_db()
    except Exception:
        pass
    return True


def _with_db_retry(fn):
    try:
        return fn()
    except sqlite3.IntegrityError:
        raise
    except sqlite3.DatabaseError as exc:
        if not _handle_corrupt_db(exc):
            raise
        return fn()


# DB helpers
def init_db():
    def _op():
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            # users table with password
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
            """)
            # measurements per user
            cur.execute("""
            CREATE TABLE IF NOT EXISTS measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                filename TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                waist_px REAL,
                waist_cm REAL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            """)
            conn.commit()
        finally:
            conn.close()
    return _with_db_retry(_op)


def get_user_by_username(username: str):
    def _op():
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, username, password_hash FROM users WHERE username = ?", (username,))
            r = cur.fetchone()
        finally:
            conn.close()
        if not r:
            return None
        return {"id": r[0], "username": r[1], "password_hash": r[2]}
    return _with_db_retry(_op)


def create_user(username: str, password: str):
    def _op():
        password_hash = generate_password_hash(password)
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
            conn.commit()
            user_id = cur.lastrowid
        finally:
            conn.close()
        return {"id": user_id, "username": username}
    return _with_db_retry(_op)


def get_user_by_id(user_id: int):
    def _op():
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, username FROM users WHERE id = ?", (user_id,))
            r = cur.fetchone()
        finally:
            conn.close()
        if not r:
            return None
        return {"id": r[0], "username": r[1]}
    return _with_db_retry(_op)


def save_measurement_record(user_id: int, filename: str, waist_px: Optional[float], waist_cm: Optional[float]):
    def _op():
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO measurements (user_id, filename, timestamp, waist_px, waist_cm) VALUES (?, ?, ?, ?, ?)",
                (user_id, filename, datetime.utcnow().isoformat(), waist_px, waist_cm)
            )
            conn.commit()
            rowid = cur.lastrowid
        finally:
            conn.close()
        return rowid
    return _with_db_retry(_op)


def get_history_for_user(user_id: int):
    def _op():
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, filename, timestamp, waist_px, waist_cm FROM measurements WHERE user_id = ? ORDER BY timestamp DESC",
                (user_id,)
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        result = []
        for r in rows:
            result.append({
                "id": r[0],
                "filename": r[1],
                "timestamp": r[2],
                "waist_px": r[3],
                "waist_cm": r[4]
            })
        return result
    return _with_db_retry(_op)


def delete_history_item_for_user(user_id: int, item_id: int):
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
        fp = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(fp):
            try:
                os.remove(fp)
            except Exception:
                pass
        return True
    return _with_db_retry(_op)


def png_bytes_from_bgr(img_bgr):
    _, buf = cv2.imencode(".png", img_bgr)
    return buf.tobytes()


# Init DB
init_db()


# Routes
@app.route('/')
@jwt_required()
def index():
    """Dashboard - requires JWT authentication"""
    return render_template('index.html')


@app.route('/login', endpoint='login_page')
def login_page():
    """Login page"""
    return render_template('login.html')


@app.route('/api/login', methods=['POST'])
def login():
    """Login endpoint - returns JWT token"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400
    
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    
    user = get_user_by_username(username)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401
    
    if not check_password_hash(user['password_hash'], password):
        return jsonify({"error": "Invalid credentials"}), 401
    
    # Create access token
    access_token = create_access_token(identity=user['id'])
    return jsonify({"access_token": access_token}), 200


@app.route('/api/register', methods=['POST'])
def register():
    """Register new user endpoint"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400
    
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    
    # Check if user exists
    if get_user_by_username(username):
        return jsonify({"error": "Username already exists"}), 400
    
    try:
        user = create_user(username, password)
        access_token = create_access_token(identity=user['id'])
        return jsonify({"access_token": access_token, "message": "User created successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/upload', methods=['POST'])
@jwt_required()
def upload_image():
    """Upload image endpoint - requires JWT"""
    user_id = get_jwt_identity()
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    use_height = request.form.get('use_height', 'false').lower() in ('true', '1', 'yes')
    height_cm = request.form.get('height_cm')
    use_segmentation = request.form.get('use_segmentation', 'false').lower() in ('true', '1', 'yes')
    
    # Read file
    file_bytes = file.read()
    npimg = np.frombuffer(file_bytes, np.uint8)
    img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
    if img is None:
        return jsonify({"error": "Could not decode image"}), 400
    
    # Process image
    height_input = int(height_cm) if use_height and height_cm else None
    waist_px, debug_img, px_per_cm = estimate_waist_width_px(img, use_segmentation=use_segmentation, height_cm=height_input)
    
    # Save image
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_name = f"user{user_id}_img_{ts}_{secure_filename(file.filename)}"
    save_path = os.path.join(UPLOAD_DIR, safe_name)
    cv2.imwrite(save_path, img)
    
    # Save record
    waist_cm = (waist_px / px_per_cm) if (waist_px is not None and px_per_cm) else None
    save_measurement_record(user_id, safe_name, float(waist_px) if waist_px is not None else None, float(waist_cm) if waist_cm is not None else None)
    
    # Prepare response
    debug_png = png_bytes_from_bgr(debug_img)
    debug_b64 = base64.b64encode(debug_png).decode("utf-8")
    
    response = {
        "filename": safe_name,
        "waist_px": int(waist_px) if waist_px is not None else None,
        "waist_cm": waist_cm,
        "debug_png_b64": debug_b64
    }
    return jsonify(response), 200


@app.route('/api/history', methods=['GET'])
@jwt_required()
def api_history():
    """Get history endpoint - requires JWT"""
    user_id = get_jwt_identity()
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    history = get_history_for_user(user_id)
    return jsonify(history), 200


@app.route('/api/history/<int:item_id>', methods=['DELETE'])
@jwt_required()
def api_delete_history(item_id):
    """Delete history item endpoint - requires JWT"""
    user_id = get_jwt_identity()
    ok = delete_history_item_for_user(user_id, item_id)
    if not ok:
        return jsonify({"error": "Item not found"}), 404
    return jsonify({"deleted": item_id}), 200


@app.route('/uploads/<filename>')
@jwt_required()
def uploaded_file(filename):
    """Serve uploaded files - requires JWT"""
    return send_from_directory(UPLOAD_DIR, filename)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)

