from flask import Flask, request, jsonify
import shutil
import sqlite3
import os
from openai import OpenAI
from cchatbot.dataset_loader import load_dataset, find_relevant_response

app = Flask(__name__)

# Copy DB from chatify to cchatbot if not exists
db_src = "chatify/chatify.db"
db_dest = "cchatbot/chatify.db"
if not os.path.exists(db_dest):
    shutil.copyfile(db_src, db_dest)

# Load dataset from the copied DB
DATASET = load_dataset(db_dest)

# Set your Gemini API key
api_key = os.getenv("GEMINI_API_KEY", "AIzaSyDO5ne4OUFWB5dnSqWlQ9nWbD59w-c4tm0")
if not api_key:
    raise ValueError("Please set the GEMINI_API_KEY environment variable")

# Initialize OpenAI client with Gemini endpoint
client = OpenAI(
    api_key=api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

@app.route('/chat', methods=['POST'])
def chat():
    user_prompt = request.json.get("prompt", "")

    # Search dataset for relevant information
    context = find_relevant_response(DATASET, user_prompt)

    # Construct prompt with context
    full_prompt = f"Context:\n{context}\n\nUser Query: {user_prompt}"

    # Generate response using Gemini
    response = client.chat.completions.create(
        model="gemini-2.0-flash",
        messages=[{"role": "user", "content": full_prompt}]
    )

    answer = response.choices[0].message.content
    return jsonify({"response": answer})


if __name__ == '__main__':
    app.run(debug=True)
