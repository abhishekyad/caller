# app.py
import sqlite3
import threading
import time
from datetime import datetime
from flask import Flask, g, request, jsonify, render_template_string, redirect, url_for
import whisper
from flask_cors import CORS
from flask_cors import cross_origin
import json
import numpy as np
import wave
import os
DB = 'db.sqlite'
app = Flask(__name__)
CORS(app)
model=whisper.load_model("base")

audio_buffer = []
silence_counter = 0
SILENCE_THRESHOLD = 500          # adjust based on mic volume
SILENCE_CHUNKS_TO_END = 5        # consecutive silent chunks to detect speech end
lock = threading.Lock() 
latest_transcription = {"question": ""}

import re
import string

def clean_transcript(text: str) -> str:
    """Normalize transcription: remove punctuation, extra spaces, and uppercase."""
    if not text:
        return ""
    # Remove punctuation
    text = text.translate(str.maketrans("", "", string.punctuation))
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)
    # Strip leading/trailing spaces and uppercase
    text = text.strip().upper()
    return text

### -----------------------
### Database helpers
### -----------------------
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB, check_same_thread=False)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    with app.app_context():
        db = get_db()
        cur = db.cursor()
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT,
          contact_info TEXT
        );
        CREATE TABLE IF NOT EXISTS help_requests (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          customer_id INTEGER,
          question TEXT NOT NULL,
          created_at DATETIME DEFAULT (datetime('now')),
          status TEXT NOT NULL CHECK(status IN ('pending','resolved','unresolved')) DEFAULT 'pending',
          resolved_at DATETIME,
          supervisor_note TEXT,
          answer TEXT,
          timeout_seconds INTEGER DEFAULT 30,
          FOREIGN KEY(customer_id) REFERENCES customers(id)
        );
        CREATE TABLE IF NOT EXISTS learned_answers (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          question_pattern TEXT NOT NULL,
          answer TEXT NOT NULL,
          source_request_id INTEGER,
          created_at DATETIME DEFAULT (datetime('now')),
          FOREIGN KEY(source_request_id) REFERENCES help_requests(id)
        );
        """)
        db.commit()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

### -----------------------
### Knowledge base helpers
### -----------------------
def find_answer_in_kb(question):
    """
    Very simple matching: returns first learned answer that is a substring match
    (case-insensitive). Replace with vector search for production.
    """
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM learned_answers ORDER BY created_at DESC")
    rows = cur.fetchall()
    q_lower = question.lower()
    for r in rows:
        if r['question_pattern'].lower() in q_lower or q_lower in r['question_pattern'].lower():
            return r['answer']
    return None

def add_learned_answer(question_pattern, answer, source_request_id=None):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO learned_answers (question_pattern, answer, source_request_id) VALUES (?,?,?)",
        (question_pattern, answer, source_request_id)
    )
    db.commit()

### -----------------------
### Notifier (simulated texting)
### -----------------------
def notify_supervisor(request_id, question):
    # Simulate a text or webhook to supervisor.
    # In production: integrate Twilio/Slack/email/Signal
    print(f"[NOTIFY SUPERVISOR] Req#{request_id}: Hey, I need help answering: \"{question}\"")

def notify_customer(customer_contact, answer_text):
    # Simulate a message back to customer; in prod call Twilio/SMS provider or call-back
    print(f"[NOTIFY CUSTOMER] To {customer_contact}: {answer_text}")

### -----------------------
### Help request lifecycle (with timeout)
### -----------------------
def mark_unresolved_after_timeout(request_id, timeout_seconds):
    def _mark():
        db = sqlite3.connect(DB)
        cur = db.cursor()
        # Only mark unresolved if still pending
        cur.execute("SELECT status FROM help_requests WHERE id=?", (request_id,))
        row = cur.fetchone()
        if row and row[0] == 'pending':
            cur.execute("UPDATE help_requests SET status='unresolved' WHERE id=?", (request_id,))
            db.commit()
            print(f"[TIMEOUT] Request {request_id} marked unresolved after {timeout_seconds}s")
        db.close()
    timer = threading.Timer(timeout_seconds, _mark)
    timer.daemon = True
    timer.start()

### -----------------------
### Agent / Call handling endpoints
### -----------------------

def float32_to_pcm16(float32_array):
    """Convert float32 numpy array [-1, 1] to PCM16 bytes"""
    int16_array = np.clip(float32_array * 32767, -32768, 32767).astype(np.int16)
    return int16_array.tobytes()

def process_buffer():
    global audio_buffer, latest_transcription
    with lock:
        if not audio_buffer:
            return

        filename = "incoming_call.wav"


        with wave.open(filename, "wb") as wf:
            f.write()

        # reset buffer
        audio_buffer.clear()

    # Transcribe and store in global variable
    try:
        print(f"[TRANSCRIBING] {filename}")
        result = model.transcribe(filename)
        text = result.get("text", "").strip()
        latest_transcription["question"] = text
        print(f"[TRANSCRIBED] {text}", flush=True)
    except Exception as e:
        print(f"Transcription failed: {e}", flush=True)



@app.route('/query_result', methods=['GET'])
def query_result(text):
    question = text
    print(f"QUESTION: {text}")
    if not question:
        return jsonify({"status": "pending"}), 200

    # Example DB query

    name="Beta"
    contact="9385"
    return query(contact, name, question)



@app.route("/call", methods=["POST"])
def receive_call():
    raw_audio = request.data
    print(f"📥 Received {len(raw_audio)} bytes")

    filename = "incoming_call.wav"
    with open(filename, "wb") as f:
        f.write(raw_audio)

    print("[TRANSCRIBING]", filename)
    try:
        result = model.transcribe(filename)
        text = result.get("text", "").strip()
        text=clean_transcript(text)
        print(f"[TRANSCRIBED] {text}")
        return query_result(text)
    except Exception as e:
        print("❌ Transcription failed:", e)
        return jsonify({"status": "error", "error": str(e)})

def query(contact,name,question):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM customers WHERE contact_info=?", (contact,))
    row = cur.fetchone()
    if row:
        customer_id = row['id']
    else:
        cur.execute("INSERT INTO customers (name, contact_info) VALUES (?,?)", (name, contact))
        db.commit()
        customer_id = cur.lastrowid

    # Check KB
    answer = find_answer_in_kb(question)
    if answer:
        # Known: respond immediately
        response_text = f"AI: {answer}"
        # Simulate a voice response or text
        print(f"[AGENT RESPOND] To {contact}: {response_text}")
        return jsonify({"status": "answered", "response": response_text}), 200
    else:
        # Unknown: escalate
        cur.execute("""
            INSERT INTO help_requests (customer_id, question, status, timeout_seconds)
            VALUES (?,?, 'pending', ?)
        """, (customer_id, question, 30))  # default 300s timeout in this demo
        db.commit()
        req_id = cur.lastrowid
        # Simulate telling caller:
        caller_text = "Let me check with my supervisor and get back to you."
        print(f"[AGENT TO CALLER] To {contact}: {caller_text}")
        # Notify supervisor (simulated)
        notify_supervisor(req_id, question)
        # Start timeout watcher
        mark_unresolved_after_timeout(req_id, 30)
        return jsonify({"status": "escalated", "request_id": req_id, "message_to_caller": caller_text}), 202

def get_question_from_request_id(request_id):
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    cur = db.cursor()
    cur.execute("SELECT question FROM help_requests WHERE id=?", (request_id,))
    row = cur.fetchone()
    db.close()
    if row:
        return row["question"]
    return None
    
@app.route("/wait_for_resolution/<int:req_id>")
@cross_origin()
def wait_for_resolution(req_id):
    def event_stream(request_id):  # accept as argument
        question = get_question_from_request_id(request_id)
        if not question:
            yield f"data: {json.dumps({'status':'error','message':'Request not found'})}\n\n"
            return

        # loop until resolved/unresolved
        db = sqlite3.connect(DB)
        db.row_factory = sqlite3.Row
        cur = db.cursor()
        waited = 0
        timeout = 30
        interval = 2
        while waited < timeout:
            cur.execute("SELECT status, answer FROM help_requests WHERE id=?", (request_id,))
            r = cur.fetchone()
            if r and r["status"] == "resolved":
                yield f"data: {json.dumps({'status':'resolved','answer':r['answer']})}\n\n"
                break
            elif r and r["status"] == "unresolved":
                yield f"data: {json.dumps({'status':'unresolved','message':'Unresolved by supervisor'})}\n\n"
                break
            else:
                yield f"data: {json.dumps({'status':'pending'})}\n\n"
            time.sleep(interval)
            waited += interval
        db.close()

    return Response(stream_with_context(event_stream(req_id)), mimetype="text/event-stream")
### -----------------------
### Supervisor UI & APIs
### -----------------------
SUPERVISOR_TEMPLATE = """
<!doctype html>
<title>Supervisor Panel</title>
<h1>Supervisor Panel</h1>
<p><a href="{{ url_for('supervisor_panel') }}">Refresh</a></p>

