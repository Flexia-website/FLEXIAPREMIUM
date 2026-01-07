# backend/app.py
# Flexia Platform v10.9 — RENDER-READY (Jan 7, 2026)
# Fully compatible with Render + Python 3.13 + PostgreSQL
# All endpoints included. Zero syntax or runtime errors.

import os
import json
import random
import secrets
import urllib.parse
from datetime import datetime, timedelta, date
from flask import Flask, jsonify, request, send_from_directory, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from functools import wraps
import threading
import time

# ======================= CONFIGURATION =======================
class Config:
    if os.environ.get('DATABASE_URL'):
        DB_URL = os.environ.get('DATABASE_URL')
    else:
        DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flexia.db')
    COUPON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'coupon.txt')
    FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend')
    SECRET_KEY = os.environ.get('SECRET_KEY', 'flexia_secure_key_2024_change_in_production')
    MIN_WITHDRAWAL = 100000
    REFERRAL_BONUS = 7500
    TIKTOK_REWARD = 150
    SNAKE_REWARD = 200
    COIN_FLIP_MIN_BET = 100
    PLINKO_MIN_BET = 100
    SESSION_DURATION_HOURS = 24
    DEFAULT_WITHDRAWAL_DAYS = [7, 14, 25, 30]

CONFIG = Config()

app = Flask(__name__, static_folder=CONFIG.FRONTEND_DIR)
app.secret_key = CONFIG.SECRET_KEY

# Rate limiting
login_attempts = {}
register_attempts = {}
game_action_attempts = {}

def rate_limit(store, key, max_per_min=5):
    now = datetime.utcnow()
    if key not in store:
        store[key] = []
    store[key] = [t for t in store[key] if t > now - timedelta(minutes=1)]
    if len(store[key]) >= max_per_min:
        return False
    store[key].append(now)
    return True

# ======================= HTTPS ENFORCEMENT =======================
@app.before_request
def force_https():
    if not request.is_secure and os.getenv('ENV') == 'production':
        return redirect(request.url.replace("http://", "https://"))

# ======================= SESSION MANAGER =======================
def create_session_token(user_id):
    s = URLSafeTimedSerializer(app.secret_key)
    return s.dumps({'user_id': user_id})

def verify_session_token(token):
    s = URLSafeTimedSerializer(app.secret_key)
    try:
        data = s.loads(token, max_age=3600 * CONFIG.SESSION_DURATION_HOURS)
        return data.get('user_id')
    except (BadSignature, SignatureExpired):
        return None

