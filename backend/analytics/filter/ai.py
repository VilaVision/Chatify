import sqlite3
import json
import requests
import os
import time

class QAGenerator:
    def __init__(self, source_db='chatify.db', qa_db='qa_dataset.db'):
        self.source_db = source_db
        self.qa_db = qa_db
        self.api_key = os.getenv('GEMINI_API_KEY')  # Make sure this is set in your environment
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.api_key}"
        self.setup_database()

    def setup_database(self):
        """Create Q&A database"""
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

    def get_content(self):
        """Load content from source database"""
        try:
            conn = sqlite3.connect(self.source_db)
            cursor = conn.execute('SELECT url, text, title FROM scraped_pages')
            content = cursor.fetchall()
            conn.close()
            return content
        except Exception as e:
            print(f"[!] Error reading source DB: {e}")
            return []

    def generate_qa(self, text, url, title=""):
        """Generate Q&A using Gemini API"""
        prompt = f"""
Generate as many useful and clear question-answer pairs as possible from the following webpage content. 
Each answer should include a reference to the source URL at the end.

Title: {title}
URL: {url}

{text.strip()}
"""
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt.strip()
                        }
                    ]
                }
            ]
        }

        try:
            response = requests.post(
                self.api_url,
                headers={'Content-Type': 'application/json'},
                json=payload,
                timeout=60
            )

            if response.status_code == 200:
                content = response.json()
                output_text = content["candidates"][0]["content"]["parts"][0]["text"]

                # Try to parse output as JSON array first
                try:
                    qa_pairs = json.loads(output_text)
                    if isinstance(qa_pairs, list) and all("question" in qa and "answer" in qa for qa in qa_pairs):
                        return [(qa['question'], qa['answer'], url, title) for qa in qa_pairs]
                except:
                    # Fallback to splitting plain text if not JSON
                    lines = [line.strip() for line in output_text.split('\n') if line.strip()]
                    qa_pairs = []
                    for i in range(0, len(lines), 2):
                        if i + 1 < len(lines):
                            q = lines[i].replace("Q:", "").strip()
                            a = lines[i+1].replace("A:", "").strip()
                            if q and a:
                                qa_pairs.append((q, a, url, title))
                    return qa_pairs

            else:
                print(f"[!] Gemini API Error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"[!] Gemini API request failed for {url}: {e}")
        return []

    def save_qa(self, qa_pairs):
        """Save Q&A pairs to database"""
        if qa_pairs:
            try:
                conn = sqlite3.connect(self.qa_db)
                conn.executemany(
                    'INSERT INTO qa_pairs (question, answer, source_url, source_title) VALUES (?, ?, ?, ?)',
                    qa_pairs
                )
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[!] Error saving to DB: {e}")

    def process(self, max_pages=5):
        """Main processing function"""
        content = self.get_content()[:max_pages]
        total_qa = 0

        for url, text, title in content:
            if not text.strip():
                continue
            print(f"[>] Generating Q&A from: {url}")
            qa_pairs = self.generate_qa(text, url, title)
            self.save_qa(qa_pairs)
            total_qa += len(qa_pairs)
            time.sleep(3)  # Rate limit between requests

        print(f"[✓] Total Q&A pairs generated: {total_qa}")


# CLI test
if __name__ == "__main__":
    generator = QAGenerator()
    generator.process(max_pages=10)