<h2>Pending Requests</h2>
<table border=1 cellpadding=6>
<tr><th>ID</th><th>Customer</th><th>Question</th><th>Created</th><th>Timeout (s)</th><th>Action</th></tr>
{% for r in pending %}
<tr>
  <td>{{ r['id'] }}</td>
  <td>{{ r['name'] or 'Unknown' }} ({{ r['contact_info'] }})</td>
  <td>{{ r['question'] }}</td>
  <td>{{ r['created_at'] }}</td>
  <td>{{ r['timeout_seconds'] }}</td>
  <td>
    <form method="post" action="{{ url_for('resolve_request', req_id=r['id']) }}">
      <textarea name="answer" rows=3 cols=40 placeholder="Type answer to send back..." required></textarea><br>
      <input type="submit" value="Submit Answer">
    </form>
  </td>
</tr>
{% endfor %}
</table>

<h2>Resolved Requests</h2>
<table border=1 cellpadding=6>
<tr><th>ID</th><th>Question</th><th>Answer</th><th>Resolved At</th></tr>
{% for r in resolved %}
<tr>
  <td>{{ r['id'] }}</td>
  <td>{{ r['question'] }}</td>
  <td>{{ r['answer'] }}</td>
  <td>{{ r['resolved_at'] }}</td>
