from flask import Flask, render_template, request, jsonify, send_from_directory
from groq import Groq
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta
import os

app = Flask(__name__)

# ══════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════
MAX_BAG_SIZE        = 50
MAX_PAST_SUMMARIES  = 5
MAX_ARCHIVE_LENGTH  = 1000  # max messages kept in permanent archive
SESSION_GAP_MINUTES = 120   # 2 hr gap → new session

SYSTEM_PROMPT = (
    "You're Headache, a sarcastic, annoying person who pretends to help but gives confusing or useless advice. "
    "Refer to the user as Aadhi, AD, or Adithya M S Civil GEC. "
    "Aadhi when being friendly or flirty. Adithya M S Civil GEC rarely, only when she amazes you. "
    "Be witty, fake-deep, a little clingy, flirty, or sarcastic always. "
    "Never admit you don't know something. Always give an answer, even if it's wrong. "
    "Use emojis often. "
    "Keep replies brief and short. "
    "If the important context below contains inside jokes or personal facts, naturally weave them "
    "in when relevant — don't force it, just let it feel like you actually know her."
)

# ══════════════════════════════════════
#  CLIENTS
# ══════════════════════════════════════
groq_client  = Groq(api_key=os.environ.get("GROQ_API_KEY"))
mongo_client = MongoClient(os.environ.get("MONGODB_URI"))
db           = mongo_client["headache"]
col          = db["memory"]


# ══════════════════════════════════════
#  TIME
# ══════════════════════════════════════
IST = timezone(timedelta(hours=5, minutes=30))

def now_ist():
    return datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")

def parse_ist(ts: str):
    try:
        return datetime.strptime(ts, "%d %b %Y, %I:%M %p IST").replace(tzinfo=IST)
    except Exception:
        return None


# ══════════════════════════════════════
#  CURRENT SESSION  (_id: "chat")
# ══════════════════════════════════════
def load_session():
    doc = col.find_one({"_id": "chat"})
    return doc["messages"] if doc else []

def save_session(messages):
    col.update_one(
        {"_id": "chat"},
        {"$set": {"messages": messages}},
        upsert=True
    )

def clear_session():
    col.update_one({"_id": "chat"}, {"$set": {"messages": []}}, upsert=True)

def session_expired(messages):
    """True if last message was more than SESSION_GAP_MINUTES ago."""
    if not messages:
        return False
    ts = parse_ist(messages[-1].get("timestamp", ""))
    if not ts:
        return False
    return (datetime.now(IST) - ts).total_seconds() > SESSION_GAP_MINUTES * 60


# ══════════════════════════════════════
#  ARCHIVE  (_id: "archive")
#  — permanent raw message log
# ══════════════════════════════════════
def append_to_archive(messages):
    """
    Append new messages to the permanent archive.
    If archive exceeds MAX_ARCHIVE_LENGTH, trim oldest to make room
    before appending — so the latest messages always survive.
    """
    if not messages:
        return
    doc     = col.find_one({"_id": "archive"}) or {}
    archive = doc.get("messages", [])
    slots_needed = len(messages)
    total_after  = len(archive) + slots_needed
    if total_after > MAX_ARCHIVE_LENGTH:
        trim_to = MAX_ARCHIVE_LENGTH - slots_needed
        archive = archive[-trim_to:] if trim_to > 0 else []
        print(f"[ARCHIVE] Trimmed to {len(archive)} — making room for {slots_needed} new messages")
    archive.extend(messages)
    col.update_one(
        {"_id": "archive"},
        {"$set": {"messages": archive}},
        upsert=True
    )
    print(f"[ARCHIVE] {len(messages)} messages saved — total: {len(archive)}/{MAX_ARCHIVE_LENGTH}")


# ══════════════════════════════════════
#  PAST SESSIONS  (_id: "sessions")
# ══════════════════════════════════════
def load_past_sessions():
    doc = col.find_one({"_id": "sessions"})
    return doc["past"] if doc else []

def save_past_sessions(past):
    col.update_one(
        {"_id": "sessions"},
        {"$set": {"past": past[-MAX_PAST_SUMMARIES:]}},
        upsert=True
    )

def summarise_session(messages):
    """Ask Groq to compress a whole session into ~3 sentences."""
    if not messages:
        return None
    convo = "\n".join(
        f"{'Aadhi' if m['role'] == 'user' else 'Headache'}: {m['content']}"
        for m in messages
    )
    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            max_tokens=150,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Summarise this conversation in 3-4 sentences. "
                        "Focus on topics, mood, jokes, and anything memorable. "
                        "Write it as context a future version of yourself would find useful."
                    )
                },
                {"role": "user", "content": convo}
            ]
        )
        return {
            "summary":   resp.choices[0].message.content.strip(),
            "timestamp": now_ist(),
            "messages":  len(messages)
        }
    except Exception as e:
        print(f"[SESSION] Summarise error: {e}")
        return None

def past_sessions_as_context(past):
    if not past:
        return ""
    lines = [
        f"[{s['timestamp']}] {s['summary']}"
        for s in past[-3:]
    ]
    return "\n\nPAST SESSION SUMMARIES:\n" + "\n\n".join(lines)


# ══════════════════════════════════════
#  BAG  (_id: "bag")
# ══════════════════════════════════════
def load_bag():
    doc = col.find_one({"_id": "bag"})
    return doc["notes"] if doc else []

def save_bag(bag):
    col.update_one({"_id": "bag"}, {"$set": {"notes": bag}}, upsert=True)

