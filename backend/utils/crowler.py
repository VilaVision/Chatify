import requests
from urllib.parse import urljoin, urlparse, urlunparse
from bs4 import BeautifulSoup
import time
import json
from collections import defaultdict, deque
import re
import os
from typing import Set, Dict, List, Optional
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import signal

class DeepWebsiteCrawler:
    def __init__(self, base_url: str, delay: float = 1.0, max_workers: int = 20, timeout: int = 20):
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(base_url).netloc
        self.delay = delay
        self.max_workers = max_workers
        self.timeout = timeout

        self.visited_urls: Set[str] = set()
        self.queued_urls: Set[str] = set()
        self.url_queue = deque([base_url])
        self.site_structure: Dict = {}
        self.files_found: Dict[str, Set[str]] = defaultdict(set)
        self.page_relationships: Dict[str, Set[str]] = defaultdict(set)

        self.visited_lock = threading.Lock()
        self.queue_lock = threading.Lock()
        self.structure_lock = threading.Lock()

        self.stats = {
            'pages_crawled': 0,
            'files_found': 0,
            'errors': 0,
            'start_time': None
        }

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        })

        self.file_extensions = {
            'images': ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico', '.bmp', '.tiff'],
            'documents': ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.rtf', '.odt'],
            'media': ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mp3', '.wav', '.ogg', '.aac', '.flac'],
            'code': ['.js', '.css', '.html', '.htm', '.xml', '.json', '.php', '.py', '.java', '.cpp', '.c'],
            'archives': ['.zip', '.rar', '.tar', '.gz', '.7z', '.bz2'],
            'fonts': ['.ttf', '.otf', '.woff', '.woff2', '.eot'],
            'data': ['.csv', '.tsv', '.sql', '.db', '.sqlite']
        }

        self.ignore_patterns = [
            r'#.*',
            r'javascript:.*',
            r'mailto:.*',
            r'tel:.*',
            r'.*\.(exe|dmg|pkg|deb|rpm)$',
        ]

        self.stop_crawling = False
        # signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        print("\nStopping crawler... (Press Ctrl+C again to force quit)")
        self.stop_crawling = True

    def is_valid_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ''))
            if not (parsed.netloc == self.domain and parsed.scheme in ['http', 'https']):
                return False
            for pattern in self.ignore_patterns:
                if re.match(pattern, url, re.IGNORECASE):
                    return False
            with self.visited_lock:
                if clean_url in self.visited_urls or clean_url in self.queued_urls:
                    return False
            return True
        except Exception:
            return False

    def classify_file(self, url: str) -> Optional[str]:
        url_lower = url.lower()
        clean_url = urlparse(url_lower).path
        for category, extensions in self.file_extensions.items():
            if any(clean_url.endswith(ext) for ext in extensions):
                return category
        return None

    def extract_links(self, html: str, base_url: str) -> Set[str]:
        links = set()
        try:
            soup = BeautifulSoup(html, 'html.parser')
            selectors = [
                ('a', 'href'),
                ('link', 'href'),
                ('script', 'src'),
                ('img', 'src'),
                ('iframe', 'src'),
                ('embed', 'src'),
                ('object', 'data'),
                ('source', 'src'),
                ('track', 'src'),
                ('area', 'href'),
                ('base', 'href'),
                ('form', 'action')
            ]
            for tag, attr in selectors:
                for element in soup.find_all(tag):
                    url = element.get(attr)
                    if url:
                        absolute_url = urljoin(base_url, url)
                        links.add(absolute_url)
            css_patterns = [
                r'url\(["\']?([^"\'()]+)["\']?\)',
                r'@import\s+["\']([^"\']+)["\']',
                r'src:\s*url\(["\']?([^"\'()]+)["\']?\)'
            ]
            for pattern in css_patterns:
                css_links = re.findall(pattern, html, re.IGNORECASE)
                for css_url in css_links:
                    absolute_url = urljoin(base_url, css_url)
                    links.add(absolute_url)
            js_patterns = [
                r'["\']([^"\']*\.(?:js|json|css|png|jpg|jpeg|gif|svg|pdf|doc|docx|xls|xlsx))["\']',
                r'src\s*=\s*["\']([^"\']+)["\']',
                r'href\s*=\s*["\']([^"\']+)["\']'
            ]
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    for pattern in js_patterns:
                        js_links = re.findall(pattern, script.string, re.IGNORECASE)
                        for js_url in js_links:
                            if not js_url.startswith(('http', '//')):
                                absolute_url = urljoin(base_url, js_url)
                                links.add(absolute_url)
        except Exception as e:
            print(f"Error extracting links from {base_url}: {e}")
        return links

    def fetch_page(self, url: str) -> Optional[Dict]:
        try:
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code == 403:
                print("403 Forbidden, trying with different user agent...")
                backup_headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15'
                }
                response = self.session.get(url, headers=backup_headers, timeout=self.timeout)
            if response.status_code == 403:
                print("Still forbidden, trying as Googlebot...")
                googlebot_headers = {
                    'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
                }
                response = self.session.get(url, headers=googlebot_headers, timeout=self.timeout)
            if response.status_code == 403:
                print("Still forbidden, trying minimal headers...")
                minimal_session = requests.Session()
                response = minimal_session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return {
                'content': response.text,
                'status_code': response.status_code,
                'content_type': response.headers.get('content-type', ''),
                'size': len(response.content)
            }
        except requests.exceptions.HTTPError as e:
            with self.structure_lock:
                self.stats['errors'] += 1
            if e.response.status_code == 403:
                print(f"Access forbidden to {url} - website blocks crawlers")
            elif e.response.status_code == 404:
                print(f"Page not found: {url}")
            elif e.response.status_code == 429:
                print(f"Rate limited on {url} - consider increasing delay")
            else:
                print(f"HTTP {e.response.status_code} error for {url}")
            return None
        except requests.exceptions.Timeout:
            with self.structure_lock:
                self.stats['errors'] += 1
            print(f"Timeout fetching {url}")
            return None
        except requests.exceptions.ConnectionError:
            with self.structure_lock:
                self.stats['errors'] += 1
            print(f"Connection error for {url}")
            return None
        except Exception as e:
            with self.structure_lock:
                self.stats['errors'] += 1
            print(f"Error fetching {url}: {str(e)[:100]}")
            return None

    def process_url(self, url: str) -> Optional[Dict]:
        if self.stop_crawling:
            return None
        with self.visited_lock:
            if url in self.visited_urls:
                return None
            self.visited_urls.add(url)
        print(f"Crawling: {url}")
        page_data = self.fetch_page(url)
        if not page_data:
            return None
        page_info = {
            'url': url,
            'title': '',
            'description': '',
            'links': set(),
            'files': defaultdict(set),
            'status_code': page_data['status_code'],
            'content_type': page_data['content_type'],
            'size': page_data['size']
        }
        if 'text/html' in page_data['content_type'].lower():
            try:
                soup = BeautifulSoup(page_data['content'], 'html.parser')
                title_tag = soup.find('title')
                if title_tag:
                    page_info['title'] = title_tag.get_text().strip()
                desc_tag = soup.find('meta', attrs={'name': 'description'})
                if desc_tag:
                    page_info['description'] = desc_tag.get('content', '').strip()
                links = self.extract_links(page_data['content'], url)
                new_urls = []
                for link in links:
                    if self.is_valid_url(link):
                        file_type = self.classify_file(link)
                        if file_type:
                            page_info['files'][file_type].add(link)
                            with self.structure_lock:
                                self.files_found[file_type].add(link)
                                self.stats['files_found'] += 1
                        else:
                            page_info['links'].add(link)
                            new_urls.append(link)
                            with self.structure_lock:
                                self.page_relationships[url].add(link)
                if new_urls and not self.stop_crawling:
                    with self.queue_lock:
                        for new_url in new_urls:
                            if new_url not in self.queued_urls:
                                self.url_queue.append(new_url)
                                self.queued_urls.add(new_url)
            except Exception as e:
                print(f"Error processing HTML for {url}: {e}")
        with self.structure_lock:
            self.stats['pages_crawled'] += 1
        if self.delay > 0:
            time.sleep(self.delay)
        return page_info

    def crawl_website(self) -> Dict:
        print(f"Starting crawl of: {self.base_url}")
        print(f"Configuration:")
        print(f"   - Max workers: {self.max_workers}")
        print(f"   - Delay: {self.delay}s")
        print(f"   - Timeout: {self.timeout}s")
        print("-" * 60)
        self.stats['start_time'] = time.time()
        self.queued_urls.add(self.base_url)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            try:
                while self.url_queue and not self.stop_crawling:
                    current_batch = []
                    with self.queue_lock:
                        batch_size = min(self.max_workers * 2, len(self.url_queue))
                        for _ in range(batch_size):
                            if self.url_queue:
                                current_batch.append(self.url_queue.popleft())
                    if not current_batch:
                        break
                    future_to_url = {
                        executor.submit(self.process_url, url): url
                        for url in current_batch
                    }
                    for future in as_completed(future_to_url):
                        if self.stop_crawling:
                            break
                        url = future_to_url[future]
                        try:
                            page_info = future.result()
                            if page_info:
                                with self.structure_lock:
                                    self.site_structure[url] = page_info
                        except Exception as e:
                            print(f"Error processing {url}: {e}")
                    self.print_progress()
            except KeyboardInterrupt:
                print("\nCrawling interrupted by user")
                self.stop_crawling = True
        elapsed_time = time.time() - self.stats['start_time']
        print(f"\nCrawling completed in {elapsed_time:.2f} seconds")
        return self.site_structure

    def print_progress(self):
        elapsed = time.time() - self.stats['start_time']
        pages_per_sec = self.stats['pages_crawled'] / elapsed if elapsed > 0 else 0
        with self.queue_lock:
            queue_size = len(self.url_queue)
        print(f"Progress: {self.stats['pages_crawled']} pages | "
              f"{self.stats['files_found']} files | "
              f"{queue_size} queued | "
              f"{pages_per_sec:.1f} pages/sec | "
              f"{self.stats['errors']} errors")

    def build_site_map(self) -> Dict:
        site_map = {
            'root': self.base_url,
            'pages': {},
            'structure': {},
            'statistics': self.get_statistics()
        }
        for url, page_info in self.site_structure.items():
            page_data = dict(page_info)
            page_data['links'] = list(page_info['links'])
            for file_type, files in page_info['files'].items():
                page_data['files'][file_type] = list(files)
            site_map['pages'][url] = page_data
        for parent, children in self.page_relationships.items():
            site_map['structure'][parent] = list(children)
        return site_map

    def get_statistics(self) -> Dict:
        elapsed = time.time() - self.stats['start_time'] if self.stats['start_time'] else 0
        file_stats = {}
        total_files = 0
        for file_type, files in self.files_found.items():
            count = len(files)
            file_stats[file_type] = count
            total_files += count
        return {
            'pages_crawled': self.stats['pages_crawled'],
            'total_files': total_files,
            'files_by_type': file_stats,
            'errors': self.stats['errors'],
            'elapsed_time': elapsed,
            'pages_per_second': self.stats['pages_crawled'] / elapsed if elapsed > 0 else 0,
            'unique_urls_found': len(self.visited_urls),
            'domain': self.domain
        }

    def print_detailed_summary(self):
        stats = self.get_statistics()
        print("\n" + "="*60)
        print(f"DEEP CRAWL SUMMARY FOR: {self.domain}")
        print("="*60)
        print(f"Pages crawled: {stats['pages_crawled']}")
        print(f"Total files found: {stats['total_files']}")
        print(f"Time elapsed: {stats['elapsed_time']:.2f} seconds")
        print(f"Average speed: {stats['pages_per_second']:.2f} pages/second")
        print(f"Errors encountered: {stats['errors']}")
        if stats['files_by_type']:
            print("\nFILES BY TYPE:")
            for file_type, count in sorted(stats['files_by_type'].items()):
                print(f"   {file_type.capitalize()}: {count}")
        print("\nTOP PAGES BY OUTBOUND LINKS:")
        page_link_counts = []
        for url, page_info in self.site_structure.items():
            link_count = len(page_info.get('links', []))
            if link_count > 0:
                page_link_counts.append((link_count, url, page_info.get('title', 'Untitled')))
        for count, url, title in sorted(page_link_counts, reverse=True)[:10]:
            print(f"   {count:3d} links - {title[:50]}...")

    def save_detailed_structure(self, filename: str = "deep_website_structure.json"):
        try:
            site_map = self.build_site_map()
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(site_map, f, indent=2, ensure_ascii=False, default=str)
            print(f"\nComplete structure saved to: {filename}")
            print(f"   File size: {os.path.getsize(filename) / 1024 / 1024:.2f} MB")
        except Exception as e:
            print(f"Error saving structure: {e}")

    def save_sitemap_xml(self, filename: str = "sitemap.xml"):
        try:
            xml_content = ['<?xml version="1.0" encoding="UTF-8"?>']
            xml_content.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
            for url in self.site_structure.keys():
                xml_content.append('  <url>')
                xml_content.append(f'    <loc>{url}</loc>')
                xml_content.append('  </url>')
            xml_content.append('</urlset>')
            with open(filename, 'w', encoding='utf-8') as f:
                f.write('\n'.join(xml_content))
            print(f"XML Sitemap saved to: {filename}")
        except Exception as e:
            print(f"Error saving sitemap: {e}")

def run_crawler(base_url: str, delay=1.0, max_workers=20, timeout=20, max_pages=None) -> dict:
    crawler = DeepWebsiteCrawler(
        base_url=base_url,
        delay=delay,
        max_workers=max_workers,
        timeout=timeout
    )
    structure = crawler.crawl_website()
    return {
        'structure': structure,
        'page_urls': list(structure.keys())
    }
