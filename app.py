import os
from flask import Flask, request, jsonify, render_template, redirect
from flask_cors import CORS
import mysql.connector
import bcrypt
import random
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from dotenv import load_dotenv
import uuid
import logging
import sys

load_dotenv()

app = Flask(__name__, static_folder='public', static_url_path='/public')
app.secret_key = os.environ.get('SECRET_KEY', 'default-dev-key-change-in-prod')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
CORS(app, supports_credentials=True)

# Configure root logger to always write to stdout so terminal shows app logs
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
app.logger.setLevel(logging.DEBUG)

# Reduce noisy werkzeug access log to INFO while keeping app logs at DEBUG
logging.getLogger('werkzeug').setLevel(logging.INFO)

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', 3306)),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASS', ''),
    'database': os.environ.get('DB_NAME', 'spxbank')
}

db_pool = None

def init_db_pool():
    global db_pool
    if db_pool is None:
        try:
            db_pool = mysql.connector.pooling.MySQLConnectionPool(
                pool_name="spxbank_pool",
                pool_size=5,
                pool_reset_session=True,
                **DB_CONFIG
            )
            app.logger.info("[DB INIT] Connection pool created successfully.")
        except mysql.connector.Error as e:
            app.logger.exception(f"[DB INIT ERROR] Could not initialize DB pool: {e}")
            db_pool = None
            raise
    return db_pool

def get_db_connection():
    if db_pool is None:
        init_db_pool()
    if db_pool is None:
        raise RuntimeError("Database connection pool is not initialized.")
    return db_pool.get_connection()

def run_migrations():
    """Auto-migrate DB schema on startup. Safe to run repeatedly."""
    migrations = [
        # Add action column to otps if it doesn't already exist
        "ALTER TABLE otps ADD COLUMN action VARCHAR(50) NOT NULL DEFAULT 'LOGIN'",
    ]
    try:
        init_db_pool()
        conn = get_db_connection()
        cursor = conn.cursor()
        for sql in migrations:
            try:
                cursor.execute(sql)
                conn.commit()
                app.logger.info(f"[MIGRATION OK] {sql[:60]}...")
            except Exception as e:
                # 1060 = Duplicate column name — column already exists, safe to skip
                if hasattr(e, 'errno') and e.errno == 1060:
                    app.logger.info(f"[MIGRATION SKIP] Column already exists — {sql[:60]}")
                else:
                    app.logger.warning(f"[MIGRATION WARN] {e}")
        cursor.close()
        conn.close()
    except mysql.connector.Error as e:
        app.logger.exception(f"[MIGRATION ERROR] Could not connect for migrations: {e}")
    except Exception as e:
        app.logger.exception(f"[MIGRATION ERROR] {e}")

run_migrations()

