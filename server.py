import json
import sqlite3
import os
import secrets
import hashlib
from flask import Flask, request, send_from_directory, session, redirect, jsonify
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

PORT = int(os.environ.get('PORT', 8000))

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_main_db():
    return "main_database.sqlite"

def get_location_db(location_code):
    safe_name = "".join(c for c in location_code if c.isalnum() or c in "_-")
    return f"location_{safe_name}.sqlite"

def init_main_db():
    conn = sqlite3.connect(get_main_db())
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        address TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS location_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        location_code TEXT NOT NULL,
        username TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        email TEXT,
        role TEXT DEFAULT 'user',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(location_code, username)
    )''')
    conn.commit()
    conn.close()

def init_location_db(location_code):
    db_path = get_location_db(location_code)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS store (key TEXT PRIMARY KEY, value TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS location_info (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    conn.close()

def create_default_location():
    conn = sqlite3.connect(get_main_db())
    c = conn.cursor()
    
    locations_data = [
        ('HQ', 'Headquarters', 'Main Office - Chennai'),
        ('CHN', 'Chennai', 'Chennai Branch - Tamil Nadu'),
        ('HSR', 'Hosur', 'Hosur Branch - Krishnagiri District'),
    ]
    
    for code, name, address in locations_data:
        c.execute("SELECT code FROM locations WHERE code = ?", (code,))
        if not c.fetchone():
            c.execute("INSERT INTO locations (code, name, address) VALUES (?, ?, ?)",
                     (code, name, address))
            c.execute("INSERT INTO location_users (location_code, username, password_hash, email, role) VALUES (?, ?, ?, ?, ?)",
                     (code, 'admin', hash_password('admin123'), f'admin@{code.lower()}.com', 'admin'))
            conn.commit()
            
            init_location_db(code)
            
            loc_conn = sqlite3.connect(get_location_db(code))
            loc_c = loc_conn.cursor()
            loc_c.execute("INSERT OR IGNORE INTO store (key, value) VALUES ('location_name', ?)",
                         (json.dumps(name),))
            loc_conn.commit()
            loc_conn.close()
            
            print(f"Location '{name}' ({code}) created - admin/admin123")
    
    conn.close()

init_main_db()
create_default_location()

@app.route('/')
def index():
    if 'username' not in session:
        return redirect('/login.html')
    if 'location_code' not in session:
        return redirect('/select-location.html')
    return send_from_directory('public', 'index.html')

@app.route('/login.html')
def login_page():
    if 'username' in session:
        if 'location_code' not in session:
            return send_from_directory('public', 'select-location.html')
        return redirect('/')
    return send_from_directory('public', 'login.html')

@app.route('/select-location.html')
def select_location_page():
    return send_from_directory('public', 'select-location.html')

@app.route('/api/locations', methods=['GET'])
def get_locations():
    conn = sqlite3.connect(get_main_db())
    c = conn.cursor()
    c.execute("SELECT code, name, address FROM locations ORDER BY name")
    locations = [{"code": r[0], "name": r[1], "address": r[2]} for r in c.fetchall()]
    conn.close()
    return jsonify(locations)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    location = data.get('location', '').strip().upper()
    
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    
    conn = sqlite3.connect(get_main_db())
    c = conn.cursor()
    c.execute("SELECT password_hash, role FROM location_users WHERE username = ? AND location_code = ?",
              (username, location))
    row = c.fetchone()
    conn.close()
    
    if row and row[0] == hash_password(password):
        session['username'] = username
        session['location_code'] = location
        session['role'] = row[1]
        
        loc_conn = sqlite3.connect(get_location_db(location))
        loc_c = loc_conn.cursor()
        loc_c.execute("SELECT value FROM store WHERE key = 'location_name'")
        name_row = loc_c.fetchone()
        session['location_name'] = json.loads(name_row[0]) if name_row else location
        loc_conn.close()
        
        return jsonify({"status": "success", "username": username, "location": location})
    
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"status": "success"})

@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    if 'username' in session:
        return jsonify({
            "authenticated": True, 
            "username": session['username'],
            "location": session.get('location_code', ''),
            "location_name": session.get('location_name', ''),
            "role": session.get('role', 'user')
        })
    return jsonify({"authenticated": False})

@app.route('/api/change-password', methods=['POST'])
def change_password():
    if 'username' not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    data = request.get_json()
    current = data.get('currentPassword', '')
    new_pass = data.get('newPassword', '')
    
    if not current or not new_pass:
        return jsonify({"error": "All fields required"}), 400
    
    conn = sqlite3.connect(get_main_db())
    c = conn.cursor()
    c.execute("SELECT password_hash FROM location_users WHERE username = ? AND location_code = ?",
              (session['username'], session['location_code']))
    row = c.fetchone()
    
    if not row or row[0] != hash_password(current):
        conn.close()
        return jsonify({"error": "Current password incorrect"}), 400
    
    c.execute("UPDATE location_users SET password_hash = ? WHERE username = ? AND location_code = ?",
              (hash_password(new_pass), session['username'], session['location_code']))
    conn.commit()
    conn.close()
    
    return jsonify({"status": "success"})

@app.route('/api/users', methods=['GET', 'POST', 'PUT', 'DELETE'])
def manage_users():
    if 'username' not in session or session.get('role') != 'admin':
        return jsonify({"error": "Admin access required"}), 403
    
    conn = sqlite3.connect(get_main_db())
    c = conn.cursor()
    
    if request.method == 'GET':
        c.execute("SELECT id, username, email, role, created_at FROM location_users WHERE location_code = ?",
                  (session['location_code'],))
        users = [{"id": r[0], "username": r[1], "email": r[2], "role": r[3], "created_at": r[4]} 
                 for r in c.fetchall()]
        conn.close()
        return jsonify(users)
    
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        email = data.get('email', '').strip()
        role = data.get('role', 'user')
        
        if not username or not password:
            conn.close()
            return jsonify({"error": "Username and password required"}), 400
        
        c.execute("SELECT id FROM location_users WHERE username = ? AND location_code = ?",
                  (username, session['location_code']))
        if c.fetchone():
            conn.close()
            return jsonify({"error": "User already exists"}), 400
        
        c.execute("INSERT INTO location_users (location_code, username, password_hash, email, role) VALUES (?, ?, ?, ?, ?)",
                 (session['location_code'], username, hash_password(password), email, role))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    
    if request.method == 'PUT':
        data = request.get_json()
        user_id = data.get('id')
        new_password = data.get('newPassword', '')
        new_role = data.get('role')
        
        if new_password:
            c.execute("UPDATE location_users SET password_hash = ? WHERE id = ? AND location_code = ?",
                     (hash_password(new_password), user_id, session['location_code']))
        
        if new_role:
            c.execute("UPDATE location_users SET role = ? WHERE id = ? AND location_code = ?",
                     (new_role, user_id, session['location_code']))
        
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    
    if request.method == 'DELETE':
        user_id = request.args.get('id')
        c.execute("DELETE FROM location_users WHERE id = ? AND location_code = ? AND role != 'admin'",
                 (user_id, session['location_code']))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})

@app.route('/api/all-locations', methods=['GET', 'POST', 'DELETE'])
def manage_locations():
    if 'username' not in session or session.get('role') != 'admin':
        return jsonify({"error": "Admin access required"}), 403
    
    conn = sqlite3.connect(get_main_db())
    c = conn.cursor()
    
    if request.method == 'GET':
        c.execute("SELECT code, name, address, created_at FROM locations ORDER BY name")
        locations = [{"code": r[0], "name": r[1], "address": r[2], "created_at": r[3]} for r in c.fetchall()]
        conn.close()
        return jsonify(locations)
    
    if request.method == 'POST':
        data = request.get_json()
        code = data.get('code', '').strip().upper()
        name = data.get('name', '').strip()
        address = data.get('address', '').strip()
        
        if not code or not name:
            conn.close()
            return jsonify({"error": "Code and name required"}), 400
        
        c.execute("SELECT id FROM locations WHERE code = ?", (code,))
        if c.fetchone():
            conn.close()
            return jsonify({"error": "Location code already exists"}), 400
        
        c.execute("INSERT INTO locations (code, name, address) VALUES (?, ?, ?)", (code, name, address))
        conn.commit()
        conn.close()
        
        init_location_db(code)
        
        loc_conn = sqlite3.connect(get_location_db(code))
        loc_c = loc_conn.cursor()
        loc_c.execute("INSERT INTO store (key, value) VALUES ('location_name', ?)",
                     (json.dumps(name),))
        loc_c.execute("INSERT INTO location_users (location_code, username, password_hash, email, role) VALUES (?, ?, ?, ?, ?)",
                     (code, 'admin', hash_password('admin123'), f'admin@{code.lower()}.com', 'admin'))
        loc_conn.commit()
        loc_conn.close()
        
        return jsonify({"status": "success", "code": code})
    
    if request.method == 'DELETE':
        code = request.args.get('code')
        if code == 'HQ':
            conn.close()
            return jsonify({"error": "Cannot delete default HQ location"}), 400
        
        c.execute("DELETE FROM locations WHERE code = ?", (code,))
        c.execute("DELETE FROM location_users WHERE location_code = ?", (code,))
        conn.commit()
        conn.close()
        
        try:
            os.remove(get_location_db(code))
        except:
            pass
        
        return jsonify({"status": "success"})

@app.route('/api/load')
def load_data():
    if 'username' not in session or 'location_code' not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    conn = sqlite3.connect(get_location_db(session['location_code']))
    c = conn.cursor()
    c.execute("SELECT key, value FROM store")
    rows = c.fetchall()
    conn.close()
    data = {k: json.loads(v) for k, v in rows}
    return jsonify(data)

@app.route('/api/save', methods=['POST'])
def save_data():
    if 'username' not in session or 'location_code' not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        data = request.get_json()
        conn = sqlite3.connect(get_location_db(session['location_code']))
        c = conn.cursor()
        for key, value in data.items():
            c.execute("INSERT OR REPLACE INTO store (key, value) VALUES (?, ?)", 
                     (key, json.dumps(value)))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/<path:path>')
def serve_static(path):
    if 'username' not in session:
        if path not in ['login.html', 'select-location.html']:
            return redirect('/login.html')
    return send_from_directory('public', path)

if __name__ == '__main__':
    print(f"==================================================")
    print(f" AssetCore Multi-Location Server")
    print(f" SQLite Database System")
    print(f"")
    print(f" -> Open browser at: http://localhost:{PORT}")
    print(f"")
    print(f" DEFAULT CREDENTIALS PER LOCATION:")
    print(f" ----------------------------------------")
    print(f" HQ (Headquarters)  | admin / admin123")
    print(f" ----------------------------------------")
    print(f"==================================================")
    app.run(host='0.0.0.0', port=PORT)
