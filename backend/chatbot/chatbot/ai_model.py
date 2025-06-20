import sqlite3

conn = sqlite3.connect("chatbot/chatify.db")  # or your correct path
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

print("Tables in the DB:", tables)

conn.close()