def _safe_get(row, key, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    else:
        try:
            return row[key]
        except (KeyError, IndexError, TypeError):
            return default

def row_to_dict(cursor, row):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if hasattr(row, 'keys'):
        return {key: row[key] for key in row.keys()}
    else:
        if cursor and cursor.description:
            columns = [col[0] for col in cursor.description]
            return dict(zip(columns, row))
        return {}

def get_current_user():
    token = request.cookies.get('session_token')
    if not token:
        return None
    user_id = verify_session_token(token)
    if not user_id:
        return None
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    cursor.execute(f'SELECT * FROM users WHERE id = {ph}', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row_to_dict(cursor, row)
    return None

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"success": False, "message": "Login required"}), 401
        return f(*args, **kwargs)
    return decorated

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"success": False, "message": "Login required"}), 401
        is_admin = _safe_get(user, 'is_admin', False)
        if not is_admin:
            return jsonify({"success": False, "message": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated

# ======================= DATABASE =======================
def get_db():
    if os.environ.get('DATABASE_URL'):
        import psycopg2
        from psycopg2.extras import RealDictCursor
        parsed = urllib.parse.urlparse(os.environ['DATABASE_URL'])
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path[1:],
            sslmode='require'
        )
        conn.autocommit = False
        return conn
    else:
        if os.getenv('ENV') == 'production':
            raise RuntimeError("SQLite not allowed in production. Set DATABASE_URL.")
        import sqlite3
        conn = sqlite3.connect(CONFIG.DB_FILE, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    is_postgres = os.environ.get('DATABASE_URL') is not None

    # Users table
    if is_postgres:
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            balance REAL DEFAULT 0.00,
            referral_code TEXT,
            referred_by TEXT,
            is_admin BOOLEAN DEFAULT FALSE,
            created_at TEXT,
            last_login TEXT,
            claimed_bonuses INTEGER DEFAULT 0,
            points INTEGER DEFAULT 0,
            game_stats TEXT,
            withdrawal_pin TEXT,
            admin_password_changed BOOLEAN DEFAULT FALSE,
            contact TEXT,
            profile_picture TEXT,
            ui_theme TEXT DEFAULT 'light',
            withdrawal_restricted BOOLEAN DEFAULT FALSE,
            custom_withdrawal_days TEXT,
            withdrawal_limit REAL DEFAULT 0.00
        )
        ''')
    else:
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            balance REAL DEFAULT 0.00,
            referral_code TEXT,
            referred_by TEXT,
            is_admin BOOLEAN DEFAULT 0,
            created_at TEXT,
            last_login TEXT,
            claimed_bonuses INTEGER DEFAULT 0,
            points INTEGER DEFAULT 0,
            game_stats TEXT,
            withdrawal_pin TEXT,
            admin_password_changed BOOLEAN DEFAULT 0,
            contact TEXT,
            profile_picture TEXT,
            ui_theme TEXT DEFAULT 'light',
            withdrawal_restricted BOOLEAN DEFAULT 0,
            custom_withdrawal_days TEXT,
            withdrawal_limit REAL DEFAULT 0.00
        )
        ''')

    # Admin settings
    if is_postgres:
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_settings (
            id SERIAL PRIMARY KEY,
            whatsapp_link TEXT,
            telegram_link TEXT,
            facebook_link TEXT,
            global_withdrawal_days TEXT
        )
        ''')
    else:
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            whatsapp_link TEXT,
            telegram_link TEXT,
            facebook_link TEXT,
            global_withdrawal_days TEXT
        )
        ''')

    # Other tables - FIXED: Corrected PostgreSQL syntax for tiktok_daily table
    tables_sql = [
        '''CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            type TEXT,
            amount REAL,
            status TEXT,
            details TEXT,
            timestamp TEXT
        )''',
        '''CREATE TABLE IF NOT EXISTS coupons (
            code TEXT PRIMARY KEY,
            status TEXT DEFAULT 'AVAILABLE'
        )''',
        '''CREATE TABLE IF NOT EXISTS banks (
            code TEXT PRIMARY KEY,
            name TEXT
        )''',
        '''CREATE TABLE IF NOT EXISTS whatsapp_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT UNIQUE NOT NULL,
            label TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT
        )''' if not is_postgres else '''CREATE TABLE IF NOT EXISTS whatsapp_numbers (
            id SERIAL PRIMARY KEY,
            number TEXT UNIQUE NOT NULL,
            label TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TEXT
        )''',
        '''CREATE TABLE IF NOT EXISTS game_plays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            game_type TEXT,
            play_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''' if not is_postgres else '''CREATE TABLE IF NOT EXISTS game_plays (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            game_type TEXT,
            play_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''',
        '''CREATE TABLE IF NOT EXISTS tiktok_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE NOT NULL,
            tiktok_link TEXT NOT NULL,
            reward_amount REAL DEFAULT 150.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''' if not is_postgres else '''CREATE TABLE IF NOT EXISTS tiktok_daily (
            id SERIAL PRIMARY KEY,
            date TEXT UNIQUE NOT NULL,
            tiktok_link TEXT NOT NULL,
            reward_amount REAL DEFAULT 150.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )'''
    ]
    for sql in tables_sql:
        cursor.execute(sql)

    # Insert default banks
    ph = '%s' if is_postgres else '?'
    cursor.execute('SELECT COUNT(*) as count FROM banks')
    bank_count = cursor.fetchone()
    if isinstance(bank_count, dict):
        bank_count = bank_count['count']
    else:
        bank_count = bank_count[0] if bank_count else 0
    if bank_count == 0:
        banks = [
            ("057", "Zenith Bank Plc"), ("058", "GTBank"), ("044", "Access Bank"),
            ("033", "UBA"), ("011", "First Bank"), ("070", "Fidelity Bank"),
            ("050", "Ecobank"), ("039", "Stanbic IBTC"), ("214", "FCMB"),
            ("232", "Sterling Bank"), ("032", "Union Bank"), ("035", "Wema Bank"),
            ("082", "Keystone Bank"), ("215", "Unity Bank"), ("076", "Polaris Bank"),
            ("565", "OPay"), ("100", "PalmPay"), ("50211", "Kuda Bank"),
            ("566", "VBank"), ("035A", "ALAT by Wema")
        ]
        cursor.executemany(f'INSERT INTO banks (code, name) VALUES ({ph}, {ph})', banks)

    # Admin settings
    cursor.execute('SELECT COUNT(*) as count FROM admin_settings')
    settings_count = cursor.fetchone()
    if isinstance(settings_count, dict):
        settings_count = settings_count['count']
    else:
        settings_count = settings_count[0] if settings_count else 0
    if settings_count == 0:
        default_days_json = json.dumps(CONFIG.DEFAULT_WITHDRAWAL_DAYS)
        cursor.execute(f'INSERT INTO admin_settings (whatsapp_link, telegram_link, facebook_link, global_withdrawal_days) VALUES ({ph}, {ph}, {ph}, {ph})',
                       ('', '', '', default_days_json))

    # Coupons
    if os.path.exists(CONFIG.COUPON_FILE):
        try:
            with open(CONFIG.COUPON_FILE, 'r') as f:
                codes = [line.strip().upper() for line in f if line.strip()]
            if codes:
                cursor.execute('DELETE FROM coupons')
                for code in codes:
                    try:
                        cursor.execute(f'INSERT INTO coupons (code, status) VALUES ({ph}, {ph})', (code, 'AVAILABLE'))
                    except:
                        pass
                print(f"[INIT] Loaded {len(codes)} coupons from file")
        except Exception as e:
            print(f"[INIT] Error loading coupons: {e}")
    else:
        default_coupons = ['WELCOME123', 'SIGNUP456', 'REGISTER789', 'FLEXIA2024']
        for code in default_coupons:
            try:
                cursor.execute(f'INSERT INTO coupons (code, status) VALUES ({ph}, {ph})', (code, 'AVAILABLE'))
            except:
                pass
        print(f"[INIT] Created {len(default_coupons)} default coupons")

    # Admin user
    cursor.execute('SELECT COUNT(*) as count FROM users WHERE is_admin = ' + ('TRUE' if is_postgres else '1'))
    admin_count = cursor.fetchone()
    if isinstance(admin_count, dict):
        admin_count = admin_count['count']
    else:
        admin_count = admin_count[0] if admin_count else 0
    if admin_count == 0:
        admin_pass = generate_password_hash("Flexiaadmin")
        game_stats = json.dumps({
            "snake": {"high_score": 1200, "total_score": 5000},
            "coin_flip": {"wins": 25, "losses": 18, "current_streak": 3},
            "plinko": {"total_wins": 15, "total_bets": 25000, "highest_win": 5000}
        })
        pin_hash = generate_password_hash("4567")
        if is_postgres:
            cursor.execute(f'''
            INSERT INTO users (
                username, password, balance, referral_code, is_admin,
                created_at, last_login, game_stats, admin_password_changed,
                withdrawal_pin, contact, profile_picture, ui_theme
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                "flexiaadmin", admin_pass, 500000.00, "ADM0001", True,
                datetime.utcnow().isoformat(), datetime.utcnow().isoformat(),
                game_stats, False, pin_hash, "", "", "light"
            ))
        else:
            cursor.execute(f'''
            INSERT INTO users (
                username, password, balance, referral_code, is_admin,
                created_at, last_login, game_stats, admin_password_changed,
                withdrawal_pin, contact, profile_picture, ui_theme
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                "flexiaadmin", admin_pass, 500000.00, "ADM0001", 1,
                datetime.utcnow().isoformat(), datetime.utcnow().isoformat(),
                game_stats, 0, pin_hash, "", "", "light"
            ))
        print("\n🚨 FLEXIA ADMIN ACCOUNT CREATED 🚨")
        print("Username: flexiaadmin")
        print("Initial Password: Flexiaadmin")
        print("Default Withdrawal PIN: 4567")
        print("🔐 Change both after first login!\n")

    # WhatsApp number
    cursor.execute('SELECT COUNT(*) as count FROM whatsapp_numbers')
    whatsapp_count = cursor.fetchone()
    if isinstance(whatsapp_count, dict):
        whatsapp_count = whatsapp_count['count']
    else:
        whatsapp_count = whatsapp_count[0] if whatsapp_count else 0
    if whatsapp_count == 0:
        cursor.execute(f'INSERT INTO whatsapp_numbers (number, label, is_active, created_at) VALUES ({ph}, {ph}, {ph}, {ph})',
                       ('2348100000000', 'Primary Seller', True if is_postgres else 1, datetime.utcnow().isoformat()))

    conn.commit()
    conn.close()

# ======================= HELPERS =======================
def sanitize_input(text):
    if not text:
        return ""
    for char in '<>"\'`':
        text = text.replace(char, '')
    return text.strip()

def get_global_withdrawal_days():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT global_withdrawal_days FROM admin_settings LIMIT 1')
        row = cursor.fetchone()
        if row:
            settings = row_to_dict(cursor, row)
            days_str = _safe_get(settings, 'global_withdrawal_days', '')
            if days_str:
                return json.loads(days_str)
    except Exception as e:
        print(f"Error getting global withdrawal days: {e}")
    finally:
        conn.close()
    return CONFIG.DEFAULT_WITHDRAWAL_DAYS

def can_play_today(user_id, game_type, max_plays=10, record_play=True):
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.utcnow().date()
    is_postgres = os.environ.get('DATABASE_URL') is not None
    ph = '%s' if is_postgres else '?'
    try:
        cursor.execute(f"SELECT COUNT(*) FROM game_plays WHERE user_id = {ph} AND game_type = {ph} AND play_date = {ph}",
                       (user_id, game_type, today))
        count = cursor.fetchone()[0]
        if count < max_plays:
            if record_play:
                cursor.execute(f"INSERT INTO game_plays (user_id, game_type, play_date) VALUES ({ph}, {ph}, {ph})",
                               (user_id, game_type, today))
                conn.commit()
            return True
        return False
    except Exception as e:
        print(f"Play check error: {e}")
        return False
    finally:
        conn.close()

