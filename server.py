import json
import sqlite3
import os
from flask import Flask, request, send_from_directory

app = Flask(__name__, static_folder='public')

PORT = int(os.environ.get('PORT', 8000))
DB_FILE = "database.sqlite"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS store (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    if path == 'api/load':
        return load_data()
    return send_from_directory('public', path)

@app.route('/api/load')
def load_data():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT key, value FROM store")
    rows = c.fetchall()
    conn.close()
    data = {k: json.loads(v) for k, v in rows}
    return app.response_class(json.dumps(data), mimetype='application/json')

@app.route('/api/save', methods=['POST'])
def save_data():
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
    print(f"==================================================")
    app.run(host='0.0.0.0', port=PORT)
