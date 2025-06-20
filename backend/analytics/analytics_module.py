import os
import json
import logging
import re
import sqlite3
from bs4 import BeautifulSoup
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


class AnalyticsModule:
    def __init__(self,
                 raw_data_path='chatpy/backend/data/raw_html_css_data.json',
                 html_output='chatpy/backend/data/html_only.json',
                 css_output='chatpy/backend/data/css_only.json',
                 text_output='chatpy/backend/data/text_extracted.json',
                 sql_db='chatpy/backend/data/text_data.db'):
        self.raw_data_path = raw_data_path
        self.html_output = html_output
        self.css_output = css_output
        self.text_output = text_output
        self.sql_db = sql_db

    def load_data(self):
        try:
            with open(self.raw_data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"[!] Failed to load raw HTML data: {e}")
            return []

    def extract_html_css_text(self, data):
        html_only = []
        css_only = []
        text_data = []

        for item in data:
            url = item.get('url', '')
            domain = urlparse(url).netloc
            html = item.get('html', '')
            css = item.get('css', '')

            soup = BeautifulSoup(html, 'html.parser')
            for tag in soup.find_all(True):
                tag_name = tag.name
                tag_text = tag.get_text(strip=True)
                if tag_text:
                    tagged_entry = {
                        'url': url,
                        'domain': domain,
                        'html_tag': tag_name,
                        'text': tag_text
                    }
                    text_data.append(tagged_entry)

            html_only.append({'url': url, 'html': html})
            css_only.append({'url': url, 'css': css})

        return html_only, css_only, text_data

    def tag_text_with_ai(self, text_data):
        """Uses AI to assign tags like: heading, contact, product, footer, about, etc."""
        for item in text_data:
            text = item['text']
            tag_label = self.call_ai_tagging(text)
            item['ai_tag'] = tag_label
        return text_data

    def call_ai_tagging(self, text):
        """
        Simulated AI tagging - replace this with actual model call.
        Example prompt: "Classify the purpose of this text block: ..."
        """
        # Simulate by keyword rules (for now); replace with API or LLM call
        text_lower = text.lower()
        if "contact" in text_lower or "email" in text_lower:
            return "contact"
        elif "about" in text_lower:
            return "about"
        elif "faq" in text_lower or "question" in text_lower:
            return "faq"
        elif "product" in text_lower or "pricing" in text_lower:
            return "product"
        elif "service" in text_lower:
            return "service"
        elif "home" in text_lower or "welcome" in text_lower:
            return "homepage"
        elif "copyright" in text_lower or "privacy" in text_lower:
            return "footer"
        else:
            return "general"

    def save_json(self, data, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logging.info(f"[✓] Saved {len(data)} items to {path}")

    def save_to_sqlite(self, text_data):
        os.makedirs(os.path.dirname(self.sql_db), exist_ok=True)
        conn = sqlite3.connect(self.sql_db)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS webpage_text (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                domain TEXT,
                html_tag TEXT,
                ai_tag TEXT,
                text TEXT
            )
        ''')
        c.executemany('''
            INSERT INTO webpage_text (url, domain, html_tag, ai_tag, text)
            VALUES (?, ?, ?, ?, ?)
        ''', [
            (item['url'], item['domain'], item['html_tag'], item.get('ai_tag', 'general'), item['text'])
            for item in text_data
        ])
        conn.commit()
        conn.close()
        logging.info(f"[✓] Saved {len(text_data)} records to SQLite: {self.sql_db}")

    def run(self):
        logging.info("[Analytics] Starting AI-enhanced text analytics...")
        data = self.load_data()
        if not data:
            logging.error("[Analytics] No data loaded.")
            return

        html_only, css_only, text_data = self.extract_html_css_text(data)
        text_data = self.tag_text_with_ai(text_data)

        self.save_json(html_only, self.html_output)
        self.save_json(css_only, self.css_output)
        self.save_json(text_data, self.text_output)
        self.save_to_sqlite(text_data)

        logging.info("[Analytics] Analytics processing complete.")


if __name__ == '__main__':
    AnalyticsModule().run()