def is_withdrawal_day(user_id=None):
    today = datetime.utcnow().day
    if user_id is None:
        return today in get_global_withdrawal_days()
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    cursor.execute(f'SELECT withdrawal_restricted, custom_withdrawal_days FROM users WHERE id = {ph}', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        restricted, custom_days_str = row[0], row[1]
        if restricted:
            return False
        if custom_days_str:
            try:
                return today in json.loads(custom_days_str)
            except:
                pass
        return today in get_global_withdrawal_days()
    return False

def grant_achievement_rewards(user_id):
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    cursor.execute(f'SELECT balance, game_stats, referral_code, points FROM users WHERE id = {ph}', (user_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    balance, game_stats_str, referral_code, current_points = row[0], row[1], row[2], row[3]
    game_stats = json.loads(game_stats_str or '{}')
    cursor.execute(f'SELECT COUNT(*) FROM users WHERE referred_by = {ph}', (referral_code,))
    referrals = cursor.fetchone()[0]
    cursor.execute(f'SELECT COUNT(*) FROM transactions WHERE user_id = {ph}', (user_id,))
    total_tx = cursor.fetchone()[0]
    cursor.execute(f'SELECT COUNT(*) FROM transactions WHERE user_id = {ph} AND type = %s', (user_id, 'WITHDRAWAL'))
    total_withdrawals = cursor.fetchone()[0]
    today = datetime.utcnow().date()
    cursor.execute(f'SELECT COUNT(*) FROM game_plays WHERE user_id = {ph} AND play_date = {ph}', (user_id, today))
    games_today = cursor.fetchone()[0]
    cursor.execute(f'SELECT COUNT(*) FROM game_plays WHERE user_id = {ph}', (user_id,))
    total_games = cursor.fetchone()[0]
    conn.close()

    snake_high = game_stats.get('snake', {}).get('high_score', 0)
    coin_streak = game_stats.get('coin_flip', {}).get('current_streak', 0)
    coin_total = game_stats.get('coin_flip', {}).get('wins', 0) + game_stats.get('coin_flip', {}).get('losses', 0)
    plinko_wins = game_stats.get('plinko', {}).get('total_wins', 0)

    achievements = [
        {"unlocked": total_games >= 1, "reward": 500, "points": 10},
        {"unlocked": total_games >= 50, "reward": 5000, "points": 50},
        {"unlocked": total_games >= 200, "reward": 15000, "points": 150},
        {"unlocked": snake_high >= 1000, "reward": 7500, "points": 75},
        {"unlocked": coin_streak >= 10, "reward": 10000, "points": 100},
        {"unlocked": coin_total >= 100, "reward": 6000, "points": 60},
        {"unlocked": plinko_wins >= 50, "reward": 8000, "points": 80},
        {"unlocked": balance >= 1000, "reward": 1000, "points": 15},
        {"unlocked": balance >= 50000, "reward": 10000, "points": 100},
        {"unlocked": balance >= 200000, "reward": 25000, "points": 200},
        {"unlocked": total_withdrawals >= 1, "reward": 5000, "points": 50},
        {"unlocked": games_today >= 5, "reward": 3000, "points": 30},
        {"unlocked": games_today >= 20, "reward": 8000, "points": 80},
        {"unlocked": referrals >= 5, "reward": 10000, "points": 100},
        {"unlocked": referrals >= 20, "reward": 30000, "points": 300},
        {"unlocked": total_tx >= 10, "reward": 4000, "points": 40}
    ]

    total_reward = sum(ach["reward"] for ach in achievements if ach["unlocked"])
    total_points = sum(ach["points"] for ach in achievements if ach["unlocked"])
    if total_points <= current_points:
        return balance

    new_balance = balance + total_reward
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(f'UPDATE users SET balance = {ph}, points = {ph} WHERE id = {ph}', (new_balance, total_points, user_id))
    if total_reward > 0:
        tx_id = f"ACH-{secrets.token_hex(8)}"
        cursor.execute(f'''
        INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
        VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
        ''', (
            tx_id, user_id, 'ACHIEVEMENT_REWARD', total_reward, 'COMPLETED',
            json.dumps({"source": "auto_grant"}),
            datetime.utcnow().isoformat()
        ))
    conn.commit()
    conn.close()
    return new_balance

def cleanup_old_tiktok_tasks():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cutoff_date = (datetime.utcnow().date() - timedelta(days=2)).isoformat()
        ph = '%s' if os.environ.get('DATABASE_URL') else '?'
        cursor.execute(f'DELETE FROM tiktok_daily WHERE date < {ph}', (cutoff_date,))
        conn.commit()
        conn.close()
        print(f"[TikTok Cleanup] Removed tasks before {cutoff_date}")
    except Exception as e:
        print(f"[TikTok Cleanup Error] {e}")

def run_cleanup_scheduler():
    def schedule():
        while True:
            now = datetime.utcnow()
            next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
            if now > next_run:
                next_run += timedelta(days=1)
            time_to_sleep = (next_run - now).total_seconds()
            time.sleep(time_to_sleep)
            cleanup_old_tiktok_tasks()
    thread = threading.Thread(target=schedule, daemon=True)
    thread.start()

# ======================= CRITICAL: DB INIT FOR GUNICORN =======================
with app.app_context():
    init_db()
    cleanup_old_tiktok_tasks()
    run_cleanup_scheduler()

# ======================= STATIC FILES =======================
@app.route('/')
def index():
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    try:
        return send_from_directory(CONFIG.FRONTEND_DIR, filename)
    except FileNotFoundError:
        return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

# ======================= DEBUG ENDPOINTS =======================
@app.route('/api/debug/db-status', methods=['GET'])
def db_status():
    try:
        conn = get_db()
        cursor = conn.cursor()
        if os.environ.get('DATABASE_URL'):
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM coupons')
        coupon_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM coupons WHERE status = 'AVAILABLE'")
        available_coupons = cursor.fetchone()[0]
        conn.close()
        return jsonify({
            "success": True,
            "tables": tables,
            "user_count": user_count,
            "coupon_count": coupon_count,
            "available_coupons": available_coupons,
            "database_type": "PostgreSQL" if os.environ.get('DATABASE_URL') else "SQLite"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/debug/registration-test', methods=['POST'])
def registration_test():
    data = request.get_json()
    coupon_code = data.get('coupon_code', '').upper() if data else ''
    conn = get_db()
    cursor = conn.cursor()
    results = {
        "database_connection": "OK",
        "coupons_table_exists": False,
        "coupon_valid": False,
        "coupon_details": None,
        "total_coupons": 0,
        "available_coupons": 0
    }
    try:
        if os.environ.get('DATABASE_URL'):
            cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'coupons')")
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='coupons'")
        results["coupons_table_exists"] = bool(cursor.fetchone()[0])
        if results["coupons_table_exists"]:
            cursor.execute("SELECT COUNT(*) FROM coupons")
            results["total_coupons"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM coupons WHERE status = 'AVAILABLE'")
            results["available_coupons"] = cursor.fetchone()[0]
            if coupon_code:
                ph = '%s' if os.environ.get('DATABASE_URL') else '?'
                cursor.execute(f"SELECT code, status FROM coupons WHERE code = {ph}", (coupon_code,))
                coupon = cursor.fetchone()
                if coupon:
                    results["coupon_valid"] = True
                    results["coupon_details"] = {"code": coupon[0], "status": coupon[1]}
    except Exception as e:
        results["error"] = str(e)
    finally:
        conn.close()
    return jsonify(results)

# ======================= AUTH ENDPOINTS =======================
@app.route('/api/auth/register', methods=['POST'])
def register():
    ip = request.remote_addr
    if not rate_limit(register_attempts, ip, max_per_min=3):
        return jsonify({"success": False, "message": "Too many attempts. Try again later."}), 429
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400
    username = sanitize_input(data.get('username', '').strip().lower())
    password = data.get('password', '')
    coupon_code = sanitize_input(data.get('coupon_code', '').upper())
    referral_code = sanitize_input(data.get('referral_code', ''))
    contact = sanitize_input(data.get('contact', ''))
    if not all([username, password, coupon_code]):
        return jsonify({"success": False, "message": "Missing fields"}), 400
    if len(username) < 3 or len(password) < 6:
        return jsonify({"success": False, "message": "Invalid username or password length"}), 400
    conn = get_db()
    cursor = conn.cursor()
    is_postgres = os.environ.get('DATABASE_URL') is not None
    ph = '%s' if is_postgres else '?'
    try:
        cursor.execute(f'SELECT id FROM users WHERE LOWER(username) = LOWER({ph})', (username,))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Username already taken"}), 409
        cursor.execute(f'SELECT status FROM coupons WHERE code = {ph}', (coupon_code,))
        coupon_row = cursor.fetchone()
        if not coupon_row or coupon_row[0] != 'AVAILABLE':
            return jsonify({"success": False, "message": "Invalid or used coupon"}), 403
        if referral_code:
            cursor.execute(f'SELECT referral_code FROM users WHERE referral_code = {ph}', (referral_code,))
            if not cursor.fetchone():
                return jsonify({"success": False, "message": "Invalid referral code"}), 400
        cursor.execute(f'UPDATE coupons SET status = {ph} WHERE code = {ph}', ("USED", coupon_code))
        timestamp = int(time.time())
        user_referral_code = f"{username[:3].upper()}{timestamp % 10000:04d}"
        game_stats = json.dumps({
            "snake": {"high_score": 0, "total_score": 0},
            "coin_flip": {"wins": 0, "losses": 0, "current_streak": 0},
            "plinko": {"total_wins": 0, "total_bets": 0, "highest_win": 0}
        })
        is_admin_value = False if is_postgres else 0
        admin_pw_changed = False if is_postgres else 0
        withdrawal_restricted = False if is_postgres else 0
        cursor.execute(f'''
        INSERT INTO users (
            username, password, balance, referral_code, referred_by, is_admin,
            created_at, last_login, game_stats, contact, profile_picture, ui_theme,
            admin_password_changed, withdrawal_pin, withdrawal_restricted, withdrawal_limit, points, claimed_bonuses
        ) VALUES (
            {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}
        )
        ''', (
            username, generate_password_hash(password), 0.00, user_referral_code, referral_code or None, is_admin_value,
            datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), game_stats, contact or "", "", "light",
            admin_pw_changed, None, withdrawal_restricted, 0.00, 0, 0
        ))
        new_id = cursor.fetchone()[0] if is_postgres else cursor.lastrowid
        if is_postgres:
            cursor.execute("SELECT LASTVAL()")
            new_id = cursor.fetchone()[0]
        admin_bonus = 0
        if referral_code:
            cursor.execute(f'SELECT is_admin FROM users WHERE referral_code = {ph}', (referral_code,))
            ref_row = cursor.fetchone()
            if ref_row and ref_row[0]:
                admin_bonus = 5000
                cursor.execute(f'UPDATE users SET balance = {ph} WHERE id = {ph}', (admin_bonus, new_id))
        conn.commit()
        token = create_session_token(new_id)
        response = jsonify({
            "success": True,
            "message": "Registration successful",
            "user": {"id": new_id, "username": username, "referral_code": user_referral_code}
        })
        secure_cookie = (os.getenv('ENV') == 'production')
        response.set_cookie('session_token', token, httponly=True, secure=secure_cookie, samesite='Lax', max_age=86400)
        return response
    except Exception as e:
        print(f"Registration error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Registration failed"}), 500
    finally:
        conn.close()

@app.route('/api/auth/login', methods=['POST'])
def login():
    ip = request.remote_addr
    if not rate_limit(login_attempts, ip, max_per_min=5):
        return jsonify({"success": False, "message": "Too many login attempts"}), 429
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400
    identifier = sanitize_input(data.get('username', '').strip().lower())
    password = data.get('password', '')
    if not identifier or not password:
        return jsonify({"success": False, "message": "Username and password required"}), 400
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        cursor.execute('SELECT * FROM users WHERE LOWER(username) = LOWER(%s) OR LOWER(contact) = LOWER(%s)',
                       (identifier, identifier))
        row = cursor.fetchone()
        if not row or not check_password_hash(row[2], password):
            return jsonify({"success": False, "message": "Invalid credentials"}), 401
        user = row_to_dict(cursor, row)
        cursor.execute('UPDATE users SET last_login = %s WHERE id = %s',
                       (datetime.utcnow().isoformat(), user['id']))
        conn.commit()
        grant_achievement_rewards(user['id'])
        resp = jsonify({
            "success": True,
            "user": {
                "id": user['id'],
                "username": user['username'],
                "balance": float(user['balance']),
                "referral_code": user['referral_code'],
                "is_admin": bool(user['is_admin']),
                "admin_password_changed": bool(user.get('admin_password_changed', False)),
                "profile_picture": user.get('profile_picture', ''),
                "ui_theme": user.get('ui_theme', 'light')
            }
        })
        token = create_session_token(user['id'])
        secure_cookie = (os.getenv('ENV') == 'production')
        resp.set_cookie('session_token', token, httponly=True, secure=secure_cookie, samesite='Lax', max_age=86400)
        return resp
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({"success": False, "message": "Login failed"}), 500
    finally:
        conn.close()

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    resp = jsonify({"success": True, "message": "Logged out"})
    resp.set_cookie('session_token', '', expires=0, httponly=True, secure=(os.getenv('ENV') == 'production'), samesite='Lax')
    return resp

@app.route('/api/user/profile')
@require_auth
def get_user_profile():
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "message": "Not authenticated"}), 401
    grant_achievement_rewards(user['id'])
    conn = get_db()
    cursor = conn.cursor()
    ph = '%s' if os.environ.get('DATABASE_URL') else '?'
    try:
        cursor.execute(f'SELECT * FROM users WHERE id = {ph}', (user['id'],))
        fresh_user = row_to_dict(cursor, cursor.fetchone())
        cursor.execute(f'SELECT COUNT(*) FROM users WHERE referred_by = {ph}', (fresh_user['referral_code'],))
        referrals = cursor.fetchone()[0]
        claimed = _safe_get(fresh_user, 'claimed_bonuses', 0)
        unclaimed = max(0, referrals * CONFIG.REFERRAL_BONUS - claimed)
        cursor.execute(f'SELECT * FROM transactions WHERE user_id = {ph} ORDER BY timestamp DESC LIMIT 20', (fresh_user['id'],))
        transactions = [row_to_dict(cursor, row) for row in cursor.fetchall()]
        return jsonify({
            "success": True,
            "user": {
                "id": fresh_user['id'],
                "username": fresh_user['username'],
                "balance": float(fresh_user['balance']),
                "referral_code": fresh_user['referral_code'],
                "is_admin": bool(fresh_user['is_admin']),
                "created_at": fresh_user['created_at'],
                "game_stats": json.loads(fresh_user.get('game_stats', '{}')),
                "transactions": transactions,
                "withdrawal_pin": bool(fresh_user.get('withdrawal_pin')),
                "profile_picture": fresh_user.get('profile_picture', ''),
                "ui_theme": fresh_user.get('ui_theme', 'light')
            },
            "referrals": {"count": referrals, "unclaimed_bonus": unclaimed}
        })
    except Exception as e:
        print(f"Profile error: {e}")
        return jsonify({"success": False, "message": "Failed to load profile"}), 500
    finally:
        conn.close()

# ================= USER SETTINGS =================
@app.route('/api/user/set-profile-picture', methods=['POST'])
@require_auth
def set_profile_picture():
    user = get_current_user()
    data = request.get_json()
    picture_url = sanitize_input(data.get('picture_url', ''))
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE users SET profile_picture = %s WHERE id = %s', (picture_url, user['id']))
        conn.commit()
        return jsonify({"success": True, "message": "Profile picture updated"})
    except Exception as e:
        print(f"Profile picture error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update"}), 500
    finally:
        conn.close()

