import sqlite3
import os
from utils.data_handler import load_qa_pairs

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Data', 'qa_data.db'))

def init_qa_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS qa_pairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            category TEXT,
            source_url TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_qa_pair(question, answer, category=None, source_url=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO qa_pairs (question, answer, category, source_url)
        VALUES (?, ?, ?, ?)
    ''', (question, answer, category, source_url))
    conn.commit()
    conn.close()

def get_all_qa_pairs():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT question, answer, category, source_url FROM qa_pairs')
    rows = c.fetchall()
    conn.close()
    return [
        {"question": q, "answer": a, "category": c, "source_url": s}
        for q, a, c, s in rows
    ]

def get_best_answer(user_question):
    # Simple keyword match; replace with semantic search for better results
    qa_pairs = load_qa_pairs()
    user_question_lower = user_question.lower()
    for qa in qa_pairs:
        if qa.question.lower() in user_question_lower or user_question_lower in qa.question.lower():
            return qa.answer
    # Fallback: return first answer or None
    return qa_pairs[0].answer if qa_pairs else None