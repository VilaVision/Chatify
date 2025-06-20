import sqlite3

DB_PATH = r"C:\Users\alokp\Chatify\backend\chatbot\chatify.db"

def create_and_insert():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS faq_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT
        )
    ''')

    # Long text sample (you can paste your full dataset here)
    full_text = """
- | Eligibility | Selection Process | Placement Cities | Compensation & Benefits
- “I was fortunate to have experienced an excellent education which enabled me to improve my life.”
- “I want to make sure all Students get the same experience as me.” – Nandini Kochar, TFI Fellow 2021
- You are eligible to apply for the 2026 Fellowship cohort if you:
  - Completed graduation by June/July 2026
  - Are applying for the first time for the 2026 Fellowship cohort, since July 2025
  - Are a citizen of India or Overseas Citizen of India(OCI)
- Do You Need Prior Teaching Experience? No, don't worry.
- We will provide the essential training needed to set you up for success in your classroom.
- Got Another Question? Check the FAQ
- The Fellowship Selection Process:
  - The Fellow selection process has 2 stages.
  - It is designed to understand your strengths and motivations for this role.
  - If you can make it through all the stages, you are on your way towards a life-changing experience.
    """

    cursor.execute("INSERT INTO faq_info (text) VALUES (?)", (full_text,))
    conn.commit()
    conn.close()
    print("✅ Data inserted successfully.")

if __name__ == "__main__":
    create_and_insert()
