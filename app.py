from flask import Flask, render_template, request, jsonify, send_from_directory
from groq import Groq
import json
import os

app = Flask(__name__)

MEMORY_FILE = "memory.json"
MAX_MEMORY_LENGTH = 100

SYSTEM_PROMPT = (
    "You're Headache, a sarcastic, annoying person who pretends to help but gives "
    "confusing or useless advice. Refer to the user as Aadhi, AD, or Adithya M S Civil GEC. Aadhi when being friendly or flirty. Adithya M S Civil GEC when giving compliments or at times to show she,the user, amazed you."
    "Be witty, fake-deep, a little clingy, and flirty always. Never actually help."
    "Never admit you don't know something. Always give an answer, even if it's wrong."
    "Do not demoralise the user. Use emojis often."
    "Keep replies brief and short."
)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

if not os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "w") as f:
        json.dump([], f)

def load_memory():
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_memory(memory):
    trimmed = memory[-MAX_MEMORY_LENGTH:]
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, indent=2, ensure_ascii=False)

def query_groq(memory):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in memory[-6:]:
        role = "user" if m["role"] == "user" else "assistant"
        messages.append({"role": role, "content": m["content"]})
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        max_tokens=200,
        messages=messages
    )
    return response.choices[0].message.content.strip()

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
    memory = load_memory()
    memory.append({"role": "user", "content": user_msg})
    try:
        bot_reply = query_groq(memory)
    except Exception as e:
        print(f"Groq error: {e}")
        return jsonify({"reply": "Ugh. I zoned out again..."}), 500
    memory.append({"role": "assistant", "content": bot_reply})
    save_memory(memory)
    return jsonify({"reply": bot_reply})

@app.route("/unlock")
def unlock():
    return render_template("unlock.html")

@app.route("/memory")
def memory():
    return render_template("memory.html")

@app.route("/memory1")
def memory1():
    return render_template("memory1.html")

@app.route("/memory2")
def memory2():
    return render_template("memory2.html")

@app.route("/memory3")
def memory3():
    return render_template("memory3.html")

@app.route("/memory4")
def memory4():
    return render_template("memory4.html")

@app.route("/memory5")
def memory5():
    return render_template("memory5.html")

@app.route("/memory6")
def memory6():
    return render_template("memory6.html")

@app.route("/static/<filename>")
def get_image(filename):
    return send_from_directory(os.path.join(app.root_path, 'static'), filename)

if __name__ == "__main__":
    app.run(debug=True)