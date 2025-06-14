from flask import Blueprint, request, jsonify
import traceback
import sqlite3
import os
import shutil
from db.chatify_manager import ChatifyManager
from db.qa_manager import QAManager

scan_blueprint = Blueprint('scan', __name__)

CHATBOT_DIR = os.path.join(os.path.dirname(__file__), 'chatbot')  # Adjust if needed
os.makedirs(CHATBOT_DIR, exist_ok=True)  # Ensure chatbot folder exists

TEMP_FILES = [
    "crawled_links.json",
    "extracted_dataset.json"
]

def cleanup_temp_files():
    for file in TEMP_FILES:
        if os.path.exists(file):
            os.remove(file)
            print(f"🗑️ Removed temp file: {file}")


def copy_databases():
    try:
        shutil.copy("chatify.db", os.path.join(CHATBOT_DIR, "chatify.db"))
        shutil.copy("qa_dataset.db", os.path.join(CHATBOT_DIR, "qa_dataset.db"))
        print("📁 Copied databases to chatbot directory.")
    except Exception as e:
        print(f"[!] Failed to copy DBs: {e}")


@scan_blueprint.route('/api/scan', methods=['POST'])
def scan_route():
    try:
        # 1. Receive input link
        data = request.get_json()
        source_url = data.get('source_url')
        if not source_url:
            return jsonify({'error': 'No source URL provided'}), 400

        print("🌐 Step 1: Starting Crawl + Extract + Save...")
        chatify = ChatifyManager()
        extracted_file = chatify.process_url(source_url)

        print("💡 Step 2: Generating Q&A from chatify.db...")
        qa_manager = QAManager(source_db='chatify.db', qa_db='qa_dataset.db')
        qa_manager.process_all()

        print("🧹 Step 3: Cleaning up temp files...")
        cleanup_temp_files()

        print("📦 Step 4: Copying databases to chatbot directory...")
        copy_databases()

        # 5. Return Q&A pairs (latest 15)
        qa_conn = sqlite3.connect("qa_dataset.db")
        cursor = qa_conn.execute("SELECT question, answer, source_url FROM qa_pairs ORDER BY id DESC LIMIT 15")
        qa_pairs = [{"question": q, "answer": a, "source_url": url} for q, a, url in cursor.fetchall()]
        qa_conn.close()

        return jsonify({
            "message": "Crawling, Extraction, DB Save, Q&A Generation, and Backup completed.",
            "qa_pairs": qa_pairs
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'Internal error: {str(e)}'}), 500


@scan_blueprint.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({'status': 'ready'}), 200
