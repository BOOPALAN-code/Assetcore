import json
import sqlite3
import os
import secrets
import hashlib
from flask import Flask, request, send_from_directory, session, redirect, url_for
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

PORT = int(os.environ.get('PORT', 8000))
DB_FILE = "database.sqlite"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS store (key TEXT PRIMARY KEY, value TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash TEXT, created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY, username TEXT, expires_at TEXT)")
    conn.commit()
    
    c.execute("SELECT username FROM users WHERE username = 'admin'")
    if not c.fetchone():
        hashed = hashlib.sha256("admin123".encode()).hexdigest()
        c.execute("INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                  ("admin", hashed, datetime.now().isoformat()))
        conn.commit()
        print("Default admin created: admin / admin123")
    
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/')
def index():
    if 'username' not in session:
        return send_from_directory('public', 'login.html')
    return send_from_directory('public', 'index.html')

@app.route('/login.html')
def login_page():
    if 'username' in session:
        return redirect('/')
    return send_from_directory('public', 'login.html')

@app.route('/<path:path>')
def serve_static(path):
    if 'username' not in session and path != 'login.html':
        return redirect('/login.html')
    
    if path == 'api/login':
        return login()
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
    
    return send_from_directory('public', path)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return app.response_class(json.dumps({"error": "Username and password required"}), 
                                status=400, mimetype='application/json')
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    
    if row and row[0] == hash_password(password):
        session['username'] = username
        return app.response_class(json.dumps({"status": "success", "username": username}), 
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
        return app.response_class(json.dumps({"authenticated": True, "username": session['username']}), 
                                mimetype='application/json')
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

@app.route('/api/users', methods=['GET', 'POST', 'DELETE'])
def manage_users():
    if 'username' not in session:
        return app.response_class(json.dumps({"error": "Not authenticated"}), 
                                status=401, mimetype='application/json')
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    if request.method == 'GET':
        c.execute("SELECT username, created_at FROM users")
        users = [{"username": u[0], "created_at": u[1]} for u in c.fetchall()]
        conn.close()
        return app.response_class(json.dumps(users), mimetype='application/json')
    
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            conn.close()
            return app.response_class(json.dumps({"error": "Username and password required"}), 
                                    status=400, mimetype='application/json')
        
        c.execute("SELECT username FROM users WHERE username = ?", (username,))
        if c.fetchone():
            conn.close()
            return app.response_class(json.dumps({"error": "User already exists"}), 
                                    status=400, mimetype='application/json')
        
        c.execute("INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                  (username, hash_password(password), datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return app.response_class(json.dumps({"status": "success"}), mimetype='application/json')
    
    if request.method == 'DELETE':
        username = request.args.get('username')
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
    print(f"==================================================")
    app.run(host='0.0.0.0', port=PORT)
