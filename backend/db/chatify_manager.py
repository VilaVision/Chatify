import os
import json
import sqlite3
from utils.crowler import run_crawler
from utils.extractor import WebScraper

class ChatifyManager:
    def __init__(self, db_path='chatify.db'):
        self.db_path = db_path

    def process_url(self, url, max_pages=50):
        print("🌐 Crawling...")
        run_crawler(url, max_pages=max_pages, delay=1.0)

        print("📄 Extracting...")
        scraper = WebScraper(json_file="crawled_links.json", output_file="extracted_dataset.json")
        scraper.run()

        print("💾 Saving to DB...")
        self.save_extracted_to_db("extracted_dataset.json")
        return "extracted_dataset.json"

    def save_extracted_to_db(self, json_path):
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"{json_path} not found")

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        pages = data.get("pages") if isinstance(data, dict) else data

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scraped_pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                domain TEXT,
                title TEXT,
                text TEXT,
                status TEXT
            )
        """)

        for entry in pages:
            cursor.execute("""
                INSERT INTO scraped_pages (url, domain, title, text, status)
                VALUES (?, ?, ?, ?, ?)
            """, (
                entry.get('url'),
                entry.get('domain'),
                entry.get('title'),
                entry.get('text'),
                entry.get('status')
            ))

        conn.commit()
        conn.close()
        print("✅ Extracted data saved to chatify.db")