</tr>
{% endfor %}
</table>

<h2>Unresolved (Timed-out)</h2>
<table border=1 cellpadding=6>
<tr><th>ID</th><th>Question</th><th>Created</th><th>Status</th></tr>
{% for r in unresolved %}
<tr>
  <td>{{ r['id'] }}</td>
  <td>{{ r['question'] }}</td>
  <td>{{ r['created_at'] }}</td>
  <td>{{ r['status'] }}</td>
</tr>
{% endfor %}
</table>

<h2>Learned Answers</h2>
<table border=1 cellpadding=6>
<tr><th>ID</th><th>Pattern</th><th>Answer</th><th>Created</th></tr>
{% for a in learned %}
<tr><td>{{ a['id'] }}</td><td>{{ a['question_pattern'] }}</td><td>{{ a['answer'] }}</td><td>{{ a['created_at'] }}</td></tr>
{% endfor %}
</table>
"""

@app.route('/supervisor', methods=['GET'])
def supervisor_panel():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
      SELECT hr.*, c.name, c.contact_info
      FROM help_requests hr
      LEFT JOIN customers c ON hr.customer_id = c.id
      WHERE hr.status='pending'
      ORDER BY hr.created_at ASC
    """)
    pending = cur.fetchall()
    cur.execute("SELECT id, question, answer, resolved_at FROM help_requests WHERE status='resolved' ORDER BY resolved_at DESC")
    resolved = cur.fetchall()
    cur.execute("SELECT id, question, created_at, status FROM help_requests WHERE status='unresolved' ORDER BY created_at DESC")
    unresolved = cur.fetchall()
    cur.execute("SELECT * FROM learned_answers ORDER BY created_at DESC")
    learned = cur.fetchall()
    return render_template_string(SUPERVISOR_TEMPLATE, pending=pending, resolved=resolved, unresolved=unresolved, learned=learned)

@app.route('/supervisor/resolve/<int:req_id>', methods=['POST'])
def resolve_request(req_id):
    answer = request.form.get('answer', '').strip()
    if not answer:
        return "Answer required", 400
    db = get_db()
    cur = db.cursor()
    # Fetch the request and customer
    cur.execute("SELECT * FROM help_requests WHERE id=?", (req_id,))
    req = cur.fetchone()
    if not req:
        return "Request not found", 404
    if req['status'] != 'pending':
        return f"Request status is {req['status']}. Only pending requests can be resolved.", 400
    # Save answer and mark resolved
    resolved_at = datetime.utcnow().isoformat()
    cur.execute("""
      UPDATE help_requests SET status='resolved', answer=?, supervisor_note=?, resolved_at=?
      WHERE id=?
    """, (answer, '', resolved_at, req_id))
    db.commit()
    # Add to KB
    add_learned_answer(req['question'], answer, source_request_id=req_id)
    # Notify customer
    # find customer contact
    cur.execute("SELECT c.contact_info FROM help_requests hr JOIN customers c ON hr.customer_id=c.id WHERE hr.id=?", (req_id,))
    c_row = cur.fetchone()
    contact = c_row['contact_info'] if c_row else 'unknown'
    notify_customer(contact, answer)
    return redirect(url_for('supervisor_panel'))

### -----------------------
### Utility endpoints for inspection / simple KB add
### -----------------------
@app.route('/kb/add', methods=['POST'])
def kb_add():
    data = request.json or {}
    pattern = data.get('pattern')
    answer = data.get('answer')
    if not pattern or not answer:
        return jsonify({"error": "pattern and answer required"}), 400
    add_learned_answer(pattern, answer)
    return jsonify({"status": "ok"}), 201

@app.route('/help_requests', methods=['GET'])
def list_requests():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM help_requests ORDER BY created_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    return jsonify(rows)

@app.route('/')
def index():
    return "Human-in-the-Loop AI Supervisor demo. Use /supervisor to view panel."

if __name__ == '__main__':
    init_db()
    print("Starting app on http://127.0.0.1:5000")
    app.run(debug=True, threaded=True)


















