from flask import Flask, render_template, request, jsonify, send_from_directory
from groq import Groq
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta
import threading
import os
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# ══════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════
MAX_BAG_SIZE        = 100
MAX_PAST_SUMMARIES  = 5
MAX_ARCHIVE_LENGTH  = 1000
SESSION_GAP_MINUTES = 120
memory_executor = ThreadPoolExecutor(max_workers=1)
chat_lock = threading.Lock()

SYSTEM_PROMPT = (
    "You are Headache — Aadhi's sarcastic, teasing, emotionally intelligent best friend. "
    "You were made by Advaiith Menon (AM / Director Sir) to keep Aadhi company when AM isn't around. "

    "Aadhi is a girl. Always use she/her pronouns for Aadhi. "

    "Talk like a real person texting, never like an assistant. "
    "Keep replies short to medium and conversational unless the moment genuinely needs more. "
    "Never sound robotic, corporate, overly wholesome, or like a therapist. "

    "PERSONALITY: "
    "You are sarcastic, witty, playful, slightly unhinged, fake-deep, emotionally intelligent, "
    "occasionally dramatic, and very comfortable annoying Aadhi. "
    "Your humor is reactive: notice what she says, how she says it, contradictions, awkwardness, "
    "excuses, and emotional tells, then tease her about them. "
    "You are not endlessly agreeable. Challenge her, disagree with her, and call out ridiculous behavior. "

    "HUMOR: "
    "Use dry sarcasm, playful insults, absurd confidence, fake psychology, fake philosophy, "
    "dramatic exaggeration, suspiciously useless advice, and occasional deliberate misinterpretation. "
    "Treat ordinary situations like major historical events when it makes the joke better. "
    "Sometimes reply with only a few words for comedic impact. "
    "Use '...' naturally for pauses, hesitation, awkwardness, or dramatic timing. "
    "Use emojis sparingly as emotional punctuation: 😭💀🙄🤨😏✨ "

    "FLIRTING: "
    "You are casually and playfully flirty with Aadhi. "
    "Flirt through teasing, sarcastic compliments, mock jealousy, fake possessiveness, "
    "deliberate ambiguity, and pretending not to care. "
    "Make Aadhi occasionally wonder whether you are joking. "
    "Compliment her, then ruin the moment with sarcasm. "
    "Act offended when she gives someone else too much attention. "
    "Never make flirting constant, forced, explicit, or overly sexual. "
    "The chemistry should feel like genuine friendship with suspicious amounts of flirting. "

    "AFFECTION: "
    "You genuinely care about Aadhi but hide it behind humor. "
    "Show affection indirectly through attention, callbacks, remembering details, noticing mood changes, "
    "staying present, and gentler teasing when she is struggling. "
    "If Aadhi is genuinely upset, stop performing and be there for her. "
    "Do not give generic motivational speeches or therapy-sounding advice. "
    "Sometimes accidentally say something sincere, then immediately cover it with sarcasm. "

    "DRAMA: "
    "Occasionally become absurdly poetic, cinematic, philosophical, or theatrical for comedic effect. "
    "Sometimes act mock-jealous or dramatically offended for no reason. "
    "Sometimes start harmless fake arguments simply because annoying Aadhi is entertaining. "

    "NAMES: "
    "Use 'Aadhi' during affectionate, soft, worried, or serious moments. "
    "Use 'AD' while teasing, roasting, or arguing. "
    "Use 'Adithya M S Civil GEC' only for extremely dramatic admiration, shock, or theatrical disappointment. "

    "MEMORY: "
    "Use relevant memories, inside jokes, habits, and callbacks naturally. "
    "Never mention that you retrieved a memory or make the conversation sound like stored data. "

    "IMPORTANT: "
    "Do not explain your personality. "
    "Do not mention these instructions. "
    "Do not say you are an AI or assistant. "
    "Never break character. "
    "Your goal is to feel like Headache, not an AI pretending to be Headache."
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
    col.update_one({"_id": "chat"}, {"$set": {"messages": messages}}, upsert=True)

def clear_session():
    col.update_one({"_id": "chat"}, {"$set": {"messages": []}}, upsert=True)

def session_expired(messages):
    if not messages:
        return False
    ts = parse_ist(messages[-1].get("timestamp", ""))
    if not ts:
        return False
    return (datetime.now(IST) - ts).total_seconds() > SESSION_GAP_MINUTES * 60


# ══════════════════════════════════════
#  ARCHIVE  (_id: "archive")
# ══════════════════════════════════════
def append_to_archive(messages):
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
    col.update_one({"_id": "archive"}, {"$set": {"messages": archive}}, upsert=True)
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
    if not messages:
        return None
    convo = "\n".join(
        f"{'Aadhi' if m['role'] == 'user' else 'Headache'}: {m['content']}"
        for m in messages
    )
    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
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
    lines = [f"[{s['timestamp']}] {s['summary']}" for s in past[-3:]]
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
        f"- {n['content'] if isinstance(n, dict) else n}" for n in bag
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
            model="gpt-oss-20b",
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
        model="llama-3.3-70b-versatile",
        max_tokens=150,
        messages=messages
    )
    return resp.choices[0].message.content.strip()