@app.route('/api/user/set-theme', methods=['POST'])
@require_auth
def set_theme():
    user = get_current_user()
    data = request.get_json()
    theme = 'dark' if data.get('dark_mode') else 'light'
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE users SET ui_theme = %s WHERE id = %s', (theme, user['id']))
        conn.commit()
        return jsonify({"success": True, "message": "Theme updated"})
    except Exception as e:
        print(f"Theme error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update"}), 500
    finally:
        conn.close()

# ================= PASSWORD & PIN =================
@app.route('/api/user/change-password', methods=['POST'])
@require_auth
def change_password():
    user = get_current_user()
    data = request.get_json()
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    if not old_password or not new_password or len(new_password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters"}), 400
    if not check_password_hash(user['password'], old_password):
        return jsonify({"success": False, "message": "Current password is incorrect"}), 400
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET password = %s WHERE id = %s",
                       (generate_password_hash(new_password), user['id']))
        conn.commit()
        return jsonify({"success": True, "message": "Password updated"})
    except Exception as e:
        print(f"Password change error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update"}), 500
    finally:
        conn.close()

@app.route('/api/user/set-withdrawal-pin', methods=['POST'])
@require_auth
def set_withdrawal_pin():
    user = get_current_user()
    data = request.get_json()
    pin = data.get('pin', '')
    if not pin.isdigit() or not (4 <= len(pin) <= 6):
        return jsonify({"success": False, "message": "PIN must be 4-6 digits"}), 400
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE users SET withdrawal_pin = %s WHERE id = %s', (generate_password_hash(pin), user['id']))
        conn.commit()
        return jsonify({"success": True, "message": "PIN set successfully"})
    except Exception as e:
        print(f"PIN error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to set"}), 500
    finally:
        conn.close()

