# backend/app.py - COMPLETE SECURE PRODUCTION VERSION (NO REDIS)
# FLEXIA Platform - SECURE PRODUCTION VERSION v15.0

import os
import json
import random
import secrets
import urllib.parse
import logging
import traceback
import hashlib
import uuid
import tenacity
import re
import smtplib
import bcrypt
import pyotp
import qrcode
import base64
import io
from datetime import datetime, timedelta, date
from functools import wraps
import threading
import time
import subprocess
import shutil
from logging.handlers import RotatingFileHandler
from collections import defaultdict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2 import sql
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import Flask, jsonify, request, send_from_directory, session
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ======================= CONFIGURATION =======================
class Config:
    DB_URL = os.environ.get('DATABASE_URL')
    if not DB_URL:
        raise RuntimeError("❌ DATABASE_URL environment variable is required.")
    
    COUPON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'coupon.txt')
    FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend')
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    
    # Game rewards
    MIN_WITHDRAWAL = int(os.environ.get('MIN_WITHDRAWAL', 100000))
    REFERRAL_BONUS = int(os.environ.get('REFERRAL_BONUS', 7500))
    TIKTOK_REWARD = int(os.environ.get('TIKTOK_REWARD', 150))
    SNAKE_REWARD = int(os.environ.get('SNAKE_REWARD', 200))
    COIN_FLIP_MIN_BET = int(os.environ.get('COIN_FLIP_MIN_BET', 100))
    PLINKO_MIN_BET = int(os.environ.get('PLINKO_MIN_BET', 100))
    
    # Game limits per day
    SNAKE_PLAYS_PER_DAY = 10
    COIN_PLAYS_PER_DAY = 2
    PLINKO_PLAYS_PER_DAY = 2
    SPIN_PLAYS_PER_DAY = 1
    TIKTOK_PLAYS_PER_DAY = 1
    
    # Session settings
    SESSION_DURATION_HOURS = int(os.environ.get('SESSION_DURATION_HOURS', 24))
    DEFAULT_WITHDRAWAL_DAYS = json.loads(os.environ.get('DEFAULT_WITHDRAWAL_DAYS', '[7, 14, 25, 30]'))
    
    # Security settings
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'PROPERCHILD')
    SESSION_TIMEOUT = 3600  # 1 hour in seconds
    LOGIN_MAX_ATTEMPTS = 5  # per IP per hour
    ACCOUNT_LOCKOUT_ATTEMPTS = 20
    ACCOUNT_LOCKOUT_DURATION = 24 * 3600  # 24 hours
    PASSWORD_MIN_LENGTH = 12
    PASSWORD_REQUIRE_SPECIAL = True
    
    # IP Whitelist for admin panel
    ADMIN_IP_WHITELIST = os.environ.get('ADMIN_IP_WHITELIST', '').split(',')
    
    # 2FA settings
    ENABLE_2FA = True
    ENABLE_ADMIN_2FA = True
    
    # Withdrawal settings
    WITHDRAWAL_COOLDOWN_HOURS = 24
    WITHDRAWALS_PER_DAY = 1
    
    # Email settings (for security alerts)
    SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
    SECURITY_EMAIL = os.environ.get('SECURITY_EMAIL')
    
    # Session security
    SESSION_COOKIE_SECURE = os.environ.get('ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)
    
    # Rate limiting
    MAX_LOGIN_ATTEMPTS = int(os.environ.get('MAX_LOGIN_ATTEMPTS', 5))
    MAX_REGISTER_ATTEMPTS = int(os.environ.get('MAX_REGISTER_ATTEMPTS', 3))
    MAX_GAME_ATTEMPTS = int(os.environ.get('MAX_GAME_ATTEMPTS', 10))
    
    # CORS
    ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', '*').split(',')
    
    # Database
    DB_POOL_MIN = int(os.environ.get('DB_POOL_MIN', 1))
    DB_POOL_MAX = int(os.environ.get('DB_POOL_MAX', 20))
    DB_CONNECTION_TIMEOUT = int(os.environ.get('DB_CONNECTION_TIMEOUT', 30))
    
    # API Versioning
    API_CURRENT_VERSION = "v1"
    API_SUPPORTED_VERSIONS = ["v1"]

CONFIG = Config()
app = Flask(__name__, static_folder=CONFIG.FRONTEND_DIR)
app.secret_key = CONFIG.SECRET_KEY
app.config['PERMANENT_SESSION_LIFETIME'] = CONFIG.PERMANENT_SESSION_LIFETIME

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# ======================= CORS CONFIGURATION =======================
CORS(app, resources={
    r"/api/*": {
        "origins": CONFIG.ALLOWED_ORIGINS,
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        "allow_headers": ["Content-Type", "Authorization", "X-Request-ID", "X-2FA-Token", "X-API-Version"],
        "expose_headers": ["X-Request-ID", "X-API-Version"],
        "supports_credentials": True,
        "max_age": 86400
    }
})

# ======================= API VERSIONING MIDDLEWARE =======================
class APIVersion:
    """API Version management class"""
    
    @staticmethod
    def get_version_from_request():
        """Extract version from request path"""
        path = request.path
        if '/api/v' in path:
            parts = path.split('/')
            for part in parts:
                if part.startswith('v') and part[1:].isdigit():
                    return part
        return None
    
    @staticmethod
    def validate_version(version):
        """Validate if version is supported"""
        return version in CONFIG.API_SUPPORTED_VERSIONS
    
    @staticmethod
    def get_current_version():
        """Get current API version"""
        return CONFIG.API_CURRENT_VERSION
    
    @staticmethod
    def get_api_base(version=None):
        """Get API base path for a version"""
        if not version:
            version = CONFIG.API_CURRENT_VERSION
        return f"/api/{version}"

def api_version_required(f):
    """Decorator to handle API versioning"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check version from path
        version = APIVersion.get_version_from_request()
        
        if version and not APIVersion.validate_version(version):
            return jsonify({
                "success": False,
                "message": f"Unsupported API version: {version}",
                "supported_versions": CONFIG.API_SUPPORTED_VERSIONS,
                "current_version": CONFIG.API_CURRENT_VERSION,
                "request_id": request.id
            }), 400
        
        # If no version in path, use current version
        if not version:
            version = CONFIG.API_CURRENT_VERSION
        
        # Add version to request context
        request.api_version = version
        
        return f(*args, **kwargs)
    return decorated

# ======================= SECURITY MIDDLEWARE =======================
class SecurityMiddleware:
    """Middleware for enhanced security"""
    
    @staticmethod
    def check_ip_whitelist(ip_address):
        """Check if IP is in admin whitelist"""
        if not CONFIG.ADMIN_IP_WHITELIST or not CONFIG.ADMIN_IP_WHITELIST[0]:
            return True  # No whitelist configured
        return ip_address in CONFIG.ADMIN_IP_WHITELIST
    
    @staticmethod
    def validate_password(password):
        """Validate password strength"""
        if len(password) < CONFIG.PASSWORD_MIN_LENGTH:
            return False, f"Password must be at least {CONFIG.PASSWORD_MIN_LENGTH} characters"
        
        if CONFIG.PASSWORD_REQUIRE_SPECIAL:
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
                return False, "Password must contain at least one special character"
        
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        
        if not re.search(r'\d', password):
            return False, "Password must contain at least one number"
        
        return True, "Password is strong"
    
    @staticmethod
    def generate_2fa_secret():
        """Generate a new 2FA secret"""
        return pyotp.random_base32()
    
    @staticmethod
    def generate_2fa_qr(secret, username):
        """Generate QR code for 2FA setup"""
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name=username, issuer_name="FLEXIA Platform")
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    
    @staticmethod
    def verify_2fa_token(secret, token):
        """Verify 2FA token"""
        totp = pyotp.TOTP(secret)
        return totp.verify(token)
    
    @staticmethod
    def send_security_alert(subject, message, recipient=None):
        """Send security alert email"""
        if not CONFIG.SECURITY_EMAIL or not CONFIG.SMTP_USERNAME:
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = CONFIG.SMTP_USERNAME
            msg['To'] = recipient or CONFIG.SECURITY_EMAIL
            msg['Subject'] = f"[SECURITY ALERT] {subject}"
            
            msg.attach(MIMEText(message, 'plain'))
            
            server = smtplib.SMTP(CONFIG.SMTP_SERVER, CONFIG.SMTP_PORT)
            server.starttls()
            server.login(CONFIG.SMTP_USERNAME, CONFIG.SMTP_PASSWORD)
            server.send_message(msg)
            server.quit()
            
            app.logger.info(f"Security alert sent: {subject}")
            return True
        except Exception as e:
            app.logger.error(f"Failed to send security alert: {e}")
            return False

security = SecurityMiddleware()

# ======================= AUDIT LOGGING =======================
class AuditLogger:
    """Enhanced audit logging system"""
    
    @staticmethod
    def log_admin_action(user_id, action, details, ip_address):
        """Log admin actions"""
        conn = None
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO audit_logs 
                (user_id, action_type, action_details, ip_address, timestamp)
                VALUES (%s, %s, %s, %s, %s)
            ''', (user_id, action, json.dumps(details), ip_address, datetime.utcnow().isoformat()))
            conn.commit()
        except Exception as e:
            app.logger.error(f"Failed to log admin action: {e}")
        finally:
            if conn:
                return_db_connection(conn)
    
    @staticmethod
    def log_failed_login(username, ip_address, reason):
        """Log failed login attempts"""
        conn = None
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO failed_logins 
                (username, ip_address, reason, timestamp)
                VALUES (%s, %s, %s, %s)
            ''', (username, ip_address, reason, datetime.utcnow().isoformat()))
            conn.commit()
            
            # Check if threshold exceeded
            cursor.execute('''
                SELECT COUNT(*) FROM failed_logins 
                WHERE ip_address = %s AND timestamp > NOW() - INTERVAL '1 hour'
            ''', (ip_address,))
            count = cursor.fetchone()[0]
            
            if count >= CONFIG.LOGIN_MAX_ATTEMPTS:
                security.send_security_alert(
                    "Rate Limit Exceeded",
                    f"IP {ip_address} exceeded login attempts ({count} in last hour)",
                    CONFIG.SECURITY_EMAIL
                )
        except Exception as e:
            app.logger.error(f"Failed to log failed login: {e}")
        finally:
            if conn:
                return_db_connection(conn)
    
    @staticmethod
    def log_security_event(event_type, details, severity="MEDIUM"):
        """Log security events"""
        conn = None
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO security_events 
                (event_type, event_details, severity, timestamp)
                VALUES (%s, %s, %s, %s)
            ''', (event_type, json.dumps(details), severity, datetime.utcnow().isoformat()))
            conn.commit()
            
            # Send alert for high severity events
            if severity == "HIGH":
                security.send_security_alert(
                    f"High Severity Security Event: {event_type}",
                    json.dumps(details, indent=2),
                    CONFIG.SECURITY_EMAIL
                )
        except Exception as e:
            app.logger.error(f"Failed to log security event: {e}")
        finally:
            if conn:
                return_db_connection(conn)
    
    @staticmethod
    def log_payment_approval(admin_id, transaction_id, action, details):
        """Log payment approvals"""
        AuditLogger.log_admin_action(
            admin_id,
            f"PAYMENT_{action}",
            {"transaction_id": transaction_id, **details},
            request.remote_addr
        )

audit_logger = AuditLogger()

# ======================= REQUEST ID MIDDLEWARE =======================
@app.before_request
def assign_request_id():
    """Assign a unique ID to each request for tracing"""
    request.id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
    request.start_time = time.time()

@app.after_request
def add_request_id_header(response):
    """Add request ID to response headers"""
    response.headers['X-Request-ID'] = getattr(request, 'id', '')
    
    # Add API version header
    if hasattr(request, 'api_version'):
        response.headers['X-API-Version'] = request.api_version
    
    # Log request duration
    if hasattr(request, 'start_time'):
        duration = time.time() - request.start_time
        if duration > 5:  # Log slow requests
            app.logger.warning(f"[{request.id}] Slow request: {request.method} {request.path} took {duration:.2f}s")
    
    return response

# ======================= JSON VALIDATION MIDDLEWARE =======================
@app.before_request
def validate_json():
    """Validate JSON payload for POST/PUT/PATCH requests"""
    if request.method in ['POST', 'PUT', 'PATCH'] and request.content_type == 'application/json':
        try:
            if request.get_data():
                request.get_json()
        except Exception as e:
            app.logger.error(f"[{request.id}] Invalid JSON: {e}")
            return jsonify({
                "success": False,
                "message": "Invalid JSON payload",
                "request_id": request.id
            }), 400
    return None

# ======================= SETUP LOGGING =======================
def setup_logging():
    """Configure application logging"""
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        'logs/flexia.log',
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)

    # Security log handler
    security_handler = RotatingFileHandler(
        'logs/security.log',
        maxBytes=5242880,  # 5MB
        backupCount=5
    )
    security_handler.setFormatter(logging.Formatter(
        '%(asctime)s [SECURITY] [%(request_id)s] [%(ip)s] %(message)s'
    ))
    security_handler.setLevel(logging.WARNING)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(request_id)s] %(message)s'
    ))
    console_handler.setLevel(logging.DEBUG if os.getenv('ENV') != 'production' else logging.INFO)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(security_handler)
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.INFO)

    # Configure Flask logger
    app.logger.handlers.clear()
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.INFO)

    # Configure werkzeug logger
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.handlers.clear()
    werkzeug_logger.addHandler(file_handler)
    werkzeug_logger.setLevel(logging.WARNING)

    # Add request ID filter
    class RequestIDFilter(logging.Filter):
        def filter(self, record):
            record.request_id = getattr(request, 'id', 'no-request-id')
            record.ip = getattr(request, 'remote_addr', 'no-ip')
            return True
    
    for handler in [file_handler, security_handler, console_handler]:
        handler.addFilter(RequestIDFilter())

setup_logging()

# ======================= SECURITY HEADERS =======================
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # Dynamic CSP based on environment
    if os.getenv('ENV') == 'production':
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'"
        )
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    else:
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'"
        )
    
    return response

# ======================= ERROR HANDLERS =======================
@app.errorhandler(404)
def not_found_error(error):
    app.logger.warning(f'[{request.id}] 404 error: {request.url}')
    if request.path.startswith('/api/'):
        return jsonify({
            "success": False,
            "message": "API endpoint not found",
            "request_id": request.id
        }), 404
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f'[{request.id}] 500 error: {str(error)}')
    app.logger.error(f'[{request.id}] {traceback.format_exc()}')
    if request.path.startswith('/api/'):
        return jsonify({
            "success": False,
            "message": "Internal server error",
            "request_id": request.id
        }), 500
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(400)
def bad_request_error(error):
    app.logger.warning(f'[{request.id}] 400 error: {str(error)}')
    if request.path.startswith('/api/'):
        return jsonify({
            "success": False,
            "message": "Bad request",
            "request_id": request.id
        }), 400
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(401)
def unauthorized_error(error):
    app.logger.warning(f'[{request.id}] 401 error: {request.url}')
    if request.path.startswith('/api/'):
        return jsonify({
            "success": False,
            "message": "Authentication required",
            "request_id": request.id
        }), 401
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(403)
def forbidden_error(error):
    app.logger.warning(f'[{request.id}] 403 error: {request.url}')
    if request.path.startswith('/api/'):
        return jsonify({
            "success": False,
            "message": "Access forbidden",
            "request_id": request.id
        }), 403
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.errorhandler(429)
def too_many_requests_error(error):
    app.logger.warning(f'[{request.id}] 429 rate limit exceeded: {request.remote_addr}')
    if request.path.startswith('/api/'):
        return jsonify({
            "success": False,
            "message": "Too many requests",
            "request_id": request.id
        }), 429
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

# ======================= REQUEST TIMEOUT HANDLER =======================
class RequestTimeout(Exception):
    pass

@app.errorhandler(RequestTimeout)
def handle_timeout(error):
    app.logger.warning(f'[{request.id}] Request timeout: {request.url}')
    return jsonify({
        "success": False,
        "message": "Request timeout",
        "request_id": request.id
    }), 408

# ======================= INPUT VALIDATION =======================
def validate_input(data, rules):
    """Validate input against rules dictionary"""
    errors = {}
    for field, rule in rules.items():
        value = data.get(field)
        
        # Required check
        if rule.get('required') and (value is None or value == ''):
            errors[field] = f"{field} is required"
            continue
        
        if value is None:
            continue
            
        # Type checking
        if 'type' in rule:
            if rule['type'] == 'int':
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    errors[field] = f"{field} must be an integer"
                    continue
            elif rule['type'] == 'float':
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    errors[field] = f"{field} must be a number"
                    continue
            elif rule['type'] == 'string' and not isinstance(value, str):
                errors[field] = f"{field} must be a string"
                    continue
            elif rule['type'] == 'bool' and not isinstance(value, bool):
                errors[field] = f"{field} must be a boolean"
                    continue
        
        # Range checks
        if 'min' in rule and value < rule['min']:
            errors[field] = f"{field} must be at least {rule['min']}"
        if 'max' in rule and value > rule['max']:
            errors[field] = f"{field} must be at most {rule['max']}"
        if 'min_length' in rule and len(str(value)) < rule['min_length']:
            errors[field] = f"{field} must be at least {rule['min_length']} characters"
        if 'max_length' in rule and len(str(value)) > rule['max_length']:
            errors[field] = f"{field} must be at most {rule['max_length']} characters"
        if 'pattern' in rule and not re.match(rule['pattern'], str(value)):
            errors[field] = f"{field} has invalid format"
        if 'choices' in rule and value not in rule['choices']:
            errors[field] = f"{field} must be one of {rule['choices']}"
    
    return errors

def sanitize_input(text):
    """Sanitize input to prevent XSS and SQL injection"""
    if not text:
        return ""
    if isinstance(text, (int, float, bool)):
        return text
    text = str(text).strip()
    # Remove potentially dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '`', ';', '--', '/*', '*/', 'xp_']
    for char in dangerous_chars:
        text = text.replace(char, '')
    # Prevent SQL injection
    text = re.sub(r'(\s*)(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|EXEC)\b)', r'\1', text, flags=re.IGNORECASE)
    return text

# ======================= DATABASE CONNECTION POOLING =======================
db_pool = None

def init_db_pool():
    """Initialize database connection pool"""
    global db_pool
    try:
        db_pool = SimpleConnectionPool(
            CONFIG.DB_POOL_MIN,
            CONFIG.DB_POOL_MAX,
            dsn=CONFIG.DB_URL,
            connect_timeout=CONFIG.DB_CONNECTION_TIMEOUT
        )
        app.logger.info('✅ Database connection pool initialized')
    except Exception as e:
        app.logger.error(f'❌ Failed to initialize connection pool: {str(e)}')
        raise

def get_db():
    """Get a database connection from the pool"""
    global db_pool
    if not db_pool:
        init_db_pool()
    try:
        conn = db_pool.getconn()
        conn.autocommit = False
        return conn
    except Exception as e:
        app.logger.error(f'[{request.id}] Error getting connection from pool: {str(e)}')
        raise

def return_db_connection(conn):
    """Return a database connection to the pool"""
    global db_pool
    try:
        if conn and not conn.closed:
            conn.rollback()  # Ensure no open transactions
            db_pool.putconn(conn)
    except Exception as e:
        app.logger.error(f'[{request.id}] Error returning connection: {str(e)}')
        try:
            conn.close()
        except:
            pass

def get_pool_stats():
    """Get connection pool statistics"""
    global db_pool
    if db_pool:
        return {
            "min_connections": db_pool.minconn,
            "max_connections": db_pool.maxconn,
            "current_connections": len(db_pool._used),
            "available_connections": len(db_pool._idle)
        }
    return None

@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
    retry=tenacity.retry_if_exception_type(psycopg2.OperationalError)
)
def execute_with_retry(cursor, sql_str, params=None):
    """Execute SQL with retry logic"""
    try:
        if params:
            return cursor.execute(sql_str, params)
        else:
            return cursor.execute(sql_str)
    except Exception as e:
        app.logger.error(f"SQL execution error: {str(e)}")
        raise

# ======================= DATABASE CONNECTION DECORATOR =======================
def with_db_connection(func):
    """Decorator to handle database connections automatically"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        conn = None
        try:
            conn = get_db()
            cursor = conn.cursor()
            kwargs['cursor'] = cursor
            kwargs['conn'] = conn
            result = func(*args, **kwargs)
            conn.commit()
            return result
        except Exception as e:
            app.logger.error(f'[{request.id}] Database error in {func.__name__}: {str(e)}')
            app.logger.error(f'[{request.id}] {traceback.format_exc()}')
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                return_db_connection(conn)
    return wrapper

# ======================= DATABASE HEALTH CHECK =======================
def check_db_health():
    """Check database connection health"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cursor.fetchone()
        return True
    except Exception as e:
        app.logger.error(f'Database health check failed: {str(e)}')
        return False
    finally:
        if conn:
            return_db_connection(conn)

def schedule_health_checks():
    """Schedule periodic database health checks"""
    def run_checks():
        app.logger.info('Database health check scheduler started')
        while True:
            try:
                time.sleep(300)  # Every 5 minutes
                if not check_db_health():
                    app.logger.error("Database connection unhealthy")
                else:
                    app.logger.debug("Database health check passed")
            except Exception as e:
                app.logger.error(f"Health check scheduler error: {str(e)}")
                time.sleep(60)
    
    thread = threading.Thread(target=run_checks, daemon=True)
    thread.start()

# ======================= RATE LIMITING =======================
def rate_limit_db_decorator(limit_per_minute=5, key_prefix="rl"):
    """Database-backed rate limiting decorator"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Use IP + endpoint as key
            ip = request.remote_addr
            endpoint = f"{request.method}:{request.path}"
            key = f"{key_prefix}:{ip}:{endpoint}"
            
            if not check_rate_limit_db(key, limit_per_minute):
                return jsonify({
                    "success": False,
                    "message": "Too many requests. Please try again later.",
                    "request_id": request.id
                }), 429
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

def check_rate_limit_db(key, limit_per_minute, window_seconds=60):
    """Check rate limit using PostgreSQL"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=window_seconds)
        
        # Check current count
        cursor.execute('''
            SELECT COUNT(*) FROM rate_limits 
            WHERE key = %s AND created_at > %s
        ''', (key, cutoff))
        
        count = cursor.fetchone()[0]
        
        if count >= limit_per_minute:
            return False
        
        # Record this request
        cursor.execute('''
            INSERT INTO rate_limits (key, created_at, expires_at)
            VALUES (%s, %s, %s + INTERVAL '%s seconds')
        ''', (key, now, now, window_seconds * 2))
        
        # Clean old entries
        cursor.execute('DELETE FROM rate_limits WHERE expires_at < %s', (now,))
        
        conn.commit()
        return True
    except Exception as e:
        app.logger.error(f"Rate limit check error: {e}")
        return True  # Fail open on error
    finally:
        if conn:
            return_db_connection(conn)

# ======================= SESSION MANAGER =======================
def create_session_token(user_id):
    """Create a secure session token"""
    s = URLSafeTimedSerializer(app.secret_key)
    return s.dumps({'user_id': user_id, 'created_at': datetime.utcnow().timestamp()})

def verify_session_token(token):
    """Verify and decode a session token"""
    s = URLSafeTimedSerializer(app.secret_key)
    try:
        data = s.loads(token, max_age=CONFIG.SESSION_TIMEOUT)
        user_id = data.get('user_id')
        
        # Check if user is locked
        conn = None
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT is_locked, lock_until FROM users WHERE id = %s', (user_id,))
            row = cursor.fetchone()
            if row and row[0]:
                lock_until = row[1]
                if lock_until and datetime.fromisoformat(lock_until) > datetime.utcnow():
                    return None
        finally:
            if conn:
                return_db_connection(conn)
        
        return user_id
    except (BadSignature, SignatureExpired) as e:
        app.logger.warning(f'[{request.id}] Invalid session token: {str(e)}')
        return None

def row_to_dict(cursor, row):
    """Convert database row to dictionary"""
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if hasattr(row, 'keys'):
        return {key: row[key] for key in row.keys()}
    elif cursor and cursor.description:
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))
    return {}

def get_current_user():
    """Get current authenticated user"""
    token = request.cookies.get('session_token')
    if not token:
        return None
    
    user_id = verify_session_token(token)
    if not user_id:
        return None
    
    # Check session timeout
    session_last_activity = session.get('last_activity')
    if session_last_activity:
        last_activity = datetime.fromisoformat(session_last_activity)
        if (datetime.utcnow() - last_activity).seconds > CONFIG.SESSION_TIMEOUT:
            return None
    
    # Update last activity
    session['last_activity'] = datetime.utcnow().isoformat()
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        execute_with_retry(cursor, 'SELECT * FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        return row_to_dict(cursor, row)
    except Exception as e:
        app.logger.error(f'[{request.id}] Error getting current user: {str(e)}')
        return None
    finally:
        if conn:
            return_db_connection(conn)

def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            app.logger.warning(f'[{request.id}] Unauthorized access attempt to {request.path}')
            return jsonify({
                "success": False,
                "message": "Login required",
                "request_id": request.id
            }), 401
        
        # Check if 2FA is required
        if CONFIG.ENABLE_2FA and user.get('is_admin') and CONFIG.ENABLE_ADMIN_2FA:
            if user.get('two_fa_enabled') and not session.get('two_fa_verified'):
                return jsonify({
                    "success": False,
                    "message": "2FA verification required",
                    "requires_2fa": True,
                    "request_id": request.id
                }), 403
        
        return f(*args, **kwargs)
    return decorated

def require_admin(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user.get('is_admin'):
            app.logger.warning(f'[{request.id}] Non-admin user {user["id"]} attempted admin endpoint {request.path}')
            audit_logger.log_security_event(
                "UNAUTHORIZED_ADMIN_ACCESS",
                {"user_id": user["id"], "username": user["username"], "endpoint": request.path},
                "HIGH"
            )
            return jsonify({
                "success": False,
                "message": "Admin access required",
                "request_id": request.id
            }), 403
        
        # IP whitelist check for admin panel
        if not security.check_ip_whitelist(request.remote_addr):
            app.logger.warning(f'[{request.id}] IP {request.remote_addr} not in admin whitelist')
            audit_logger.log_security_event(
                "IP_WHITELIST_VIOLATION",
                {"ip_address": request.remote_addr, "endpoint": request.path},
                "HIGH"
            )
            return jsonify({
                "success": False,
                "message": "Access denied",
                "request_id": request.id
            }), 403
        
        return f(*args, **kwargs)
    return decorated

# ======================= BACKUP SYSTEM =======================
def backup_database():
    """Create database backup"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        app.logger.info('Creating PostgreSQL backup...')
        backup_file = f'backups/backup_flexia_{timestamp}.sql'
        
        if not os.path.exists('backups'):
            os.makedirs('backups')
        
        parsed = urllib.parse.urlparse(CONFIG.DB_URL)
        env = os.environ.copy()
        env['PGPASSWORD'] = parsed.password
        
        result = subprocess.run([
            'pg_dump',
            '-h', parsed.hostname,
            '-p', str(parsed.port),
            '-U', parsed.username,
            '-d', parsed.path[1:],
            '-f', backup_file,
            '--no-password'
        ], env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            app.logger.info(f'PostgreSQL backup created: {backup_file}')
            return backup_file
        else:
            app.logger.error(f'PostgreSQL backup failed: {result.stderr}')
            return None
    except Exception as e:
        app.logger.error(f'Backup failed: {str(e)}')
        app.logger.error(traceback.format_exc())
        return None

def run_backup_scheduler():
    """Run backup scheduler"""
    def schedule():
        app.logger.info('Backup scheduler started')
        while True:
            try:
                now = datetime.utcnow()
                next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
                if now > next_run:
                    next_run += timedelta(days=1)
                time_to_sleep = (next_run - now).total_seconds()
                app.logger.info(f'Next backup scheduled in {time_to_sleep/3600:.1f} hours')
                time.sleep(time_to_sleep)
                backup_file = backup_database()
                if backup_file:
                    app.logger.info(f'Daily backup completed: {backup_file}')
                    cleanup_old_backups()
                else:
                    app.logger.error('Daily backup failed')
            except Exception as e:
                app.logger.error(f'Backup scheduler error: {str(e)}')
                time.sleep(3600)
    
    thread = threading.Thread(target=schedule, daemon=True)
    thread.start()

def cleanup_old_backups():
    """Clean up old backup files"""
    try:
        if not os.path.exists('backups'):
            return
        
        cutoff_time = datetime.now() - timedelta(days=30)  # 30-day retention
        for filename in os.listdir('backups'):
            filepath = os.path.join('backups', filename)
            if os.path.isfile(filepath) and filename.endswith('.sql'):
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                if file_time < cutoff_time:
                    os.remove(filepath)
                    app.logger.info(f'Removed old backup: {filename}')
    except Exception as e:
        app.logger.error(f'Cleanup old backups error: {str(e)}')

# ======================= DATABASE INITIALIZATION =======================
@with_db_connection
def add_missing_columns(cursor, conn):
    """Add missing columns to users table - FIXED SECURE VERSION"""
    try:
        # Define columns to add with their types
        columns_to_add = [
            ('last_achievement_check', 'TEXT'),
            ('last_game_timestamp', 'TEXT'),
            ('claimed_achievements', 'TEXT DEFAULT \'[]\''),
            ('two_fa_secret', 'TEXT'),
            ('two_fa_enabled', 'BOOLEAN DEFAULT FALSE'),
            ('last_password_change', 'TEXT'),
            ('login_attempts', 'INTEGER DEFAULT 0'),
            ('is_locked', 'BOOLEAN DEFAULT FALSE'),
            ('lock_until', 'TEXT'),
            ('last_login_ip', 'TEXT'),
            ('last_login_time', 'TEXT'),
            ('session_tokens', 'TEXT DEFAULT \'[]\''),
            ('withdrawal_last_date', 'TEXT'),
            ('withdrawal_count_today', 'INTEGER DEFAULT 0')
        ]
        
        for column_name, column_type in columns_to_add:
            # Check if column exists using parameterized query
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = %s
            """, (column_name,))
            
            if not cursor.fetchone():
                alter_query = sql.SQL("ALTER TABLE users ADD COLUMN {} {}").format(
                    sql.Identifier(column_name),
                    sql.SQL(column_type)
                )
                cursor.execute(alter_query)
                app.logger.info(f"Added missing column: {column_name}")
        
        # Create audit tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                action_type TEXT NOT NULL,
                action_details TEXT,
                ip_address TEXT,
                timestamp TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS failed_logins (
                id SERIAL PRIMARY KEY,
                username TEXT,
                ip_address TEXT,
                reason TEXT,
                timestamp TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS security_events (
                id SERIAL PRIMARY KEY,
                event_type TEXT NOT NULL,
                event_details TEXT,
                severity TEXT,
                timestamp TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payment_audit (
                id SERIAL PRIMARY KEY,
                admin_id INTEGER,
                transaction_id TEXT,
                action TEXT,
                details TEXT,
                timestamp TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rate_limits (
                id SERIAL PRIMARY KEY,
                key TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rate_limits_key ON rate_limits(key, created_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rate_limits_expires ON rate_limits(expires_at)')
        
        conn.commit()
        app.logger.info("Database column verification and audit tables created")
    except Exception as e:
        app.logger.error(f"Error adding missing columns: {e}")
        conn.rollback()
        raise

@with_db_connection
def add_database_indexes(cursor, conn):
    """Add database indexes for performance"""
    try:
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_transactions_user_timestamp ON transactions(user_id, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_transactions_type_timestamp ON transactions(type, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_game_plays_user_date ON game_plays(user_id, play_date)",
            "CREATE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code)",
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
            "CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status)",
            "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_transactions_user_type ON transactions(user_id, type)",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_user_time ON audit_logs(user_id, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_failed_logins_ip_time ON failed_logins(ip_address, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_security_events_time ON security_events(timestamp)"
        ]
        
        for sql_str in indexes:
            cursor.execute(sql_str)
        
        conn.commit()
        app.logger.info("Database indexes created/verified")
    except Exception as e:
        app.logger.error(f"Error creating indexes: {e}")
        conn.rollback()
        raise

@with_db_connection
def init_db(cursor, conn):
    """Initialize database tables"""
    try:
        # Users table
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
                withdrawal_limit REAL DEFAULT 0.00,
                last_game_timestamp TEXT,
                last_achievement_check TEXT,
                claimed_achievements TEXT DEFAULT '[]',
                two_fa_secret TEXT,
                two_fa_enabled BOOLEAN DEFAULT FALSE,
                last_password_change TEXT,
                login_attempts INTEGER DEFAULT 0,
                is_locked BOOLEAN DEFAULT FALSE,
                lock_until TEXT,
                last_login_ip TEXT,
                last_login_time TEXT,
                session_tokens TEXT DEFAULT '[]',
                withdrawal_last_date TEXT,
                withdrawal_count_today INTEGER DEFAULT 0
            )
        ''')

        # Admin settings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_settings (
                id SERIAL PRIMARY KEY,
                whatsapp_link TEXT,
                telegram_link TEXT,
                facebook_link TEXT,
                global_withdrawal_days TEXT
            )
        ''')

        # Transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                user_id INTEGER,
                type TEXT,
                amount REAL,
                status TEXT,
                details TEXT,
                timestamp TEXT,
                CONSTRAINT fk_user FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')

        # Coupons table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS coupons (
                code TEXT PRIMARY KEY,
                status TEXT DEFAULT 'AVAILABLE'
            )
        ''')

        # Banks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS banks (
                code TEXT PRIMARY KEY,
                name TEXT,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')

        # WhatsApp numbers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS whatsapp_numbers (
                id SERIAL PRIMARY KEY,
                number TEXT UNIQUE NOT NULL,
                label TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TEXT
            )
        ''')

        # Game plays table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_plays (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                game_type TEXT,
                play_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_user FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')

        # TikTok daily table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tiktok_daily (
                id SERIAL PRIMARY KEY,
                date TEXT UNIQUE NOT NULL,
                tiktok_link TEXT NOT NULL,
                reward_amount REAL DEFAULT 150.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # User game locks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_game_locks (
                user_id INTEGER PRIMARY KEY,
                lock_until TEXT,
                game_type TEXT,
                CONSTRAINT fk_user FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')

        # Insert default banks
        cursor.execute('SELECT COUNT(*) as count FROM banks')
        bank_count = cursor.fetchone()[0]
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
            for code, name in banks:
                cursor.execute('INSERT INTO banks (code, name, is_active) VALUES (%s, %s, %s)', 
                             (code, name, True))
            app.logger.info(f"Inserted {len(banks)} banks")

        # Admin settings
        cursor.execute('SELECT COUNT(*) as count FROM admin_settings')
        settings_count = cursor.fetchone()[0]
        if settings_count == 0:
            default_days_json = json.dumps(CONFIG.DEFAULT_WITHDRAWAL_DAYS)
            cursor.execute('''INSERT INTO admin_settings 
                           (whatsapp_link, telegram_link, facebook_link, global_withdrawal_days) 
                           VALUES (%s, %s, %s, %s)''',
                         ('', '', '', default_days_json))

        # Coupons
        if os.path.exists(CONFIG.COUPON_FILE):
            with open(CONFIG.COUPON_FILE, 'r') as f:
                codes = [line.strip().upper() for line in f if line.strip()]
            if codes:
                cursor.execute('DELETE FROM coupons')
                for code in codes:
                    cursor.execute('INSERT INTO coupons (code, status) VALUES (%s, %s)', 
                                 (code, 'AVAILABLE'))
                app.logger.info(f"Loaded {len(codes)} coupons from file")
        else:
            default_coupons = ['WELCOME123', 'SIGNUP456', 'REGISTER789', 'FLEXIA2024']
            for code in default_coupons:
                cursor.execute('INSERT INTO coupons (code, status) VALUES (%s, %s)', 
                             (code, 'AVAILABLE'))
            app.logger.info(f"Created {len(default_coupons)} default coupons")

        # Admin user - using configurable username
        cursor.execute('SELECT COUNT(*) as count FROM users WHERE username = %s', (CONFIG.ADMIN_USERNAME,))
        admin_count = cursor.fetchone()[0]
        if admin_count == 0:
            # Generate strong password
            admin_password = secrets.token_urlsafe(16)
            admin_pass_hash = generate_password_hash(admin_password)
            
            game_stats = json.dumps({
                "snake": {"high_score": 1200, "total_score": 5000},
                "coin_flip": {"wins": 25, "losses": 18, "current_streak": 3},
                "plinko": {"total_wins": 15, "total_bets": 25000, "highest_win": 5000}
            })
            pin_hash = generate_password_hash("4567")
            
            # Generate 2FA secret for admin
            two_fa_secret = security.generate_2fa_secret()
            qr_code = security.generate_2fa_qr(two_fa_secret, CONFIG.ADMIN_USERNAME)
            
            cursor.execute('''
                INSERT INTO users (
                    username, password, balance, referral_code, is_admin,
                    created_at, last_login, game_stats, admin_password_changed,
                    withdrawal_pin, contact, profile_picture, ui_theme,
                    last_game_timestamp, last_achievement_check, claimed_achievements,
                    two_fa_secret, two_fa_enabled, last_password_change
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                CONFIG.ADMIN_USERNAME, admin_pass_hash, 500000.00, "ADM0001", True,
                datetime.utcnow().isoformat(), datetime.utcnow().isoformat(),
                game_stats, False, pin_hash, "", "", "light",
                datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), '[]',
                two_fa_secret, True, datetime.utcnow().isoformat()
            ))
            
            # SECURE: Write admin credentials to secure file instead of logging
            setup_file = "admin_setup_secure.txt"
            with open(setup_file, 'w') as f:
                f.write("=== FLEXIA ADMIN SETUP - KEEP THIS SECURE ===\n")
                f.write(f"Username: {CONFIG.ADMIN_USERNAME}\n")
                f.write(f"Initial Password: {admin_password}\n")
                f.write(f"Default Withdrawal PIN: 4567\n")
                f.write(f"2FA Secret: {two_fa_secret}\n")
                f.write(f"QR Code Data: {qr_code}\n")
                f.write("==========================================\n")
            
            # Set secure permissions (Linux/Unix only)
            if os.name != 'nt':  # Not Windows
                os.chmod(setup_file, 0o600)  # Only owner can read/write
            
            app.logger.info("✅ Admin account created. Setup details saved to secure file.")

        # WhatsApp number
        cursor.execute('SELECT COUNT(*) as count FROM whatsapp_numbers')
        whatsapp_count = cursor.fetchone()[0]
        if whatsapp_count == 0:
            cursor.execute('''INSERT INTO whatsapp_numbers 
                           (number, label, is_active, created_at) 
                           VALUES (%s, %s, %s, %s)''',
                         ('2348160881049', 'Primary Seller', True, datetime.utcnow().isoformat()))

        conn.commit()
        app.logger.info("✅ Database initialization completed successfully!")
    except Exception as e:
        app.logger.error(f"Database init error: {e}")
        conn.rollback()
        raise

# ======================= ATOMIC OPERATIONS =======================
@with_db_connection
def update_user_balance(cursor, conn, user_id, amount_change):
    """Atomically update user balance"""
    try:
        cursor.execute('''
            UPDATE users
            SET balance = balance + %s
            WHERE id = %s
            RETURNING balance
        ''', (amount_change, user_id))
        
        row = cursor.fetchone()
        new_balance = float(row[0]) if row and row[0] else 0.0
        conn.commit()
        
        app.logger.info(f"[{request.id}] Atomic balance update for user {user_id}: {amount_change}, new balance: {new_balance}")
        return new_balance
    except Exception as e:
        app.logger.error(f"[{request.id}] Balance update error: {e}")
        conn.rollback()
        raise

@with_db_connection  
def check_game_cooldown(cursor, conn, user_id, game_type):
    """Check if user is in cooldown for a game"""
    try:
        cursor.execute('SELECT last_game_timestamp FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        if row and row[0]:
            try:
                last_game = datetime.fromisoformat(row[0])
                now = datetime.utcnow()
                if (now - last_game).total_seconds() < 1:
                    return False
            except:
                pass
        return True
    except Exception as e:
        app.logger.error(f"[{request.id}] Cooldown check error: {e}")
        return True

@with_db_connection
def update_last_game_timestamp(cursor, conn, user_id):
    """Update user's last game timestamp"""
    try:
        cursor.execute('UPDATE users SET last_game_timestamp = %s WHERE id = %s',
                      (datetime.utcnow().isoformat(), user_id))
        conn.commit()
    except Exception as e:
        app.logger.error(f"[{request.id}] Update last game timestamp error: {e}")
        conn.rollback()
        raise

@with_db_connection
def can_play_today(cursor, conn, user_id, game_type):
    """Check if user can play a game today based on game type"""
    today = datetime.utcnow().date()
    try:
        cursor.execute("SELECT COUNT(*) FROM game_plays WHERE user_id = %s AND game_type = %s AND play_date = %s",
                      (user_id, game_type, today))
        count = cursor.fetchone()[0]
        
        # Set limits based on game type
        max_plays = {
            'snake': CONFIG.SNAKE_PLAYS_PER_DAY,
            'coinflip': CONFIG.COIN_PLAYS_PER_DAY,
            'plinko': CONFIG.PLINKO_PLAYS_PER_DAY,
            'spin': CONFIG.SPIN_PLAYS_PER_DAY,
            'tiktok': CONFIG.TIKTOK_PLAYS_PER_DAY
        }.get(game_type, 1)
        
        return count < max_plays
    except Exception as e:
        app.logger.error(f"[{request.id}] Play check error: {e}")
        return False

@with_db_connection
def record_game_play(cursor, conn, user_id, game_type):
    """Record a game play for a user"""
    today = datetime.utcnow().date()
    try:
        cursor.execute("INSERT INTO game_plays (user_id, game_type, play_date) VALUES (%s, %s, %s)",
                     (user_id, game_type, today))
        conn.commit()
    except Exception as e:
        app.logger.error(f"[{request.id}] Record game play error: {e}")
        conn.rollback()
        raise

def get_global_withdrawal_days():
    """Get global withdrawal days from admin settings"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT global_withdrawal_days FROM admin_settings LIMIT 1')
        row = cursor.fetchone()
        if row and row[0]:
            days_str = row[0]
            if days_str:
                return json.loads(days_str)
    except Exception as e:
        app.logger.error(f"[{request.id}] Error getting global withdrawal days: {e}")
    finally:
        if conn:
            return_db_connection(conn)
    return CONFIG.DEFAULT_WITHDRAWAL_DAYS

@with_db_connection
def is_withdrawal_day(cursor, conn, user_id=None):
    """Check if today is a withdrawal day for a user"""
    today = datetime.utcnow().day
    if user_id is None:
        return today in get_global_withdrawal_days()
    
    try:
        cursor.execute('SELECT withdrawal_restricted, custom_withdrawal_days FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
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
    except Exception as e:
        app.logger.error(f"[{request.id}] Withdrawal day check error: {e}")
        return False

@with_db_connection
def check_withdrawal_cooldown(cursor, conn, user_id):
    """Check if user can withdraw based on cooldown period"""
    try:
        cursor.execute('SELECT withdrawal_last_date, withdrawal_count_today FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        if row:
            last_date_str, count_today = row[0], row[1]
            
            # Check daily limit
            if count_today >= CONFIG.WITHDRAWALS_PER_DAY:
                return False, "Daily withdrawal limit reached"
            
            # Check cooldown
            if last_date_str:
                try:
                    last_date = datetime.fromisoformat(last_date_str).date()
                    today = datetime.utcnow().date()
                    
                    if last_date == today:
                        return False, "Already withdrew today"
                    
                    # Check 24-hour cooldown
                    last_datetime = datetime.fromisoformat(last_date_str)
                    if (datetime.utcnow() - last_datetime).total_seconds() < CONFIG.WITHDRAWAL_COOLDOWN_HOURS * 3600:
                        return False, f"Withdrawal cooldown active. Try again in {24 - int((datetime.utcnow() - last_datetime).total_seconds() / 3600)} hours"
                except:
                    pass
        
        return True, "OK"
    except Exception as e:
        app.logger.error(f"[{request.id}] Withdrawal cooldown check error: {e}")
        return False, "System error"

# ======================= DUPLICATE CLAIM PREVENTION =======================
@with_db_connection
def check_duplicate_claim(cursor, conn, user_id, game_type, cooldown_seconds=1):
    """Check for duplicate claims within cooldown period"""
    try:
        cutoff_time = (datetime.utcnow() - timedelta(seconds=cooldown_seconds)).isoformat()
        cursor.execute('''
            SELECT COUNT(*) FROM transactions
            WHERE user_id = %s AND type LIKE %s
            AND timestamp > %s
        ''', (user_id, f'%{game_type}%', cutoff_time))
        recent_claims = cursor.fetchone()[0]
        return recent_claims == 0
    except Exception as e:
        app.logger.error(f"[{request.id}] Duplicate claim check error: {e}")
        return True

def create_transaction_hash(user_id, game_type, data):
    """Create a hash for transaction deduplication"""
    data_str = json.dumps(data, sort_keys=True)
    hash_input = f"{user_id}-{game_type}-{data_str}-{int(time.time())}"
    return hashlib.sha256(hash_input.encode()).hexdigest()

# ======================= ACHIEVEMENT REWARDS =======================
@with_db_connection
def grant_achievement_rewards(cursor, conn, user_id):
    """Grant achievement rewards to a user"""
    app.logger.info(f"[{request.id}] Granting achievement rewards for user {user_id}")
    
    try:
        cursor.execute('''
            SELECT balance, game_stats, referral_code, points, last_achievement_check, claimed_achievements
            FROM users WHERE id = %s FOR UPDATE
        ''', (user_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        balance = float(row[0]) if row[0] else 0
        game_stats_str = row[1] if row[1] else '{}'
        referral_code = row[2] if row[2] else ''
        current_points = int(row[3]) if row[3] else 0
        last_check = row[4] if row[4] else None
        claimed_achievements_str = row[5] if len(row) > 5 and row[5] else '[]'
        
        try:
            claimed_achievements = json.loads(claimed_achievements_str)
        except:
            claimed_achievements = []

        # Early exit if checked recently
        if last_check:
            try:
                last_check_time = datetime.fromisoformat(last_check)
                if (datetime.utcnow() - last_check_time).total_seconds() < 300:
                    return balance
            except:
                pass

        game_stats = json.loads(game_stats_str)
        cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by = %s', (referral_code,))
        referrals = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM transactions WHERE user_id = %s', (user_id,))
        total_tx = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE user_id = %s AND type = 'WITHDRAWAL'", (user_id,))
        total_withdrawals = cursor.fetchone()[0]
        today = datetime.utcnow().date()
        cursor.execute('SELECT COUNT(*) FROM game_plays WHERE user_id = %s AND play_date = %s', (user_id, today))
        games_today = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM game_plays WHERE user_id = %s', (user_id,))
        total_games = cursor.fetchone()[0]

        snake_high = game_stats.get('snake', {}).get('high_score', 0)
        coin_streak = game_stats.get('coin_flip', {}).get('current_streak', 0)
        coin_total = game_stats.get('coin_flip', {}).get('wins', 0) + game_stats.get('coin_flip', {}).get('losses', 0)
        plinko_wins = game_stats.get('plinko', {}).get('total_wins', 0)

        achievements = [
            {"id": 1, "unlocked": total_games >= 1, "reward": 500, "points": 10},
            {"id": 2, "unlocked": total_games >= 50, "reward": 5000, "points": 50},
            {"id": 3, "unlocked": total_games >= 200, "reward": 15000, "points": 150},
            {"id": 4, "unlocked": snake_high >= 1000, "reward": 7500, "points": 75},
            {"id": 5, "unlocked": coin_streak >= 10, "reward": 10000, "points": 100},
            {"id": 6, "unlocked": coin_total >= 100, "reward": 6000, "points": 60},
            {"id": 7, "unlocked": plinko_wins >= 50, "reward": 8000, "points": 80},
            {"id": 8, "unlocked": balance >= 1000, "reward": 1000, "points": 15},
            {"id": 9, "unlocked": balance >= 50000, "reward": 10000, "points": 100},
            {"id": 10, "unlocked": balance >= 200000, "reward": 25000, "points": 200},
            {"id": 11, "unlocked": total_withdrawals >= 1, "reward": 5000, "points": 50},
            {"id": 12, "unlocked": games_today >= 5, "reward": 3000, "points": 30},
            {"id": 13, "unlocked": games_today >= 20, "reward": 8000, "points": 80},
            {"id": 14, "unlocked": referrals >= 5, "reward": 10000, "points": 100},
            {"id": 15, "unlocked": referrals >= 20, "reward": 30000, "points": 300},
            {"id": 16, "unlocked": total_tx >= 10, "reward": 4000, "points": 40}
        ]

        new_achievements = [ach for ach in achievements if ach["unlocked"] and ach["id"] not in claimed_achievements]
        if not new_achievements:
            cursor.execute('UPDATE users SET last_achievement_check = %s WHERE id = %s',
                          (datetime.utcnow().isoformat(), user_id))
            conn.commit()
            return balance

        total_reward = sum(ach["reward"] for ach in new_achievements)
        total_points = sum(ach["points"] for ach in new_achievements)
        new_achievement_ids = [ach["id"] for ach in new_achievements]
        all_claimed_achievements = claimed_achievements + new_achievement_ids
        new_balance = balance + total_reward

        cursor.execute('''
            UPDATE users SET balance = %s, points = %s,
            last_achievement_check = %s, claimed_achievements = %s
            WHERE id = %s
        ''', (new_balance, current_points + total_points,
              datetime.utcnow().isoformat(),
              json.dumps(all_claimed_achievements), user_id))

        if total_reward > 0:
            tx_id = f"ACH-{secrets.token_hex(8)}"
            cursor.execute('''
                INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (
                tx_id, user_id, 'ACHIEVEMENT_REWARD', total_reward, 'COMPLETED',
                json.dumps({"source": "manual_claim", "points": total_points, "achievement_ids": new_achievement_ids}),
                datetime.utcnow().isoformat()
            ))
        
        conn.commit()
        app.logger.info(f"✅ Granted achievement rewards to user {user_id}: ₦{total_reward}, {total_points} points, achievements: {new_achievement_ids}")
        return new_balance
    except Exception as e:
        app.logger.error(f"❌ Achievement grant error for user {user_id}: {e}")
        app.logger.error(traceback.format_exc())
        raise

# ======================= TIKTOK CLEANUP =======================
@with_db_connection
def cleanup_old_tiktok_tasks(cursor, conn):
    """Clean up old TikTok tasks"""
    try:
        cutoff_date = (datetime.utcnow().date() - timedelta(days=2)).isoformat()
        cursor.execute('DELETE FROM tiktok_daily WHERE date < %s', (cutoff_date,))
        conn.commit()
        app.logger.info(f"Removed TikTok tasks before {cutoff_date}")
    except Exception as e:
        app.logger.error(f"TikTok Cleanup Error: {e}")
        conn.rollback()

def run_cleanup_scheduler():
    """Run TikTok cleanup scheduler"""
    def schedule():
        while True:
            try:
                now = datetime.utcnow()
                next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
                if now > next_run:
                    next_run += timedelta(days=1)
                time_to_sleep = (next_run - now).total_seconds()
                time.sleep(time_to_sleep)
                cleanup_old_tiktok_tasks()
            except Exception as e:
                app.logger.error(f"Cleanup scheduler error: {str(e)}")
                time.sleep(3600)
    
    thread = threading.Thread(target=schedule, daemon=True)
    thread.start()

# ======================= INITIALIZE APPLICATION =======================
with app.app_context():
    app.logger.info("🚀 Initializing FLEXIA Platform v15.0 (Secure with API Versioning)...")
    
    # Initialize database
    init_db_pool()
    init_db()
    add_missing_columns()
    add_database_indexes()
    
    # Start schedulers
    cleanup_old_tiktok_tasks()
    run_cleanup_scheduler()
    run_backup_scheduler()
    schedule_health_checks()
    
    app.logger.info("✅ FLEXIA Platform initialization complete!")
    app.logger.info(f"📊 Game Limits: Snake={CONFIG.SNAKE_PLAYS_PER_DAY}/day, Coin/Plinko={CONFIG.COIN_PLAYS_PER_DAY}/day")
    app.logger.info(f"🔐 Security: 2FA={'Enabled' if CONFIG.ENABLE_2FA else 'Disabled'}, Admin IP Whitelist: {len(CONFIG.ADMIN_IP_WHITELIST)} IPs")
    app.logger.info(f"🌐 API Versioning: Current={CONFIG.API_CURRENT_VERSION}, Supported={CONFIG.API_SUPPORTED_VERSIONS}")

# ======================= ALL API VERSION 1 ENDPOINTS =======================

# ======================= SECURITY ENDPOINTS =======================
@app.route('/api/v1/security/2fa/setup', methods=['GET'])
@api_version_required
@require_auth
@rate_limit_db_decorator(limit_per_minute=5)
def setup_2fa_v1():
    """Setup 2FA for user - API v1"""
    user = get_current_user()
    
    if not CONFIG.ENABLE_2FA:
        return jsonify({
            "success": False,
            "message": "2FA is disabled",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if already enabled
        if user.get('two_fa_enabled'):
            return jsonify({
                "success": False,
                "message": "2FA already enabled",
                "request_id": request.id,
                "api_version": request.api_version
            }), 400
        
        # Generate new secret if not exists
        if not user.get('two_fa_secret'):
            secret = security.generate_2fa_secret()
            cursor.execute('UPDATE users SET two_fa_secret = %s WHERE id = %s',
                          (secret, user['id']))
            conn.commit()
        else:
            secret = user['two_fa_secret']
        
        # Generate QR code
        qr_code = security.generate_2fa_qr(secret, user['username'])
        
        return jsonify({
            "success": True,
            "secret": secret,
            "qr_code": qr_code,
            "message": "Scan QR code with authenticator app",
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] 2FA setup error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to setup 2FA",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/security/2fa/verify', methods=['POST'])
@api_version_required
@require_auth
@rate_limit_db_decorator(limit_per_minute=5)
def verify_2fa_v1():
    """Verify 2FA token and enable - API v1"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    token = data.get('token', '')
    
    if not token or len(token) != 6:
        return jsonify({
            "success": False,
            "message": "Invalid token",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get user with fresh secret
        cursor.execute('SELECT two_fa_secret FROM users WHERE id = %s', (user['id'],))
        row = cursor.fetchone()
        
        if not row or not row[0]:
            return jsonify({
                "success": False,
                "message": "2FA not configured",
                "request_id": request.id,
                "api_version": request.api_version
            }), 400
        
        secret = row[0]
        
        # Verify token
        if not security.verify_2fa_token(secret, token):
            audit_logger.log_failed_login(
                user['username'],
                request.remote_addr,
                "Invalid 2FA token"
            )
            return jsonify({
                "success": False,
                "message": "Invalid token",
                "request_id": request.id,
                "api_version": request.api_version
            }), 400
        
        # Enable 2FA
        cursor.execute('UPDATE users SET two_fa_enabled = TRUE WHERE id = %s',
                      (user['id'],))
        conn.commit()
        
        # Mark 2FA as verified in session
        session['two_fa_verified'] = True
        
        audit_logger.log_security_event(
            "2FA_ENABLED",
            {"user_id": user['id'], "username": user['username']},
            "MEDIUM"
        )
        
        return jsonify({
            "success": True,
            "message": "2FA enabled successfully",
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] 2FA verify error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to verify 2FA",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/security/2fa/disable', methods=['POST'])
@api_version_required
@require_auth
@rate_limit_db_decorator(limit_per_minute=5)
def disable_2fa_v1():
    """Disable 2FA for user - API v1"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    token = data.get('token', '')
    password = data.get('password', '')
    
    if not token or not password:
        return jsonify({
            "success": False,
            "message": "Token and password required",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    # Verify password first
    if not check_password_hash(user['password'], password):
        audit_logger.log_failed_login(
            user['username'],
            request.remote_addr,
            "Invalid password for 2FA disable"
        )
        return jsonify({
            "success": False,
            "message": "Invalid password",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Verify 2FA token
        cursor.execute('SELECT two_fa_secret FROM users WHERE id = %s', (user['id'],))
        row = cursor.fetchone()
        
        if not row or not row[0]:
            return jsonify({
                "success": False,
                "message": "2FA not enabled",
                "request_id": request.id,
                "api_version": request.api_version
            }), 400
        
        secret = row[0]
        
        if not security.verify_2fa_token(secret, token):
            audit_logger.log_failed_login(
                user['username'],
                request.remote_addr,
                "Invalid 2FA token for disable"
            )
            return jsonify({
                "success": False,
                "message": "Invalid token",
                "request_id": request.id,
                "api_version": request.api_version
            }), 400
        
        # Disable 2FA
        cursor.execute('UPDATE users SET two_fa_enabled = FALSE WHERE id = %s',
                      (user['id'],))
        conn.commit()
        
        # Remove 2FA verification from session
        session.pop('two_fa_verified', None)
        
        audit_logger.log_security_event(
            "2FA_DISABLED",
            {"user_id": user['id'], "username": user['username']},
            "MEDIUM"
        )
        
        return jsonify({
            "success": True,
            "message": "2FA disabled successfully",
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] 2FA disable error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to disable 2FA",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/security/2fa/verify-login', methods=['POST'])
@api_version_required
@rate_limit_db_decorator(limit_per_minute=5)
def verify_2fa_login_v1():
    """Verify 2FA token during login - API v1"""
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    username = data.get('username', '')
    token = data.get('token', '')
    
    if not username or not token:
        return jsonify({
            "success": False,
            "message": "Username and token required",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT id, two_fa_secret, two_fa_enabled FROM users WHERE username = %s', (username,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({
                "success": False,
                "message": "User not found",
                "request_id": request.id,
                "api_version": request.api_version
            }), 404
        
        user_id, secret, two_fa_enabled = row[0], row[1], row[2]
        
        if not two_fa_enabled or not secret:
            return jsonify({
                "success": False,
                "message": "2FA not enabled for this user",
                "request_id": request.id,
                "api_version": request.api_version
            }), 400
        
        # Verify token
        if not security.verify_2fa_token(secret, token):
            audit_logger.log_failed_login(
                username,
                request.remote_addr,
                "Invalid 2FA token"
            )
            return jsonify({
                "success": False,
                "message": "Invalid token",
                "request_id": request.id,
                "api_version": request.api_version
            }), 400
        
        # Create session token
        session_token = create_session_token(user_id)
        
        # Mark 2FA as verified in session
        session['two_fa_verified'] = True
        
        # Update last login
        cursor.execute('UPDATE users SET last_login = %s, last_login_ip = %s WHERE id = %s',
                      (datetime.utcnow().isoformat(), request.remote_addr, user_id))
        conn.commit()
        
        response = jsonify({
            "success": True,
            "message": "2FA verified successfully",
            "requires_2fa": False,
            "request_id": request.id,
            "api_version": request.api_version
        })
        
        # Set secure cookie
        secure_cookie = (os.getenv('ENV') == 'production')
        response.set_cookie('session_token', session_token,
                          httponly=True,
                          secure=secure_cookie,
                          samesite='Lax',
                          max_age=86400)
        
        return response
    except Exception as e:
        app.logger.error(f"[{request.id}] 2FA login verify error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to verify 2FA",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/security/audit-logs', methods=['GET'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def get_audit_logs_v1():
    """Get audit logs (admin only) - API v1"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        offset = (page - 1) * limit
        
        cursor.execute('''
            SELECT al.*, u.username
            FROM audit_logs al
            LEFT JOIN users u ON al.user_id = u.id
            ORDER BY al.timestamp DESC
            LIMIT %s OFFSET %s
        ''', (limit, offset))
        
        logs = []
        for row in cursor.fetchall():
            log = row_to_dict(cursor, row)
            logs.append(log)
        
        cursor.execute('SELECT COUNT(*) FROM audit_logs')
        total = cursor.fetchone()[0]
        
        return jsonify({
            "success": True,
            "logs": logs,
            "total": total,
            "page": page,
            "limit": limit,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Audit logs error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load audit logs",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/security/failed-logins', methods=['GET'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def get_failed_logins_v1():
    """Get failed login attempts (admin only) - API v1"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT username, ip_address, reason, timestamp
            FROM failed_logins
            WHERE timestamp > NOW() - INTERVAL '24 hours'
            ORDER BY timestamp DESC
            LIMIT 100
        ''')
        
        logins = []
        for row in cursor.fetchall():
            logins.append({
                'username': row[0],
                'ip_address': row[1],
                'reason': row[2],
                'timestamp': row[3]
            })
        
        return jsonify({
            "success": True,
            "logins": logins,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Failed logins error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load failed logins",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/security/security-events', methods=['GET'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def get_security_events_v1():
    """Get security events (admin only) - API v1"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        severity = request.args.get('severity', '')
        
        query = '''
            SELECT event_type, event_details, severity, timestamp
            FROM security_events
            WHERE 1=1
        '''
        params = []
        
        if severity:
            query += ' AND severity = %s'
            params.append(severity)
        
        query += ' ORDER BY timestamp DESC LIMIT 100'
        
        cursor.execute(query, params)
        
        events = []
        for row in cursor.fetchall():
            try:
                details = json.loads(row[1]) if row[1] else {}
            except:
                details = {}
            
            events.append({
                'event_type': row[0],
                'event_details': details,
                'severity': row[2],
                'timestamp': row[3]
            })
        
        return jsonify({
            "success": True,
            "events": events,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Security events error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load security events",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

# ======================= AUTH ENDPOINTS =======================
@app.route('/api/v1/auth/register', methods=['POST'])
@api_version_required
@rate_limit_db_decorator(limit_per_minute=CONFIG.MAX_REGISTER_ATTEMPTS)
def register_v1():
    """Register a new user - API v1"""
    data = request.get_json()
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    # Input validation
    validation_rules = {
        'username': {'required': True, 'type': 'string', 'min_length': 3, 'max_length': 50},
        'password': {'required': True, 'type': 'string', 'min_length': CONFIG.PASSWORD_MIN_LENGTH},
        'coupon_code': {'required': True, 'type': 'string', 'min_length': 4},
        'referral_code': {'required': False, 'type': 'string', 'min_length': 4},
        'contact': {'required': False, 'type': 'string', 'max_length': 20}
    }
    
    errors = validate_input(data, validation_rules)
    if errors:
        return jsonify({
            "success": False,
            "message": "Validation failed",
            "errors": errors,
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    # Sanitize inputs
    username = sanitize_input(data.get('username', '').strip().lower())
    password = data.get('password', '')
    coupon_code = sanitize_input(data.get('coupon_code', '').upper())
    referral_code = sanitize_input(data.get('referral_code', ''))
    contact = sanitize_input(data.get('contact', ''))
    
    # Validate password strength
    is_valid, message = security.validate_password(password)
    if not is_valid:
        return jsonify({
            "success": False,
            "message": message,
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if username exists
        cursor.execute('SELECT id FROM users WHERE LOWER(username) = LOWER(%s)', (username,))
        if cursor.fetchone():
            return jsonify({
                "success": False,
                "message": "Username already taken",
                "request_id": request.id,
                "api_version": request.api_version
            }), 409
        
        # Check coupon
        cursor.execute('SELECT status FROM coupons WHERE code = %s', (coupon_code,))
        coupon_row = cursor.fetchone()
        if not coupon_row:
            return jsonify({
                "success": False,
                "message": "Invalid coupon code",
                "request_id": request.id,
                "api_version": request.api_version
            }), 403
        
        if coupon_row[0] != 'AVAILABLE':
            return jsonify({
                "success": False,
                "message": "Coupon already used",
                "request_id": request.id,
                "api_version": request.api_version
            }), 403
        
        # Check referral code
        if referral_code:
            cursor.execute('SELECT referral_code FROM users WHERE referral_code = %s', (referral_code,))
            if not cursor.fetchone():
                return jsonify({
                    "success": False,
                    "message": "Invalid referral code",
                    "request_id": request.id,
                    "api_version": request.api_version
                }), 400
        
        # Mark coupon as used
        cursor.execute('UPDATE coupons SET status = %s WHERE code = %s', ("USED", coupon_code))
        
        # Create user
        timestamp = int(time.time())
        user_referral_code = f"{username[:3].upper()}{timestamp % 10000:04d}"
        game_stats = json.dumps({
            "snake": {"high_score": 0, "total_score": 0},
            "coin_flip": {"wins": 0, "losses": 0, "current_streak": 0},
            "plinko": {"total_wins": 0, "total_bets": 0, "highest_win": 0}
        })
        
        # Generate 2FA secret
        two_fa_secret = security.generate_2fa_secret() if CONFIG.ENABLE_2FA else None
        
        cursor.execute('''
            INSERT INTO users (
                username, password, balance, referral_code, referred_by, is_admin,
                created_at, last_login, game_stats, contact, profile_picture, ui_theme,
                admin_password_changed, withdrawal_pin, withdrawal_restricted, withdrawal_limit,
                points, claimed_bonuses, last_game_timestamp, last_achievement_check,
                claimed_achievements, two_fa_secret, two_fa_enabled, last_password_change,
                last_login_ip, last_login_time, session_tokens
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s
            )
        ''', (
            username, generate_password_hash(password), 0.00, user_referral_code, referral_code or None, False,
            datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), game_stats, contact or "", "", "light",
            False, None, False, 0.00, 0, 0,
            datetime.utcnow().isoformat(), datetime.utcnow().isoformat(),
            '[]', two_fa_secret, False, datetime.utcnow().isoformat(),
            request.remote_addr, datetime.utcnow().isoformat(), '[]'
        ))
        
        cursor.execute("SELECT LASTVAL()")
        new_id = cursor.fetchone()[0]
        
        # Give admin bonus if referred by admin
        admin_bonus = 0
        if referral_code:
            cursor.execute('SELECT is_admin FROM users WHERE referral_code = %s', (referral_code,))
            ref_row = cursor.fetchone()
            if ref_row and ref_row[0]:
                admin_bonus = 5000
                cursor.execute('UPDATE users SET balance = %s WHERE id = %s', (admin_bonus, new_id))
        
        conn.commit()
        
        # Create session token
        token = create_session_token(new_id)
        
        # Log successful registration
        audit_logger.log_security_event(
            "USER_REGISTERED",
            {"user_id": new_id, "username": username, "referral_code": referral_code},
            "LOW"
        )
        
        response = jsonify({
            "success": True,
            "message": "Registration successful",
            "user": {
                "id": new_id,
                "username": username,
                "referral_code": user_referral_code,
                "balance": admin_bonus,
                "two_fa_enabled": False,
                "two_fa_required": CONFIG.ENABLE_2FA
            },
            "request_id": request.id,
            "api_version": request.api_version
        })
        
        # Set secure cookie
        secure_cookie = (os.getenv('ENV') == 'production')
        response.set_cookie('session_token', token,
                          httponly=True,
                          secure=secure_cookie,
                          samesite='Lax',
                          max_age=86400)
        
        app.logger.info(f"[{request.id}] New user registered: {username} (ID: {new_id})")
        return response
    except Exception as e:
        app.logger.error(f"[{request.id}] Registration error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": f"Registration failed: {str(e)}",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/auth/login', methods=['POST'])
@api_version_required
@rate_limit_db_decorator(limit_per_minute=CONFIG.MAX_LOGIN_ATTEMPTS)
def login_v1():
    """Login user - API v1"""
    data = request.get_json()
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    # Input validation
    validation_rules = {
        'username': {'required': True, 'type': 'string', 'min_length': 1},
        'password': {'required': True, 'type': 'string', 'min_length': 1}
    }
    
    errors = validate_input(data, validation_rules)
    if errors:
        return jsonify({
            "success": False,
            "message": "Validation failed",
            "errors": errors,
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    identifier = sanitize_input(data.get('username', '').strip().lower())
    password = data.get('password', '')
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE LOWER(username) = LOWER(%s) OR LOWER(contact) = LOWER(%s)',
                      (identifier, identifier))
        row = cursor.fetchone()
        
        if not row:
            audit_logger.log_failed_login(
                identifier,
                request.remote_addr,
                "User not found"
            )
            app.logger.warning(f"[{request.id}] Failed login attempt for identifier: {identifier}")
            return jsonify({
                "success": False,
                "message": "Invalid credentials",
                "request_id": request.id,
                "api_version": request.api_version
            }), 401
        
        user = row_to_dict(cursor, row)
        
        # Check if account is locked
        if user.get('is_locked'):
            lock_until = user.get('lock_until')
            if lock_until:
                try:
                    lock_time = datetime.fromisoformat(lock_until)
                    if lock_time > datetime.utcnow():
                        return jsonify({
                            "success": False,
                            "message": f"Account locked until {lock_time.strftime('%Y-%m-%d %H:%M:%S')}",
                            "request_id": request.id,
                            "api_version": request.api_version
                        }), 403
                except:
                    pass
        
        stored_password = user.get('password')
        if not stored_password or not check_password_hash(stored_password, password):
            audit_logger.log_failed_login(
                user['username'],
                request.remote_addr,
                "Invalid password"
            )
            
            # Increment login attempts
            login_attempts = user.get('login_attempts', 0) + 1
            cursor.execute('UPDATE users SET login_attempts = %s WHERE id = %s',
                          (login_attempts, user['id']))
            
            # Lock account if too many attempts
            if login_attempts >= CONFIG.ACCOUNT_LOCKOUT_ATTEMPTS:
                lock_until = (datetime.utcnow() + timedelta(seconds=CONFIG.ACCOUNT_LOCKOUT_DURATION)).isoformat()
                cursor.execute('UPDATE users SET is_locked = TRUE, lock_until = %s WHERE id = %s',
                              (lock_until, user['id']))
                
                audit_logger.log_security_event(
                    "ACCOUNT_LOCKED",
                    {"user_id": user['id'], "username": user['username'], "reason": "Too many failed attempts"},
                    "HIGH"
                )
            
            conn.commit()
            app.logger.warning(f"[{request.id}] Invalid password for user: {identifier}")
            return jsonify({
                "success": False,
                "message": "Invalid credentials",
                "request_id": request.id,
                "api_version": request.api_version
            }), 401
        
        # Reset login attempts on successful login
        cursor.execute('UPDATE users SET login_attempts = 0, is_locked = FALSE, lock_until = NULL WHERE id = %s',
                      (user['id'],))
        
        # Check if 2FA is required
        requires_2fa = False
        if CONFIG.ENABLE_2FA:
            if user.get('is_admin') and CONFIG.ENABLE_ADMIN_2FA:
                requires_2fa = True
            elif user.get('two_fa_enabled'):
                requires_2fa = True
        
        if requires_2fa:
            # Don't create session yet, require 2FA
            return jsonify({
                "success": True,
                "requires_2fa": True,
                "username": user['username'],
                "message": "2FA required",
                "request_id": request.id,
                "api_version": request.api_version
            })
        
        # Create session token
        token = create_session_token(user['id'])
        
        # Update last login
        cursor.execute('UPDATE users SET last_login = %s, last_login_ip = %s, last_login_time = %s WHERE id = %s',
                      (datetime.utcnow().isoformat(), request.remote_addr, datetime.utcnow().isoformat(), user['id']))
        conn.commit()
        
        # Log successful login
        audit_logger.log_security_event(
            "USER_LOGIN",
            {"user_id": user['id'], "username": user['username'], "ip_address": request.remote_addr},
            "LOW"
        )
        
        # Create response
        resp = jsonify({
            "success": True,
            "user": {
                "id": user['id'],
                "username": user['username'],
                "balance": float(user['balance']) if user['balance'] else 0.00,
                "referral_code": user.get('referral_code', ''),
                "is_admin": bool(user.get('is_admin', False)),
                "admin_password_changed": bool(user.get('admin_password_changed', False)),
                "profile_picture": user.get('profile_picture', ''),
                "ui_theme": user.get('ui_theme', 'light'),
                "two_fa_enabled": bool(user.get('two_fa_enabled', False))
            },
            "requires_2fa": False,
            "request_id": request.id,
            "api_version": request.api_version
        })
        
        secure_cookie = (os.getenv('ENV') == 'production')
        resp.set_cookie('session_token', token,
                       httponly=True,
                       secure=secure_cookie,
                       samesite='Lax',
                       max_age=86400)
        
        app.logger.info(f"[{request.id}] User logged in: {user['username']} (ID: {user['id']})")
        return resp
    except Exception as e:
        app.logger.error(f"[{request.id}] Login error: {e}")
        return jsonify({
            "success": False,
            "message": f"Login failed: {str(e)}",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/auth/logout', methods=['POST'])
@api_version_required
@require_auth
def logout_v1():
    """Logout user - API v1"""
    user = get_current_user()
    
    # Invalidate session token
    session.clear()
    
    # Log logout
    audit_logger.log_security_event(
        "USER_LOGOUT",
        {"user_id": user['id'], "username": user['username']},
        "LOW"
    )
    
    resp = jsonify({
        "success": True,
        "message": "Logged out",
        "request_id": request.id,
        "api_version": request.api_version
    })
    resp.set_cookie('session_token', '', expires=0)
    return resp

@app.route('/api/v1/auth/logout-all', methods=['POST'])
@api_version_required
@require_auth
@rate_limit_db_decorator(limit_per_minute=5)
def logout_all_v1():
    """Logout from all devices (on password change) - API v1"""
    user = get_current_user()
    
    # Invalidate all sessions by clearing session tokens
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET session_tokens = %s WHERE id = %s',
                      ('[]', user['id']))
        conn.commit()
    except Exception as e:
        app.logger.error(f"[{request.id}] Logout all error: {e}")
    finally:
        if conn:
            return_db_connection(conn)
    
    # Clear current session
    session.clear()
    
    audit_logger.log_security_event(
        "LOGOUT_ALL_DEVICES",
        {"user_id": user['id'], "username": user['username']},
        "MEDIUM"
    )
    
    resp = jsonify({
        "success": True,
        "message": "Logged out from all devices",
        "request_id": request.id,
        "api_version": request.api_version
    })
    resp.set_cookie('session_token', '', expires=0)
    return resp

# ======================= PASSWORD & SECURITY ENDPOINTS =======================
@app.route('/api/v1/user/change-password', methods=['POST'])
@api_version_required
@require_auth
@rate_limit_db_decorator(limit_per_minute=5)
def change_password_v1():
    """Change user password - API v1"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    validation_rules = {
        'old_password': {'required': True, 'type': 'string', 'min_length': 1},
        'new_password': {'required': True, 'type': 'string', 'min_length': CONFIG.PASSWORD_MIN_LENGTH}
    }
    
    errors = validate_input(data, validation_rules)
    if errors:
        return jsonify({
            "success": False,
            "message": "Validation failed",
            "errors": errors,
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    
    # Validate new password strength
    is_valid, message = security.validate_password(new_password)
    if not is_valid:
        return jsonify({
            "success": False,
            "message": message,
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    # Verify old password
    if not check_password_hash(user['password'], old_password):
        audit_logger.log_failed_login(
            user['username'],
            request.remote_addr,
            "Invalid old password during change"
        )
        return jsonify({
            "success": False,
            "message": "Current password is incorrect",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    # Check if new password is same as old
    if check_password_hash(user['password'], new_password):
        return jsonify({
            "success": False,
            "message": "New password must be different from old password",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Update password
        cursor.execute('UPDATE users SET password = %s, last_password_change = %s WHERE id = %s',
                      (generate_password_hash(new_password), datetime.utcnow().isoformat(), user['id']))
        conn.commit()
        
        # Log password change
        audit_logger.log_security_event(
            "PASSWORD_CHANGED",
            {"user_id": user['id'], "username": user['username']},
            "MEDIUM"
        )
        
        # Logout from all devices
        logout_all_v1()
        
        app.logger.info(f"[{request.id}] User {user['username']} changed password")
        return jsonify({
            "success": True,
            "message": "Password updated. Please login again.",
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Password change error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to update",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/admin/change-password', methods=['POST'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=5)
def admin_change_password_v1():
    """Change admin password - API v1"""
    admin_user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    validation_rules = {
        'current_password': {'required': True, 'type': 'string', 'min_length': 1},
        'new_password': {'required': True, 'type': 'string', 'min_length': CONFIG.PASSWORD_MIN_LENGTH}
    }
    
    errors = validate_input(data, validation_rules)
    if errors:
        return jsonify({
            "success": False,
            "message": "Validation failed",
            "errors": errors,
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    # Validate new password strength
    is_valid, message = security.validate_password(new_password)
    if not is_valid:
        return jsonify({
            "success": False,
            "message": message,
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    if not check_password_hash(admin_user['password'], current_password):
        audit_logger.log_failed_login(
            admin_user['username'],
            request.remote_addr,
            "Invalid admin password during change"
        )
        return jsonify({
            "success": False,
            "message": "Current password is incorrect",
            "request_id": request.id,
            "api_version": request.api_version
        }), 403
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE users SET password = %s, admin_password_changed = %s, last_password_change = %s WHERE id = %s',
                      (generate_password_hash(new_password), True, datetime.utcnow().isoformat(), admin_user['id']))
        conn.commit()
        
        # Log admin password change
        audit_logger.log_admin_action(
            admin_user['id'],
            "ADMIN_PASSWORD_CHANGE",
            {"admin_id": admin_user['id'], "username": admin_user['username']},
            request.remote_addr
        )
        
        # Logout from all devices
        logout_all_v1()
        
        app.logger.info(f"[{request.id}] Admin {admin_user['username']} changed their password")
        return jsonify({
            "success": True,
            "message": "Password changed successfully. Please login again.",
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Admin password change error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to change password",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/user/set-withdrawal-pin', methods=['POST'])
@api_version_required
@require_auth
@rate_limit_db_decorator(limit_per_minute=5)
def set_withdrawal_pin_v1():
    """Set withdrawal PIN - API v1"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    pin = data.get('pin', '')
    
    if not pin.isdigit() or not (4 <= len(pin) <= 6):
        return jsonify({
            "success": False,
            "message": "PIN must be 4-6 digits",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET withdrawal_pin = %s WHERE id = %s', 
                      (generate_password_hash(pin), user['id']))
        conn.commit()
        
        audit_logger.log_security_event(
            "WITHDRAWAL_PIN_SET",
            {"user_id": user['id'], "username": user['username']},
            "LOW"
        )
        
        app.logger.info(f"[{request.id}] User {user['username']} set withdrawal PIN")
        return jsonify({
            "success": True,
            "message": "PIN set successfully",
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] PIN error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to set",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/user/verify-withdrawal-pin', methods=['POST'])
@api_version_required
@require_auth
@rate_limit_db_decorator(limit_per_minute=10)
def verify_withdrawal_pin_v1():
    """Verify withdrawal PIN - API v1"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    pin = data.get('pin', '')
    withdrawal_pin = user.get('withdrawal_pin')
    
    if not withdrawal_pin:
        return jsonify({
            "success": False,
            "message": "No PIN set",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    if not check_password_hash(withdrawal_pin, pin):
        audit_logger.log_failed_login(
            user['username'],
            request.remote_addr,
            "Invalid withdrawal PIN"
        )
        app.logger.warning(f"[{request.id}] Invalid PIN attempt for user: {user['username']}")
        return jsonify({
            "success": False,
            "message": "Invalid PIN",
            "request_id": request.id,
            "api_version": request.api_version
        }), 403
    
    return jsonify({
        "success": True,
        "message": "PIN verified",
        "request_id": request.id,
        "api_version": request.api_version
    })

# ======================= GAME ENDPOINTS WITH LIMITS =======================
@app.route('/api/v1/games/limit-check', methods=['GET'])
@api_version_required
@require_auth
@rate_limit_db_decorator(limit_per_minute=10)
def check_game_limits_v1():
    """Check game play limits for user - API v1"""
    user = get_current_user()
    game_type = request.args.get('game', '')
    
    if not game_type:
        return jsonify({
            "success": False,
            "message": "Game type required",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    # Set limits based on game type
    max_plays = {
        'snake': CONFIG.SNAKE_PLAYS_PER_DAY,
        'coinflip': CONFIG.COIN_PLAYS_PER_DAY,
        'plinko': CONFIG.PLINKO_PLAYS_PER_DAY,
        'spin': CONFIG.SPIN_PLAYS_PER_DAY,
        'tiktok': CONFIG.TIKTOK_PLAYS_PER_DAY
    }.get(game_type, 1)
    
    today = datetime.utcnow().date()
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM game_plays WHERE user_id = %s AND game_type = %s AND play_date = %s',
                      (user['id'], game_type, today))
        played_today = cursor.fetchone()[0]
        remaining = max(0, max_plays - played_today)
        
        return jsonify({
            "success": True,
            "can_play": remaining > 0,
            "played_today": played_today,
            "remaining": remaining,
            "max_per_day": max_plays,
            "game_type": game_type,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Limit check error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to check limits",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/games/snake/report', methods=['POST'])
@api_version_required
@require_auth
@rate_limit_db_decorator(limit_per_minute=CONFIG.MAX_GAME_ATTEMPTS)
def report_snake_v1():
    """Report snake game results - 10 plays per day - API v1"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    # Input validation
    apples = data.get('apples_eaten', 0)
    try:
        apples = int(apples)
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid apple count",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    if apples <= 0 or apples > 100:
        return jsonify({
            "success": False,
            "message": "Invalid apple count (1-100)",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    # Check cooldown
    if not check_game_cooldown(user['id'], 'SNAKE'):
        return jsonify({
            "success": False,
            "message": "Please wait 1 second between games",
            "request_id": request.id,
            "api_version": request.api_version
        }), 429
    
    # Check daily limit - 10 plays per day for snake
    if not can_play_today(user['id'], 'snake'):
        return jsonify({
            "success": False,
            "message": f"Max {CONFIG.SNAKE_PLAYS_PER_DAY} snake plays per day",
            "request_id": request.id,
            "api_version": request.api_version
        }), 403
    
    # Check duplicate claim
    if not check_duplicate_claim(user['id'], 'SNAKE', cooldown_seconds=1):
        return jsonify({
            "success": False,
            "message": "Please wait before claiming again",
            "request_id": request.id,
            "api_version": request.api_version
        }), 429
    
    # Calculate reward
    reward = apples * CONFIG.SNAKE_REWARD
    
    try:
        # Update balance
        new_balance = update_user_balance(user['id'], reward)
        if new_balance is None:
            return jsonify({
                "success": False,
                "message": "Failed to update balance",
                "request_id": request.id,
                "api_version": request.api_version
            }), 500
        
        # Update game stats
        game_stats = json.loads(user.get('game_stats', '{}'))
        snake_stats = game_stats.get('snake', {'high_score': 0, 'total_score': 0})
        score = apples * 10
        
        if score > snake_stats.get('high_score', 0):
            snake_stats['high_score'] = score
        snake_stats['total_score'] = snake_stats.get('total_score', 0) + score
        game_stats['snake'] = snake_stats
        
        conn = None
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET game_stats = %s WHERE id = %s',
                          (json.dumps(game_stats), user['id']))
            
            # Update timestamps and record play
            update_last_game_timestamp(user['id'])
            record_game_play(user['id'], 'snake')
            
            # Create transaction
            tx_id = f"SNK-{int(time.time())}-{secrets.token_hex(4)}"
            cursor.execute('''
                INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (
                tx_id, user['id'], 'SNAKE_REWARD', reward, 'COMPLETED',
                json.dumps({"game": "snake", "apples": apples, "reward_per_apple": CONFIG.SNAKE_REWARD}),
                datetime.utcnow().isoformat()
            ))
            
            conn.commit()
            app.logger.info(f"[{request.id}] ✅ Snake reward granted to {user['username']}: ₦{reward}")
            
            return jsonify({
                "success": True,
                "reward": reward,
                "new_balance": new_balance,
                "apples": apples,
                "transaction_id": tx_id,
                "message": f"Success! Claimed ₦{reward} for {apples} apples",
                "request_id": request.id,
                "api_version": request.api_version
            })
        except Exception as e:
            app.logger.error(f"[{request.id}] ❌ Snake report error: {e}")
            if conn:
                conn.rollback()
            return jsonify({
                "success": False,
                "message": f"Server error: {str(e)}",
                "request_id": request.id,
                "api_version": request.api_version
            }), 500
        finally:
            if conn:
                return_db_connection(conn)
    except Exception as e:
        app.logger.error(f"[{request.id}] ❌ Snake balance update error: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to update balance: {str(e)}",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500

@app.route('/api/v1/games/coinflip/report', methods=['POST'])
@api_version_required
@require_auth
@rate_limit_db_decorator(limit_per_minute=CONFIG.MAX_GAME_ATTEMPTS)
def report_coinflip_v1():
    """Report coin flip game results - 2 plays per day - API v1"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    # Input validation
    try:
        bet = float(data.get('bet', 0))
        won = bool(data.get('won', False))
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid data",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    if bet < CONFIG.COIN_FLIP_MIN_BET or bet > 50000:
        return jsonify({
            "success": False,
            "message": f"Invalid bet (min: {CONFIG.COIN_FLIP_MIN_BET}, max: 50000)",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    if float(user['balance']) < bet:
        return jsonify({
            "success": False,
            "message": "Insufficient balance",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    # Check cooldown
    if not check_game_cooldown(user['id'], 'COINFLIP'):
        return jsonify({
            "success": False,
            "message": "Please wait 1 second between games",
            "request_id": request.id,
            "api_version": request.api_version
        }), 429
    
    # Check daily limit - 2 plays per day for coin flip
    if not can_play_today(user['id'], 'coinflip'):
        return jsonify({
            "success": False,
            "message": f"Max {CONFIG.COIN_PLAYS_PER_DAY} coin flips per day",
            "request_id": request.id,
            "api_version": request.api_version
        }), 403
    
    # Check duplicate claim
    if not check_duplicate_claim(user['id'], 'COINFLIP', cooldown_seconds=1):
        return jsonify({
            "success": False,
            "message": "Please wait before playing again",
            "request_id": request.id,
            "api_version": request.api_version
        }), 429
    
    # Calculate payout
    payout = bet * 2 if won else 0
    net_change = payout - bet
    
    try:
        # Update balance
        new_balance = update_user_balance(user['id'], net_change)
        if new_balance is None:
            return jsonify({
                "success": False,
                "message": "Failed to update balance",
                "request_id": request.id,
                "api_version": request.api_version
            }), 500
        
        conn = None
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            # Update game stats
            game_stats = json.loads(user.get('game_stats', '{}'))
            coinflip_stats = game_stats.get('coin_flip', {'wins': 0, 'losses': 0, 'current_streak': 0})
            
            if won:
                coinflip_stats['wins'] = coinflip_stats.get('wins', 0) + 1
                coinflip_stats['current_streak'] = coinflip_stats.get('current_streak', 0) + 1
            else:
                coinflip_stats['losses'] = coinflip_stats.get('losses', 0) + 1
                coinflip_stats['current_streak'] = 0
            
            game_stats['coin_flip'] = coinflip_stats
            cursor.execute('UPDATE users SET game_stats = %s WHERE id = %s',
                          (json.dumps(game_stats), user['id']))
            
            # Update timestamps and record play
            update_last_game_timestamp(user['id'])
            record_game_play(user['id'], 'coinflip')
            
            # Create transaction
            tx_type = 'COINFLIP_WIN' if won else 'COINFLIP_LOSS'
            tx_id = f"COIN-{int(time.time())}-{secrets.token_hex(4)}"
            cursor.execute('''
                INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (
                tx_id, user['id'], tx_type, net_change, 'COMPLETED',
                json.dumps({"game": "coinflip", "bet": bet, "won": won, "payout": payout}),
                datetime.utcnow().isoformat()
            ))
            
            conn.commit()
            app.logger.info(f"[{request.id}] ✅ Coin flip processed for {user['username']}: {'WON' if won else 'LOST'} {bet}, net: {net_change}")
            
            return jsonify({
                "success": True,
                "payout": payout if won else 0,
                "net_change": net_change,
                "new_balance": new_balance,
                "won": won,
                "message": f"You {'won' if won else 'lost'}! {'+' if won else '-'}₦{abs(net_change):.2f}",
                "request_id": request.id,
                "api_version": request.api_version
            })
        except Exception as e:
            app.logger.error(f"[{request.id}] ❌ Coin flip error: {e}")
            if conn:
                conn.rollback()
            return jsonify({
                "success": False,
                "message": f"Failed to process: {str(e)}",
                "request_id": request.id,
                "api_version": request.api_version
            }), 500
        finally:
            if conn:
                return_db_connection(conn)
    except Exception as e:
        app.logger.error(f"[{request.id}] ❌ Coin flip balance update error: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to update balance: {str(e)}",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500

@app.route('/api/v1/games/plinko/report', methods=['POST'])
@api_version_required
@require_auth
@rate_limit_db_decorator(limit_per_minute=CONFIG.MAX_GAME_ATTEMPTS)
def report_plinko_v1():
    """Report plinko game results - 2 plays per day - API v1"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    # Input validation
    try:
        bet = float(data.get('bet', 0))
        multiplier = float(data.get('multiplier', 0))
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid data",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    if bet < CONFIG.PLINKO_MIN_BET or bet > 50000:
        return jsonify({
            "success": False,
            "message": f"Invalid bet (min: {CONFIG.PLINKO_MIN_BET}, max: 50000)",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    if float(user['balance']) < bet:
        return jsonify({
            "success": False,
            "message": "Insufficient balance",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    if multiplier not in [0.5, 3, 10]:
        return jsonify({
            "success": False,
            "message": "Invalid multiplier",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    # Check cooldown
    if not check_game_cooldown(user['id'], 'PLINKO'):
        return jsonify({
            "success": False,
            "message": "Please wait 1 second between games",
            "request_id": request.id,
            "api_version": request.api_version
        }), 429
    
    # Check daily limit - 2 plays per day for plinko
    if not can_play_today(user['id'], 'plinko'):
        return jsonify({
            "success": False,
            "message": f"Max {CONFIG.PLINKO_PLAYS_PER_DAY} plinko plays per day",
            "request_id": request.id,
            "api_version": request.api_version
        }), 403
    
    # Check duplicate claim
    if not check_duplicate_claim(user['id'], 'PLINKO', cooldown_seconds=1):
        return jsonify({
            "success": False,
            "message": "Please wait before playing again",
            "request_id": request.id,
            "api_version": request.api_version
        }), 429
    
    # Calculate win amount
    win_amount = bet * multiplier
    net_change = win_amount - bet
    
    try:
        # Update balance
        new_balance = update_user_balance(user['id'], net_change)
        if new_balance is None:
            return jsonify({
                "success": False,
                "message": "Failed to update balance",
                "request_id": request.id,
                "api_version": request.api_version
            }), 500
        
        conn = None
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            # Update game stats
            game_stats = json.loads(user.get('game_stats', '{}'))
            plinko_stats = game_stats.get('plinko', {'total_wins': 0, 'total_bets': 0, 'highest_win': 0})
            
            plinko_stats['total_bets'] = plinko_stats.get('total_bets', 0) + bet
            if win_amount > bet:
                plinko_stats['total_wins'] = plinko_stats.get('total_wins', 0) + 1
                if win_amount > plinko_stats.get('highest_win', 0):
                    plinko_stats['highest_win'] = win_amount
            
            game_stats['plinko'] = plinko_stats
            cursor.execute('UPDATE users SET game_stats = %s WHERE id = %s',
                          (json.dumps(game_stats), user['id']))
            
            # Update timestamps and record play
            update_last_game_timestamp(user['id'])
            record_game_play(user['id'], 'plinko')
            
            # Create transaction
            tx_type = 'PLINKO_WIN' if net_change > 0 else 'PLINKO_LOSS'
            tx_id = f"PLK-{int(time.time())}-{secrets.token_hex(4)}"
            cursor.execute('''
                INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (
                tx_id, user['id'], tx_type, net_change, 'COMPLETED',
                json.dumps({"game": "plinko", "bet": bet, "multiplier": multiplier, "win_amount": win_amount}),
                datetime.utcnow().isoformat()
            ))
            
            conn.commit()
            app.logger.info(f"[{request.id}] ✅ Plinko processed for {user['username']}: bet {bet}, multiplier {multiplier}, net: {net_change}")
            
            return jsonify({
                "success": True,
                "win_amount": win_amount,
                "net_change": net_change,
                "new_balance": new_balance,
                "multiplier": multiplier,
                "message": f"Plinko result: ×{multiplier} = {'+' if net_change > 0 else ''}₦{net_change:.2f}",
                "request_id": request.id,
                "api_version": request.api_version
            })
        except Exception as e:
            app.logger.error(f"[{request.id}] ❌ Plinko error: {e}")
            if conn:
                conn.rollback()
            return jsonify({
                "success": False,
                "message": f"Failed to process: {str(e)}",
                "request_id": request.id,
                "api_version": request.api_version
            }), 500
        finally:
            if conn:
                return_db_connection(conn)
    except Exception as e:
        app.logger.error(f"[{request.id}] ❌ Plinko balance update error: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to update balance: {str(e)}",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500

# ======================= SPIN GAME ENDPOINTS =======================
@app.route('/api/v1/spin/daily-status', methods=['GET'])
@api_version_required
@require_auth
@rate_limit_db_decorator(limit_per_minute=10)
def spin_daily_status_v1():
    """Check daily spin status - API v1"""
    user = get_current_user()
    
    # Check if user has played spin today
    if not can_play_today(user['id'], 'spin'):
        return jsonify({
            "success": False,
            "message": "Daily spin already used",
            "can_spin": False,
            "request_id": request.id,
            "api_version": request.api_version
        })
    
    return jsonify({
        "success": True,
        "can_spin": True,
        "message": "Spin available",
        "request_id": request.id,
        "api_version": request.api_version
    })

@app.route('/api/v1/spin/execute', methods=['POST'])
@api_version_required
@require_auth
@rate_limit_db_decorator(limit_per_minute=CONFIG.MAX_GAME_ATTEMPTS)
def spin_execute_v1():
    """Execute spin game - API v1"""
    user = get_current_user()
    
    # Check daily limit - 1 play per day for spin
    if not can_play_today(user['id'], 'spin'):
        return jsonify({
            "success": False,
            "message": "Daily spin already used",
            "request_id": request.id,
            "api_version": request.api_version
        }), 403
    
    # Check cooldown
    if not check_game_cooldown(user['id'], 'SPIN'):
        return jsonify({
            "success": False,
            "message": "Please wait 1 second between games",
            "request_id": request.id,
            "api_version": request.api_version
        }), 429
    
    # Check duplicate claim
    if not check_duplicate_claim(user['id'], 'SPIN', cooldown_seconds=1):
        return jsonify({
            "success": False,
            "message": "Please wait before spinning again",
            "request_id": request.id,
            "api_version": request.api_version
        }), 429
    
    # Generate random spin result (1-10)
    spin_result = random.randint(1, 10)
    
    # Calculate reward based on spin result
    rewards = {
        1: 1000, 2: 500, 3: 200, 4: 100, 5: 50,
        6: 100, 7: 200, 8: 500, 9: 1000, 10: 5000
    }
    reward = rewards.get(spin_result, 0)
    
    try:
        # Update balance
        new_balance = update_user_balance(user['id'], reward)
        if new_balance is None:
            return jsonify({
                "success": False,
                "message": "Failed to update balance",
                "request_id": request.id,
                "api_version": request.api_version
            }), 500
        
        conn = None
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            # Update timestamps and record play
            update_last_game_timestamp(user['id'])
            record_game_play(user['id'], 'spin')
            
            # Create transaction
            tx_id = f"SPIN-{int(time.time())}-{secrets.token_hex(4)}"
            cursor.execute('''
                INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (
                tx_id, user['id'], 'SPIN_REWARD', reward, 'COMPLETED',
                json.dumps({"game": "spin", "spin_result": spin_result}),
                datetime.utcnow().isoformat()
            ))
            
            conn.commit()
            app.logger.info(f"[{request.id}] ✅ Spin reward granted to {user['username']}: ₦{reward}")
            
            return jsonify({
                "success": True,
                "reward": reward,
                "new_balance": new_balance,
                "spin_result": spin_result,
                "transaction_id": tx_id,
                "message": f"Spin result: {spin_result}! Won ₦{reward}",
                "request_id": request.id,
                "api_version": request.api_version
            })
        except Exception as e:
            app.logger.error(f"[{request.id}] ❌ Spin error: {e}")
            if conn:
                conn.rollback()
            return jsonify({
                "success": False,
                "message": f"Failed to process spin: {str(e)}",
                "request_id": request.id,
                "api_version": request.api_version
            }), 500
        finally:
            if conn:
                return_db_connection(conn)
    except Exception as e:
        app.logger.error(f"[{request.id}] ❌ Spin balance update error: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to update balance: {str(e)}",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500

# ======================= USER PROFILE ENDPOINTS =======================
@app.route('/api/v1/user/profile', methods=['GET'])
@api_version_required
@require_auth
@rate_limit_db_decorator(limit_per_minute=30)
def get_user_profile_v1():
    """Get user profile - API v1"""
    user = get_current_user()
    
    # Grant achievement rewards
    try:
        grant_achievement_rewards(user['id'])
    except Exception as e:
        app.logger.error(f"[{request.id}] Achievement rewards error: {e}")
    
    # Get fresh user data
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = %s', (user['id'],))
        fresh_user = row_to_dict(cursor, cursor.fetchone())
        
        if not fresh_user:
            return jsonify({
                "success": False,
                "message": "User not found",
                "request_id": request.id,
                "api_version": request.api_version
            }), 404
        
        # Get referral count
        cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by = %s', (fresh_user['referral_code'],))
        referral_count = cursor.fetchone()[0]
        
        # Get today's game plays
        today = datetime.utcnow().date()
        cursor.execute('SELECT game_type, COUNT(*) FROM game_plays WHERE user_id = %s AND play_date = %s GROUP BY game_type',
                      (fresh_user['id'], today))
        game_plays_today = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Get total transactions
        cursor.execute('SELECT COUNT(*) FROM transactions WHERE user_id = %s', (fresh_user['id'],))
        total_transactions = cursor.fetchone()[0]
        
        profile_data = {
            "id": fresh_user['id'],
            "username": fresh_user['username'],
            "balance": float(fresh_user['balance']) if fresh_user['balance'] else 0.00,
            "referral_code": fresh_user.get('referral_code', ''),
            "is_admin": bool(fresh_user.get('is_admin', False)),
            "admin_password_changed": bool(fresh_user.get('admin_password_changed', False)),
            "contact": fresh_user.get('contact', ''),
            "profile_picture": fresh_user.get('profile_picture', ''),
            "ui_theme": fresh_user.get('ui_theme', 'light'),
            "points": int(fresh_user.get('points', 0)),
            "claimed_bonuses": int(fresh_user.get('claimed_bonuses', 0)),
            "withdrawal_restricted": bool(fresh_user.get('withdrawal_restricted', False)),
            "withdrawal_limit": float(fresh_user.get('withdrawal_limit', 0.00)),
            "two_fa_enabled": bool(fresh_user.get('two_fa_enabled', False)),
            "created_at": fresh_user.get('created_at', ''),
            "last_login": fresh_user.get('last_login', ''),
            "stats": {
                "referral_count": referral_count,
                "game_plays_today": game_plays_today,
                "total_transactions": total_transactions
            },
            "game_stats": json.loads(fresh_user.get('game_stats', '{}')) if fresh_user.get('game_stats') else {},
            "withdrawal_pin_set": bool(fresh_user.get('withdrawal_pin'))
        }
        
        return jsonify({
            "success": True,
            "profile": profile_data,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Profile error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load profile",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/user/set-profile-picture', methods=['POST'])
@api_version_required
@require_auth
@rate_limit_db_decorator(limit_per_minute=5)
def set_profile_picture_v1():
    """Set user profile picture - API v1"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    profile_picture = sanitize_input(data.get('profile_picture', ''))
    
    if not profile_picture:
        return jsonify({
            "success": False,
            "message": "Profile picture required",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET profile_picture = %s WHERE id = %s',
                      (profile_picture, user['id']))
        conn.commit()
        
        app.logger.info(f"[{request.id}] User {user['username']} updated profile picture")
        return jsonify({
            "success": True,
            "message": "Profile picture updated",
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Profile picture error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to update profile picture",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/user/set-theme', methods=['POST'])
@api_version_required
@require_auth
@rate_limit_db_decorator(limit_per_minute=5)
def set_theme_v1():
    """Set user UI theme - API v1"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    theme = sanitize_input(data.get('theme', 'light'))
    
    if theme not in ['light', 'dark']:
        return jsonify({
            "success": False,
            "message": "Invalid theme (light/dark only)",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET ui_theme = %s WHERE id = %s',
                      (theme, user['id']))
        conn.commit()
        
        app.logger.info(f"[{request.id}] User {user['username']} changed theme to {theme}")
        return jsonify({
            "success": True,
            "message": f"Theme changed to {theme}",
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Theme error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to change theme",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

# ======================= ACHIEVEMENTS ENDPOINTS =======================
@app.route('/api/v1/achievements', methods=['GET'])
@api_version_required
@require_auth
@rate_limit_db_decorator(limit_per_minute=10)
def get_achievements_v1():
    """Get user achievements - API v1"""
    user = get_current_user()
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get user stats
        cursor.execute('SELECT game_stats, referral_code, balance, points FROM users WHERE id = %s', (user['id'],))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({
                "success": False,
                "message": "User not found",
                "request_id": request.id,
                "api_version": request.api_version
            }), 404
        
        game_stats_str, referral_code, balance, current_points = row[0], row[1], row[2], row[3]
        
        # Parse game stats
        game_stats = json.loads(game_stats_str) if game_stats_str else {}
        
        # Get additional stats
        cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by = %s', (referral_code,))
        referrals = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM transactions WHERE user_id = %s', (user['id'],))
        total_tx = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE user_id = %s AND type = 'WITHDRAWAL'", (user['id'],))
        total_withdrawals = cursor.fetchone()[0]
        
        today = datetime.utcnow().date()
        cursor.execute('SELECT COUNT(*) FROM game_plays WHERE user_id = %s AND play_date = %s', (user['id'], today))
        games_today = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM game_plays WHERE user_id = %s', (user['id'],))
        total_games = cursor.fetchone()[0]
        
        snake_high = game_stats.get('snake', {}).get('high_score', 0)
        coin_streak = game_stats.get('coin_flip', {}).get('current_streak', 0)
        coin_total = game_stats.get('coin_flip', {}).get('wins', 0) + game_stats.get('coin_flip', {}).get('losses', 0)
        plinko_wins = game_stats.get('plinko', {}).get('total_wins', 0)
        
        # Define achievements
        achievements = [
            {
                "id": 1,
                "name": "First Game",
                "description": "Play your first game",
                "reward": 500,
                "points": 10,
                "unlocked": total_games >= 1,
                "progress": min(total_games, 1),
                "required": 1
            },
            {
                "id": 2,
                "name": "Game Enthusiast",
                "description": "Play 50 games",
                "reward": 5000,
                "points": 50,
                "unlocked": total_games >= 50,
                "progress": min(total_games, 50),
                "required": 50
            },
            {
                "id": 3,
                "name": "Game Master",
                "description": "Play 200 games",
                "reward": 15000,
                "points": 150,
                "unlocked": total_games >= 200,
                "progress": min(total_games, 200),
                "required": 200
            },
            {
                "id": 4,
                "name": "Snake Pro",
                "description": "Reach 1000 points in Snake",
                "reward": 7500,
                "points": 75,
                "unlocked": snake_high >= 1000,
                "progress": min(snake_high, 1000),
                "required": 1000
            },
            {
                "id": 5,
                "name": "Lucky Streak",
                "description": "Get 10 consecutive wins in Coin Flip",
                "reward": 10000,
                "points": 100,
                "unlocked": coin_streak >= 10,
                "progress": min(coin_streak, 10),
                "required": 10
            },
            {
                "id": 6,
                "name": "Coin Flipper",
                "description": "Play 100 Coin Flip games",
                "reward": 6000,
                "points": 60,
                "unlocked": coin_total >= 100,
                "progress": min(coin_total, 100),
                "required": 100
            },
            {
                "id": 7,
                "name": "Plinko Champion",
                "description": "Win 50 Plinko games",
                "reward": 8000,
                "points": 80,
                "unlocked": plinko_wins >= 50,
                "progress": min(plinko_wins, 50),
                "required": 50
            },
            {
                "id": 8,
                "name": "Small Savings",
                "description": "Reach ₦1,000 balance",
                "reward": 1000,
                "points": 15,
                "unlocked": balance >= 1000,
                "progress": min(balance, 1000),
                "required": 1000
            },
            {
                "id": 9,
                "name": "Big Saver",
                "description": "Reach ₦50,000 balance",
                "reward": 10000,
                "points": 100,
                "unlocked": balance >= 50000,
                "progress": min(balance, 50000),
                "required": 50000
            },
            {
                "id": 10,
                "name": "Wealthy",
                "description": "Reach ₦200,000 balance",
                "reward": 25000,
                "points": 200,
                "unlocked": balance >= 200000,
                "progress": min(balance, 200000),
                "required": 200000
            },
            {
                "id": 11,
                "name": "First Withdrawal",
                "description": "Make your first withdrawal",
                "reward": 5000,
                "points": 50,
                "unlocked": total_withdrawals >= 1,
                "progress": min(total_withdrawals, 1),
                "required": 1
            },
            {
                "id": 12,
                "name": "Daily Gamer",
                "description": "Play 5 games in one day",
                "reward": 3000,
                "points": 30,
                "unlocked": games_today >= 5,
                "progress": min(games_today, 5),
                "required": 5
            },
            {
                "id": 13,
                "name": "Hardcore Gamer",
                "description": "Play 20 games in one day",
                "reward": 8000,
                "points": 80,
                "unlocked": games_today >= 20,
                "progress": min(games_today, 20),
                "required": 20
            },
            {
                "id": 14,
                "name": "Referral Master",
                "description": "Refer 5 friends",
                "reward": 10000,
                "points": 100,
                "unlocked": referrals >= 5,
                "progress": min(referrals, 5),
                "required": 5
            },
            {
                "id": 15,
                "name": "Referral King",
                "description": "Refer 20 friends",
                "reward": 30000,
                "points": 300,
                "unlocked": referrals >= 20,
                "progress": min(referrals, 20),
                "required": 20
            },
            {
                "id": 16,
                "name": "Active User",
                "description": "Make 10 transactions",
                "reward": 4000,
                "points": 40,
                "unlocked": total_tx >= 10,
                "progress": min(total_tx, 10),
                "required": 10
            }
        ]
        
        # Get claimed achievements
        cursor.execute('SELECT claimed_achievements FROM users WHERE id = %s', (user['id'],))
        claimed_str = cursor.fetchone()[0]
        claimed_achievements = json.loads(claimed_str) if claimed_str else []
        
        # Calculate totals
        total_achievements = len(achievements)
        unlocked_achievements = len([a for a in achievements if a['unlocked']])
        total_rewards = sum(a['reward'] for a in achievements if a['unlocked'] and a['id'] not in claimed_achievements)
        total_points = sum(a['points'] for a in achievements if a['unlocked'] and a['id'] not in claimed_achievements)
        
        return jsonify({
            "success": True,
            "achievements": achievements,
            "stats": {
                "total": total_achievements,
                "unlocked": unlocked_achievements,
                "claimed": len(claimed_achievements),
                "pending_rewards": total_rewards,
                "pending_points": total_points,
                "current_points": current_points
            },
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Achievements error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load achievements",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/achievements/claim', methods=['POST'])
@api_version_required
@require_auth
@rate_limit_db_decorator(limit_per_minute=5)
def claim_achievements_v1():
    """Claim achievement rewards - API v1"""
    user = get_current_user()
    
    try:
        # Grant achievement rewards
        new_balance = grant_achievement_rewards(user['id'])
        
        if new_balance is None:
            return jsonify({
                "success": False,
                "message": "No new achievements to claim",
                "request_id": request.id,
                "api_version": request.api_version
            })
        
        # Get updated user data
        conn = None
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT points FROM users WHERE id = %s', (user['id'],))
            points = cursor.fetchone()[0]
            
            return jsonify({
                "success": True,
                "message": "Achievement rewards claimed successfully",
                "new_balance": new_balance,
                "points": points,
                "request_id": request.id,
                "api_version": request.api_version
            })
        except Exception as e:
            app.logger.error(f"[{request.id}] Claim achievements error: {e}")
            return jsonify({
                "success": False,
                "message": "Failed to claim rewards",
                "request_id": request.id,
                "api_version": request.api_version
            }), 500
        finally:
            if conn:
                return_db_connection(conn)
    except Exception as e:
        app.logger.error(f"[{request.id}] Achievement claim error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to process achievement claim",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500

# ======================= TIKTOK ENDPOINTS =======================
@app.route('/api/v1/games/tiktok/daily', methods=['GET'])
@api_version_required
@require_auth
@rate_limit_db_decorator(limit_per_minute=10)
def tiktok_daily_v1():
    """Get today's TikTok task - API v1"""
    user = get_current_user()
    
    # Check daily limit
    if not can_play_today(user['id'], 'tiktok'):
        return jsonify({
            "success": False,
            "message": "Daily TikTok task already completed",
            "request_id": request.id,
            "api_version": request.api_version
        }), 403
    
    today = datetime.utcnow().date().isoformat()
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get today's TikTok task
        cursor.execute('SELECT tiktok_link, reward_amount FROM tiktok_daily WHERE date = %s', (today,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({
                "success": False,
                "message": "No TikTok task available today",
                "request_id": request.id,
                "api_version": request.api_version
            }), 404
        
        tiktok_link, reward_amount = row[0], row[1]
        
        return jsonify({
            "success": True,
            "tiktok_link": tiktok_link,
            "reward_amount": float(reward_amount),
            "date": today,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] TikTok daily error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load TikTok task",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/games/tiktok/follow-daily', methods=['POST'])
@api_version_required
@require_auth
@rate_limit_db_decorator(limit_per_minute=CONFIG.MAX_GAME_ATTEMPTS)
def tiktok_follow_daily_v1():
    """Claim TikTok follow reward - API v1"""
    user = get_current_user()
    
    # Check daily limit
    if not can_play_today(user['id'], 'tiktok'):
        return jsonify({
            "success": False,
            "message": "Daily TikTok task already completed",
            "request_id": request.id,
            "api_version": request.api_version
        }), 403
    
    # Check cooldown
    if not check_game_cooldown(user['id'], 'TIKTOK'):
        return jsonify({
            "success": False,
            "message": "Please wait 1 second between claims",
            "request_id": request.id,
            "api_version": request.api_version
        }), 429
    
    today = datetime.utcnow().date().isoformat()
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get today's TikTok task and reward
        cursor.execute('SELECT tiktok_link, reward_amount FROM tiktok_daily WHERE date = %s', (today,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({
                "success": False,
                "message": "No TikTok task available today",
                "request_id": request.id,
                "api_version": request.api_version
            }), 404
        
        tiktok_link, reward_amount = row[0], float(row[1])
        
        # Update balance
        new_balance = update_user_balance(user['id'], reward_amount)
        if new_balance is None:
            return jsonify({
                "success": False,
                "message": "Failed to update balance",
                "request_id": request.id,
                "api_version": request.api_version
            }), 500
        
        # Record game play
        record_game_play(user['id'], 'tiktok')
        update_last_game_timestamp(user['id'])
        
        # Create transaction
        tx_id = f"TIK-{int(time.time())}-{secrets.token_hex(4)}"
        cursor.execute('''
            INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], 'TIKTOK_REWARD', reward_amount, 'COMPLETED',
            json.dumps({"game": "tiktok", "link": tiktok_link, "date": today}),
            datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        app.logger.info(f"[{request.id}] ✅ TikTok reward granted to {user['username']}: ₦{reward_amount}")
        
        return jsonify({
            "success": True,
            "reward": reward_amount,
            "new_balance": new_balance,
            "transaction_id": tx_id,
            "message": f"Success! Claimed ₦{reward_amount} for following TikTok",
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] ❌ TikTok follow error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": f"Failed to claim reward: {str(e)}",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

# ======================= ADMIN TIKTOK ENDPOINTS =======================
@app.route('/api/v1/admin/tiktok/set-daily', methods=['POST'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_set_tiktok_daily_v1():
    """Admin: Set daily TikTok task - API v1"""
    admin_user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    tiktok_link = sanitize_input(data.get('tiktok_link', ''))
    date_str = data.get('date', '')
    reward_amount = data.get('reward_amount', CONFIG.TIKTOK_REWARD)
    
    if not tiktok_link or not date_str:
        return jsonify({
            "success": False,
            "message": "TikTok link and date required",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    # Validate date
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        date_iso = date_obj.isoformat()
    except ValueError:
        return jsonify({
            "success": False,
            "message": "Invalid date format (YYYY-MM-DD)",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Insert or update TikTok task
        cursor.execute('''
            INSERT INTO tiktok_daily (date, tiktok_link, reward_amount)
            VALUES (%s, %s, %s)
            ON CONFLICT (date) 
            DO UPDATE SET tiktok_link = EXCLUDED.tiktok_link, reward_amount = EXCLUDED.reward_amount
        ''', (date_iso, tiktok_link, reward_amount))
        
        conn.commit()
        
        # Log admin action
        audit_logger.log_admin_action(
            admin_user['id'],
            "SET_TIKTOK_DAILY",
            {"date": date_iso, "link": tiktok_link, "reward": reward_amount},
            request.remote_addr
        )
        
        app.logger.info(f"[{request.id}] Admin {admin_user['username']} set TikTok task for {date_iso}")
        return jsonify({
            "success": True,
            "message": f"TikTok task set for {date_iso}",
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Set TikTok daily error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to set TikTok task",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/admin/tiktok/get-daily', methods=['GET'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_get_tiktok_daily_v1():
    """Admin: Get TikTok tasks - API v1"""
    date_str = request.args.get('date', '')
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        if date_str:
            # Get specific date
            cursor.execute('SELECT date, tiktok_link, reward_amount, created_at FROM tiktok_daily WHERE date = %s', (date_str,))
            row = cursor.fetchone()
            
            if not row:
                return jsonify({
                    "success": False,
                    "message": "No TikTok task found for this date",
                    "request_id": request.id,
                    "api_version": request.api_version
                }), 404
            
            task = {
                'date': row[0],
                'tiktok_link': row[1],
                'reward_amount': float(row[2]),
                'created_at': row[3]
            }
            
            return jsonify({
                "success": True,
                "task": task,
                "request_id": request.id,
                "api_version": request.api_version
            })
        else:
            # Get all tasks (last 30 days)
            cutoff_date = (datetime.utcnow().date() - timedelta(days=30)).isoformat()
            cursor.execute('''
                SELECT date, tiktok_link, reward_amount, created_at 
                FROM tiktok_daily 
                WHERE date >= %s 
                ORDER BY date DESC
            ''', (cutoff_date,))
            
            tasks = []
            for row in cursor.fetchall():
                tasks.append({
                    'date': row[0],
                    'tiktok_link': row[1],
                    'reward_amount': float(row[2]),
                    'created_at': row[3]
                })
            
            return jsonify({
                "success": True,
                "tasks": tasks,
                "count": len(tasks),
                "request_id": request.id,
                "api_version": request.api_version
            })
    except Exception as e:
        app.logger.error(f"[{request.id}] Get TikTok daily error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load TikTok tasks",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/admin/tiktok/history', methods=['GET'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_tiktok_history_v1():
    """Admin: Get TikTok task history - API v1"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT date, tiktok_link, reward_amount, created_at 
            FROM tiktok_daily 
            ORDER BY date DESC 
            LIMIT 100
        ''')
        
        tasks = []
        for row in cursor.fetchall():
            tasks.append({
                'date': row[0],
                'tiktok_link': row[1],
                'reward_amount': float(row[2]),
                'created_at': row[3]
            })
        
        return jsonify({
            "success": True,
            "tasks": tasks,
            "count": len(tasks),
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] TikTok history error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load TikTok history",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

# ======================= ADMIN WITHDRAWAL SETTINGS =======================
@app.route('/api/v1/admin/global-withdrawal-days', methods=['GET'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_get_global_withdrawal_days_v1():
    """Admin: Get global withdrawal days - API v1"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT global_withdrawal_days FROM admin_settings LIMIT 1')
        row = cursor.fetchone()
        
        if row and row[0]:
            days = json.loads(row[0])
        else:
            days = CONFIG.DEFAULT_WITHDRAWAL_DAYS
        
        return jsonify({
            "success": True,
            "withdrawal_days": days,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Get withdrawal days error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load withdrawal days",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/admin/global-withdrawal-days', methods=['POST'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_set_global_withdrawal_days_v1():
    """Admin: Set global withdrawal days - API v1"""
    admin_user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    withdrawal_days = data.get('withdrawal_days', [])
    
    # Validate withdrawal days
    if not isinstance(withdrawal_days, list):
        return jsonify({
            "success": False,
            "message": "Withdrawal days must be a list",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    # Validate each day is between 1-31
    for day in withdrawal_days:
        if not isinstance(day, int) or day < 1 or day > 31:
            return jsonify({
                "success": False,
                "message": f"Invalid withdrawal day: {day}. Must be between 1-31",
                "request_id": request.id,
                "api_version": request.api_version
            }), 400
    
    # Sort and remove duplicates
    withdrawal_days = sorted(list(set(withdrawal_days)))
    days_json = json.dumps(withdrawal_days)
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE admin_settings SET global_withdrawal_days = %s', (days_json,))
        conn.commit()
        
        # Log admin action
        audit_logger.log_admin_action(
            admin_user['id'],
            "SET_GLOBAL_WITHDRAWAL_DAYS",
            {"withdrawal_days": withdrawal_days},
            request.remote_addr
        )
        
        app.logger.info(f"[{request.id}] Admin {admin_user['username']} set global withdrawal days: {withdrawal_days}")
        return jsonify({
            "success": True,
            "message": f"Global withdrawal days updated: {withdrawal_days}",
            "withdrawal_days": withdrawal_days,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Set withdrawal days error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to update withdrawal days",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/admin/user/<int:user_id>/set-custom-days', methods=['POST'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_set_user_custom_days_v1(user_id):
    """Admin: Set custom withdrawal days for a user - API v1"""
    admin_user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    custom_days = data.get('custom_days', [])
    
    # Validate custom days
    if custom_days is None:
        # Clear custom days
        custom_days_json = None
    elif isinstance(custom_days, list):
        # Validate each day is between 1-31
        for day in custom_days:
            if not isinstance(day, int) or day < 1 or day > 31:
                return jsonify({
                    "success": False,
                    "message": f"Invalid withdrawal day: {day}. Must be between 1-31",
                    "request_id": request.id,
                    "api_version": request.api_version
                }), 400
        
        # Sort and remove duplicates
        custom_days = sorted(list(set(custom_days)))
        custom_days_json = json.dumps(custom_days)
    else:
        return jsonify({
            "success": False,
            "message": "Custom days must be a list or null",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute('SELECT username FROM users WHERE id = %s', (user_id,))
        user_row = cursor.fetchone()
        
        if not user_row:
            return jsonify({
                "success": False,
                "message": "User not found",
                "request_id": request.id,
                "api_version": request.api_version
            }), 404
        
        username = user_row[0]
        
        # Update user's custom withdrawal days
        cursor.execute('UPDATE users SET custom_withdrawal_days = %s WHERE id = %s',
                      (custom_days_json, user_id))
        conn.commit()
        
        # Log admin action
        audit_logger.log_admin_action(
            admin_user['id'],
            "SET_USER_CUSTOM_WITHDRAWAL_DAYS",
            {"user_id": user_id, "username": username, "custom_days": custom_days},
            request.remote_addr
        )
        
        app.logger.info(f"[{request.id}] Admin {admin_user['username']} set custom withdrawal days for user {username}: {custom_days}")
        
        if custom_days_json:
            return jsonify({
                "success": True,
                "message": f"Custom withdrawal days set for {username}: {custom_days}",
                "custom_days": custom_days,
                "request_id": request.id,
                "api_version": request.api_version
            })
        else:
            return jsonify({
                "success": True,
                "message": f"Custom withdrawal days cleared for {username}. Will use global settings.",
                "request_id": request.id,
                "api_version": request.api_version
            })
    except Exception as e:
        app.logger.error(f"[{request.id}] Set custom days error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to update custom days",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/admin/user/<int:user_id>/set-limit', methods=['POST'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_set_user_limit_v1(user_id):
    """Admin: Set withdrawal limit for a user - API v1"""
    admin_user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    try:
        withdrawal_limit = float(data.get('withdrawal_limit', 0))
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid withdrawal limit",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    if withdrawal_limit < 0:
        return jsonify({
            "success": False,
            "message": "Withdrawal limit cannot be negative",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute('SELECT username FROM users WHERE id = %s', (user_id,))
        user_row = cursor.fetchone()
        
        if not user_row:
            return jsonify({
                "success": False,
                "message": "User not found",
                "request_id": request.id,
                "api_version": request.api_version
            }), 404
        
        username = user_row[0]
        
        # Update user's withdrawal limit
        cursor.execute('UPDATE users SET withdrawal_limit = %s WHERE id = %s',
                      (withdrawal_limit, user_id))
        conn.commit()
        
        # Log admin action
        audit_logger.log_admin_action(
            admin_user['id'],
            "SET_USER_WITHDRAWAL_LIMIT",
            {"user_id": user_id, "username": username, "withdrawal_limit": withdrawal_limit},
            request.remote_addr
        )
        
        app.logger.info(f"[{request.id}] Admin {admin_user['username']} set withdrawal limit for user {username}: ₦{withdrawal_limit}")
        
        return jsonify({
            "success": True,
            "message": f"Withdrawal limit set to ₦{withdrawal_limit:,.2f} for {username}",
            "withdrawal_limit": withdrawal_limit,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Set limit error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to update withdrawal limit",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

# ======================= PAYMENT & WITHDRAWAL SYSTEM =======================
@app.route('/api/v1/banking/withdraw', methods=['POST'])
@api_version_required
@require_auth
@rate_limit_db_decorator(limit_per_minute=5)
def withdraw_v1():
    """Withdraw funds with cooldown and daily limits - API v1"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    # Input validation
    validation_rules = {
        'amount': {'required': True, 'type': 'float', 'min': CONFIG.MIN_WITHDRAWAL},
        'bank_code': {'required': True, 'type': 'string', 'min_length': 1},
        'account_number': {'required': True, 'type': 'string', 'min_length': 10, 'max_length': 15},
        'account_name': {'required': True, 'type': 'string', 'min_length': 1},
        'pin': {'required': True, 'type': 'string', 'min_length': 4, 'max_length': 6}
    }
    
    errors = validate_input(data, validation_rules)
    if errors:
        return jsonify({
            "success": False,
            "message": "Validation failed",
            "errors": errors,
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    # Extract and sanitize data
    try:
        amount = float(data.get('amount', 0))
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid amount",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    bank_code = sanitize_input(data.get('bank_code', ''))
    account_number = sanitize_input(data.get('account_number', ''))
    account_name = sanitize_input(data.get('account_name', ''))
    pin = data.get('pin', '')
    
    # Verify PIN
    withdrawal_pin = user.get('withdrawal_pin')
    if not withdrawal_pin or not check_password_hash(withdrawal_pin, pin):
        audit_logger.log_failed_login(
            user['username'],
            request.remote_addr,
            "Invalid withdrawal PIN"
        )
        app.logger.warning(f"[{request.id}] Invalid PIN attempt for withdrawal by user: {user['username']}")
        return jsonify({
            "success": False,
            "message": "Invalid PIN",
            "request_id": request.id,
            "api_version": request.api_version
        }), 403
    
    # Check if today is withdrawal day
    if not is_withdrawal_day(user['id']):
        global_days = get_global_withdrawal_days()
        return jsonify({
            "success": False,
            "message": f"Withdrawals only on days: {', '.join(map(str, sorted(global_days)))}",
            "request_id": request.id,
            "api_version": request.api_version
        }), 403
    
    # Check withdrawal cooldown and daily limit
    can_withdraw, message = check_withdrawal_cooldown(user['id'])
    if not can_withdraw:
        return jsonify({
            "success": False,
            "message": message,
            "request_id": request.id,
            "api_version": request.api_version
        }), 403
    
    # Check minimum withdrawal
    if amount < CONFIG.MIN_WITHDRAWAL:
        return jsonify({
            "success": False,
            "message": f"Min withdrawal: ₦{CONFIG.MIN_WITHDRAWAL:,}",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    # Check balance
    if float(user['balance']) < amount:
        return jsonify({
            "success": False,
            "message": "Insufficient balance",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    # Check withdrawal limit
    withdrawal_limit = float(user.get('withdrawal_limit', 0.00))
    if withdrawal_limit > 0 and amount > withdrawal_limit:
        return jsonify({
            "success": False,
            "message": f"Max limit: ₦{withdrawal_limit:,.2f}",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    # Validate bank details
    if not bank_code or not account_number or len(account_number) < 10 or not account_number.isdigit():
        return jsonify({
            "success": False,
            "message": "Invalid bank details",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    try:
        # Update balance
        new_balance = update_user_balance(user['id'], -amount)
        if new_balance is None:
            return jsonify({
                "success": False,
                "message": "Failed to update balance",
                "request_id": request.id,
                "api_version": request.api_version
            }), 500
        
        conn = None
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            # Update withdrawal tracking
            today = datetime.utcnow().date().isoformat()
            cursor.execute('''
                UPDATE users 
                SET withdrawal_last_date = %s, 
                    withdrawal_count_today = withdrawal_count_today + 1 
                WHERE id = %s
            ''', (today, user['id']))
            
            # Create withdrawal transaction
            tx_id = f"TX-{int(datetime.utcnow().timestamp())}"
            cursor.execute('''
                INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (
                tx_id, user['id'], 'WITHDRAWAL', amount, 'PENDING',
                json.dumps({
                    'bank_code': bank_code, 
                    'account_number': account_number, 
                    'account_name': account_name,
                    'cooldown_applied': True,
                    'withdrawal_day': datetime.utcnow().day
                }),
                datetime.utcnow().isoformat()
            ))
            
            conn.commit()
            
            # Log withdrawal request
            audit_logger.log_security_event(
                "WITHDRAWAL_REQUESTED",
                {
                    "user_id": user['id'],
                    "username": user['username'],
                    "amount": amount,
                    "bank_code": bank_code,
                    "account_number": account_number[-4:],  # Last 4 digits only for security
                    "transaction_id": tx_id
                },
                "MEDIUM"
            )
            
            app.logger.info(f"[{request.id}] ✅ Withdrawal requested by {user['username']}: {amount} to {bank_code}:{account_number}")
            
            return jsonify({
                "success": True,
                "message": "Withdrawal submitted successfully",
                "transaction_id": tx_id,
                "new_balance": new_balance,
                "cooldown_applied": True,
                "cooldown_hours": CONFIG.WITHDRAWAL_COOLDOWN_HOURS,
                "request_id": request.id,
                "api_version": request.api_version
            })
        except Exception as e:
            app.logger.error(f"[{request.id}] ❌ Withdrawal database error: {e}")
            if conn:
                conn.rollback()
            return jsonify({
                "success": False,
                "message": f"Failed to create transaction: {str(e)}",
                "request_id": request.id,
                "api_version": request.api_version
            }), 500
        finally:
            if conn:
                return_db_connection(conn)
    except Exception as e:
        app.logger.error(f"[{request.id}] ❌ Withdrawal balance update error: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to update balance: {str(e)}",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500

# ======================= ADMIN PAYMENT MANAGEMENT =======================
@app.route('/api/v1/admin/payments/pending', methods=['GET'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_get_pending_payments_v1():
    """Admin: Get pending payments - API v1"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.*, u.username, u.contact
            FROM transactions t
            JOIN users u ON t.user_id = u.id
            WHERE t.type = 'WITHDRAWAL' AND t.status = 'PENDING'
            ORDER BY t.timestamp DESC
        ''')
        
        payments = []
        for row in cursor.fetchall():
            payment = row_to_dict(cursor, row)
            payments.append(payment)
        
        return jsonify({
            "success": True,
            "payments": payments,
            "count": len(payments),
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Pending payments error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load pending payments",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/admin/payments/approve', methods=['POST'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_approve_payment_v1():
    """Admin: Approve payment - API v1"""
    admin_user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    transaction_id = data.get('transaction_id')
    notes = sanitize_input(data.get('notes', ''))
    
    if not transaction_id:
        return jsonify({
            "success": False,
            "message": "Transaction ID required",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get transaction details
        cursor.execute('''
            SELECT t.*, u.username 
            FROM transactions t
            JOIN users u ON t.user_id = u.id
            WHERE t.id = %s
        ''', (transaction_id,))
        
        row = cursor.fetchone()
        if not row:
            return jsonify({
                "success": False,
                "message": "Transaction not found",
                "request_id": request.id,
                "api_version": request.api_version
            }), 404
        
        transaction = row_to_dict(cursor, row)
        
        if transaction['status'] != 'PENDING':
            return jsonify({
                "success": False,
                "message": f"Transaction already {transaction['status']}",
                "request_id": request.id,
                "api_version": request.api_version
            }), 400
        
        # Update transaction status
        cursor.execute('UPDATE transactions SET status = %s WHERE id = %s',
                      ('COMPLETED', transaction_id))
        
        # Log payment approval
        audit_logger.log_payment_approval(
            admin_user['id'],
            transaction_id,
            "APPROVE",
            {
                "user_id": transaction['user_id'],
                "username": transaction['username'],
                "amount": transaction['amount'],
                "notes": notes,
                "admin_id": admin_user['id'],
                "admin_username": admin_user['username']
            }
        )
        
        conn.commit()
        
        # Send notification to user (could be email, SMS, etc.)
        app.logger.info(f"[{request.id}] Admin {admin_user['username']} approved payment {transaction_id} for user {transaction['username']}")
        
        return jsonify({
            "success": True,
            "message": "Payment approved successfully",
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Approve payment error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to approve payment",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/admin/payments/reject', methods=['POST'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_reject_payment_v1():
    """Admin: Reject payment and refund - API v1"""
    admin_user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    transaction_id = data.get('transaction_id')
    reason = sanitize_input(data.get('reason', ''))
    
    if not transaction_id:
        return jsonify({
            "success": False,
            "message": "Transaction ID required",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get transaction details
        cursor.execute('''
            SELECT t.*, u.username 
            FROM transactions t
            JOIN users u ON t.user_id = u.id
            WHERE t.id = %s
        ''', (transaction_id,))
        
        row = cursor.fetchone()
        if not row:
            return jsonify({
                "success": False,
                "message": "Transaction not found",
                "request_id": request.id,
                "api_version": request.api_version
            }), 404
        
        transaction = row_to_dict(cursor, row)
        
        if transaction['status'] != 'PENDING':
            return jsonify({
                "success": False,
                "message": f"Transaction already {transaction['status']}",
                "request_id": request.id,
                "api_version": request.api_version
            }), 400
        
        # Refund balance
        amount = float(transaction['amount'])
        update_user_balance(transaction['user_id'], amount)
        
        # Update transaction status
        cursor.execute('UPDATE transactions SET status = %s WHERE id = %s',
                      ('REJECTED', transaction_id))
        
        # Log payment rejection
        audit_logger.log_payment_approval(
            admin_user['id'],
            transaction_id,
            "REJECT",
            {
                "user_id": transaction['user_id'],
                "username": transaction['username'],
                "amount": amount,
                "reason": reason,
                "admin_id": admin_user['id'],
                "admin_username": admin_user['username']
            }
        )
        
        conn.commit()
        
        app.logger.info(f"[{request.id}] Admin {admin_user['username']} rejected payment {transaction_id} for user {transaction['username']}, reason: {reason}")
        
        return jsonify({
            "success": True,
            "message": "Payment rejected and amount refunded",
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Reject payment error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to reject payment",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/admin/payments/history', methods=['GET'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_payment_history_v1():
    """Admin: Get payment history - API v1"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get filters
        status = request.args.get('status', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        
        query = '''
            SELECT t.*, u.username 
            FROM transactions t
            JOIN users u ON t.user_id = u.id
            WHERE t.type = 'WITHDRAWAL'
        '''
        params = []
        
        if status:
            query += ' AND t.status = %s'
            params.append(status)
        
        if start_date:
            query += ' AND t.timestamp >= %s'
            params.append(start_date)
        
        if end_date:
            query += ' AND t.timestamp <= %s'
            params.append(end_date)
        
        query += ' ORDER BY t.timestamp DESC LIMIT 100'
        
        cursor.execute(query, params)
        
        payments = []
        for row in cursor.fetchall():
            payment = row_to_dict(cursor, row)
            payments.append(payment)
        
        # Get statistics
        cursor.execute('''
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'PENDING' THEN 1 END) as pending,
                COUNT(CASE WHEN status = 'COMPLETED' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'REJECTED' THEN 1 END) as rejected,
                SUM(CASE WHEN status = 'COMPLETED' THEN amount ELSE 0 END) as total_completed_amount
            FROM transactions 
            WHERE type = 'WITHDRAWAL'
        ''')
        
        stats = cursor.fetchone()
        statistics = {
            'total': stats[0] or 0,
            'pending': stats[1] or 0,
            'completed': stats[2] or 0,
            'rejected': stats[3] or 0,
            'total_completed_amount': float(stats[4]) if stats[4] else 0.0
        }
        
        return jsonify({
            "success": True,
            "payments": payments,
            "statistics": statistics,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Payment history error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load payment history",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/admin/withdrawal-status-report', methods=['GET'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_withdrawal_status_report_v1():
    """Admin: Get withdrawal status report - API v1"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get summary by status
        cursor.execute('''
            SELECT 
                status,
                COUNT(*) as count,
                SUM(amount) as total_amount
            FROM transactions 
            WHERE type = 'WITHDRAWAL'
            GROUP BY status
            ORDER BY status
        ''')
        
        status_summary = []
        for row in cursor.fetchall():
            status_summary.append({
                'status': row[0],
                'count': row[1],
                'total_amount': float(row[2]) if row[2] else 0.0
            })
        
        # Get today's withdrawals
        today = datetime.utcnow().date().isoformat()
        cursor.execute('''
            SELECT 
                COUNT(*) as count,
                SUM(amount) as total_amount
            FROM transactions 
            WHERE type = 'WITHDRAWAL' 
            AND DATE(timestamp) = %s
        ''', (today,))
        
        today_row = cursor.fetchone()
        today_summary = {
            'count': today_row[0] or 0,
            'total_amount': float(today_row[1]) if today_row[1] else 0.0
        }
        
        # Get pending withdrawals count
        cursor.execute('''
            SELECT COUNT(*) 
            FROM transactions 
            WHERE type = 'WITHDRAWAL' AND status = 'PENDING'
        ''')
        pending_count = cursor.fetchone()[0] or 0
        
        return jsonify({
            "success": True,
            "status_summary": status_summary,
            "today_summary": today_summary,
            "pending_count": pending_count,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Withdrawal status report error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load withdrawal status report",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

# ======================= ADMIN USER MANAGEMENT =======================
@app.route('/api/v1/admin/user/<int:user_id>/toggle-admin', methods=['POST'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_toggle_admin_v1(user_id):
    """Admin: Toggle admin status for a user - API v1"""
    admin_user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    make_admin = data.get('make_admin', False)
    
    # Prevent self-demotion
    if user_id == admin_user['id']:
        return jsonify({
            "success": False,
            "message": "Cannot modify your own admin status",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute('SELECT username FROM users WHERE id = %s', (user_id,))
        user_row = cursor.fetchone()
        
        if not user_row:
            return jsonify({
                "success": False,
                "message": "User not found",
                "request_id": request.id,
                "api_version": request.api_version
            }), 404
        
        username = user_row[0]
        
        # Update admin status
        cursor.execute('UPDATE users SET is_admin = %s WHERE id = %s',
                      (make_admin, user_id))
        conn.commit()
        
        # Log admin action
        action = "GRANT_ADMIN" if make_admin else "REVOKE_ADMIN"
        audit_logger.log_admin_action(
            admin_user['id'],
            action,
            {"target_user_id": user_id, "target_username": username, "new_status": make_admin},
            request.remote_addr
        )
        
        status_text = "granted admin privileges to" if make_admin else "revoked admin privileges from"
        app.logger.info(f"[{request.id}] Admin {admin_user['username']} {status_text} {username}")
        
        return jsonify({
            "success": True,
            "message": f"Admin privileges {'granted to' if make_admin else 'revoked from'} {username}",
            "is_admin": make_admin,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Toggle admin error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to update admin status",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/admin/user/<int:user_id>', methods=['DELETE'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=5)
def admin_delete_user_v1(user_id):
    """Admin: Delete a user - API v1"""
    admin_user = get_current_user()
    
    # Prevent self-deletion
    if user_id == admin_user['id']:
        return jsonify({
            "success": False,
            "message": "Cannot delete your own account",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get user info before deletion
        cursor.execute('SELECT username FROM users WHERE id = %s', (user_id,))
        user_row = cursor.fetchone()
        
        if not user_row:
            return jsonify({
                "success": False,
                "message": "User not found",
                "request_id": request.id,
                "api_version": request.api_version
            }), 404
        
        username = user_row[0]
        
        # Delete user (cascade will handle related records)
        cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
        conn.commit()
        
        # Log admin action
        audit_logger.log_admin_action(
            admin_user['id'],
            "DELETE_USER",
            {"target_user_id": user_id, "target_username": username},
            request.remote_addr
        )
        
        app.logger.warning(f"[{request.id}] Admin {admin_user['username']} deleted user {username} (ID: {user_id})")
        
        return jsonify({
            "success": True,
            "message": f"User {username} deleted successfully",
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Delete user error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to delete user",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

# ======================= ADMIN COUPON MANAGEMENT =======================
@app.route('/api/v1/admin/coupons', methods=['GET'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_get_coupons_v1():
    """Admin: Get all coupons - API v1"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT code, status FROM coupons ORDER BY code')
        
        coupons = []
        for row in cursor.fetchall():
            coupons.append({
                'code': row[0],
                'status': row[1]
            })
        
        # Get counts
        cursor.execute('SELECT COUNT(*) as total, COUNT(CASE WHEN status = \'AVAILABLE\' THEN 1 END) as available FROM coupons')
        count_row = cursor.fetchone()
        
        return jsonify({
            "success": True,
            "coupons": coupons,
            "counts": {
                "total": count_row[0] or 0,
                "available": count_row[1] or 0,
                "used": (count_row[0] or 0) - (count_row[1] or 0)
            },
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Get coupons error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load coupons",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/admin/coupons', methods=['POST'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_create_coupon_v1():
    """Admin: Create new coupon - API v1"""
    admin_user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    coupon_code = sanitize_input(data.get('code', '')).upper()
    
    if not coupon_code:
        return jsonify({
            "success": False,
            "message": "Coupon code required",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    if len(coupon_code) < 4:
        return jsonify({
            "success": False,
            "message": "Coupon code must be at least 4 characters",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if coupon already exists
        cursor.execute('SELECT code FROM coupons WHERE code = %s', (coupon_code,))
        if cursor.fetchone():
            return jsonify({
                "success": False,
                "message": "Coupon code already exists",
                "request_id": request.id,
                "api_version": request.api_version
            }), 409
        
        # Create coupon
        cursor.execute('INSERT INTO coupons (code, status) VALUES (%s, %s)',
                      (coupon_code, 'AVAILABLE'))
        conn.commit()
        
        # Log admin action
        audit_logger.log_admin_action(
            admin_user['id'],
            "CREATE_COUPON",
            {"coupon_code": coupon_code},
            request.remote_addr
        )
        
        app.logger.info(f"[{request.id}] Admin {admin_user['username']} created coupon: {coupon_code}")
        
        return jsonify({
            "success": True,
            "message": f"Coupon {coupon_code} created successfully",
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Create coupon error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to create coupon",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/admin/coupons/bulk', methods=['POST'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_create_bulk_coupons_v1():
    """Admin: Create bulk coupons - API v1"""
    admin_user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    count = data.get('count', 1)
    prefix = sanitize_input(data.get('prefix', 'FLEX')).upper()
    length = data.get('length', 8)
    
    if count < 1 or count > 100:
        return jsonify({
            "success": False,
            "message": "Count must be between 1 and 100",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    if length < 4 or length > 12:
        return jsonify({
            "success": False,
            "message": "Length must be between 4 and 12",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        created_coupons = []
        failed_coupons = []
        
        for i in range(count):
            # Generate random suffix
            suffix = secrets.token_hex((length - len(prefix)) // 2 + 1)[:length - len(prefix)].upper()
            coupon_code = f"{prefix}{suffix}"
            
            try:
                # Check if coupon already exists
                cursor.execute('SELECT code FROM coupons WHERE code = %s', (coupon_code,))
                if not cursor.fetchone():
                    cursor.execute('INSERT INTO coupons (code, status) VALUES (%s, %s)',
                                  (coupon_code, 'AVAILABLE'))
                    created_coupons.append(coupon_code)
                else:
                    failed_coupons.append(coupon_code)
            except:
                failed_coupons.append(coupon_code)
        
        conn.commit()
        
        # Log admin action
        audit_logger.log_admin_action(
            admin_user['id'],
            "CREATE_BULK_COUPONS",
            {"count": count, "created": len(created_coupons), "failed": len(failed_coupons)},
            request.remote_addr
        )
        
        app.logger.info(f"[{request.id}] Admin {admin_user['username']} created {len(created_coupons)} coupons")
        
        return jsonify({
            "success": True,
            "message": f"Created {len(created_coupons)} coupons, {len(failed_coupons)} failed",
            "created": created_coupons,
            "failed": failed_coupons,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Create bulk coupons error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to create bulk coupons",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/admin/coupons/<coupon_code>', methods=['DELETE'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_delete_coupon_v1(coupon_code):
    """Admin: Delete a coupon - API v1"""
    admin_user = get_current_user()
    coupon_code = sanitize_input(coupon_code).upper()
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if coupon exists
        cursor.execute('SELECT code FROM coupons WHERE code = %s', (coupon_code,))
        if not cursor.fetchone():
            return jsonify({
                "success": False,
                "message": "Coupon not found",
                "request_id": request.id,
                "api_version": request.api_version
            }), 404
        
        # Delete coupon
        cursor.execute('DELETE FROM coupons WHERE code = %s', (coupon_code,))
        conn.commit()
        
        # Log admin action
        audit_logger.log_admin_action(
            admin_user['id'],
            "DELETE_COUPON",
            {"coupon_code": coupon_code},
            request.remote_addr
        )
        
        app.logger.info(f"[{request.id}] Admin {admin_user['username']} deleted coupon: {coupon_code}")
        
        return jsonify({
            "success": True,
            "message": f"Coupon {coupon_code} deleted successfully",
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Delete coupon error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to delete coupon",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

# ======================= ADMIN WHATSAPP NUMBERS =======================
@app.route('/api/v1/admin/whatsapp-numbers', methods=['GET'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_get_whatsapp_numbers_v1():
    """Admin: Get WhatsApp numbers - API v1"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT id, number, label, is_active, created_at FROM whatsapp_numbers ORDER BY is_active DESC, created_at DESC')
        
        numbers = []
        for row in cursor.fetchall():
            numbers.append({
                'id': row[0],
                'number': row[1],
                'label': row[2],
                'is_active': row[3],
                'created_at': row[4]
            })
        
        return jsonify({
            "success": True,
            "numbers": numbers,
            "count": len(numbers),
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Get WhatsApp numbers error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load WhatsApp numbers",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/admin/whatsapp-numbers', methods=['POST'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_add_whatsapp_number_v1():
    """Admin: Add WhatsApp number - API v1"""
    admin_user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    number = sanitize_input(data.get('number', ''))
    label = sanitize_input(data.get('label', ''))
    
    if not number:
        return jsonify({
            "success": False,
            "message": "WhatsApp number required",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    # Basic phone number validation
    if not re.match(r'^\+?[\d\s\-\(\)]+$', number):
        return jsonify({
            "success": False,
            "message": "Invalid phone number format",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if number already exists
        cursor.execute('SELECT id FROM whatsapp_numbers WHERE number = %s', (number,))
        if cursor.fetchone():
            return jsonify({
                "success": False,
                "message": "WhatsApp number already exists",
                "request_id": request.id,
                "api_version": request.api_version
            }), 409
        
        # Add WhatsApp number
        cursor.execute('INSERT INTO whatsapp_numbers (number, label, is_active, created_at) VALUES (%s, %s, %s, %s)',
                      (number, label or 'Seller', True, datetime.utcnow().isoformat()))
        conn.commit()
        
        # Log admin action
        audit_logger.log_admin_action(
            admin_user['id'],
            "ADD_WHATSAPP_NUMBER",
            {"number": number, "label": label},
            request.remote_addr
        )
        
        app.logger.info(f"[{request.id}] Admin {admin_user['username']} added WhatsApp number: {number}")
        
        return jsonify({
            "success": True,
            "message": f"WhatsApp number {number} added successfully",
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Add WhatsApp number error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to add WhatsApp number",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/admin/whatsapp-numbers/<int:number_id>', methods=['PUT'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_update_whatsapp_number_v1(number_id):
    """Admin: Update WhatsApp number - API v1"""
    admin_user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    number = sanitize_input(data.get('number', ''))
    label = sanitize_input(data.get('label', ''))
    is_active = data.get('is_active', True)
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if number exists
        cursor.execute('SELECT id, number FROM whatsapp_numbers WHERE id = %s', (number_id,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({
                "success": False,
                "message": "WhatsApp number not found",
                "request_id": request.id,
                "api_version": request.api_version
            }), 404
        
        old_number = row[1]
        
        # Check if new number already exists (if changing number)
        if number and number != old_number:
            cursor.execute('SELECT id FROM whatsapp_numbers WHERE number = %s AND id != %s', (number, number_id))
            if cursor.fetchone():
                return jsonify({
                    "success": False,
                    "message": "WhatsApp number already exists",
                    "request_id": request.id,
                    "api_version": request.api_version
                }), 409
        
        # Update WhatsApp number
        update_fields = []
        params = []
        
        if number:
            update_fields.append("number = %s")
            params.append(number)
        
        if label is not None:
            update_fields.append("label = %s")
            params.append(label)
        
        if is_active is not None:
            update_fields.append("is_active = %s")
            params.append(is_active)
        
        if not update_fields:
            return jsonify({
                "success": False,
                "message": "No fields to update",
                "request_id": request.id,
                "api_version": request.api_version
            }), 400
        
        params.append(number_id)
        query = f"UPDATE whatsapp_numbers SET {', '.join(update_fields)} WHERE id = %s"
        cursor.execute(query, params)
        conn.commit()
        
        # Log admin action
        audit_logger.log_admin_action(
            admin_user['id'],
            "UPDATE_WHATSAPP_NUMBER",
            {"number_id": number_id, "old_number": old_number, "new_number": number, "label": label, "is_active": is_active},
            request.remote_addr
        )
        
        app.logger.info(f"[{request.id}] Admin {admin_user['username']} updated WhatsApp number {old_number}")
        
        return jsonify({
            "success": True,
            "message": f"WhatsApp number updated successfully",
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Update WhatsApp number error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to update WhatsApp number",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/admin/whatsapp-numbers/<int:number_id>', methods=['DELETE'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_delete_whatsapp_number_v1(number_id):
    """Admin: Delete WhatsApp number - API v1"""
    admin_user = get_current_user()
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if number exists
        cursor.execute('SELECT number FROM whatsapp_numbers WHERE id = %s', (number_id,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({
                "success": False,
                "message": "WhatsApp number not found",
                "request_id": request.id,
                "api_version": request.api_version
            }), 404
        
        number = row[0]
        
        # Delete WhatsApp number
        cursor.execute('DELETE FROM whatsapp_numbers WHERE id = %s', (number_id,))
        conn.commit()
        
        # Log admin action
        audit_logger.log_admin_action(
            admin_user['id'],
            "DELETE_WHATSAPP_NUMBER",
            {"number_id": number_id, "number": number},
            request.remote_addr
        )
        
        app.logger.info(f"[{request.id}] Admin {admin_user['username']} deleted WhatsApp number: {number}")
        
        return jsonify({
            "success": True,
            "message": f"WhatsApp number {number} deleted successfully",
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Delete WhatsApp number error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to delete WhatsApp number",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

# ======================= REFERRAL ENDPOINTS =======================
@app.route('/api/v1/referral/claim', methods=['POST'])
@api_version_required
@require_auth
@rate_limit_db_decorator(limit_per_minute=5)
def claim_referral_bonus_v1():
    """Claim referral bonus - API v1"""
    user = get_current_user()
    
    # Check if user has already claimed referral bonuses
    if user.get('claimed_bonuses', 0) >= 5:
        return jsonify({
            "success": False,
            "message": "Maximum referral bonuses already claimed",
            "request_id": request.id,
            "api_version": request.api_version
        }), 403
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Count referrals
        cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by = %s', (user['referral_code'],))
        referral_count = cursor.fetchone()[0]
        
        # Calculate how many bonuses can be claimed
        total_bonuses_possible = min(referral_count // 5, 5)  # Max 5 bonuses
        already_claimed = user.get('claimed_bonuses', 0)
        bonuses_to_claim = total_bonuses_possible - already_claimed
        
        if bonuses_to_claim <= 0:
            return jsonify({
                "success": False,
                "message": "No referral bonuses available to claim",
                "request_id": request.id,
                "api_version": request.api_version
            }), 403
        
        # Calculate total bonus
        total_bonus = bonuses_to_claim * CONFIG.REFERRAL_BONUS
        
        # Update balance
        new_balance = update_user_balance(user['id'], total_bonus)
        if new_balance is None:
            return jsonify({
                "success": False,
                "message": "Failed to update balance",
                "request_id": request.id,
                "api_version": request.api_version
            }), 500
        
        # Update claimed bonuses count
        new_claimed_bonuses = already_claimed + bonuses_to_claim
        cursor.execute('UPDATE users SET claimed_bonuses = %s WHERE id = %s',
                      (new_claimed_bonuses, user['id']))
        
        # Create transaction
        tx_id = f"REF-{int(time.time())}-{secrets.token_hex(4)}"
        cursor.execute('''
            INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user['id'], 'REFERRAL_BONUS', total_bonus, 'COMPLETED',
            json.dumps({"referral_count": referral_count, "bonuses_claimed": bonuses_to_claim, "total_bonuses_claimed": new_claimed_bonuses}),
            datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        
        app.logger.info(f"[{request.id}] ✅ Referral bonus claimed by {user['username']}: ₦{total_bonus} for {referral_count} referrals")
        
        return jsonify({
            "success": True,
            "bonus": total_bonus,
            "new_balance": new_balance,
            "referral_count": referral_count,
            "bonuses_claimed": bonuses_to_claim,
            "total_bonuses_claimed": new_claimed_bonuses,
            "transaction_id": tx_id,
            "message": f"Success! Claimed ₦{total_bonus} referral bonus for {referral_count} referrals",
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] ❌ Referral claim error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": f"Failed to claim referral bonus: {str(e)}",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

# ======================= BANKING ENDPOINTS =======================
@app.route('/api/v1/banking/banks', methods=['GET'])
@api_version_required
@rate_limit_db_decorator(limit_per_minute=30)
def get_banks_v1():
    """Get banks list - API v1"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT code, name FROM banks WHERE is_active = TRUE ORDER BY name')
        
        banks = []
        for row in cursor.fetchall():
            banks.append({"code": row[0], "name": row[1]})
        
        return jsonify({
            "success": True,
            "banks": banks,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Banks error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load banks",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/whatsapp/numbers', methods=['GET'])
@api_version_required
@rate_limit_db_decorator(limit_per_minute=30)
def get_whatsapp_numbers_v1():
    """Get WhatsApp numbers for contact - API v1"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT number, label FROM whatsapp_numbers WHERE is_active = TRUE ORDER BY created_at')
        
        numbers = []
        for row in cursor.fetchall():
            numbers.append({
                "number": row[0],
                "label": row[1]
            })
        
        return jsonify({
            "success": True,
            "numbers": numbers,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] WhatsApp numbers error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load WhatsApp numbers",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

# ======================= ADMIN USER MANAGEMENT CONTINUED =======================
@app.route('/api/v1/admin/users', methods=['GET'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_get_users_v1():
    """Admin: Get all users - API v1"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        offset = (page - 1) * limit
        
        # Get search parameters
        search = request.args.get('search', '')
        is_admin = request.args.get('is_admin', '')
        
        # Build query
        query = 'SELECT id, username, balance, referral_code, is_admin, created_at, last_login, withdrawal_restricted FROM users WHERE 1=1'
        params = []
        
        if search:
            query += ' AND (username ILIKE %s OR referral_code ILIKE %s)'
            params.extend([f'%{search}%', f'%{search}%'])
        
        if is_admin == 'true':
            query += ' AND is_admin = TRUE'
        elif is_admin == 'false':
            query += ' AND is_admin = FALSE'
        
        query += ' ORDER BY created_at DESC LIMIT %s OFFSET %s'
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        
        users = []
        for row in cursor.fetchall():
            users.append({
                'id': row[0],
                'username': row[1],
                'balance': float(row[2]) if row[2] else 0.00,
                'referral_code': row[3],
                'is_admin': row[4],
                'created_at': row[5],
                'last_login': row[6],
                'withdrawal_restricted': row[7]
            })
        
        # Get total count
        count_query = 'SELECT COUNT(*) FROM users WHERE 1=1'
        count_params = []
        
        if search:
            count_query += ' AND (username ILIKE %s OR referral_code ILIKE %s)'
            count_params.extend([f'%{search}%', f'%{search}%'])
        
        if is_admin == 'true':
            count_query += ' AND is_admin = TRUE'
        elif is_admin == 'false':
            count_query += ' AND is_admin = FALSE'
        
        cursor.execute(count_query, count_params)
        total = cursor.fetchone()[0]
        
        return jsonify({
            "success": True,
            "users": users,
            "total": total,
            "page": page,
            "limit": limit,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Get users error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load users",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/admin/user/<int:user_id>', methods=['GET'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_get_user_v1(user_id):
    """Admin: Get user details - API v1"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, balance, referral_code, referred_by, is_admin, 
                   created_at, last_login, contact, profile_picture, ui_theme,
                   withdrawal_restricted, custom_withdrawal_days, withdrawal_limit,
                   points, claimed_bonuses, game_stats, two_fa_enabled,
                   last_login_ip, last_login_time
            FROM users 
            WHERE id = %s
        ''', (user_id,))
        
        row = cursor.fetchone()
        if not row:
            return jsonify({
                "success": False,
                "message": "User not found",
                "request_id": request.id,
                "api_version": request.api_version
            }), 404
        
        user = {
            'id': row[0],
            'username': row[1],
            'balance': float(row[2]) if row[2] else 0.00,
            'referral_code': row[3],
            'referred_by': row[4],
            'is_admin': row[5],
            'created_at': row[6],
            'last_login': row[7],
            'contact': row[8],
            'profile_picture': row[9],
            'ui_theme': row[10],
            'withdrawal_restricted': row[11],
            'custom_withdrawal_days': json.loads(row[12]) if row[12] else None,
            'withdrawal_limit': float(row[13]) if row[13] else 0.00,
            'points': row[14],
            'claimed_bonuses': row[15],
            'game_stats': json.loads(row[16]) if row[16] else {},
            'two_fa_enabled': row[17],
            'last_login_ip': row[18],
            'last_login_time': row[19]
        }
        
        # Get referral count
        cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by = %s', (user['referral_code'],))
        user['referral_count'] = cursor.fetchone()[0]
        
        # Get transaction count
        cursor.execute('SELECT COUNT(*) FROM transactions WHERE user_id = %s', (user_id,))
        user['transaction_count'] = cursor.fetchone()[0]
        
        # Get total withdrawn
        cursor.execute('SELECT SUM(amount) FROM transactions WHERE user_id = %s AND type = \'WITHDRAWAL\' AND status = \'COMPLETED\'', (user_id,))
        total_withdrawn = cursor.fetchone()[0]
        user['total_withdrawn'] = float(total_withdrawn) if total_withdrawn else 0.00
        
        return jsonify({
            "success": True,
            "user": user,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Get user details error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load user details",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/admin/user/<int:user_id>/toggle-restrict', methods=['POST'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_toggle_user_restrict_v1(user_id):
    """Admin: Toggle user withdrawal restriction - API v1"""
    admin_user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    restrict = data.get('restrict', False)
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute('SELECT username FROM users WHERE id = %s', (user_id,))
        user_row = cursor.fetchone()
        
        if not user_row:
            return jsonify({
                "success": False,
                "message": "User not found",
                "request_id": request.id,
                "api_version": request.api_version
            }), 404
        
        username = user_row[0]
        
        # Update withdrawal restriction
        cursor.execute('UPDATE users SET withdrawal_restricted = %s WHERE id = %s',
                      (restrict, user_id))
        conn.commit()
        
        # Log admin action
        action = "RESTRICT_USER" if restrict else "UNRESTRICT_USER"
        audit_logger.log_admin_action(
            admin_user['id'],
            action,
            {"target_user_id": user_id, "target_username": username, "restricted": restrict},
            request.remote_addr
        )
        
        status_text = "restricted" if restrict else "unrestricted"
        app.logger.info(f"[{request.id}] Admin {admin_user['username']} {status_text} user {username}")
        
        return jsonify({
            "success": True,
            "message": f"User {username} {status_text}",
            "restricted": restrict,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Toggle restrict error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to update user restriction",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/admin/user/<int:user_id>/adjust-balance', methods=['POST'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_adjust_user_balance_v1(user_id):
    """Admin: Adjust user balance - API v1"""
    admin_user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    amount = data.get('amount', 0)
    reason = sanitize_input(data.get('reason', ''))
    is_credit = data.get('is_credit', True)
    
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid amount",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    if amount <= 0:
        return jsonify({
            "success": False,
            "message": "Amount must be positive",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    if not reason:
        return jsonify({
            "success": False,
            "message": "Reason required for balance adjustment",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute('SELECT username, balance FROM users WHERE id = %s', (user_id,))
        user_row = cursor.fetchone()
        
        if not user_row:
            return jsonify({
                "success": False,
                "message": "User not found",
                "request_id": request.id,
                "api_version": request.api_version
            }), 404
        
        username, current_balance = user_row[0], float(user_row[1])
        
        # Calculate adjustment amount (negative for debit)
        adjustment = amount if is_credit else -amount
        
        # Check if debit would result in negative balance
        if not is_credit and (current_balance - amount) < 0:
            return jsonify({
                "success": False,
                "message": f"Insufficient balance. Current: ₦{current_balance:,.2f}, Debit: ₦{amount:,.2f}",
                "request_id": request.id,
                "api_version": request.api_version
            }), 400
        
        # Update balance
        new_balance = update_user_balance(user_id, adjustment)
        if new_balance is None:
            return jsonify({
                "success": False,
                "message": "Failed to update balance",
                "request_id": request.id,
                "api_version": request.api_version
            }), 500
        
        # Create transaction record
        tx_type = 'ADMIN_CREDIT' if is_credit else 'ADMIN_DEBIT'
        tx_id = f"ADJ-{int(time.time())}-{secrets.token_hex(4)}"
        cursor.execute('''
            INSERT INTO transactions (id, user_id, type, amount, status, details, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            tx_id, user_id, tx_type, adjustment, 'COMPLETED',
            json.dumps({"reason": reason, "admin_id": admin_user['id'], "admin_username": admin_user['username']}),
            datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        
        # Log admin action
        action = "CREDIT_USER" if is_credit else "DEBIT_USER"
        audit_logger.log_admin_action(
            admin_user['id'],
            action,
            {
                "target_user_id": user_id,
                "target_username": username,
                "amount": amount,
                "adjustment": adjustment,
                "reason": reason,
                "old_balance": current_balance,
                "new_balance": new_balance
            },
            request.remote_addr
        )
        
        action_text = "credited" if is_credit else "debited"
        app.logger.info(f"[{request.id}] Admin {admin_user['username']} {action_text} ₦{amount:,.2f} to user {username}. New balance: ₦{new_balance:,.2f}")
        
        return jsonify({
            "success": True,
            "message": f"Balance {action_text} successfully. New balance: ₦{new_balance:,.2f}",
            "old_balance": current_balance,
            "new_balance": new_balance,
            "adjustment": adjustment,
            "transaction_id": tx_id,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Adjust balance error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to adjust balance",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

# ======================= ADMIN TRANSACTION MANAGEMENT =======================
@app.route('/api/v1/admin/transactions', methods=['GET'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_get_transactions_v1():
    """Admin: Get all transactions - API v1"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        offset = (page - 1) * limit
        
        # Get filter parameters
        user_id = request.args.get('user_id')
        transaction_type = request.args.get('type')
        status = request.args.get('status')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Build query
        query = '''
            SELECT t.*, u.username 
            FROM transactions t
            LEFT JOIN users u ON t.user_id = u.id
            WHERE 1=1
        '''
        params = []
        
        if user_id:
            query += ' AND t.user_id = %s'
            params.append(user_id)
        
        if transaction_type:
            query += ' AND t.type = %s'
            params.append(transaction_type)
        
        if status:
            query += ' AND t.status = %s'
            params.append(status)
        
        if start_date:
            query += ' AND t.timestamp >= %s'
            params.append(start_date)
        
        if end_date:
            query += ' AND t.timestamp <= %s'
            params.append(end_date)
        
        query += ' ORDER BY t.timestamp DESC LIMIT %s OFFSET %s'
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        
        transactions = []
        for row in cursor.fetchall():
            transaction = row_to_dict(cursor, row)
            transactions.append(transaction)
        
        # Get total count
        count_query = '''
            SELECT COUNT(*) 
            FROM transactions t
            LEFT JOIN users u ON t.user_id = u.id
            WHERE 1=1
        '''
        count_params = []
        
        if user_id:
            count_query += ' AND t.user_id = %s'
            count_params.append(user_id)
        
        if transaction_type:
            count_query += ' AND t.type = %s'
            count_params.append(transaction_type)
        
        if status:
            count_query += ' AND t.status = %s'
            count_params.append(status)
        
        if start_date:
            count_query += ' AND t.timestamp >= %s'
            count_params.append(start_date)
        
        if end_date:
            count_query += ' AND t.timestamp <= %s'
            count_params.append(end_date)
        
        cursor.execute(count_query, count_params)
        total = cursor.fetchone()[0]
        
        return jsonify({
            "success": True,
            "transactions": transactions,
            "total": total,
            "page": page,
            "limit": limit,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Get transactions error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load transactions",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/admin/transaction/<transaction_id>/update', methods=['POST'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_update_transaction_v1(transaction_id):
    """Admin: Update transaction status - API v1"""
    admin_user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    status = data.get('status', '')
    notes = sanitize_input(data.get('notes', ''))
    
    if status not in ['PENDING', 'COMPLETED', 'REJECTED']:
        return jsonify({
            "success": False,
            "message": "Invalid status. Must be PENDING, COMPLETED, or REJECTED",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get transaction details
        cursor.execute('''
            SELECT t.*, u.username, u.id as user_id
            FROM transactions t
            JOIN users u ON t.user_id = u.id
            WHERE t.id = %s
        ''', (transaction_id,))
        
        row = cursor.fetchone()
        if not row:
            return jsonify({
                "success": False,
                "message": "Transaction not found",
                "request_id": request.id,
                "api_version": request.api_version
            }), 404
        
        transaction = row_to_dict(cursor, row)
        old_status = transaction['status']
        
        # If changing from PENDING to REJECTED, refund the amount
        if old_status == 'PENDING' and status == 'REJECTED' and transaction['type'] == 'WITHDRAWAL':
            amount = float(transaction['amount'])
            update_user_balance(transaction['user_id'], amount)
        
        # Update transaction status
        cursor.execute('UPDATE transactions SET status = %s WHERE id = %s',
                      (status, transaction_id))
        
        # Update details if notes provided
        if notes:
            try:
                details = json.loads(transaction['details']) if transaction['details'] else {}
                details['admin_notes'] = notes
                details['admin_id'] = admin_user['id']
                details['admin_username'] = admin_user['username']
                details['updated_at'] = datetime.utcnow().isoformat()
                
                cursor.execute('UPDATE transactions SET details = %s WHERE id = %s',
                             (json.dumps(details), transaction_id))
            except:
                pass  # If details can't be parsed, skip updating
        
        conn.commit()
        
        # Log admin action
        audit_logger.log_admin_action(
            admin_user['id'],
            "UPDATE_TRANSACTION",
            {
                "transaction_id": transaction_id,
                "user_id": transaction['user_id'],
                "username": transaction['username'],
                "old_status": old_status,
                "new_status": status,
                "notes": notes,
                "amount": transaction['amount']
            },
            request.remote_addr
        )
        
        app.logger.info(f"[{request.id}] Admin {admin_user['username']} updated transaction {transaction_id} from {old_status} to {status}")
        
        return jsonify({
            "success": True,
            "message": f"Transaction status updated from {old_status} to {status}",
            "old_status": old_status,
            "new_status": status,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Update transaction error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to update transaction",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

# ======================= ADMIN SETTINGS =======================
@app.route('/api/v1/admin/settings', methods=['GET'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_get_settings_v1():
    """Admin: Get admin settings - API v1"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT whatsapp_link, telegram_link, facebook_link, global_withdrawal_days FROM admin_settings LIMIT 1')
        row = cursor.fetchone()
        
        if not row:
            return jsonify({
                "success": False,
                "message": "Settings not found",
                "request_id": request.id,
                "api_version": request.api_version
            }), 404
        
        settings = {
            'whatsapp_link': row[0] or '',
            'telegram_link': row[1] or '',
            'facebook_link': row[2] or '',
            'global_withdrawal_days': json.loads(row[3]) if row[3] else CONFIG.DEFAULT_WITHDRAWAL_DAYS
        }
        
        return jsonify({
            "success": True,
            "settings": settings,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Get settings error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load settings",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/admin/settings', methods=['POST'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_update_settings_v1():
    """Admin: Update admin settings - API v1"""
    admin_user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    whatsapp_link = sanitize_input(data.get('whatsapp_link', ''))
    telegram_link = sanitize_input(data.get('telegram_link', ''))
    facebook_link = sanitize_input(data.get('facebook_link', ''))
    global_withdrawal_days = data.get('global_withdrawal_days', [])
    
    # Validate withdrawal days
    if global_withdrawal_days:
        if not isinstance(global_withdrawal_days, list):
            return jsonify({
                "success": False,
                "message": "Withdrawal days must be a list",
                "request_id": request.id,
                "api_version": request.api_version
            }), 400
        
        # Validate each day is between 1-31
        for day in global_withdrawal_days:
            if not isinstance(day, int) or day < 1 or day > 31:
                return jsonify({
                    "success": False,
                    "message": f"Invalid withdrawal day: {day}. Must be between 1-31",
                    "request_id": request.id,
                    "api_version": request.api_version
                }), 400
        
        # Sort and remove duplicates
        global_withdrawal_days = sorted(list(set(global_withdrawal_days)))
        global_withdrawal_days_json = json.dumps(global_withdrawal_days)
    else:
        global_withdrawal_days_json = json.dumps(CONFIG.DEFAULT_WITHDRAWAL_DAYS)
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Update settings
        cursor.execute('''
            UPDATE admin_settings 
            SET whatsapp_link = %s, telegram_link = %s, facebook_link = %s, global_withdrawal_days = %s
            WHERE id = (SELECT MIN(id) FROM admin_settings)
        ''', (whatsapp_link, telegram_link, facebook_link, global_withdrawal_days_json))
        
        conn.commit()
        
        # Log admin action
        audit_logger.log_admin_action(
            admin_user['id'],
            "UPDATE_SETTINGS",
            {
                "whatsapp_link": whatsapp_link,
                "telegram_link": telegram_link,
                "facebook_link": facebook_link,
                "global_withdrawal_days": global_withdrawal_days
            },
            request.remote_addr
        )
        
        app.logger.info(f"[{request.id}] Admin {admin_user['username']} updated settings")
        
        return jsonify({
            "success": True,
            "message": "Settings updated successfully",
            "settings": {
                'whatsapp_link': whatsapp_link,
                'telegram_link': telegram_link,
                'facebook_link': facebook_link,
                'global_withdrawal_days': json.loads(global_withdrawal_days_json) if global_withdrawal_days_json else CONFIG.DEFAULT_WITHDRAWAL_DAYS
            },
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Update settings error: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to update settings",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

# ======================= ADMIN STATISTICS =======================
@app.route('/api/v1/admin/stats', methods=['GET'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def admin_get_stats_v1():
    """Admin: Get platform statistics - API v1"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # User statistics
        cursor.execute('SELECT COUNT(*) as total_users FROM users')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) as today_users FROM users WHERE DATE(created_at) = CURRENT_DATE')
        today_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) as admin_users FROM users WHERE is_admin = TRUE')
        admin_users = cursor.fetchone()[0]
        
        # Balance statistics
        cursor.execute('SELECT SUM(balance) as total_balance FROM users')
        total_balance = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT AVG(balance) as avg_balance FROM users')
        avg_balance = cursor.fetchone()[0] or 0
        
        # Transaction statistics
        cursor.execute('SELECT COUNT(*) as total_transactions FROM transactions')
        total_transactions = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) as today_transactions FROM transactions WHERE DATE(timestamp) = CURRENT_DATE')
        today_transactions = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(amount) as total_withdrawn FROM transactions WHERE type = \'WITHDRAWAL\' AND status = \'COMPLETED\'')
        total_withdrawn = cursor.fetchone()[0] or 0
        
        # Game statistics
        cursor.execute('SELECT COUNT(*) as total_game_plays FROM game_plays')
        total_game_plays = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) as today_game_plays FROM game_plays WHERE play_date = CURRENT_DATE')
        today_game_plays = cursor.fetchone()[0]
        
        # Coupon statistics
        cursor.execute('SELECT COUNT(*) as total_coupons FROM coupons')
        total_coupons = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) as available_coupons FROM coupons WHERE status = \'AVAILABLE\'')
        available_coupons = cursor.fetchone()[0]
        
        # Active users (logged in last 7 days)
        cursor.execute('SELECT COUNT(*) as active_users FROM users WHERE last_login >= NOW() - INTERVAL \'7 days\'')
        active_users = cursor.fetchone()[0]
        
        stats = {
            'users': {
                'total': total_users,
                'today': today_users,
                'admins': admin_users,
                'active': active_users
            },
            'balance': {
                'total': float(total_balance),
                'average': float(avg_balance)
            },
            'transactions': {
                'total': total_transactions,
                'today': today_transactions,
                'total_withdrawn': float(total_withdrawn)
            },
            'games': {
                'total_plays': total_game_plays,
                'today_plays': today_game_plays
            },
            'coupons': {
                'total': total_coupons,
                'available': available_coupons,
                'used': total_coupons - available_coupons
            }
        }
        
        return jsonify({
            "success": True,
            "stats": stats,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Get stats error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load statistics",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

# ======================= FRAUD PREVENTION ENDPOINTS =======================
@app.route('/api/v1/fraud/detect-multiple-accounts', methods=['GET'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=5)
def detect_multiple_accounts_v1():
    """Detect potential multiple accounts - API v1"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Detect accounts with same IP address
        cursor.execute('''
            SELECT last_login_ip, COUNT(*) as account_count, 
                   STRING_AGG(username, ', ') as usernames,
                   STRING_AGG(id::text, ', ') as user_ids
            FROM users 
            WHERE last_login_ip IS NOT NULL 
            AND last_login_ip != ''
            GROUP BY last_login_ip 
            HAVING COUNT(*) > 1
            ORDER BY account_count DESC
            LIMIT 20
        ''')
        
        suspicious_ips = []
        for row in cursor.fetchall():
            suspicious_ips.append({
                'ip_address': row[0],
                'account_count': row[1],
                'usernames': row[2].split(', '),
                'user_ids': row[3].split(', ')
            })
        
        # Detect accounts with similar usernames
        cursor.execute('''
            SELECT referred_by, COUNT(*) as ref_count,
                   STRING_AGG(username, ', ') as usernames
            FROM users 
            WHERE referred_by IS NOT NULL 
            AND referred_by != ''
            GROUP BY referred_by 
            HAVING COUNT(*) > 5
            ORDER BY ref_count DESC
            LIMIT 20
        ''')
        
        suspicious_refs = []
        for row in cursor.fetchall():
            suspicious_refs.append({
                'referral_code': row[0],
                'referral_count': row[1],
                'usernames': row[2].split(', ')
            })
        
        return jsonify({
            "success": True,
            "suspicious_ips": suspicious_ips,
            "suspicious_referrals": suspicious_refs,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Multiple accounts detection error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to detect multiple accounts",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/fraud/detect-bot-patterns', methods=['GET'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=5)
def detect_bot_patterns_v1():
    """Detect bot patterns in game plays - API v1"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Detect rapid game plays
        cursor.execute('''
            SELECT u.username, u.id, 
                   COUNT(gp.id) as plays_today,
                   MIN(gp.created_at) as first_play,
                   MAX(gp.created_at) as last_play
            FROM game_plays gp
            JOIN users u ON gp.user_id = u.id
            WHERE gp.play_date = CURRENT_DATE
            GROUP BY u.id, u.username
            HAVING COUNT(gp.id) > 50
            ORDER BY plays_today DESC
            LIMIT 20
        ''')
        
        rapid_players = []
        for row in cursor.fetchall():
            rapid_players.append({
                'username': row[0],
                'user_id': row[1],
                'plays_today': row[2],
                'first_play': row[3],
                'last_play': row[4]
            })
        
        # Detect perfect game scores (potential cheating)
        cursor.execute('''
            SELECT u.username, u.id, 
                   COUNT(*) as perfect_scores,
                   MAX(t.timestamp) as last_perfect
            FROM transactions t
            JOIN users u ON t.user_id = u.id
            WHERE t.type = 'SNAKE_REWARD' 
            AND (t.details::json->>'apples')::integer = 100
            GROUP BY u.id, u.username
            HAVING COUNT(*) > 3
            ORDER BY perfect_scores DESC
            LIMIT 20
        ''')
        
        perfect_scores = []
        for row in cursor.fetchall():
            perfect_scores.append({
                'username': row[0],
                'user_id': row[1],
                'perfect_scores': row[2],
                'last_perfect': row[3]
            })
        
        return jsonify({
            "success": True,
            "rapid_players": rapid_players,
            "perfect_scores": perfect_scores,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Bot pattern detection error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to detect bot patterns",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

# ======================= BUSINESS INTELLIGENCE ENDPOINTS =======================
@app.route('/api/v1/analytics/dashboard', methods=['GET'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=10)
def analytics_dashboard_v1():
    """Get analytics dashboard data - API v1"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # User acquisition metrics
        cursor.execute('''
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as new_users,
                COUNT(CASE WHEN referred_by IS NOT NULL THEN 1 END) as referred_users
            FROM users 
            WHERE created_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        ''')
        
        user_acquisition = []
        for row in cursor.fetchall():
            user_acquisition.append({
                'date': row[0].isoformat() if hasattr(row[0], 'isoformat') else row[0],
                'new_users': row[1],
                'referred_users': row[2]
            })
        
        # Retention analytics
        cursor.execute('''
            SELECT 
                DATE(last_login) as date,
                COUNT(*) as active_users
            FROM users 
            WHERE last_login >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(last_login)
            ORDER BY date DESC
        ''')
        
        user_retention = []
        for row in cursor.fetchall():
            user_retention.append({
                'date': row[0].isoformat() if hasattr(row[0], 'isoformat') else row[0],
                'active_users': row[1]
            })
        
        # Revenue metrics
        cursor.execute('''
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as withdrawals,
                SUM(amount) as total_withdrawn
            FROM transactions 
            WHERE type = 'WITHDRAWAL' 
            AND status = 'COMPLETED'
            AND timestamp >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
        ''')
        
        revenue_metrics = []
        for row in cursor.fetchall():
            revenue_metrics.append({
                'date': row[0].isoformat() if hasattr(row[0], 'isoformat') else row[0],
                'withdrawals': row[1],
                'total_withdrawn': float(row[2]) if row[2] else 0.0
            })
        
        # Game popularity metrics
        cursor.execute('''
            SELECT 
                game_type,
                COUNT(*) as play_count,
                DATE(play_date) as date
            FROM game_plays 
            WHERE play_date >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY game_type, DATE(play_date)
            ORDER BY date DESC, play_count DESC
        ''')
        
        game_metrics = []
        for row in cursor.fetchall():
            game_metrics.append({
                'game_type': row[0],
                'play_count': row[1],
                'date': row[2].isoformat() if hasattr(row[2], 'isoformat') else row[2]
            })
        
        # Withdrawal pattern analysis
        cursor.execute('''
            SELECT 
                EXTRACT(HOUR FROM timestamp::timestamp) as hour,
                COUNT(*) as withdrawal_count,
                AVG(amount) as avg_amount
            FROM transactions 
            WHERE type = 'WITHDRAWAL'
            AND timestamp >= NOW() - INTERVAL '30 days'
            GROUP BY EXTRACT(HOUR FROM timestamp::timestamp)
            ORDER BY hour
        ''')
        
        withdrawal_patterns = []
        for row in cursor.fetchall():
            withdrawal_patterns.append({
                'hour': int(row[0]),
                'withdrawal_count': row[1],
                'avg_amount': float(row[2]) if row[2] else 0.0
            })
        
        # Overall statistics
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(balance) FROM users')
        total_balance = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT COUNT(*) FROM transactions WHERE type = \'WITHDRAWAL\' AND status = \'COMPLETED\'')
        total_withdrawals = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(amount) FROM transactions WHERE type = \'WITHDRAWAL\' AND status = \'COMPLETED\'')
        total_withdrawn = cursor.fetchone()[0] or 0
        
        return jsonify({
            "success": True,
            "user_acquisition": user_acquisition,
            "user_retention": user_retention,
            "revenue_metrics": revenue_metrics,
            "game_metrics": game_metrics,
            "withdrawal_patterns": withdrawal_patterns,
            "overall_stats": {
                "total_users": total_users,
                "total_balance": float(total_balance),
                "total_withdrawals": total_withdrawals,
                "total_withdrawn": float(total_withdrawn)
            },
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Analytics dashboard error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to load analytics",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/reports/generate', methods=['POST'])
@api_version_required
@require_admin
@rate_limit_db_decorator(limit_per_minute=5)
def generate_report_v1():
    """Generate custom report - API v1"""
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "No data provided",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    report_type = data.get('report_type', '')
    start_date = data.get('start_date', '')
    end_date = data.get('end_date', '')
    
    if not report_type:
        return jsonify({
            "success": False,
            "message": "Report type required",
            "request_id": request.id,
            "api_version": request.api_version
        }), 400
    
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        report_data = {}
        
        if report_type == 'financial':
            # Financial reconciliation report
            cursor.execute('''
                SELECT 
                    DATE(timestamp) as date,
                    type,
                    COUNT(*) as transaction_count,
                    SUM(amount) as total_amount,
                    status
                FROM transactions 
                WHERE timestamp BETWEEN %s AND %s
                GROUP BY DATE(timestamp), type, status
                ORDER BY date DESC, type
            ''', (start_date or '1970-01-01', end_date or '2099-12-31'))
            
            financial_data = []
            for row in cursor.fetchall():
                financial_data.append({
                    'date': row[0].isoformat() if hasattr(row[0], 'isoformat') else row[0],
                    'type': row[1],
                    'transaction_count': row[2],
                    'total_amount': float(row[3]) if row[3] else 0.0,
                    'status': row[4]
                })
            
            report_data = financial_data
            
        elif report_type == 'user_behavior':
            # User behavior report
            cursor.execute('''
                SELECT 
                    u.username,
                    u.created_at,
                    u.last_login,
                    COUNT(DISTINCT gp.play_date) as active_days,
                    COUNT(gp.id) as total_games,
                    SUM(CASE WHEN t.type = 'WITHDRAWAL' THEN 1 ELSE 0 END) as withdrawal_count,
                    SUM(CASE WHEN t.type = 'WITHDRAWAL' AND t.status = 'COMPLETED' THEN t.amount ELSE 0 END) as total_withdrawn
                FROM users u
                LEFT JOIN game_plays gp ON u.id = gp.user_id
                LEFT JOIN transactions t ON u.id = t.user_id
                WHERE u.created_at BETWEEN %s AND %s
                GROUP BY u.id, u.username, u.created_at, u.last_login
                ORDER BY u.created_at DESC
                LIMIT 100
            ''', (start_date or '1970-01-01', end_date or '2099-12-31'))
            
            user_behavior = []
            for row in cursor.fetchall():
                user_behavior.append({
                    'username': row[0],
                    'created_at': row[1],
                    'last_login': row[2],
                    'active_days': row[3],
                    'total_games': row[4],
                    'withdrawal_count': row[5],
                    'total_withdrawn': float(row[6]) if row[6] else 0.0
                })
            
            report_data = user_behavior
        
        elif report_type == 'game_performance':
            # Game performance report
            cursor.execute('''
                SELECT 
                    gp.game_type,
                    DATE(gp.play_date) as date,
                    COUNT(DISTINCT gp.user_id) as unique_players,
                    COUNT(gp.id) as total_plays,
                    SUM(CASE WHEN t.type LIKE '%REWARD' THEN t.amount ELSE 0 END) as total_rewards
                FROM game_plays gp
                LEFT JOIN transactions t ON gp.user_id = t.user_id 
                    AND DATE(t.timestamp) = gp.play_date
                    AND t.type LIKE '%REWARD'
                WHERE gp.play_date BETWEEN %s AND %s
                GROUP BY gp.game_type, DATE(gp.play_date)
                ORDER BY date DESC, total_plays DESC
            ''', (start_date or '1970-01-01', end_date or '2099-12-31'))
            
            game_performance = []
            for row in cursor.fetchall():
                game_performance.append({
                    'game_type': row[0],
                    'date': row[1].isoformat() if hasattr(row[1], 'isoformat') else row[1],
                    'unique_players': row[2],
                    'total_plays': row[3],
                    'total_rewards': float(row[4]) if row[4] else 0.0
                })
            
            report_data = game_performance
        
        else:
            return jsonify({
                "success": False,
                "message": "Invalid report type",
                "request_id": request.id,
                "api_version": request.api_version
            }), 400
        
        return jsonify({
            "success": True,
            "report_type": report_type,
            "start_date": start_date,
            "end_date": end_date,
            "data": report_data,
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] Generate report error: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to generate report",
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

# ======================= HEALTH & DEBUG ENDPOINTS =======================
@app.route('/api/v1/debug/db-status', methods=['GET'])
@api_version_required
@rate_limit_db_decorator(limit_per_minute=10)
def db_status_v1():
    """Get database status and statistics - API v1"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        tables = [row[0] for row in cursor.fetchall()]
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM coupons')
        coupon_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM coupons WHERE status = 'AVAILABLE'")
        available_coupons = cursor.fetchone()[0]
        
        pool_stats = get_pool_stats()
        
        return jsonify({
            "success": True,
            "tables": tables,
            "user_count": user_count,
            "coupon_count": coupon_count,
            "available_coupons": available_coupons,
            "database_type": "PostgreSQL",
            "connection_pool": "active" if db_pool else "inactive",
            "pool_stats": pool_stats,
            "database_health": check_db_health(),
            "request_id": request.id,
            "api_version": request.api_version
        })
    except Exception as e:
        app.logger.error(f"[{request.id}] DB status error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "request_id": request.id,
            "api_version": request.api_version
        }), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/health', methods=['GET'])
@api_version_required
@rate_limit_db_decorator(limit_per_minute=30)
def api_health_v1():
    """Health check endpoint - API v1"""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        db_status = 'connected'
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM transactions WHERE status = %s', ('PENDING',))
        pending_withdrawals = cursor.fetchone()[0]
        
        # Calculate uptime
        if not hasattr(api_health_v1, 'start_time'):
            api_health_v1.start_time = datetime.utcnow()
        
        uptime = datetime.utcnow() - api_health_v1.start_time
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
        
        pool_stats = get_pool_stats()
        
        return jsonify({
            "status": "online",
            "service": "FLEXIA API v15.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": uptime_str,
            "database": db_status,
            "database_health": check_db_health(),
            "version": "15.0",
            "api_version": request.api_version,
            "stats": {
                "total_users": user_count,
                "pending_withdrawals": pending_withdrawals
            },
            "environment": os.getenv('ENV', 'development'),
            "connection_pool": "active" if db_pool else "inactive",
            "pool_stats": pool_stats,
            "security": {
                "2fa_enabled": CONFIG.ENABLE_2FA,
                "admin_2fa_enabled": CONFIG.ENABLE_ADMIN_2FA,
                "ip_whitelist": len(CONFIG.ADMIN_IP_WHITELIST) > 0
            },
            "game_limits": {
                "snake_per_day": CONFIG.SNAKE_PLAYS_PER_DAY,
                "coin_per_day": CONFIG.COIN_PLAYS_PER_DAY,
                "plinko_per_day": CONFIG.PLINKO_PLAYS_PER_DAY
            },
            "request_id": request.id
        }), 200
    except Exception as e:
        app.logger.error(f'[{request.id}] Health check failed: {str(e)}')
        return jsonify({
            "status": "degraded",
            "error": str(e),
            "request_id": request.id,
            "api_version": request.api_version
        }), 503
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/v1/debug/pool-stats', methods=['GET'])
@api_version_required
@require_admin
def pool_stats_v1():
    """Get connection pool statistics - API v1"""
    stats = get_pool_stats()
    return jsonify({
        "success": True,
        "pool_stats": stats,
        "request_id": request.id,
        "api_version": request.api_version
    })

# ======================= API VERSION INFORMATION =======================
@app.route('/api/versions', methods=['GET'])
def api_versions():
    """Get information about available API versions"""
    return jsonify({
        "success": True,
        "versions": CONFIG.API_SUPPORTED_VERSIONS,
        "current_version": CONFIG.API_CURRENT_VERSION,
        "endpoints": {
            "v1": {
                "auth": ["/api/v1/auth/register", "/api/v1/auth/login", "/api/v1/auth/logout"],
                "user": ["/api/v1/user/change-password", "/api/v1/user/set-withdrawal-pin"],
                "games": ["/api/v1/games/snake/report", "/api/v1/games/coinflip/report", "/api/v1/games/plinko/report"],
                "banking": ["/api/v1/banking/withdraw"],
                "admin": ["/api/v1/admin/payments/pending", "/api/v1/admin/payments/approve"],
                "security": ["/api/v1/security/2fa/setup", "/api/v1/security/2fa/verify"],
                "analytics": ["/api/v1/analytics/dashboard", "/api/v1/reports/generate"],
                "health": ["/api/v1/health", "/api/v1/debug/db-status"]
            }
        },
        "request_id": request.id
    })

# ======================= LEGACY ENDPOINTS REDIRECT =======================
@app.route('/api/auth/register', methods=['POST'])
def legacy_register():
    """Legacy endpoint redirect to v1"""
    return jsonify({
        "success": False,
        "message": "API version required. Use /api/v1/auth/register instead.",
        "current_version": CONFIG.API_CURRENT_VERSION,
        "redirect": "/api/v1/auth/register",
        "request_id": request.id
    }), 301

@app.route('/api/auth/login', methods=['POST'])
def legacy_login():
    """Legacy endpoint redirect to v1"""
    return jsonify({
        "success": False,
        "message": "API version required. Use /api/v1/auth/login instead.",
        "current_version": CONFIG.API_CURRENT_VERSION,
        "redirect": "/api/v1/auth/login",
        "request_id": request.id
    }), 301

@app.route('/api/games/snake/report', methods=['POST'])
def legacy_snake_report():
    """Legacy endpoint redirect to v1"""
    return jsonify({
        "success": False,
        "message": "API version required. Use /api/v1/games/snake/report instead.",
        "current_version": CONFIG.API_CURRENT_VERSION,
        "redirect": "/api/v1/games/snake/report",
        "request_id": request.id
    }), 301

# ======================= STATIC FILES =======================
@app.route('/')
def index():
    """Serve frontend index.html"""
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    try:
        return send_from_directory(CONFIG.FRONTEND_DIR, filename)
    except FileNotFoundError:
        return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

# ======================= CATCH-ALL ROUTE =======================
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    """Catch-all route for SPA routing"""
    if path.startswith('api/'):
        return jsonify({
            "success": False,
            "message": "API endpoint not found",
            "request_id": request.id
        }), 404
    return send_from_directory(CONFIG.FRONTEND_DIR, 'index.html')

# ======================= MAIN ENTRY POINT =======================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.getenv('ENV') != 'production'
    
    app.logger.info(f"🚀 Starting Flexia Platform SECURE v15.0 on port {port} (debug: {debug})")
    app.logger.info(f"📊 Database pool: {CONFIG.DB_POOL_MIN}-{CONFIG.DB_POOL_MAX} connections")
    app.logger.info(f"🌐 CORS allowed origins: {CONFIG.ALLOWED_ORIGINS}")
    app.logger.info(f"🔐 Security Features Enabled:")
    app.logger.info(f"   - 2FA: {'Enabled' if CONFIG.ENABLE_2FA else 'Disabled'}")
    app.logger.info(f"   - Admin 2FA: {'Enabled' if CONFIG.ENABLE_ADMIN_2FA else 'Disabled'}")
    app.logger.info(f"   - IP Whitelist: {len(CONFIG.ADMIN_IP_WHITELIST)} IPs")
    app.logger.info(f"   - Session Timeout: {CONFIG.SESSION_TIMEOUT//3600} hours")
    app.logger.info(f"🎮 Game Limits:")
    app.logger.info(f"   - Snake: {CONFIG.SNAKE_PLAYS_PER_DAY} plays/day")
    app.logger.info(f"   - Coin Flip: {CONFIG.COIN_PLAYS_PER_DAY} plays/day")
    app.logger.info(f"   - Plinko: {CONFIG.PLINKO_PLAYS_PER_DAY} plays/day")
    app.logger.info(f"💰 Withdrawal Settings:")
    app.logger.info(f"   - Cooldown: {CONFIG.WITHDRAWAL_COOLDOWN_HOURS} hours")
    app.logger.info(f"   - Daily Limit: {CONFIG.WITHDRAWALS_PER_DAY} per day")
    app.logger.info(f"🌐 API Versioning:")
    app.logger.info(f"   - Current Version: {CONFIG.API_CURRENT_VERSION}")
    app.logger.info(f"   - Supported Versions: {CONFIG.API_SUPPORTED_VERSIONS}")
    app.logger.info(f"   - Legacy Redirects: Enabled")
    
    # For production, use Gunicorn instead
    if os.getenv('ENV') == 'production':
        app.logger.info("⚡ Running in PRODUCTION mode")
    else:
        app.logger.info("🔧 Running in DEVELOPMENT mode")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
