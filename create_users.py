import sqlite3
import hashlib
from datetime import datetime

DB_FILE = "C:/Users/Admingxl2/Downloads/AssetCore_ServerPackage_Updated/database.sqlite"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

conn = sqlite3.connect(DB_FILE)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password_hash TEXT,
    email TEXT,
    role TEXT DEFAULT 'user',
    created_at TEXT
)''')

c.execute('''CREATE TABLE IF NOT EXISTS store (
    key TEXT PRIMARY KEY,
    value TEXT
)''')

c.execute("DELETE FROM users WHERE username IN ('admin', 'user1', 'user2', 'manager', 'technician')")

users = [
    ('admin', 'admin123', 'admin@assetcore.com', 'admin'),
    ('user1', 'user123', 'user1@company.com', 'user'),
    ('user2', 'user123', 'user2@company.com', 'user'),
    ('manager', 'manager123', 'manager@company.com', 'user'),
    ('technician', 'tech123', 'tech@company.com', 'user'),
]

for username, password, email, role in users:
    hashed = hash_password(password)
    c.execute('INSERT INTO users (username, password_hash, email, role, created_at) VALUES (?, ?, ?, ?, ?)',
              (username, hashed, email, role, datetime.now().isoformat()))

conn.commit()
conn.close()

print("=" * 50)
print("USERS CREATED SUCCESSFULLY!")
print("=" * 50)
print()
print("LOGIN CREDENTIALS:")
print("-" * 50)
for username, password, email, role in users:
    print(f"  {role.upper():8} | {username:15} | Password: {password}")
print()
print("=" * 50)
print("Login at: http://localhost:8000")
print("=" * 50)
