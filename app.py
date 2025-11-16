from flask import Flask, request, jsonify
from flask_cors import CORS
import time

app = Flask(__name__)
CORS(app)  # Allow frontend to call API

messages = []

@app.post("/send")
def send_message():
    data = request.json
    text = data.get("text", "").strip()
    if not text:
        return {"status": "error", "msg": "Empty message"}, 400

    messages.append({"text": text, "time": int(time.time() * 1000)})
    return {"status": "ok"}

@app.get("/messages")
def get_messages():
    return jsonify(messages)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)  # Render uses $PORT, will override
