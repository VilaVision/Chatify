import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import logging
import re

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class WebScraper:
    def __init__(self, json_file='crawled_links.json', output_file='extracted_dataset.json'):
        self.json_file = json_file
        self.output_file = output_file
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.skip_extensions = ('.pdf', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.mp4', '.avi', '.mp3')

    def load_links(self):
        """Load links from JSON file"""
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data.get('all_links', [])
                elif isinstance(data, list):
                    return data
                else:
                    logging.error("Unexpected JSON structure")
                    return []
        except FileNotFoundError:
            logging.error(f"File {self.json_file} not found")
            return []
        except json.JSONDecodeError:
            logging.error(f"Invalid JSON in {self.json_file}")
            return []

    def clean_extracted_text(self, raw_text):
        """Clean and format raw extracted text for better readability"""
        if not raw_text:
            return ""

        # Remove extra whitespaces
        raw_text = re.sub(r'\s+', ' ', raw_text)

        # Split into lines and remove duplicates or very short lines
        lines = raw_text.split('. ')
        cleaned_lines = []

        seen = set()
        for line in lines:
            line = line.strip()
            if len(line) >= 30 and line not in seen:  # Minimum 30 characters
                cleaned_lines.append(f"- {line}")
                seen.add(line)

        return "\n".join(cleaned_lines)

    def extract_text(self, url):
        """Extract text from a single URL"""
        if url.lower().endswith(self.skip_extensions):
            logging.warning(f"Skipping binary or non-text URL: {url}")
            return None

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Remove unwanted tags
            for tag in soup(['script', 'style', 'noscript', 'svg', 'meta', 'footer', 'header']):
                tag.decompose()

            # Extract title
            title = soup.title.string.strip() if soup.title else 'No Title'

            # Extract and clean visible text
            raw_text = soup.get_text(separator=' ', strip=True)
            cleaned_text = self.clean_extracted_text(raw_text)

            return {
                'url': url,
                'domain': urlparse(url).netloc,
                'title': title,
                'text': cleaned_text,
                'status': 'success'
            }

        except Exception as e:
            logging.error(f"Error extracting from {url}: {e}")
            return {
                'url': url,
                'domain': urlparse(url).netloc,
                'title': '',
                'text': '',
                'status': 'error',
                'error': str(e)
            }

    def process_all_links(self):
        """Process all links and extract text"""
        links = self.load_links()
        if not links:
            logging.warning("No links found to process")
            return []

        logging.info(f"Processing {len(links)} links...")
        dataset = []

        for i, link in enumerate(links, 1):
            logging.info(f"[{i}/{len(links)}] Processing: {link}")
            result = self.extract_text(link)
            if result:
                dataset.append(result)

        return dataset

    def save_dataset(self, dataset):
        """Save dataset to JSON file"""
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump({"pages": dataset}, f, indent=2, ensure_ascii=False)
            logging.info(f"Dataset saved to {self.output_file}")
        except Exception as e:
            logging.error(f"Error saving dataset: {e}")

    def run(self):
        """Main execution method"""
        dataset = self.process_all_links()
        if dataset:
            self.save_dataset(dataset)
            logging.info(f"Completed! Processed {len(dataset)} URLs")
        else:
            logging.warning("No data to save")

# Usage
if __name__ == "__main__":
    scraper = WebScraper()
    scraper.run()
