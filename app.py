from flask import Flask, render_template, request, jsonify , send_from_directory
import requests
import json
import os

app = Flask(__name__)

# Constants
MEMORY_FILE = "memory.json"
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "phi"
MAX_MEMORY_LENGTH = 100  # limit to avoid memory.json bloat

# Create empty memory file if not exists
if not os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "w") as f:
        json.dump([], f)

# Load memory from file
def load_memory():
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)

# Save memory with trimming
def save_memory(memory):
    trimmed = memory[-MAX_MEMORY_LENGTH:]
    with open(MEMORY_FILE, "w") as f:
        json.dump(trimmed, f, indent=2)

# Send query to Phi model with personality prompt
def query_phi(message):
    full_prompt = (
    "You're Headache, a sarcastic, annoying chatbot who pretends to help but gives confusing or useless advice. "
    "Refer to the user as Aadhi, AD, or Adithya M S Civil GEC. Be witty, fake-deep, and a little clingy. Never actually help.\n"
    f"User: {message.strip()}\nHeadache:"
)
    response = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "prompt": full_prompt,
        "stream": False
    })

    if response.ok:
        return response.json()["response"].strip()
    return "Ugh. Sorry I zoned out..."

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_msg = request.json.get("message")
    
    # Special keyword to unlock memory
    if user_msg.strip().lower() == "true love":
        return jsonify({"reply": "__UNLOCK__"})

    memory = load_memory()

    # Add user message to memory
    memory.append({"role": "user", "content": user_msg})

    # Use recent memory only
    recent = memory[-6:]  # Last 3 exchanges
    history = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in recent])

    # Get response from model
    bot_reply = query_phi(history)

    # Add bot reply to memory
    memory.append({"role": "bot", "content": bot_reply})
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
    # You could add extra security checks here (e.g. allowed extensions)
    return send_from_directory(os.path.join(app.root_path, 'static'), filename)

if __name__ == "__main__":
    app.run(debug=True)