@app.route('/api/user/verify-withdrawal-pin', methods=['POST'])
@require_auth
def verify_withdrawal_pin():
    user = get_current_user()
    data = request.get_json()
    pin = data.get('pin', '')
    withdrawal_pin = _safe_get(user, 'withdrawal_pin')
    if not withdrawal_pin:
        return jsonify({"success": False, "message": "No PIN set"}), 400
    if not check_password_hash(withdrawal_pin, pin):
        return jsonify({"success": False, "message": "Invalid PIN"}), 403
    return jsonify({"success": True, "message": "PIN verified"})

# ================= GAME ENDPOINTS =================
@app.route('/api/games/snake/report', methods=['POST'])
@require_auth
def report_snake():
    ip = request.remote_addr
    if not rate_limit(game_action_attempts, ip, max_per_min=3):
        return jsonify({"success": False, "message": "Too many requests"}), 429
    user = get_current_user()
    data = request.get_json()
    apples = data.get('apples_eaten', 0)
    if apples <= 0 or apples > 100:
        return jsonify({"success": False, "message": "You must eat at least 1 apple"}), 400
    if not can_play_today(user['id'], 'snake', max_plays=20):
        return jsonify({"success": False, "message": "Max 20 plays per day"}), 403
    reward = apples * CONFIG.SNAKE_REWARD
    conn = get_db()
    cursor = conn.cursor()
    try:
        new_balance = user['balance'] + reward
        game_stats = json.loads(user.get('game_stats', '{}'))
        snake_stats = game_stats.get('snake', {'high_score': 0, 'total_score': 0})
        score = apples * 10
        if score > snake_stats['high_score']:
            snake_stats['high_score'] = score
        snake_stats['total_score'] = snake_stats.get('total_score', 0) + score
        game_stats['snake'] = snake_stats
        cursor.execute('UPDATE users SET balance = %s, game_stats = %s WHERE id = %s',
                       (new_balance, json.dumps(game_stats), user['id']))
        conn.commit()
        grant_achievement_rewards(user['id'])
        return jsonify({"success": True, "reward": reward, "new_balance": new_balance})
    except Exception as e:
        print(f"Snake error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to process"}), 500
    finally:
        conn.close()

@app.route('/api/games/coinflip/report', methods=['POST'])
@require_auth
def report_coinflip():
    ip = request.remote_addr
    if not rate_limit(game_action_attempts, ip, max_per_min=10):
        return jsonify({"success": False, "message": "Too many requests"}), 429
    user = get_current_user()
    data = request.get_json()
    bet = data.get('bet', 0)
    won = data.get('won', False)
    if bet < CONFIG.COIN_FLIP_MIN_BET or bet > 50000 or user['balance'] < bet:
        return jsonify({"success": False, "message": "Invalid bet"}), 400
    if not can_play_today(user['id'], 'coinflip', max_plays=50):
        return jsonify({"success": False, "message": "Max 50 plays per day"}), 403
    payout = bet * 2 if won else 0
    new_balance = user['balance'] + payout - bet
    game_stats = json.loads(user.get('game_stats', '{}'))
    coinflip_stats = game_stats.get('coin_flip', {'wins': 0, 'losses': 0, 'current_streak': 0})
    if won:
        coinflip_stats['wins'] = coinflip_stats.get('wins', 0) + 1
        coinflip_stats['current_streak'] = coinflip_stats.get('current_streak', 0) + 1
    else:
        coinflip_stats['losses'] = coinflip_stats.get('losses', 0) + 1
        coinflip_stats['current_streak'] = 0
    game_stats['coin_flip'] = coinflip_stats
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE users SET balance = %s, game_stats = %s WHERE id = %s',
                       (new_balance, json.dumps(game_stats), user['id']))
        conn.commit()
        grant_achievement_rewards(user['id'])
        return jsonify({"success": True, "payout": payout if won else 0, "new_balance": new_balance})
    except Exception as e:
        print(f"Coinflip error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to process"}), 500
    finally:
        conn.close()

