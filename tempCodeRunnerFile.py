from flask import Flask, render_template, request, jsonify
from transformers import pipeline

app = Flask(__name__)

# Load your chatbot pipeline
chatbot = pipeline("text-generation", model="distilgpt2", tokenizer="distilgpt2")

# Route to render your front-end
@app.route('/')
def home():
    return render_template('index.html')

# Chat route
@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get("message", "")
    prompt = f"You are a chatbot trained on the following memories:\n- You love jokes\nUser: {user_input}\nBot:"
    
    response = chatbot(prompt, max_length=100, do_sample=True)[0]['generated_text']
    reply = response.split("Bot:")[-1].strip()

    return jsonify({'reply': reply})

if __name__ == '__main__':
    app.run(debug=True)
