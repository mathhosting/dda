from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import os, time, uuid, bcrypt

app = Flask(__name__)
CORS(app)

# ---------- DATABASE CONNECTION ----------
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL)

# ---------- SESSIONS (TOKEN AUTH) ----------
sessions = {}  # token: user_id

def get_user_by_token(token):
    user_id = sessions.get(token)
    if not user_id:
        return None
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, username, profile_picture FROM users WHERE id=%s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    if user:
        return {"id": user[0], "username": user[1], "profile_picture": user[2]}
    return None

# ---------- INITIALIZE DATABASE ----------
def init_db():
    conn = get_conn()
    cur = conn.cursor()
    # Users table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
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

# ---------- REGISTER ----------
@app.post("/register")
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    profile_picture = data.get("profile_picture")
    if not username or not password:
        return {"error": "Username and password required"}, 400

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, password, profile_picture) VALUES (%s,%s,%s) RETURNING id, username, profile_picture",
            (username, hashed.decode(), profile_picture)
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

# ---------- LOGIN ----------
@app.post("/login")
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return {"error": "Username and password required"}, 400

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, password, username, profile_picture FROM users WHERE username=%s", (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user:
        return {"error": "Invalid username or password"}, 400
    if not bcrypt.checkpw(password.encode(), user[1].encode()):
        return {"error": "Invalid username or password"}, 400

    token = str(uuid.uuid4())
    sessions[token] = user[0]
    return {"token": token, "user": {"id": user[0], "username": user[2], "profile_picture": user[3]}}

# ---------- LOGOUT ----------
@app.post("/logout")
def logout():
    token = request.headers.get("Authorization")
    if token in sessions:
        del sessions[token]
    return {"status": "logged out"}

# ---------- SEARCH USERS ----------
@app.get("/users")
def search_users():
    token = request.headers.get("Authorization")
    if not get_user_by_token(token):
        return {"error": "Unauthorized"}, 401

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

# ---------- SEND MESSAGE ----------
@app.post("/send")
def send_message():
    token = request.headers.get("Authorization")
    user = get_user_by_token(token)
    if not user:
        return {"error": "Unauthorized"}, 401

    data = request.json
    to_user = data.get("to_user")
    text = data.get("text")
    if not to_user or not text:
        return {"error": "Missing parameters"}, 400

    timestamp = int(time.time() * 1000)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages (from_user, to_user, text, timestamp) VALUES (%s,%s,%s,%s)",
        (user['id'], to_user, text, timestamp)
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "ok"}

# ---------- GET MESSAGES BETWEEN TWO USERS ----------
@app.get("/messages")
def get_messages():
    token = request.headers.get("Authorization")
    user = get_user_by_token(token)
    if not user:
        return {"error": "Unauthorized"}, 401

    other_id = request.args.get("user2")
    if not other_id:
        return {"error": "Missing user ID"}, 400

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT m.id, m.from_user, m.to_user, m.text, m.timestamp, u.username, u.profile_picture
        FROM messages m
        JOIN users u ON m.from_user = u.id
        WHERE (from_user=%s AND to_user=%s) OR (from_user=%s AND to_user=%s)
        ORDER BY timestamp ASC
    """, (user['id'], other_id, other_id, user['id']))
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

# ---------- DELETE MESSAGE ----------
@app.delete("/messages/<int:msg_id>")
def delete_message(msg_id):
    token = request.headers.get("Authorization")
    user = get_user_by_token(token)
    if not user:
        return {"error": "Unauthorized"}, 401

    conn = get_conn()
    cur = conn.cursor()
    # Only allow deleting messages sent by this user
    cur.execute("DELETE FROM messages WHERE id=%s AND from_user=%s", (msg_id, user['id']))
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "deleted"}

# ---------- RUN SERVER ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