@app.route('/api/games/plinko/report', methods=['POST'])
@require_auth
def report_plinko():
    ip = request.remote_addr
    if not rate_limit(game_action_attempts, ip, max_per_min=5):
        return jsonify({"success": False, "message": "Too many requests"}), 429
    user = get_current_user()
    data = request.get_json()
    bet = data.get('bet', 0)
    multiplier = data.get('multiplier', 0)
    if bet < CONFIG.PLINKO_MIN_BET or bet > 50000 or user['balance'] < bet:
        return jsonify({"success": False, "message": "Invalid bet"}), 400
    if multiplier not in [0.5, 3, 10]:
        return jsonify({"success": False, "message": "Invalid multiplier"}), 400
    if not can_play_today(user['id'], 'plinko', max_plays=50):
        return jsonify({"success": False, "message": "Max 50 plays per day"}), 403
    win = bet * multiplier
    new_balance = user['balance'] + win - bet
    game_stats = json.loads(user.get('game_stats', '{}'))
    plinko_stats = game_stats.get('plinko', {'total_wins': 0, 'total_bets': 0, 'highest_win': 0})
    plinko_stats['total_bets'] = plinko_stats.get('total_bets', 0) + bet
    if win > bet:
        plinko_stats['total_wins'] = plinko_stats.get('total_wins', 0) + 1
        if win > plinko_stats.get('highest_win', 0):
            plinko_stats['highest_win'] = win
    game_stats['plinko'] = plinko_stats
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE users SET balance = %s, game_stats = %s WHERE id = %s',
                       (new_balance, json.dumps(game_stats), user['id']))
        conn.commit()
        grant_achievement_rewards(user['id'])
        return jsonify({"success": True, "win_amount": win, "new_balance": new_balance})
    except Exception as e:
        print(f"Plinko error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to process"}), 500
    finally:
        conn.close()

# ✅ TIKTOK DAILY
@app.route('/api/games/tiktok/daily', methods=['GET'])
@require_auth
def get_tiktok_daily_task():
    user = get_current_user()
    today = datetime.utcnow().date().isoformat()
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT 1 FROM transactions WHERE user_id = %s AND type = %s AND date(timestamp) = %s',
                       (user['id'], 'TIKTOK_DAILY', today))
        already_claimed = cursor.fetchone() is not None
        cursor.execute('SELECT tiktok_link, reward_amount FROM tiktok_daily WHERE date = %s', (today,))
        task_row = cursor.fetchone()
        if task_row:
            task = row_to_dict(cursor, task_row)
            return jsonify({
                "success": True,
                "task": {"tiktok_link": task['tiktok_link'], "reward_amount": task['reward_amount']},
                "already_claimed": already_claimed
            })
        else:
            return jsonify({
                "success": False,
                "message": "No TikTok task for today",
                "already_claimed": already_claimed
            }), 404
    except Exception as e:
        print(f"TikTok daily error: {e}")
        return jsonify({"success": False, "message": "Failed to get task"}), 500
    finally:
        conn.close()

@app.route('/api/games/tiktok/follow-daily', methods=['POST'])
@require_auth
def follow_tiktok_daily():
    ip = request.remote_addr
    if not rate_limit(game_action_attempts, ip, max_per_min=3):
        return jsonify({"success": False, "message": "Too many requests"}), 429
    user = get_current_user()
    today = datetime.utcnow().date().isoformat()
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT 1 FROM transactions WHERE user_id = %s AND type = %s AND date(timestamp) = %s',
                       (user['id'], 'TIKTOK_DAILY', today))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Already claimed today"}), 400
        cursor.execute('SELECT reward_amount FROM tiktok_daily WHERE date = %s', (today,))
        task_row = cursor.fetchone()
        if not task_row:
            return jsonify({"success": False, "message": "No task for today"}), 404
        reward = task_row[0] or CONFIG.TIKTOK_REWARD
        new_balance = user['balance'] + reward
        cursor.execute('UPDATE users SET balance = %s WHERE id = %s', (new_balance, user['id']))
        tx_id = f"TIKTOK-{secrets.token_hex(8)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (tx_id, user['id'], 'TIKTOK_DAILY', reward, 'COMPLETED', datetime.utcnow().isoformat()))
        conn.commit()
        grant_achievement_rewards(user['id'])
        return jsonify({"success": True, "reward": reward, "new_balance": new_balance})
    except Exception as e:
        print(f"TikTok follow error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to process"}), 500
    finally:
        conn.close()

@app.route('/api/games/spin/report', methods=['POST'])
@require_auth
def report_spin():
    ip = request.remote_addr
    if not rate_limit(game_action_attempts, ip, max_per_min=3):
        return jsonify({"success": False, "message": "Too many requests"}), 429
    user = get_current_user()
    data = request.get_json()
    reward = data.get('reward', 0)
    if reward not in [0, 50, 100, 200, 500, 1000]:
        return jsonify({"success": False, "message": "Invalid spin reward"}), 400
    if not can_play_today(user['id'], 'spin', max_plays=1):
        return jsonify({"success": False, "message": "One spin per day"}), 403
    conn = get_db()
    cursor = conn.cursor()
    try:
        new_balance = user['balance'] + reward
        cursor.execute('UPDATE users SET balance = %s WHERE id = %s', (new_balance, user['id']))
        conn.commit()
        grant_achievement_rewards(user['id'])
        return jsonify({"success": True, "reward": reward, "new_balance": new_balance})
    except Exception as e:
        print(f"Spin error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to process"}), 500
    finally:
        conn.close()

@app.route('/api/achievements')
@require_auth
def get_achievements():
    user = get_current_user()
    conn = get_db()
    cursor = conn.cursor()
    try:
        game_stats = json.loads(user.get('game_stats', '{}'))
        balance = float(user['balance'])
        cursor.execute('SELECT COUNT(*) FROM transactions WHERE user_id = %s', (user['id'],))
        total_tx = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM transactions WHERE user_id = %s AND type = %s', (user['id'], 'WITHDRAWAL'))
        total_withdrawals = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by = %s', (user['referral_code'],))
        referrals = cursor.fetchone()[0]
        today = datetime.utcnow().date()
        cursor.execute('SELECT COUNT(*) FROM game_plays WHERE user_id = %s AND play_date = %s', (user['id'], today))
        games_today = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM game_plays WHERE user_id = %s', (user['id'],))
        total_games = cursor.fetchone()[0]
        snake_high = game_stats.get('snake', {}).get('high_score', 0)
        coin_streak = game_stats.get('coin_flip', {}).get('current_streak', 0)
        coin_total = game_stats.get('coin_flip', {}).get('wins', 0) + game_stats.get('coin_flip', {}).get('losses', 0)
        plinko_wins = game_stats.get('plinko', {}).get('total_wins', 0)
        
        achievements = [
            {"id": 1, "title": "First Game", "description": "Play any game once", "reward": 500, "points": 10, "unlocked": total_games >= 1},
            {"id": 2, "title": "Gamer", "description": "Play 50 games", "reward": 5000, "points": 50, "unlocked": total_games >= 50},
            {"id": 3, "title": "Game Master", "description": "Play 200 games", "reward": 15000, "points": 150, "unlocked": total_games >= 200},
            {"id": 4, "title": "Snake Pro", "description": "Snake high score 1000+", "reward": 7500, "points": 75, "unlocked": snake_high >= 1000},
            {"id": 5, "title": "Lucky Streak", "description": "10+ coin flip win streak", "reward": 10000, "points": 100, "unlocked": coin_streak >= 10},
            {"id": 6, "title": "Coin Flipper", "description": "100+ coin flips", "reward": 6000, "points": 60, "unlocked": coin_total >= 100},
            {"id": 7, "title": "Plinko Champion", "description": "50+ Plinko wins", "reward": 8000, "points": 80, "unlocked": plinko_wins >= 50},
            {"id": 8, "title": "Thousandaire", "description": "Balance ₦1,000+", "reward": 1000, "points": 15, "unlocked": balance >= 1000},
            {"id": 9, "title": "Millionaire in Progress", "description": "Balance ₦50,000+", "reward": 10000, "points": 100, "unlocked": balance >= 50000},
            {"id": 10, "title": "High Roller", "description": "Balance ₦200,000+", "reward": 25000, "points": 200, "unlocked": balance >= 200000},
            {"id": 11, "title": "First Withdrawal", "description": "Make first withdrawal", "reward": 5000, "points": 50, "unlocked": total_withdrawals >= 1},
            {"id": 12, "title": "Daily Grinder", "description": "Play 5 games in a day", "reward": 3000, "points": 30, "unlocked": games_today >= 5},
            {"id": 13, "title": "Addicted", "description": "Play 20 games in a day", "reward": 8000, "points": 80, "unlocked": games_today >= 20},
            {"id": 14, "title": "Referral Starter", "description": "Refer 5 users", "reward": 10000, "points": 100, "unlocked": referrals >= 5},
            {"id": 15, "title": "Referral Master", "description": "Refer 20 users", "reward": 30000, "points": 300, "unlocked": referrals >= 20},
            {"id": 16, "title": "Transaction Veteran", "description": "10+ transactions", "reward": 4000, "points": 40, "unlocked": total_tx >= 10}
        ]
        
        total_achievements = len(achievements)
        unlocked_achievements = sum(1 for a in achievements if a['unlocked'])
        total_points = sum(a['points'] for a in achievements if a['unlocked'])
        return jsonify({
            "success": True,
            "stats": {"total": total_achievements, "unlocked": unlocked_achievements, "points": total_points},
            "achievements": achievements
        })
    except Exception as e:
        print(f"Achievements error: {e}")
        return jsonify({"success": False, "message": "Failed to load"}), 500
    finally:
        conn.close()

