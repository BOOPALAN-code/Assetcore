import json
import sqlite3
import os
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = 8000
DB_FILE = "database.sqlite"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Simple JSON document store
    c.execute("CREATE TABLE IF NOT EXISTS store (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    conn.close()

class AssetCoreServer(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/load':
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT key, value FROM store")
            rows = c.fetchall()
            conn.close()
            
            data = {k: json.loads(v) for k, v in rows}
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
        else:
            # Default to index.html
            if self.path == '/':
                self.path = '/public/index.html'
            super().do_GET()

    def do_POST(self):
        if self.path == '/api/save':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                for key, value in data.items():
                    c.execute("INSERT OR REPLACE INTO store (key, value) VALUES (?, ?)", 
                             (key, json.dumps(value)))
                conn.commit()
                conn.close()
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success"}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        else:
            self.send_error(404, "Not Found")

if __name__ == '__main__':
    init_db()
    print(f"==================================================")
    print(f" AssetCore Server running correctly!")
    print(f" SQLite Database connected: {DB_FILE}")
    print(f"")
    print(f" -> Open your browser at: http://localhost:{PORT}")
    print(f"==================================================")
    HTTPServer(('', PORT), AssetCoreServer).serve_forever()
