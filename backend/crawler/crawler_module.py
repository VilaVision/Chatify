#!/usr/bin/env python3

import os
import time
import json
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from collections import deque

class MinimalCrawler:
    def __init__(self, base_url, max_pages=500, delay=1.0, verbose=True):
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(base_url).netloc
        self.max_pages = max_pages
        self.delay = delay
        self.verbose = verbose

        self.visited = set()
        self.queue = deque([base_url])
        self.crawled_data = {}
        self.all_discovered_links = set()

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def normalize_url(self, url):
        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        return normalized.rstrip('/')

    def is_valid_url(self, url):
        try:
            parsed = urlparse(url)
            normalized_url = self.normalize_url(url)
            return (
                parsed.scheme in ['http', 'https'] and
                parsed.netloc == self.domain and
                normalized_url not in self.visited and
                not url.lower().endswith((
                    '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.svg',
                    '.ico', '.mp4', '.mp3', '.avi', '.webp', '.woff', '.woff2', '.ttf'
                ))
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
                        normalized_url = self.normalize_url(full_url)
                        if self.is_valid_url(full_url):
                            links.add(normalized_url)
                            self.all_discovered_links.add(normalized_url)
        except Exception as e:
            if self.verbose:
                print(f"[!] Error extracting links from {base_url}: {e}")
        return links

    def crawl(self):
        if self.verbose:
            print(f"[+] Starting recursive crawl from: {self.base_url}")
        
        normalized_base = self.normalize_url(self.base_url)
        self.queue = deque([normalized_base])
        
        while self.queue and len(self.visited) < self.max_pages:
            url = self.queue.popleft()
            normalized_url = self.normalize_url(url)
            
            if normalized_url in self.visited:
                continue

            if self.verbose:
                print(f"[>] Crawling: {normalized_url}")
            self.visited.add(normalized_url)
            self.all_discovered_links.add(normalized_url)

            html = self.fetch_page(normalized_url)
            if not html:
                continue

            soup = BeautifulSoup(html, 'html.parser')
            title_tag = soup.find('title')
            title_text = title_tag.get_text().strip() if title_tag else "No Title"

            links = self.extract_links(html, normalized_url)

            self.crawled_data[normalized_url] = {
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

    def save_to_json(self, filename="chatpy/backend/data/crawled_links.json"):
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)

            output = {
                "base_url": self.normalize_url(self.base_url),
                "total_pages_crawled": len(self.visited),
                "total_unique_links_discovered": len(self.all_discovered_links),
                "crawled_pages": sorted(list(self.visited)),
                "all_discovered_links": sorted(list(self.all_discovered_links)),
                "page_details": self.crawled_data,
                "summary": {
                    "pages_successfully_crawled": len(self.crawled_data),
                    "unique_links_found_total": len(self.all_discovered_links),
                    "average_links_per_page": round(
                        sum(v['links_count'] for v in self.crawled_data.values()) / len(self.crawled_data), 2
                    ) if self.crawled_data else 0
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

    def get_unique_urls(self):
        return sorted(list(self.all_discovered_links))

    def print_summary(self):
        unique_urls = self.get_unique_urls()
        print(f"\n[📋] UNIQUE URLS SUMMARY")
        print(f"Total unique URLs discovered: {len(unique_urls)}")
        print(f"Pages successfully crawled: {len(self.visited)}")
        print(f"URLs in queue when stopped: {len(self.queue)}")

        if self.verbose:
            preview = unique_urls[:10] if len(unique_urls) > 20 else unique_urls
            print(f"\n[🔗] Sample URLs:")
            for i, url in enumerate(preview, 1):
                print(f"  {i:2d}. {url}")
            if len(unique_urls) > 20:
                print(f"  ... and {len(unique_urls) - 10} more")


def run_crawler(
    url: str,
    max_pages: int = 50,
    delay: float = 1.0,
    verbose: bool = True,
    save_json: bool = True,
    json_filename: str = "chatpy/backend/data/crawled_links.json"
) -> tuple:
    crawler = MinimalCrawler(url, max_pages, delay, verbose)
    data = crawler.crawl()
    crawler.print_summary()
    saved_file = crawler.save_to_json(json_filename) if save_json else None

    if verbose:
        print(f"\n[✅] CRAWLING COMPLETE")
        print(f"Unique URLs discovered: {len(crawler.get_unique_urls())}")
        print(f"Pages successfully crawled: {len(data)}")
        if saved_file:
            print(f"Results saved in: {saved_file}")
        else:
            print("Results not saved.")

    return data, saved_file, crawler.get_unique_urls()


if __name__ == "__main__":
    print("This script defines a crawler class.")
    print("To use it, import and call:")
    print("from crawler.crawler_module import run_crawler")
    print("run_crawler('https://example.com', max_pages=10)")