def get_email_template(action, first_name, otp):
    subject = "Login Verification OTP"
    heading = "Verify your SPX Bank login"
    body_desc = "Use the OTP below to complete your sign-in. This code is valid for 5 minutes."
    security_note = "🔒 Never share this OTP with anyone, including SPX Bank staff."
    footer_text = "If you didn't request this code, you can safely ignore this email."

    if action == 'REGISTER':
        subject = "Registration Verification OTP"
        heading = "Verify your email address"
        body_desc = "Use the OTP below to verify your email and complete your SPX Bank account registration. This code is valid for 5 minutes."
        security_note = "🔒 Never share this OTP with anyone, including SPX Bank staff."
        footer_text = "If you didn't attempt to create an account with SPX Bank, please ignore this email."
    elif action == 'RESET_PASSWORD':
        subject = "Password Reset OTP"
        heading = "Reset your SPX Bank password"
        body_desc = "We received a request to reset your netbanking password. Use the code below to proceed. Valid for 5 minutes."
        security_note = "🔒 SPX Bank will never ask for this code. Do not share it with anyone."
        footer_text = "If you didn't request a password reset, please ignore this email or secure your account."

    plain_text = f"{heading}\n\n{body_desc}\n\nVerification Code: {otp}\n\n{security_note}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
    </head>
    <body style="margin: 0; padding: 0; background-color: #f8f9fa; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
        <span style="display:none; font-size:1px; color:#ffffff; line-height:1px; max-height:0px; max-width:0px; opacity:0; overflow:hidden;">
            Your SPX Bank verification code is enclosed. Please do not share this code with anyone.
        </span>
        <div style="background-color: #f8f9fa; padding: 40px 20px;">
            <div style="max-width: 500px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05); padding: 40px; border: 1px solid #eaeaea;">
                <h1 style="color: #111827; font-size: 20px; font-weight: 700; margin-top: 0; margin-bottom: 16px; text-align: center;">
                    {heading}
                </h1>
                
                <p style="color: #4b5563; font-size: 15px; line-height: 1.6; margin-bottom: 30px; text-align: center;">
                    {body_desc}
                </p>
                
                <div style="background-color: #f4f5f7; border: 1px solid #eaeaea; padding: 24px; text-align: center; border-radius: 6px; margin-bottom: 30px;">
                    <div style="font-size: 32px; font-weight: 700; color: #5C2D91; letter-spacing: 6px; margin-left: 8px;">
                        {otp}
                    </div>
                </div>
                
                <p style="color: #6b7280; font-size: 13px; line-height: 1.5; margin-bottom: 0; text-align: center;">
                    {security_note}
                </p>
                
                <hr style="border: none; border-top: 1px solid #eaeaea; margin: 30px 0;">
                
                <div style="text-align: center; color: #9ca3af; font-size: 12px; line-height: 1.5;">
                    <p style="margin: 0 0 8px 0;">{footer_text}</p>
                    <p style="margin: 0;">&copy; 2026 SPX Bank. All rights reserved.</p>
                    <p style="font-size: 11px; color: #888888; margin-top: 15px;">
                        <span style="display:none; font-size:1px; color:#ffffff; opacity:0;">Ref: {uuid.uuid4()}</span>
                    </p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return subject, html_content, plain_text

def send_real_email(to_email, subject, html_body, plain_text):
    try:
        smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com').strip()
        smtp_port = int(os.environ.get('SMTP_PORT', 465))
        smtp_user = os.environ.get('SMTP_USER', '').strip()
        smtp_pass = os.environ.get('SMTP_PASS', '').strip()

        if not smtp_user or not smtp_pass:
            app.logger.warning("SMTP credentials not set. Simulated email:")
            app.logger.info(f"To: {to_email}\nSubject: {subject}\nBody: HTML Content rendered")
            return True

        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = f"SPX Bank <{smtp_user}>"
        msg['To'] = to_email
        msg.set_content(plain_text)
        msg.add_alternative(html_body, subtype='html')

        # Logo attachment logic removed

        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True
    except Exception as e:
        app.logger.exception(f"Email error: {e}")
        return False

# --- VIEW ROUTES ---
@app.route('/')
def root():
    """Redirect root to canonical welcome URL."""
    return redirect('/registration/welcome')

@app.route('/registration/welcome')
def index():
    """Entry point: Login & Registration SPA."""
    return render_template('index.html')

@app.route('/registration/account-identification')
def password_recovery():
    """Password Recovery landing — serves the same SPA with the forgot-password view."""
    return render_template('index.html')

@app.route('/home/landingPage/homePage')
def overview():
    """Main authenticated dashboard."""
    return render_template('overview.html')

@app.route('/logout')
def logout_redirect():
    """Server-side logout: instructs the client back to the welcome / login page."""
    return redirect('/registration/welcome')

@app.route('/home/landingPage/manageRelationship/transactionAccounts')
def accounts():
    return render_template('accounts.html')

@app.route('/home/landingPage/manageRelationship/investments')
def investments():
    return render_template('investment.html')
