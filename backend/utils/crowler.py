#!/usr/bin/env python3
"""
Recursive Full-Site Web Crawler (All Link Sources)
"""

import requests
import json
import time
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from collections import deque

class MinimalCrawler:
    def __init__(self, base_url, max_pages=50, delay=1.0, verbose=True):
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(base_url).netloc
        self.max_pages = max_pages
        self.delay = delay
        self.verbose = verbose

        self.visited = set()
        self.queue = deque([base_url])
        self.crawled_data = {}

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def is_valid_url(self, url):
        try:
            parsed = urlparse(url)
            return (
                parsed.scheme in ['http', 'https'] and
                parsed.netloc == self.domain and
                url not in self.visited and
                not url.endswith(('.pdf', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.svg', '.ico', '.mp4', '.mp3'))
            )
        except:
            return False

    def fetch_page(self, url):
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            if self.verbose:
                print(f"[!] Error fetching {url}: {e}")
            return None

    def extract_links(self, html, base_url):
        links = set()
        try:
            soup = BeautifulSoup(html, 'html.parser')
            for tag in soup.find_all():
                for attr in ['href', 'src']:
                    link = tag.get(attr)
                    if link:
                        full_url = urljoin(base_url, link.strip())
                        if self.is_valid_url(full_url):
                            links.add(full_url)
        except Exception as e:
            if self.verbose:
                print(f"[!] Error extracting links from {base_url}: {e}")
        return links

    def crawl(self):
        if self.verbose:
            print(f"[+] Starting recursive crawl from: {self.base_url}")
        
        while self.queue and len(self.visited) < self.max_pages:
            url = self.queue.popleft()
            if url in self.visited:
                continue

            if self.verbose:
                print(f"[>] Crawling: {url}")
            self.visited.add(url)

            html = self.fetch_page(url)
            if not html:
                continue

            soup = BeautifulSoup(html, 'html.parser')
            title_tag = soup.find('title')
            title_text = title_tag.get_text().strip() if title_tag else "No Title"

            links = self.extract_links(html, url)

            self.crawled_data[url] = {
                "title": title_text,
                "links_found": list(links),
                "links_count": len(links)
            }

            for link in links:
                if link not in self.visited and link not in self.queue:
                    self.queue.append(link)

            time.sleep(self.delay)

        if self.verbose:
            print(f"[✓] Crawling completed. Pages visited: {len(self.visited)}")

        return self.crawled_data

    def save_to_json(self, filename="crawled_links.json"):
        try:
            output = {
                "base_url": self.base_url,
                "total_pages": len(self.visited),
                "all_links": list(self.visited),
                "page_details": self.crawled_data,
                "summary": {
                    "total_unique_links": len(self.visited),
                    "total_links_found": sum(v['links_count'] for v in self.crawled_data.values())
                }
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)

            if self.verbose:
                print(f"[💾] Data saved to: {filename}")
            return filename
        except Exception as e:
            if self.verbose:
                print(f"[!] Error saving to JSON: {e}")
            return None


def run_crawler(
    url: str,
    max_pages: int = 50,
    delay: float = 1.0,
    verbose: bool = True,
    save_json: bool = True,
    json_filename: str = "crawled_links.json"
) -> tuple:
    """
    Full-site recursive crawler. Returns crawled data and saved file path.
    """
    crawler = MinimalCrawler(url, max_pages, delay, verbose)
    data = crawler.crawl()
    saved_file = crawler.save_to_json(json_filename) if save_json else None

    if verbose:
        print("\n[📊] SUMMARY")
        print(f"Pages crawled: {len(data)}")
        if saved_file:
            print(f"Results saved in: {saved_file}")
        else:
            print("Results not saved.")

    return data, saved_file
if __name__ == "__main__":
    print("This script defines a crawler class. To use it, import and call run_crawler(url).")

