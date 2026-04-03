import json
import sqlite3
import os
import secrets
import hashlib
import smtplib
import random
import string
from flask import Flask, request, send_from_directory, session, redirect, url_for
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

PORT = int(os.environ.get('PORT', 8000))
DB_FILE = "database.sqlite"

# Email Configuration
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_EMAIL = os.environ.get('SMTP_EMAIL', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
FROM_NAME = os.environ.get('FROM_NAME', 'AssetCore')

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS store (key TEXT PRIMARY KEY, value TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash TEXT, email TEXT, role TEXT DEFAULT 'user', created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS otp_store (email TEXT PRIMARY KEY, otp TEXT, expires_at TEXT, attempts INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS login_otp (email TEXT, otp TEXT, expires_at TEXT)")
    conn.commit()
    
    c.execute("SELECT username FROM users WHERE username = 'admin'")
    if not c.fetchone():
        hashed = hashlib.sha256("admin123".encode()).hexdigest()
        c.execute("INSERT INTO users (username, password_hash, email, role, created_at) VALUES (?, ?, ?, ?, ?)",
                  ("admin", hashed, "admin@example.com", "admin", datetime.now().isoformat()))
        conn.commit()
        print("Default admin created: admin / admin123")
    
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

def send_email(to_email, subject, body):
    try:
        if not SMTP_EMAIL or not SMTP_PASSWORD:
            print(f"Email simulation - To: {to_email}, OTP: {body.split('Code: ')[-1][:6]}")
            return True
        
        msg = MIMEMultipart()
        msg['From'] = f"{FROM_NAME} <{SMTP_EMAIL}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

@app.route('/')
def index():
    if 'username' not in session:
        return redirect('/login.html')
    return send_from_directory('public', 'index.html')

@app.route('/login.html')
def login_page():
    if 'username' in session:
        return redirect('/')
    return send_from_directory('public', 'login.html')

@app.route('/<path:path>')
def serve_static(path):
    if path == 'api/login':
        return login()
    if path == 'api/request-otp':
        return request_otp()
    if path == 'api/verify-otp':
        return verify_otp()
    if path == 'api/logout':
        return logout()
    if path == 'api/check-auth':
        return check_auth()
    if path == 'api/change-password':
        return change_password()
    if path == 'api/load':
        return load_data()
    if path == 'api/save':
        return save_data()
    if path == 'api/users':
        return manage_users()
    
    if 'username' not in session:
        return redirect('/login.html')
    
    return send_from_directory('public', path)

@app.route('/api/request-otp', methods=['POST'])
def request_otp():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    
    if not email:
        return app.response_class(json.dumps({"error": "Email required"}), 
                                status=400, mimetype='application/json')
    
    otp = generate_otp()
    expires_at = (datetime.now() + timedelta(minutes=5)).isoformat()
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM login_otp WHERE email = ?", (email,))
    c.execute("INSERT INTO login_otp (email, otp, expires_at) VALUES (?, ?, ?)",
              (email, hash_password(otp), expires_at))
    conn.commit()
    conn.close()
    
    subject = f"{FROM_NAME} - Login OTP Verification"
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #2563eb, #1d4ed8); padding: 20px; border-radius: 10px 10px 0 0;">
            <h1 style="color: white; margin: 0;">{FROM_NAME}</h1>
        </div>
        <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; border: 1px solid #e5e7eb;">
            <h2 style="color: #1f2937; margin-top: 0;">Your Login OTP</h2>
            <p style="color: #6b7280; font-size: 14px;">Use this code to verify your login:</p>
            <div style="background: #ffffff; border: 2px dashed #2563eb; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0;">
                <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #2563eb;">{otp}</span>
            </div>
            <p style="color: #dc2626; font-size: 12px;">⚠️ This code expires in 5 minutes. Do not share with anyone.</p>
        </div>
        <p style="color: #9ca3af; font-size: 12px; text-align: center; margin-top: 20px;">
            If you didn't request this, please ignore this email.
        </p>
    </body>
    </html>
    """
    
    success = send_email(email, subject, body)
    
    return app.response_class(json.dumps({
        "status": "success" if success else "simulated",
        "message": "OTP sent to your email" if success else f"OTP (dev mode): {otp}",
        "email": email[:3] + "***" + email[email.index('@')-2:]
    }), mimetype='application/json')

@app.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    otp = data.get('otp', '').strip()
    
    if not email or not otp:
        return app.response_class(json.dumps({"error": "Email and OTP required"}), 
                                status=400, mimetype='application/json')
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT otp, expires_at FROM login_otp WHERE email = ?", (email,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        return app.response_class(json.dumps({"error": "No OTP requested for this email"}), 
                                status=400, mimetype='application/json')
    
    stored_hash, expires_at = row
    
    if datetime.now() > datetime.fromisoformat(expires_at):
        conn.close()
        return app.response_class(json.dumps({"error": "OTP has expired. Request a new one."}), 
                                status=400, mimetype='application/json')
    
    if stored_hash != hash_password(otp):
        return app.response_class(json.dumps({"error": "Invalid OTP"}), 
                                status=400, mimetype='application/json')
    
    c.execute("DELETE FROM login_otp WHERE email = ?", (email,))
    conn.commit()
    conn.close()
    
    return app.response_class(json.dumps({"status": "success", "message": "OTP verified"}), 
                            mimetype='application/json')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    login_type = data.get('type', 'password')
    
    if login_type == 'otp':
        email = data.get('email', '').strip().lower()
        otp = data.get('otp', '').strip()
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT username FROM users WHERE email = ?", (email,))
        row = c.fetchone()
        conn.close()
        
        if not row:
            return app.response_class(json.dumps({"error": "No account found with this email"}), 
                                    status=401, mimetype='application/json')
        
        username = row[0]
        
        c.execute("SELECT otp, expires_at FROM login_otp WHERE email = ?", (email,))
        otp_row = c.fetchone()
        
        if not otp_row or otp_row[0] != hash_password(otp):
            return app.response_class(json.dumps({"error": "Invalid OTP"}), 
                                    status=401, mimetype='application/json')
        
        if datetime.now() > datetime.fromisoformat(otp_row[1]):
            return app.response_class(json.dumps({"error": "OTP expired"}), 
                                    status=401, mimetype='application/json')
        
        c.execute("DELETE FROM login_otp WHERE email = ?", (email,))
        conn.commit()
        conn.close()
        
        session['username'] = username
        session['email'] = email
        return app.response_class(json.dumps({"status": "success", "username": username, "method": "otp"}), 
                                mimetype='application/json')
    
    else:
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return app.response_class(json.dumps({"error": "Username and password required"}), 
                                    status=400, mimetype='application/json')
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT password_hash, email FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        conn.close()
        
        if row and row[0] == hash_password(password):
            session['username'] = username
            session['email'] = row[1]
            return app.response_class(json.dumps({"status": "success", "username": username, "method": "password"}), 
                                    mimetype='application/json')
        
        return app.response_class(json.dumps({"error": "Invalid credentials"}), 
                                status=401, mimetype='application/json')

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return app.response_class(json.dumps({"status": "success"}), mimetype='application/json')

@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    if 'username' in session:
        return app.response_class(json.dumps({
            "authenticated": True, 
            "username": session['username'],
            "email": session.get('email', '')
        }), mimetype='application/json')
    return app.response_class(json.dumps({"authenticated": False}), mimetype='application/json')

@app.route('/api/change-password', methods=['POST'])
def change_password():
    if 'username' not in session:
        return app.response_class(json.dumps({"error": "Not authenticated"}), 
                                status=401, mimetype='application/json')
    
    data = request.get_json()
    current = data.get('currentPassword', '')
    new_pass = data.get('newPassword', '')
    
    if not current or not new_pass:
        return app.response_class(json.dumps({"error": "All fields required"}), 
                                status=400, mimetype='application/json')
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE username = ?", (session['username'],))
    row = c.fetchone()
    
    if not row or row[0] != hash_password(current):
        conn.close()
        return app.response_class(json.dumps({"error": "Current password incorrect"}), 
                                status=400, mimetype='application/json')
    
    c.execute("UPDATE users SET password_hash = ? WHERE username = ?", 
              (hash_password(new_pass), session['username']))
    conn.commit()
    conn.close()
    
    return app.response_class(json.dumps({"status": "success"}), mimetype='application/json')

@app.route('/api/users', methods=['GET', 'POST', 'PUT', 'DELETE'])
def manage_users():
    if 'username' not in session:
        return app.response_class(json.dumps({"error": "Not authenticated"}), 
                                status=401, mimetype='application/json')
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    if request.method == 'GET':
        c.execute("SELECT username, email, role, created_at FROM users")
        users = [{"username": u[0], "email": u[1], "role": u[2], "created_at": u[3]} for u in c.fetchall()]
        conn.close()
        return app.response_class(json.dumps(users), mimetype='application/json')
    
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        email = data.get('email', '').strip().lower()
        role = data.get('role', 'user')
        
        if not username or not password or not email:
            conn.close()
            return app.response_class(json.dumps({"error": "All fields required"}), 
                                    status=400, mimetype='application/json')
        
        c.execute("SELECT username FROM users WHERE username = ? OR email = ?", (username, email))
        if c.fetchone():
            conn.close()
            return app.response_class(json.dumps({"error": "User already exists"}), 
                                    status=400, mimetype='application/json')
        
        c.execute("INSERT INTO users (username, password_hash, email, role, created_at) VALUES (?, ?, ?, ?, ?)",
                  (username, hash_password(password), email, role, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return app.response_class(json.dumps({"status": "success"}), mimetype='application/json')
    
    if request.method == 'PUT':
        data = request.get_json()
        username = data.get('username', '')
        new_password = data.get('newPassword', '')
        
        if session['username'] != 'admin' and session['username'] != username:
            conn.close()
            return app.response_class(json.dumps({"error": "Unauthorized"}), 
                                    status=403, mimetype='application/json')
        
        if new_password:
            c.execute("UPDATE users SET password_hash = ? WHERE username = ?", 
                      (hash_password(new_password), username))
        
        if 'role' in data and session['username'] == 'admin':
            c.execute("UPDATE users SET role = ? WHERE username = ?", 
                      (data['role'], username))
        
        if 'email' in data:
            c.execute("UPDATE users SET email = ? WHERE username = ?", 
                      (data['email'], username))
        
        conn.commit()
        conn.close()
        return app.response_class(json.dumps({"status": "success"}), mimetype='application/json')
    
    if request.method == 'DELETE':
        username = request.args.get('username')
        
        if session['username'] != 'admin':
            conn.close()
            return app.response_class(json.dumps({"error": "Only admin can delete users"}), 
                                    status=403, mimetype='application/json')
        
        if username == 'admin':
            conn.close()
            return app.response_class(json.dumps({"error": "Cannot delete admin"}), 
                                    status=400, mimetype='application/json')
        
        c.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
        conn.close()
        return app.response_class(json.dumps({"status": "success"}), mimetype='application/json')

@app.route('/api/load')
def load_data():
    if 'username' not in session:
        return app.response_class(json.dumps({"error": "Not authenticated"}), 
                                status=401, mimetype='application/json')
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT key, value FROM store")
    rows = c.fetchall()
    conn.close()
    data = {k: json.loads(v) for k, v in rows}
    return app.response_class(json.dumps(data), mimetype='application/json')

@app.route('/api/save', methods=['POST'])
def save_data():
    if 'username' not in session:
        return app.response_class(json.dumps({"error": "Not authenticated"}), 
                                status=401, mimetype='application/json')
    
    try:
        data = request.get_json()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        for key, value in data.items():
            c.execute("INSERT OR REPLACE INTO store (key, value) VALUES (?, ?)", 
                     (key, json.dumps(value)))
        conn.commit()
        conn.close()
        return app.response_class(json.dumps({"status": "success"}), mimetype='application/json')
    except Exception as e:
        return app.response_class(json.dumps({"error": str(e)}), status=500, mimetype='application/json')

if __name__ == '__main__':
    init_db()
    print(f"==================================================")
    print(f" AssetCore Server running correctly!")
    print(f" SQLite Database connected: {DB_FILE}")
    print(f"")
    print(f" -> Open your browser at: http://localhost:{PORT}")
    print(f" -> Default Login: admin / admin123")
    print(f"")
    print(f" Email OTP: Configure SMTP_EMAIL & SMTP_PASSWORD env vars")
    print(f"==================================================")
    app.run(host='0.0.0.0', port=PORT)
