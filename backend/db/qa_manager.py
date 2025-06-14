import os
import sqlite3
import json
import requests
import time
from datetime import datetime

class QAManager:
    def __init__(self, source_db='chatify.db', qa_db='qa_dataset.db'):
        self.source_db = source_db
        self.qa_db = qa_db
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.api_key}"
        self._init_qa_db()

    def _init_qa_db(self):
        conn = sqlite3.connect(self.qa_db)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS qa_pairs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT,
                answer TEXT,
                source_url TEXT,
                source_title TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def _fetch_scraped_content(self):
        conn = sqlite3.connect(self.source_db)
        cursor = conn.execute("SELECT url, title, text FROM scraped_pages")
        results = cursor.fetchall()
        conn.close()
        return results

    def _generate_qa(self, text, url, title):
        prompt = f"""
Generate as many question-answer pairs as possible from this content.

Title: {title}
URL: {url}

{text[:3000]}
Return only a JSON array like:
[
  {{ "question": "...", "answer": "..." }},
  ...
]
"""

        response = requests.post(
            self.api_url,
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=45
        )

        try:
            result = response.json()
            content = result.get("candidates", [])[0]["content"]["parts"][0]["text"]
            qa_list = json.loads(content)
            return [(qa['question'], qa['answer'], url, title) for qa in qa_list]
        except Exception as e:
            print(f"[!] Failed to parse QA for {url}: {e}")
            return []

    def _save_qa_pairs(self, qa_list):
        if not qa_list:
            return
        conn = sqlite3.connect(self.qa_db)
        conn.executemany(
            "INSERT INTO qa_pairs (question, answer, source_url, source_title) VALUES (?, ?, ?, ?)",
            qa_list
        )
        conn.commit()
        conn.close()

    def process_all(self):
        print("💬 Generating Q&A from database entries...")
        entries = self._fetch_scraped_content()
        total = 0
        for url, title, text in entries:
            print(f"[→] Processing {url}")
            qa = self._generate_qa(text, url, title)
            self._save_qa_pairs(qa)
            total += len(qa)
            time.sleep(2)  # rate limiting
        print(f"✅ Done. Total Q&A pairs saved: {total}")
