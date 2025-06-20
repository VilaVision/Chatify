import json
import os
import sqlite3
from bs4 import BeautifulSoup

# File paths
json_path = r"C:\Users\alokp\Chatify\backend\extracted_dataset.json"
html_output = r"C:\Users\alokp\Chatify\backend\html_content.json"
css_output = r"C:\Users\alokp\Chatify\backend\css_content.json"
db_path = r"C:\Users\alokp\Chatify\backend\chatify.db"

# Load JSON data
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

html_data = []
css_data = []
db_entries = []

# Process each item
for item in data:
    link = item.get('link')
    html = item.get('html', '')

    soup = BeautifulSoup(html, 'html.parser')

    # Extract all CSS inside <style> tags
    styles = [style.get_text() for style in soup.find_all('style')]
    css_data.extend(styles)

    # Store HTML content without style
    for style in soup.find_all('style'):
        style.decompose()  # remove style tags from HTML

    html_data.append({
        "link": link,
        "html": str(soup)
    })

    # Extract tags and text for the database
    for tag in soup.find_all():
        tag_name = tag.name
        tag_text = tag.get_text(strip=True)
        if tag_text:
            db_entries.append((link, tag_name, tag_text))


# Save HTML content
with open(html_output, 'w', encoding='utf-8') as f:
    json.dump(html_data, f, indent=2, ensure_ascii=False)

# Save CSS content
with open(css_output, 'w', encoding='utf-8') as f:
    json.dump(css_data, f, indent=2, ensure_ascii=False)

# Create and populate SQLite database
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Create table
c.execute('''
    CREATE TABLE IF NOT EXISTS chatify_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        link TEXT,
        tag TEXT,
        content TEXT
    )
''')

# Insert data
c.executemany('INSERT INTO chatify_data (link, tag, content) VALUES (?, ?, ?)', db_entries)

conn.commit()
conn.close()

print("✅ All files and database created successfully.")