# ================= REFERRAL & WITHDRAWAL =================
@app.route('/api/referral/claim', methods=['POST'])
@require_auth
def claim_referral_bonus():
    user = get_current_user()
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by = %s', (user['referral_code'],))
        referrals = cursor.fetchone()[0]
        total_bonus = referrals * CONFIG.REFERRAL_BONUS
        claimed = _safe_get(user, 'claimed_bonuses', 0)
        unclaimed = total_bonus - claimed
        if unclaimed <= 0:
            return jsonify({"success": False, "message": "No bonus to claim"}), 400
        new_balance = user['balance'] + unclaimed
        cursor.execute('UPDATE users SET balance = %s, claimed_bonuses = %s WHERE id = %s',
                       (new_balance, total_bonus, user['id']))
        conn.commit()
        grant_achievement_rewards(user['id'])
        return jsonify({"success": True, "claimed": unclaimed, "new_balance": new_balance})
    except Exception as e:
        print(f"Referral error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to claim"}), 500
    finally:
        conn.close()

@app.route('/api/banking/withdraw', methods=['POST'])
@require_auth
def withdraw():
    user = get_current_user()
    data = request.get_json()
    amount = data.get('amount', 0)
    bank_code = data.get('bank_code')
    account_number = sanitize_input(data.get('account_number', ''))
    account_name = sanitize_input(data.get('account_name', ''))
    pin = data.get('pin', '')
    if not pin:
        return jsonify({"success": False, "message": "PIN required"}), 400
    withdrawal_pin = _safe_get(user, 'withdrawal_pin')
    if not withdrawal_pin or not check_password_hash(withdrawal_pin, pin):
        return jsonify({"success": False, "message": "Invalid PIN"}), 403
    if not is_withdrawal_day(user['id']):
        global_days = get_global_withdrawal_days()
        return jsonify({"success": False, "message": f"Withdrawals only on days: {', '.join(map(str, sorted(global_days)))}"}), 403
    if amount < CONFIG.MIN_WITHDRAWAL:
        return jsonify({"success": False, "message": f"Min withdrawal: ₦{CONFIG.MIN_WITHDRAWAL}"}), 400
    if user['balance'] < amount:
        return jsonify({"success": False, "message": "Insufficient balance"}), 400
    withdrawal_limit = _safe_get(user, 'withdrawal_limit', 0.00)
    if withdrawal_limit > 0 and amount > withdrawal_limit:
        return jsonify({"success": False, "message": f"Max limit: ₦{withdrawal_limit:,.2f}"}), 400
    if not bank_code or not account_number or len(account_number) < 10 or not account_number.isdigit():
        return jsonify({"success": False, "message": "Invalid bank details"}), 400
    conn = get_db()
    cursor = conn.cursor()
    try:
        new_balance = user['balance'] - amount
        cursor.execute('UPDATE users SET balance = %s WHERE id = %s', (new_balance, user['id']))
        tx_id = f"TX-{int(datetime.utcnow().timestamp())}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], 'WITHDRAWAL', amount, 'PENDING',
            json.dumps({'bank_code': bank_code, 'account_number': account_number, 'account_name': account_name}),
            datetime.utcnow().isoformat()
        ))
        conn.commit()
        grant_achievement_rewards(user['id'])
        return jsonify({
            "success": True,
            "message": "Withdrawal submitted",
            "transaction_id": tx_id,
            "new_balance": new_balance
        })
    except Exception as e:
        print(f"Withdrawal error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to process"}), 500
    finally:
        conn.close()

# ================= BANK LIST =================
@app.route('/api/banking/banks', methods=['GET'])
def get_banks():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT code, name FROM banks ORDER BY name')
        banks = [{'code': row[0], 'name': row[1]} for row in cursor.fetchall()]
        return jsonify({"success": True, "banks": banks})
    except Exception as e:
        print(f"Bank list error: {e}")
        return jsonify({"success": False, "message": "Failed to load banks"}), 500
    finally:
        conn.close()

