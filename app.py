from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import os
import time

app = Flask(__name__)
CORS(app)  # allow frontend to access API

# --- DATABASE CONNECTION ---
DATABASE_URL = os.environ.get("DATABASE_URL") or \
    "postgresql://dbforchatapplmao_user:BPDifiqeZjfK2nL22lkk0UQkPgcqHlBs@dpg-d4chpkali9vc73c0p010-a.oregon-postgres.render.com/dbforchatapplmao"

def get_conn():
    return psycopg2.connect(DATABASE_URL)

# --- INIT TABLES ---
def init_db():
    conn = get_conn()
    cur = conn.cursor()
    # Users table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        profile_picture TEXT
    )
    """)
    # Messages table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        from_user INT REFERENCES users(id),
        to_user INT REFERENCES users(id),
        text TEXT,
        timestamp BIGINT
    )
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

# --- USER API ---
@app.post("/register")
def register():
    data = request.json
    username = data.get("username")
    profile_picture = data.get("profile_picture")
    if not username:
        return {"error": "Username required"}, 400

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, profile_picture) VALUES (%s, %s) RETURNING id, username, profile_picture",
            (username, profile_picture)
        )
        user = cur.fetchone()
        conn.commit()
        return {"user": {"id": user[0], "username": user[1], "profile_picture": user[2]}}
    except psycopg2.IntegrityError:
        conn.rollback()
        return {"error": "Username already exists"}, 400
    finally:
        cur.close()
        conn.close()

@app.get("/users")
def search_users():
    q = request.args.get("search", "")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, profile_picture FROM users WHERE username ILIKE %s",
        (f"%{q}%",)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([{"id": r[0], "username": r[1], "profile_picture": r[2]} for r in rows])

# --- MESSAGE API ---
@app.post("/send")
def send_message():
    data = request.json
    from_user = data.get("from_user")
    to_user = data.get("to_user")
    text = data.get("text")
    if not (from_user and to_user and text):
        return {"error": "Missing parameters"}, 400

    timestamp = int(time.time() * 1000)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages (from_user, to_user, text, timestamp) VALUES (%s, %s, %s, %s)",
        (from_user, to_user, text, timestamp)
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "ok"}

@app.get("/messages")
def get_messages():
    user1 = request.args.get("user1")
    user2 = request.args.get("user2")
    if not (user1 and user2):
        return {"error": "Missing user IDs"}, 400

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT m.id, m.from_user, m.to_user, m.text, m.timestamp, u.username, u.profile_picture
        FROM messages m
        JOIN users u ON m.from_user = u.id
        WHERE (from_user=%s AND to_user=%s) OR (from_user=%s AND to_user=%s)
        ORDER BY timestamp ASC
    """, (user1, user2, user2, user1))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    messages = []
    for r in rows:
        messages.append({
            "id": r[0],
            "from_user": r[1],
            "to_user": r[2],
            "text": r[3],
            "timestamp": r[4],
            "from_username": r[5],
            "from_profile": r[6]
        })
    return jsonify(messages)

@app.delete("/messages/<int:msg_id>")
def delete_message(msg_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM messages WHERE id=%s", (msg_id,))
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "deleted"}

# --- RUN SERVER ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