# -------------------

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    first_name = data.get('firstName')
    last_name = data.get('lastName')

    if not all([username, email, password, first_name, last_name]):
        return jsonify({'success': False, 'message': 'Missing fields'}), 400

    hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Enforce OTP validation
        cursor.execute("SELECT * FROM otps WHERE email=%s AND used=TRUE ORDER BY created_at DESC LIMIT 1", (email,))
        otp_record = cursor.fetchone()
        
        if not otp_record:
            return jsonify({'success': False, 'message': 'OTP verification required'}), 403
            
        if otp_record['expires_at'] < datetime.now():
            return jsonify({'success': False, 'message': 'Verified OTP has expired. Please request a new one.'}), 403

        # 2. Duplicate check
        cursor.execute("SELECT id FROM users WHERE username=%s OR email=%s", (username, email))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': 'Username or email already exists'}), 409
            
        # 3. Consume OTP
        cursor.execute("DELETE FROM otps WHERE id=%s", (otp_record['id'],))
        
        account_number = f"#8849-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"

        sql = """
        INSERT INTO users (username, email, password_hash, first_name, last_name, account_number, balance) 
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (username, email, hashed_pw, first_name, last_name, account_number, 25000.00))
        conn.commit()

        user_obj = {
            'username': username,
            'name': f"{first_name} {last_name}",
            'email': email,
            'accountType': 'Savings Account',
            'accountNumber': account_number,
            'balance': '25,000.00'
        }
        return jsonify({'success': True, 'user': user_obj})
        
    except Exception as e:
        app.logger.exception(f"DB Error: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()

        if not user:
            return jsonify({'success': False, 'message': 'Invalid username or password'}), 401

        # Check lockout
        now = datetime.now()
        if user['lockout_until']:
            if user['lockout_until'] > now:
                remaining = int((user['lockout_until'] - now).total_seconds())
                app.logger.warning(f"[LOCKOUT BLOCKED] Login attempt rejected for locked user: {username}")
                return jsonify({'success': False, 'error': 'Account locked', 'lockout': True, 'remaining_seconds': remaining, 'message': f'Account locked. Please wait {remaining} seconds.'}), 423
            else:
                cursor.execute("UPDATE users SET failed_attempts=0, lockout_until=NULL WHERE id=%s", (user['id'],))
                conn.commit()
                user['failed_attempts'] = 0
                user['lockout_until'] = None
                app.logger.info(f"[LOCKOUT EXPIRED] Resetting failed attempts and lockout timestamp for user: {username}")

        # Verify password
        if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            # Reset attempts on success
            cursor.execute("UPDATE users SET failed_attempts=0, lockout_until=NULL WHERE id=%s", (user['id'],))
            conn.commit()

            user_obj = {
                'username': user['username'],
                'name': f"{user['first_name']} {user['last_name']}",
                'email': user['email'],
                'accountType': 'Savings Account',
                'accountNumber': user['account_number'],
                'balance': str(user['balance'])
            }
            return jsonify({'success': True, 'user': user_obj, 'email': user['email']})
        else:
            # Failed attempt
            attempts = user['failed_attempts'] + 1
            if attempts >= 3:
                lockout_time = now + timedelta(seconds=30)
                cursor.execute("UPDATE users SET failed_attempts=%s, lockout_until=%s WHERE id=%s", (attempts, lockout_time, user['id']))
                conn.commit()
                return jsonify({'success': False, 'error': 'Account locked', 'lockout': True, 'remaining_seconds': 30, 'message': 'Account locked. Please wait 30 seconds.'}), 423
            else:
                cursor.execute("UPDATE users SET failed_attempts=%s WHERE id=%s", (attempts, user['id']))
                conn.commit()
                remaining = 3 - attempts
                msg = f'Incorrect password. {remaining} attempt{"s" if remaining > 1 else ""} remaining.'
                return jsonify({'success': False, 'lockout': False, 'attempts_remaining': remaining, 'message': msg}), 401

    except Exception as e:
        app.logger.exception(f"DB Error: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

@app.route('/api/send-otp', methods=['POST'])
def send_otp():
    data = request.json
    email = data.get('email')
    action = data.get('action')
    frontend_username = data.get('username')
    
    if not email:
        return jsonify({'success': False, 'message': 'Missing data'}), 400

    otp = str(random.randint(100000, 999999))
    expires_at = datetime.now() + timedelta(minutes=5)
    
    first_name = frontend_username if frontend_username else "Customer"

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT first_name, username FROM users WHERE email=%s", (email,))
        user_record = cursor.fetchone()
        
        if action == 'REGISTER':
            cursor.execute("SELECT id FROM users WHERE username=%s OR email=%s", (frontend_username, email))
            if cursor.fetchone():
                return jsonify({'success': False, 'message': 'Username or email already exists'}), 409
        
        if action == 'RESET_PASSWORD' and not user_record:
            return jsonify({'success': False, 'message': 'No account found with this email address'}), 404

        if user_record:
            if user_record.get('first_name'):
                first_name = user_record['first_name']
            elif user_record.get('username'):
                first_name = user_record['username']

        cursor.execute("INSERT INTO otps (email, otp, action, expires_at) VALUES (%s, %s, %s, %s)", (email, otp, action, expires_at))
        conn.commit()
    except Exception as e:
        app.logger.exception(f"[SEND-OTP ERROR] {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

    subject, html_body, plain_text = get_email_template(action, first_name, otp)
    email_sent = send_real_email(email, subject, html_body, plain_text)
    if not email_sent:
        return jsonify({'success': False, 'message': 'Failed to send OTP email. Please check SMTP settings.'}), 500

    return jsonify({'success': True, 'message': 'OTP sent'})

@app.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    data = request.json
    email = data.get('email')
    otp = data.get('otp')

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM otps WHERE email=%s AND used=FALSE ORDER BY created_at DESC LIMIT 1", (email,))
        record = cursor.fetchone()

        if not record:
            return jsonify({'success': False, 'message': 'No pending OTP found'})

        if record['expires_at'] < datetime.now():
            return jsonify({'success': False, 'message': 'OTP expired'})

        if record['otp'] == otp:
            cursor.execute("UPDATE otps SET used=TRUE WHERE id=%s", (record['id'],))
            conn.commit()

            # For RESET_PASSWORD: store verified email in server-side session
            action = data.get('action', '')
            if action == 'RESET_PASSWORD':
                from flask import session as flask_session
                flask_session['verified_reset_email'] = email
                flask_session['verified_reset_at'] = datetime.now().isoformat()
                app.logger.debug(f"[RESET SESSION SET] verified_reset_email={email}")

            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Invalid OTP'})
            
    except Exception as e:
        app.logger.exception(f"DB Error: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    from flask import session as flask_session
    data = request.json
    email = data.get('email')
    new_password = data.get('password')

    if not email or not new_password:
        return jsonify({'success': False, 'message': 'Missing data'}), 400

    # --- Auth check: Flask session (primary) OR DB-verified OTP fallback ---
    session_email = flask_session.get('verified_reset_email')
    is_session_verified = (session_email == email)

    if not is_session_verified:
        # Fallback: check otps table for a verified RESET_PASSWORD OTP within 15 min
        try:
            conn_check = get_db_connection()
            cursor_check = conn_check.cursor(dictionary=True, buffered=True)
            cursor_check.execute(
                "SELECT id FROM otps WHERE email=%s AND action='RESET_PASSWORD' AND used=TRUE AND created_at >= NOW() - INTERVAL 15 MINUTE ORDER BY created_at DESC LIMIT 1",
                (email,)
            )
            otp_fallback = cursor_check.fetchone()
            cursor_check.close()
            conn_check.close()
        except Exception as db_e:
            app.logger.exception(f"[RESET AUTH CHECK ERROR] {db_e}")
            otp_fallback = None

        if not otp_fallback:
            app.logger.warning(f"[RESET REJECTED] No valid session or verified OTP for {email}")
            return jsonify({'success': False, 'message': 'Session expired or unauthorized. Please restart the password reset flow.'}), 403

        app.logger.info(f"[RESET AUTH] DB-fallback OTP verification passed for {email}")
    else:
        app.logger.info(f"[RESET AUTH] Session verification passed for {email}")

    try:
        conn = get_db_connection()

        # Fetch the current password hash to check for reuse
        cursor = conn.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT password_hash FROM users WHERE email=%s", (email,))
        user_row = cursor.fetchone()
        cursor.close()

        if user_row and bcrypt.checkpw(new_password.encode('utf-8'), user_row['password_hash'].encode('utf-8')):
            return jsonify({'success': False, 'error': 'same_password', 'message': 'New password cannot be the same as the old password.'}), 400

        hashed_pw = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())

        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password_hash=%s WHERE email=%s", (hashed_pw, email))
        conn.commit()

        affected = cursor.rowcount
        app.logger.info(f"[RESET SUCCESS] Password updated for {email}, rows affected: {affected}")
        cursor.close()

        if affected == 0:
            return jsonify({'success': False, 'message': 'No account found with this email address or update failed'}), 404

        # Clear the session flag — single use
        flask_session.pop('verified_reset_email', None)
        flask_session.pop('verified_reset_at', None)

        return jsonify({'success': True, 'message': 'Password reset successful'})
    except Exception as e:
        app.logger.exception(f"[RESET ERROR] {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()

# ==========================================================================
# SPX BANK INVESTMENT PORTAL MODULE VIEW ROUTES & API ENDPOINTS
# ==========================================================================

@app.route('/investments')
@app.route('/home/landingPage/manageRelationship/investments')
def investments_main():
    return render_template('investments/main.html')

@app.route('/investments/mutual-funds')
def investments_mutual_funds():
    return render_template('investments/mutual_funds.html')

@app.route('/investments/mutual-funds/<int:fund_id>')
def investments_mutual_fund_detail(fund_id):
    return render_template('investments/mutual_fund_detail.html', fund_id=fund_id)

@app.route('/investments/nps')
def investments_nps():
    return render_template('investments/nps.html')

@app.route('/investments/ppf')
def investments_ppf():
    return render_template('investments/ppf.html')

@app.route('/investments/ipo')
def investments_ipo():
    return render_template('investments/ipo.html')

@app.route('/investments/ipo/<int:ipo_id>')
def investments_ipo_detail(ipo_id):
    return render_template('investments/ipo_detail.html', ipo_id=ipo_id)

@app.route('/investments/demat')
def investments_demat():
    return render_template('investments/demat.html')

@app.route('/investments/securities/<int:security_id>')
def investments_security_detail(security_id):
    return render_template('investments/security_detail.html', security_id=security_id)

@app.route('/investments/transactions')
def investments_transactions():
    return render_template('investments/transactions.html')

@app.route('/investments/goals')
def investments_goals():
    return render_template('investments/goals.html')

# --- INVESTMENT API ENDPOINTS ---
@app.route('/api/investments', methods=['GET'])
def api_investments_overview():
    return jsonify({
        'success': True,
        'summary': {
            'total_investment': 25000.00,
            'current_value': 27850.00,
            'total_returns': 2850.00,
            'returns_percent': 11.40,
            'today_change': 320.00,
            'today_change_percent': 1.16
        }
    })

@app.route('/api/mutual-funds', methods=['GET'])
def api_mutual_funds():
    funds = [
        {'id': 1, 'name': 'SPX Large Cap Flexi Equity Fund', 'category': 'Equity', 'risk_level': 'Very High', 'return_1y': 22.4, 'return_3y': 18.2, 'return_5y': 16.5, 'min_investment': 500, 'aum': '14,250 Cr', 'nav': 142.85, 'rating': 5, 'expense_ratio': 0.85},
        {'id': 2, 'name': 'SPX Focused Bluechip Fund', 'category': 'Equity', 'risk_level': 'Very High', 'return_1y': 19.8, 'return_3y': 16.9, 'return_5y': 15.2, 'min_investment': 1000, 'aum': '22,100 Cr', 'nav': 88.40, 'rating': 5, 'expense_ratio': 0.92},
        {'id': 3, 'name': 'SPX Dynamic Debt Scheme', 'category': 'Debt', 'risk_level': 'Low', 'return_1y': 7.6, 'return_3y': 7.2, 'return_5y': 7.0, 'min_investment': 500, 'aum': '8,900 Cr', 'nav': 34.20, 'rating': 4, 'expense_ratio': 0.35},
        {'id': 4, 'name': 'SPX Balanced Advantage Fund', 'category': 'Hybrid', 'risk_level': 'Moderate', 'return_1y': 14.5, 'return_3y': 13.8, 'return_5y': 12.9, 'min_investment': 500, 'aum': '11,400 Cr', 'nav': 62.10, 'rating': 4, 'expense_ratio': 0.75}
    ]
    return jsonify({'success': True, 'mutual_funds': funds})

@app.route('/api/mutual-funds/<int:fund_id>', methods=['GET'])
def api_mutual_fund_detail(fund_id):
    fund = {
        'id': fund_id,
        'name': 'SPX Large Cap Flexi Equity Fund' if fund_id == 1 else 'SPX Focused Bluechip Fund',
        'category': 'Equity Direct Growth',
        'risk_level': 'Very High',
        'nav': 142.85,
        'aum': '₹14,250 Cr',
        'expense_ratio': 0.85,
        'min_investment': 500
    }
    return jsonify({'success': True, 'fund': fund})

@app.route('/api/mutual-funds/invest', methods=['POST'])
def api_mutual_funds_invest():
    return jsonify({'success': True, 'message': 'Lump-sum investment processed successfully', 'reference_id': 'MF' + str(random.randint(100000, 999999))})

@app.route('/api/mutual-funds/sip', methods=['POST'])
def api_mutual_funds_sip():
    return jsonify({'success': True, 'message': 'SIP registered successfully', 'reference_id': 'SIP' + str(random.randint(100000, 999999))})

@app.route('/api/nps', methods=['GET'])
def api_nps_get():
    return jsonify({
        'success': True,
        'nps': {
            'pran': '1100-XXXX-8921',
            'current_value': 45200.00,
            'total_contribution': 38000.00,
            'current_returns': 7200.00,
            'pension_fund': 'SPX Pension Fund Managers Ltd'
        }
    })

@app.route('/api/nps/open', methods=['POST'])
def api_nps_open():
    pran = '1100-' + str(random.randint(1000, 9999)) + '-' + str(random.randint(1000, 9999))
    return jsonify({'success': True, 'message': 'NPS Account created successfully', 'pran': pran})

@app.route('/api/ppf', methods=['GET'])
def api_ppf_get():
    return jsonify({
        'success': True,
        'ppf': {
            'account_number': '#PPF-8849-XXXX-4012',
            'opening_date': '2024-04-12',
            'current_balance': 125400.00,
            'total_contribution': 110000.00,
            'interest_earned': 15400.00,
            'maturity_date': '2039-04-12'
        }
    })

@app.route('/api/ppf/open', methods=['POST'])
def api_ppf_open():
    acc_num = '#PPF-8849-' + str(random.randint(1000, 9999)) + '-' + str(random.randint(1000, 9999))
    return jsonify({'success': True, 'message': 'PPF Account created successfully', 'account_number': acc_num})

@app.route('/api/ppf/deposit', methods=['POST'])
def api_ppf_deposit():
    return jsonify({'success': True, 'message': 'PPF Deposit processed successfully', 'reference_id': 'PPF' + str(random.randint(100000, 999999))})

@app.route('/api/ipos', methods=['GET'])
def api_ipos_get():
    ipos = [
        {'id': 1, 'company_name': 'TechVista Solutions Ltd', 'symbol': 'TECHVISTA', 'issue_size': '₹1,450 Cr', 'price_band': '₹420 - ₹445', 'lot_size': 33, 'status': 'Open', 'subscription_status': '14.8x'},
        {'id': 2, 'company_name': 'GreenEnergy Renewables India', 'symbol': 'GREENNRG', 'issue_size': '₹2,800 Cr', 'price_band': '₹185 - ₹195', 'lot_size': 75, 'status': 'Upcoming', 'subscription_status': '1.0x'}
    ]
    return jsonify({'success': True, 'ipos': ipos})

@app.route('/api/ipos/<int:ipo_id>', methods=['GET'])
def api_ipo_detail(ipo_id):
    return jsonify({'success': True, 'ipo': {'id': ipo_id, 'company_name': 'TechVista Solutions Ltd', 'price_band': '₹420 - ₹445', 'lot_size': 33, 'cutoff_price': 445}})

@app.route('/api/ipos/apply', methods=['POST'])
def api_ipos_apply():
    return jsonify({'success': True, 'message': 'IPO Application submitted & funds blocked successfully', 'application_id': 'ASBA' + str(random.randint(100000, 999999))})

@app.route('/api/demat', methods=['GET'])
def api_demat_get():
    holdings = [
        {'symbol': 'SPX', 'company_name': 'SPX CORP', 'quantity': 30, 'avg_price': 1150.00, 'current_price': 1245.50, 'invested_value': 34500.00, 'current_value': 37365.00, 'gain_loss': 2865.00, 'gain_percent': 8.30},
        {'symbol': 'RELIANCE', 'company_name': 'RELIANCE IND', 'quantity': 15, 'avg_price': 2800.00, 'current_price': 2940.00, 'invested_value': 42000.00, 'current_value': 44100.00, 'gain_loss': 2100.00, 'gain_percent': 5.00},
        {'symbol': 'INFY', 'company_name': 'INFOSYS LTD', 'quantity': 10, 'avg_price': 1600.00, 'current_price': 1780.40, 'invested_value': 16000.00, 'current_value': 17804.00, 'gain_loss': 1804.00, 'gain_percent': 11.28}
    ]
    return jsonify({
        'success': True,
        'demat': {
            'demat_number': '#1204-XXXX-8819',
            'holdings_count': 3,
            'invested_value': 84500.00,
            'current_value': 96820.00,
            'overall_gain': 12320.00,
            'holdings': holdings
        }
    })

@app.route('/api/demat/open', methods=['POST'])
def api_demat_open():
    demat_num = '#1204-' + str(random.randint(1000, 9999)) + '-' + str(random.randint(1000, 9999))
    return jsonify({'success': True, 'message': 'Demat Account created successfully', 'demat_number': demat_num})

@app.route('/api/investments/portfolio', methods=['GET'])
def api_investments_portfolio():
    return jsonify({
        'success': True,
        'portfolio': {
            'total_value': 27850.00,
            'breakdown': {
                'mutual_funds': 17420.00,
                'ppf': 125400.00,
                'nps': 45200.00,
                'demat': 96820.00
            }
        }
    })

@app.route('/api/investments/transactions', methods=['GET'])
def api_investments_transactions():
    txs = [
        {'date': '2026-08-10', 'product': 'Mutual Fund', 'type': 'SIP', 'amount': 5000.00, 'status': 'Completed', 'reference_id': 'TXN982140591'},
        {'date': '2026-08-12', 'product': 'IPO', 'type': 'IPO Application', 'amount': 14685.00, 'status': 'Applied', 'reference_id': 'ASBA-77182901'},
        {'date': '2026-07-15', 'product': 'PPF', 'type': 'Deposit', 'amount': 10000.00, 'status': 'Completed', 'reference_id': 'TXN441209841'}
    ]
    return jsonify({'success': True, 'transactions': txs})

@app.route('/api/investments/goals', methods=['GET', 'POST'])
def api_investments_goals():
    if request.method == 'POST':
        return jsonify({'success': True, 'message': 'Goal created successfully'})
    goals = [
        {'name': 'Dream Home Fund', 'category': 'Home', 'target_amount': 5000000, 'current_savings': 1250000, 'monthly_investment': 28500, 'progress': 25.0},
        {'name': 'Child Higher Education', 'category': 'Education', 'target_amount': 2500000, 'current_savings': 680000, 'monthly_investment': 12000, 'progress': 27.2}
    ]
    return jsonify({'success': True, 'goals': goals})

if __name__ == '__main__':
    app.run(port=5000, debug=True)