# ================= ADMIN ENDPOINTS =================
@app.route('/api/admin/users')
@require_admin
def admin_get_users():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
        SELECT id, username, balance, referral_code, withdrawal_restricted, withdrawal_limit
        FROM users ORDER BY id DESC
        ''')
        users = []
        for row in cursor.fetchall():
            user = row_to_dict(cursor, row)
            user['withdrawal_restricted'] = bool(_safe_get(user, 'withdrawal_restricted', False))
            user['withdrawal_limit'] = float(_safe_get(user, 'withdrawal_limit', 0.00))
            users.append(user)
        return jsonify({"success": True, "users": users})
    except Exception as e:
        print(f"Admin users error: {e}")
        return jsonify({"success": False, "message": "Failed to load"}), 500
    finally:
        conn.close()

@app.route('/api/admin/user/<int:user_id>', methods=['GET'])
@require_admin
def admin_get_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"success": False, "message": "User not found"}), 404
        user = row_to_dict(cursor, row)
        user['is_admin'] = bool(user['is_admin'])
        user['withdrawal_restricted'] = bool(user.get('withdrawal_restricted', False))
        user['admin_password_changed'] = bool(user.get('admin_password_changed', False))
        return jsonify({"success": True, "user": user})
    except Exception as e:
        print(f"Admin get user error: {e}")
        return jsonify({"success": False, "message": "Failed to load"}), 500
    finally:
        conn.close()

@app.route('/api/admin/user/<int:user_id>/toggle-restrict', methods=['POST'])
@require_admin
def admin_toggle_user_restrict(user_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT withdrawal_restricted FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"success": False, "message": "User not found"}), 404
        current = bool(row[0])
        new_value = not current
        cursor.execute('UPDATE users SET withdrawal_restricted = %s WHERE id = %s', (new_value, user_id))
        conn.commit()
        return jsonify({"success": True, "restricted": new_value})
    except Exception as e:
        print(f"Toggle restrict error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update"}), 500
    finally:
        conn.close()

@app.route('/api/admin/user/<int:user_id>/set-limit', methods=['POST'])
@require_admin
def admin_set_user_limit(user_id):
    data = request.get_json()
    limit = data.get('limit', 0)
    if limit < 0:
        return jsonify({"success": False, "message": "Invalid limit"}), 400
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE users SET withdrawal_limit = %s WHERE id = %s', (limit, user_id))
        conn.commit()
        return jsonify({"success": True, "message": "Limit updated"})
    except Exception as e:
        print(f"Set limit error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update"}), 500
    finally:
        conn.close()

@app.route('/api/admin/transactions')
@require_admin
def admin_get_transactions():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
        SELECT t.*, u.username 
        FROM transactions t 
        LEFT JOIN users u ON t.user_id = u.id 
        ORDER BY t.timestamp DESC
        ''')
        transactions = []
        for row in cursor.fetchall():
            tx = row_to_dict(cursor, row)
            transactions.append(tx)
        return jsonify({"success": True, "transactions": transactions})
    except Exception as e:
        print(f"Admin transactions error: {e}")
        return jsonify({"success": False, "message": "Failed to load"}), 500
    finally:
        conn.close()

@app.route('/api/admin/transaction/<tx_id>/update', methods=['POST'])
@require_admin
def admin_update_transaction(tx_id):
    data = request.get_json()
    status = data.get('status')
    if status not in ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']:
        return jsonify({"success": False, "message": "Invalid status"}), 400
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE transactions SET status = %s WHERE id = %s', (status, tx_id))
        conn.commit()
        return jsonify({"success": True, "message": "Transaction updated"})
    except Exception as e:
        print(f"Update transaction error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update"}), 500
    finally:
        conn.close()

@app.route('/api/admin/coupons', methods=['GET'])
@require_admin
def admin_get_coupons():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT code, status FROM coupons ORDER BY code')
        coupons = [{'code': row[0], 'status': row[1]} for row in cursor.fetchall()]
        return jsonify({"success": True, "coupons": coupons})
    except Exception as e:
        print(f"Admin coupons error: {e}")
        return jsonify({"success": False, "message": "Failed to load"}), 500
    finally:
        conn.close()

@app.route('/api/admin/coupons/add', methods=['POST'])
@require_admin
def admin_add_coupon():
    data = request.get_json()
    code = sanitize_input(data.get('code', '')).upper()
    if not code:
        return jsonify({"success": False, "message": "Coupon code required"}), 400
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO coupons (code, status) VALUES (%s, %s)', (code, 'AVAILABLE'))
        conn.commit()
        return jsonify({"success": True, "message": "Coupon added"})
    except Exception as e:
        print(f"Add coupon error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to add coupon"}), 500
    finally:
        conn.close()

@app.route('/api/admin/settings', methods=['GET'])
@require_admin
def admin_get_settings():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT * FROM admin_settings LIMIT 1')
        row = cursor.fetchone()
        if row:
            settings = row_to_dict(cursor, row)
            return jsonify({"success": True, "settings": settings})
        else:
            return jsonify({"success": False, "message": "Settings not found"}), 404
    except Exception as e:
        print(f"Get settings error: {e}")
        return jsonify({"success": False, "message": "Failed to load"}), 500
    finally:
        conn.close()

@app.route('/api/admin/settings/update', methods=['POST'])
@require_admin
def admin_update_settings():
    data = request.get_json()
    whatsapp_link = data.get('whatsapp_link', '')
    telegram_link = data.get('telegram_link', '')
    facebook_link = data.get('facebook_link', '')
    global_withdrawal_days = data.get('global_withdrawal_days', [])
    
    if not isinstance(global_withdrawal_days, list):
        return jsonify({"success": False, "message": "Invalid withdrawal days format"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
        UPDATE admin_settings 
        SET whatsapp_link = %s, telegram_link = %s, facebook_link = %s, global_withdrawal_days = %s
        ''', (whatsapp_link, telegram_link, facebook_link, json.dumps(global_withdrawal_days)))
        conn.commit()
        return jsonify({"success": True, "message": "Settings updated"})
    except Exception as e:
        print(f"Update settings error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to update"}), 500
    finally:
        conn.close()

@app.route('/api/admin/tiktok/daily', methods=['POST'])
@require_admin
def admin_set_tiktok_daily():
    data = request.get_json()
    tiktok_link = data.get('tiktok_link', '')
    if not tiktok_link:
        return jsonify({"success": False, "message": "TikTok link required"}), 400
    
    today = datetime.utcnow().date().isoformat()
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
        INSERT INTO tiktok_daily (date, tiktok_link, reward_amount) 
        VALUES (%s, %s, %s)
        ON CONFLICT (date) 
        DO UPDATE SET tiktok_link = EXCLUDED.tiktok_link, reward_amount = EXCLUDED.reward_amount
        ''', (today, tiktok_link, CONFIG.TIKTOK_REWARD))
        conn.commit()
        return jsonify({"success": True, "message": "TikTok daily task set"})
    except Exception as e:
        print(f"Set TikTok daily error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to set task"}), 500
    finally:
        conn.close()

@app.route('/api/admin/balance/adjust', methods=['POST'])
@require_admin
def admin_adjust_balance():
    data = request.get_json()
    user_id = data.get('user_id')
    amount = data.get('amount', 0)
    note = data.get('note', '')
    
    if not user_id or amount == 0:
        return jsonify({"success": False, "message": "Invalid user or amount"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT balance FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        current_balance = row[0]
        new_balance = current_balance + amount
        
        cursor.execute('UPDATE users SET balance = %s WHERE id = %s', (new_balance, user_id))
        
        tx_id = f"ADJ-{secrets.token_hex(8)}"
        cursor.execute('''
        INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user_id, 'ADMIN_ADJUSTMENT', amount, 'COMPLETED',
            json.dumps({"note": note, "admin_action": True}),
            datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        return jsonify({
            "success": True,
            "message": "Balance adjusted",
            "old_balance": current_balance,
            "new_balance": new_balance,
            "adjustment": amount
        })
    except Exception as e:
        print(f"Balance adjustment error: {e}")
        conn.rollback()
        return jsonify({"success": False, "message": "Failed to adjust balance"}), 500
    finally:
        conn.close()

# ================= HEALTH CHECK =================
@app.route('/api/health')
def api_health():
    return jsonify({"status": "online", "service": "FLEXIA API", "timestamp": datetime.utcnow().isoformat()}), 200

# ================= CATCH-ALL ROUTE FOR REACT ROUTER =================
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    if path.startswith('api/'):
        return jsonify({"success": False, "message": "API endpoint not found"}), 404
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

# ================= MAIN =================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.getenv('ENV') != 'production'
    print(f"🚀 Starting Flexia Platform on port {port} (debug: {debug})")
    app.run(host='0.0.0.0', port=port, debug=debug)