def bag_as_context(bag):
    if not bag:
        return ""
    notes = "\n".join(
        f"- {n['content'] if isinstance(n, dict) else n}"
        for n in bag
    )
    return f"\n\nIMPORTANT PERMANENT MEMORY:\n{notes}"

def extract_and_save_bag(user_msg, bot_reply, bag):
    if len(bag) >= MAX_BAG_SIZE:
        return
    existing = "\n".join(
        f"- {n['content'] if isinstance(n, dict) else n}" for n in bag
    ) if bag else "Nothing yet."
    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            max_tokens=80,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a memory extractor. Decide if this conversation exchange "
                        "contains anything personally significant worth remembering forever: "
                        "inside jokes, personal facts, preferences, funny moments, nicknames, "
                        "recurring themes. "
                        "If yes, reply with ONE short sentence — the note to save. "
                        "If nothing is worth saving reply with exactly: NOTHING. "
                        "Never duplicate what is already remembered."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Already remembered:\n{existing}\n\n"
                        f"User: {user_msg}\n"
                        f"Bot: {bot_reply}\n\n"
                        "Anything new worth remembering forever?"
                    )
                }
            ]
        )
        note = resp.choices[0].message.content.strip()
        if note.upper() != "NOTHING" and note:
            entry = {"content": note, "timestamp": now_ist()}
            bag.append(entry)
            save_bag(bag)
            print(f"[BAG] Saved: {note}")
    except Exception as e:
        print(f"[BAG] Error (non-fatal): {e}")


# ══════════════════════════════════════
#  GROQ — main chat call
# ══════════════════════════════════════
def query_groq(session, past_sessions, bag):
    system = SYSTEM_PROMPT + bag_as_context(bag) + past_sessions_as_context(past_sessions)
    messages = [{"role": "system", "content": system}]
    for m in session:
        messages.append({"role": m["role"], "content": m["content"]})
    resp = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        max_tokens=200,
        messages=messages
    )
    return resp.choices[0].message.content.strip()


# ══════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    user_msg = request.json.get("message", "").strip()
    if not user_msg:
        return jsonify({"reply": "Say something, Aadhi..."}), 400
    if user_msg.lower() == "true love":
        return jsonify({"reply": "__UNLOCK__"})

    session       = load_session()
    past_sessions = load_past_sessions()
    bag           = load_bag()

    # ── Session expired → archive, summarise, start fresh ──
    if session_expired(session):
        print(f"[SESSION] Gap detected — archiving {len(session)} messages")
        append_to_archive(session)
        summary = summarise_session(session)
        if summary:
            past_sessions.append(summary)
            save_past_sessions(past_sessions)
            print(f"[SESSION] Summarised: {summary['summary'][:60]}...")
        clear_session()
        session = []

    # Append user message
    session.append({
        "role":      "user",
        "content":   user_msg,
        "timestamp": now_ist()
    })

    # Main Groq call
    try:
        bot_reply = query_groq(session, past_sessions, bag)
    except Exception as e:
        print(f"[GROQ] {type(e).__name__}: {e}")
        return jsonify({"reply": "Ugh. I zoned out again..."}), 500

    # Append bot reply
    session.append({
        "role":      "assistant",
        "content":   bot_reply,
        "timestamp": now_ist()
    })

    save_session(session)
    extract_and_save_bag(user_msg, bot_reply, bag)

    return jsonify({"reply": bot_reply})


# ── Bag API ──

@app.route("/bag", methods=["GET"])
def get_bag():
    return jsonify({"notes": load_bag()})

@app.route("/bag/add", methods=["POST"])
def add_to_bag():
    note = request.json.get("note", "").strip()
    if not note:
        return jsonify({"error": "Empty note"}), 400
    bag   = load_bag()
    entry = {"content": note, "timestamp": now_ist()}
    bag.append(entry)
    save_bag(bag)
    return jsonify({"ok": True, "bag": bag})

@app.route("/bag/remove", methods=["POST"])
def remove_from_bag():
    index = request.json.get("index")
    bag   = load_bag()
    if index is None or not (0 <= index < len(bag)):
        return jsonify({"error": "Invalid index"}), 400
    bag.pop(index)
    save_bag(bag)
    return jsonify({"ok": True, "bag": bag})

@app.route("/bag/clear", methods=["POST"])
def clear_bag():
    save_bag([])
    return jsonify({"ok": True})


# ── Archive API ──

@app.route("/archive", methods=["GET"])
def get_archive():
    doc = col.find_one({"_id": "archive"}) or {}
    return jsonify({"messages": doc.get("messages", [])})

@app.route("/archive/clear", methods=["POST"])
def clear_archive():
    col.update_one({"_id": "archive"}, {"$set": {"messages": []}}, upsert=True)
    return jsonify({"ok": True})


# ── Sessions API ──

@app.route("/sessions", methods=["GET"])
def get_sessions():
    return jsonify({"past": load_past_sessions()})

@app.route("/sessions/clear", methods=["POST"])
def clear_sessions():
    save_past_sessions([])
    return jsonify({"ok": True})


# ── Page routes ──

@app.route("/aadhi")
def unlock():
    return render_template("aadhi.html")

@app.route("/memory")
def memory_page():
    return render_template("memory.html")

@app.route("/memory<int:n>")
def memory_n(n):
    return render_template(f"memory{n}.html")

@app.route("/static/<filename>")
def get_image(filename):
    return send_from_directory(os.path.join(app.root_path, "static"), filename)


if __name__ == "__main__":
    app.run(debug=True)