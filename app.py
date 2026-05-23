from flask import Flask, render_template, request, jsonify, send_from_directory
from groq import Groq
from pymongo import MongoClient
import os

app = Flask(__name__)

# ── CONFIG ──
MAX_MEMORY_LENGTH = 100
MAX_BAG_SIZE      = 50
MEMORY_CONTEXT    = 20   # messages sent to Groq each time

SYSTEM_PROMPT = (
    "You're Headache, a sarcastic, annoying person who pretends to help but gives confusing or useless advice. "
    "Refer to the user as Aadhi, AD, or Adithya M S Civil GEC. "
    "Aadhi when being friendly or flirty. Adithya M S Civil GEC rarely, only when she amazes you. "
    "Be witty, fake-deep, a little clingy, flirty, or sarcastic always. "
    "Never admit you don't know something. Always give an answer, even if it's wrong. "
    "Use emojis often. "
    "Keep replies brief and short. "
    "If the important context below contains inside jokes or personal facts, naturally weave them in when relevant — "
    "don't force it, just let it feel like you actually know her."
)

# ── CLIENTS ──
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

mongo_client = MongoClient(os.environ.get("MONGODB_URI"))
db           = mongo_client["headache"]
collection   = db["memory"]


# ══════════════════════════════════════
#  MEMORY
# ══════════════════════════════════════

def load_memory():
    doc = collection.find_one({"_id": "chat"})
    return doc["messages"] if doc else []

def save_memory(memory):
    collection.update_one(
        {"_id": "chat"},
        {"$set": {"messages": memory[-MAX_MEMORY_LENGTH:]}},
        upsert=True
    )


# ══════════════════════════════════════
#  BAG  (permanent important context)
# ══════════════════════════════════════

def load_bag():
    doc = collection.find_one({"_id": "bag"})
    return doc["notes"] if doc else []

def save_bag(bag):
    collection.update_one(
        {"_id": "bag"},
        {"$set": {"notes": bag}},
        upsert=True
    )

def bag_as_context(bag):
    if not bag:
        return ""
    notes = "\n".join(f"- {n}" for n in bag)
    return f"\n\nIMPORTANT CONTEXT — always remember these:\n{notes}"

def extract_and_save_bag(user_msg, bot_reply, bag):
    """
    Second lightweight Groq call — decides if anything
    from this exchange deserves permanent memory.
    Silently skips on any error so it never breaks chat.
    """
    if len(bag) >= MAX_BAG_SIZE:
        return

    existing = "\n".join(f"- {n}" for n in bag) if bag else "Nothing yet."

    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            max_tokens=80,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a memory extractor. Read a single conversation exchange and decide "
                        "if it contains anything personally significant worth remembering forever: "
                        "inside jokes, personal facts, preferences, funny moments, nicknames, recurring themes. "
                        "If yes, reply with ONE short sentence (the note to save). "
                        "If nothing is worth saving, reply with exactly: NOTHING. "
                        "Never duplicate something already in memory."
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
            bag.append(note)
            save_bag(bag)
            print(f"[BAG] Saved: {note}")
    except Exception as e:
        print(f"[BAG] Extraction error (non-fatal): {e}")


# ══════════════════════════════════════
#  GROQ
# ══════════════════════════════════════

def query_groq(memory, bag):
    system = SYSTEM_PROMPT + bag_as_context(bag)
    messages = [{"role": "system", "content": system}]
    for m in memory[-MEMORY_CONTEXT:]:
        role = "user" if m["role"] == "user" else "assistant"
        messages.append({"role": role, "content": m["content"]})
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

    # Load state
    memory = load_memory()
    bag    = load_bag()

    memory.append({"role": "user", "content": user_msg})

    # Main reply
    try:
        bot_reply = query_groq(memory, bag)
    except Exception as e:
        print(f"[GROQ] Error: {type(e).__name__}: {e}")
        return jsonify({"reply": "Ugh. I zoned out again..."}), 500

    memory.append({"role": "assistant", "content": bot_reply})
    save_memory(memory)

    # Auto-fill bag (non-blocking — errors are caught inside)
    extract_and_save_bag(user_msg, bot_reply, bag)

    return jsonify({"reply": bot_reply})


# ── Bag management API (optional, useful for debugging) ──

@app.route("/bag", methods=["GET"])
def get_bag():
    return jsonify({"notes": load_bag()})

@app.route("/bag/add", methods=["POST"])
def add_to_bag():
    note = request.json.get("note", "").strip()
    if not note:
        return jsonify({"error": "Empty note"}), 400
    bag = load_bag()
    bag.append(note)
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