from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import os
import time

app = Flask(__name__)
CORS(app)

# Get DB URL from environment variable or use your string
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL)

# Initialize tables if they don't exist
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