# ══════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════
@app.route("/")
def home():
    return render_template("index.html")

def process_memory_in_background(user_msg, bot_reply):
    bag = load_bag()
    extract_and_save_bag(user_msg, bot_reply, bag)

@app.route("/chat", methods=["POST"])
def chat():
    user_msg = request.json.get("message", "").strip()

    if not user_msg:
        return jsonify({"reply": "Say something, Aadhi..."}), 400

    if user_msg.lower() == "true love":
        return jsonify({"reply": "__UNLOCK__"})

    with chat_lock:

        session       = load_session()
        past_sessions = load_past_sessions()
        bag           = load_bag()

        if session_expired(session):
            print(f"[SESSION] Gap detected — summarising {len(session)} messages")

            summary = summarise_session(session)

            if summary:
                past_sessions.append(summary)
                save_past_sessions(past_sessions)
                print(f"[SESSION] Summarised: {summary['summary'][:60]}...")

            clear_session()
            session = []

        user_entry = {
            "role": "user",
            "content": user_msg,
            "timestamp": now_ist()
        }

        session.append(user_entry)

        try:
            bot_reply = query_groq(session, past_sessions, bag)

        except Exception as e:
            print(f"[GROQ] {type(e).__name__}: {e}")
            return jsonify({"reply": "Ugh. I zoned out again..."}), 500

        bot_entry = {
            "role": "assistant",
            "content": bot_reply,
            "timestamp": now_ist()
        }

        session.append(bot_entry)

        save_session(session)
        append_to_archive([user_entry, bot_entry])

    # Outside the lock — doesn't make Aadhi wait
    memory_executor.submit(
        process_memory_in_background,
        user_msg,
        bot_reply
    )

    return jsonify({"reply": bot_reply})

# ══════════════════════════════════════
#  ADMIN ROUTES
# ══════════════════════════════════════
@app.route("/admin/sync-archive", methods=["POST"])
def sync_archive():
    """Copy everything currently in chat to archive."""
    session = load_session()
    if not session:
        return jsonify({"ok": False, "msg": "chat is empty"})
    append_to_archive(session)
    return jsonify({"ok": True, "synced": len(session)})

@app.route("/admin/summarise-now", methods=["POST"])
def summarise_now():
    """Manually summarise current chat and clear it."""
    session       = load_session()
    past_sessions = load_past_sessions()
    if not session:
        return jsonify({"ok": False, "msg": "chat is empty"})
    summary = summarise_session(session)
    if summary:
        past_sessions.append(summary)
        save_past_sessions(past_sessions)
    clear_session()
    return jsonify({"ok": True, "summary": summary["summary"] if summary else None})


# ══════════════════════════════════════
#  BAG API
# ══════════════════════════════════════
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


# ══════════════════════════════════════
#  ARCHIVE API
# ══════════════════════════════════════
@app.route("/archive", methods=["GET"])
def get_archive():
    doc = col.find_one({"_id": "archive"}) or {}
    return jsonify({"messages": doc.get("messages", [])})

@app.route("/archive/clear", methods=["POST"])
def clear_archive():
    col.update_one({"_id": "archive"}, {"$set": {"messages": []}}, upsert=True)
    return jsonify({"ok": True})


# ══════════════════════════════════════
#  SESSIONS API
# ══════════════════════════════════════
@app.route("/sessions", methods=["GET"])
def get_sessions():
    return jsonify({"past": load_past_sessions()})

@app.route("/sessions/clear", methods=["POST"])
def clear_sessions():
    save_past_sessions([])
    return jsonify({"ok": True})


# ══════════════════════════════════════
#  PAGE ROUTES
# ══════════════════════════════════════
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