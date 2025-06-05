import requests
import time
import json
import re
import os
import csv
import mimetypes
import threading
import datetime
import argparse
import pandas as pd
from urllib.parse import urljoin, urlparse, urlunparse
from bs4 import BeautifulSoup
from collections import defaultdict, deque
from typing import Set, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.robotparser import RobotFileParser
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from backend.utils.data_handler import save_scraped_page

class run_crawler:
    def __init__(self, base_url: str, delay: float = 1.0, max_workers: int = 20, 
                 timeout: int = 20, max_pages: int = None, use_selenium: bool = False,
                 respect_robots: bool = True, extract_emails: bool = True,
                 extract_phones: bool = True, extract_social_links: bool = True):
        """
        Enhanced website crawler with comprehensive data extraction
        
        Args:
            base_url: Starting URL for crawling
            delay: Delay between requests in seconds
            max_workers: Number of concurrent workers
            timeout: Request timeout in seconds
            max_pages: Maximum pages to crawl (None for unlimited)
            use_selenium: Use Selenium for JavaScript-heavy sites
            respect_robots: Respect robots.txt file
            extract_emails: Extract email addresses
            extract_phones: Extract phone numbers
            extract_social_links: Extract social media links
        """
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(base_url).netloc
        self.delay = delay
        self.max_workers = max_workers
        self.timeout = timeout
        self.max_pages = max_pages
        self.use_selenium = use_selenium
        self.respect_robots = respect_robots
        self.extract_emails = extract_emails
        self.extract_phones = extract_phones
        self.extract_social_links = extract_social_links

        # Core tracking sets and structures
        self.visited_urls: Set[str] = set()
        self.queued_urls: Set[str] = set()
        self.url_queue = deque([base_url])
        self.site_structure: Dict = {}
        self.files_found: Dict[str, Set[str]] = defaultdict(set)
        self.page_relationships: Dict[str, Set[str]] = defaultdict(set)
        
        # Enhanced data extraction
        self.extracted_data: Dict = {
            'emails': set(),
            'phones': set(),
            'social_links': set(),
            'forms': [],
            'images': [],
            'documents': [],
            'external_links': set(),
            'page_content': {},
            'metadata': {},
            'headings_structure': {},
            'api_endpoints': set(),
            'javascript_files': set(),
            'css_files': set()
        }

        # Thread locks
        self.visited_lock = threading.Lock()
        self.queue_lock = threading.Lock()
        self.structure_lock = threading.Lock()
        self.data_lock = threading.Lock()

        # Statistics
        self.stats = {
            'pages_crawled': 0,
            'files_found': 0,
            'errors': 0,
            'start_time': None,
            'data_extracted': 0,
            'forms_found': 0,
            'redirects': 0
        }

        # Session setup
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

        # Selenium setup
        self.driver = None
        if self.use_selenium:
            self._setup_selenium()

        # File extensions (enhanced)
        self.file_extensions = {
            'images': ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico', '.bmp', '.tiff', '.avif'],
            'documents': ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.rtf', '.odt', '.ods', '.odp'],
            'media': ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mp3', '.wav', '.ogg', '.aac', '.flac', '.webm', '.mkv'],
            'code': ['.js', '.css', '.html', '.htm', '.xml', '.json', '.php', '.py', '.java', '.cpp', '.c', '.rb', '.go'],
            'archives': ['.zip', '.rar', '.tar', '.gz', '.7z', '.bz2', '.xz'],
            'fonts': ['.ttf', '.otf', '.woff', '.woff2', '.eot'],
            'data': ['.csv', '.tsv', '.sql', '.db', '.sqlite', '.xlsx', '.xls'],
            'feeds': ['.rss', '.atom', '.xml'],
            'config': ['.yaml', '.yml', '.ini', '.conf', '.config', '.env']
        }

        # Enhanced ignore patterns
        self.ignore_patterns = [
            r'#.*',
            r'javascript:.*',
            r'mailto:.*',
            r'tel:.*',
            r'.*\.(exe|dmg|pkg|deb|rpm|msi)$',
            r'.*logout.*',
            r'.*signout.*',
            r'.*admin.*',
            r'.*login.*',
            r'.*\?.*download.*',
            r'.*print.*',
            r'.*calendar.*\.ics$'
        ]

        # Regex patterns for data extraction
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        self.phone_pattern = re.compile(r'(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\+\d{1,3}[-.\s]?\d{4,14}')
        self.social_patterns = {
            'facebook': re.compile(r'(?:https?://)?(?:www\.)?facebook\.com/[A-Za-z0-9._-]+', re.IGNORECASE),
            'twitter': re.compile(r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/[A-Za-z0-9._-]+', re.IGNORECASE),
            'linkedin': re.compile(r'(?:https?://)?(?:www\.)?linkedin\.com/(?:in|company)/[A-Za-z0-9._-]+', re.IGNORECASE),
            'instagram': re.compile(r'(?:https?://)?(?:www\.)?instagram\.com/[A-Za-z0-9._-]+', re.IGNORECASE),
            'youtube': re.compile(r'(?:https?://)?(?:www\.)?youtube\.com/(?:channel|user|c)/[A-Za-z0-9._-]+', re.IGNORECASE),
            'github': re.compile(r'(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9._-]+', re.IGNORECASE)
        }

        self.api_pattern = re.compile(r'/api/[^"\s]+|/rest/[^"\s]+|/graphql[^"\s]*', re.IGNORECASE)

        self.stop_crawling = False
        self.robots_parser = None
        
        # Initialize robots.txt parser
        if self.respect_robots:
            self._init_robots_parser()

    def _setup_selenium(self):
        """Setup Selenium WebDriver for JavaScript-heavy sites"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument(f'--user-agent={self.session.headers["User-Agent"]}')
            
            self.driver = webdriver.Chrome(options=chrome_options)
            print("Selenium WebDriver initialized successfully")
        except Exception as e:
            print(f"Failed to initialize Selenium: {e}")
            self.use_selenium = False

    def _init_robots_parser(self):
        """Initialize robots.txt parser"""
        try:
            robots_url = urljoin(self.base_url, '/robots.txt')
            self.robots_parser = RobotFileParser()
            self.robots_parser.set_url(robots_url)
            self.robots_parser.read()
            print(f"Loaded robots.txt from {robots_url}")
        except Exception as e:
            print(f"Could not load robots.txt: {e}")
            self.robots_parser = None

    def _signal_handler(self, signum, frame):
        print("\nStopping crawler... (Press Ctrl+C again to force quit)")
        self.stop_crawling = True
        if self.driver:
            self.driver.quit()

    def is_valid_url(self, url: str) -> bool:
        """Enhanced URL validation with robots.txt respect"""
        try:
            parsed = urlparse(url)
            clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ''))
            
            # Check domain
            if not (parsed.netloc == self.domain and parsed.scheme in ['http', 'https']):
                return False
            
            # Check robots.txt
            if self.robots_parser and not self.robots_parser.can_fetch(self.session.headers['User-Agent'], url):
                return False
            
            # Check ignore patterns
            for pattern in self.ignore_patterns:
                if re.match(pattern, url, re.IGNORECASE):
                    return False
            
            # Check if already processed
            with self.visited_lock:
                if clean_url in self.visited_urls or clean_url in self.queued_urls:
                    return False
            
            return True
        except Exception:
            return False

    def classify_file(self, url: str) -> Optional[str]:
        """Enhanced file classification"""
        url_lower = url.lower()
        clean_url = urlparse(url_lower).path
        
        # Check MIME type first
        mime_type, _ = mimetypes.guess_type(url)
        if mime_type:
            if mime_type.startswith('image/'):
                return 'images'
            elif mime_type.startswith('video/') or mime_type.startswith('audio/'):
                return 'media'
            elif mime_type in ['application/pdf', 'application/msword']:
                return 'documents'
        
        # Fallback to extension-based classification
        for category, extensions in self.file_extensions.items():
            if any(clean_url.endswith(ext) for ext in extensions):
                return category
        return None

    def extract_comprehensive_data(self, html: str, url: str) -> Dict:
        """Extract comprehensive data from HTML content"""
        extracted = {
            'emails': set(),
            'phones': set(),
            'social_links': set(),
            'forms': [],
            'headings': {'h1': [], 'h2': [], 'h3': [], 'h4': [], 'h5': [], 'h6': []},
            'images': [],
            'external_links': set(),
            'internal_links': set(),
            'text_content': '',
            'metadata': {},
            'api_endpoints': set(),
            'word_count': 0,
            'language': None
        }

        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract text content
            for script in soup(["script", "style"]):
                script.decompose()
            text_content = soup.get_text()
            extracted['text_content'] = ' '.join(text_content.split())
            extracted['word_count'] = len(extracted['text_content'].split())
            
            # Extract emails
            if self.extract_emails:
                emails = self.email_pattern.findall(text_content)
                extracted['emails'].update(emails)
            
            # Extract phone numbers
            if self.extract_phones:
                phones = self.phone_pattern.findall(text_content)
                extracted['phones'].update(phones)
            
            # Extract social media links
            if self.extract_social_links:
                for platform, pattern in self.social_patterns.items():
                    social_links = pattern.findall(html)
                    for link in social_links:
                        if not link.startswith('http'):
                            link = 'https://' + link
                        extracted['social_links'].add((platform, link))
            
            # Extract forms
            forms = soup.find_all('form')
            for form in forms:
                form_data = {
                    'action': form.get('action', ''),
                    'method': form.get('method', 'GET').upper(),
                    'fields': []
                }
                
                inputs = form.find_all(['input', 'select', 'textarea'])
                for input_field in inputs:
                    field_data = {
                        'name': input_field.get('name', ''),
                        'type': input_field.get('type', 'text'),
                        'required': input_field.has_attr('required')
                    }
                    form_data['fields'].append(field_data)
                
                extracted['forms'].append(form_data)
            
            # Extract headings structure
            for level in range(1, 7):
                headings = soup.find_all(f'h{level}')
                extracted['headings'][f'h{level}'] = [h.get_text().strip() for h in headings]
            
            # Extract images with metadata
            images = soup.find_all('img')
            for img in images:
                img_data = {
                    'src': img.get('src', ''),
                    'alt': img.get('alt', ''),
                    'title': img.get('title', ''),
                    'width': img.get('width'),
                    'height': img.get('height')
                }
                if img_data['src']:
                    img_data['src'] = urljoin(url, img_data['src'])
                extracted['images'].append(img_data)
            
            # Extract metadata
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                name = meta.get('name') or meta.get('property') or meta.get('http-equiv')
                content = meta.get('content')
                if name and content:
                    extracted['metadata'][name] = content
            
            # Extract language
            html_tag = soup.find('html')
            if html_tag and html_tag.get('lang'):
                extracted['language'] = html_tag.get('lang')
            
            # Extract API endpoints from JavaScript
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    api_matches = self.api_pattern.findall(script.string)
                    for match in api_matches:
                        extracted['api_endpoints'].add(urljoin(url, match))
            
            # Extract all links and classify them
            links = soup.find_all('a', href=True)
            for link in links:
                href = link['href']
                absolute_url = urljoin(url, href)
                parsed_link = urlparse(absolute_url)
                
                if parsed_link.netloc == self.domain:
                    extracted['internal_links'].add(absolute_url)
                elif parsed_link.netloc:  # External link
                    extracted['external_links'].add(absolute_url)

        except Exception as e:
            print(f"Error extracting data from {url}: {e}")
        
        return extracted

    def extract_links(self, html: str, base_url: str) -> Set[str]:
        """Enhanced link extraction with better coverage"""
        links = set()
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Standard selectors
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
                ('form', 'action'),
                ('frame', 'src'),
                ('video', 'src'),
                ('audio', 'src')
            ]
            
            for tag, attr in selectors:
                for element in soup.find_all(tag):
                    url = element.get(attr)
                    if url:
                        absolute_url = urljoin(base_url, url)
                        links.add(absolute_url)
            
            # Extract from CSS
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
            
            # Extract from JavaScript
            js_patterns = [
                r'["\']([^"\']*\.(?:js|json|css|png|jpg|jpeg|gif|svg|pdf|doc|docx|xls|xlsx))["\']',
                r'src\s*=\s*["\']([^"\']+)["\']',
                r'href\s*=\s*["\']([^"\']+)["\']',
                r'fetch\s*\(\s*["\']([^"\']+)["\']',
                r'ajax\s*\(\s*["\']([^"\']+)["\']',
                r'window\.location\s*=\s*["\']([^"\']+)["\']'
            ]
            
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    for pattern in js_patterns:
                        js_links = re.findall(pattern, script.string, re.IGNORECASE)
                        for js_url in js_links:
                            if not js_url.startswith(('http', '//', 'data:', 'blob:')):
                                absolute_url = urljoin(base_url, js_url)
                                links.add(absolute_url)
            
            # Extract from meta refresh
            meta_refresh = soup.find('meta', attrs={'http-equiv': 'refresh'})
            if meta_refresh and meta_refresh.get('content'):
                content = meta_refresh.get('content')
                url_match = re.search(r'url=([^;]+)', content, re.IGNORECASE)
                if url_match:
                    refresh_url = urljoin(base_url, url_match.group(1).strip())
                    links.add(refresh_url)
                    
        except Exception as e:
            print(f"Error extracting links from {base_url}: {e}")
        
        return links

    def fetch_page_selenium(self, url: str) -> Optional[Dict]:
        """Fetch page using Selenium for JavaScript-heavy content"""
        try:
            self.driver.get(url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Scroll to load lazy content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Get page source after JavaScript execution
            html_content = self.driver.page_source
            
            return {
                'content': html_content,
                'status_code': 200,
                'content_type': 'text/html',
                'size': len(html_content)
            }
            
        except Exception as e:
            print(f"Selenium error for {url}: {e}")
            return None

    def fetch_page(self, url: str) -> Optional[Dict]:
        """Enhanced page fetching with multiple fallback strategies"""
        # Try Selenium first if enabled
        if self.use_selenium:
            selenium_result = self.fetch_page_selenium(url)
            if selenium_result:
                return selenium_result
        
        # Fallback to requests
        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            
            # Handle redirects
            if response.history:
                with self.structure_lock:
                    self.stats['redirects'] += 1
            
            # Try different user agents for 403 errors
            if response.status_code == 403:
                user_agents = [
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',
                    'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0'
                ]
                
                for ua in user_agents:
                    try:
                        response = self.session.get(url, headers={'User-Agent': ua}, timeout=self.timeout)
                        if response.status_code != 403:
                            break
                    except:
                        continue
            
            response.raise_for_status()
            
            return {
                'content': response.text,
                'status_code': response.status_code,
                'content_type': response.headers.get('content-type', ''),
                'size': len(response.content),
                'final_url': response.url,
                'encoding': response.encoding
            }
            
        except requests.exceptions.HTTPError as e:
            with self.structure_lock:
                self.stats['errors'] += 1
            if e.response.status_code == 403:
                print(f"Access forbidden to {url}")
            elif e.response.status_code == 404:
                print(f"Page not found: {url}")
            elif e.response.status_code == 429:
                print(f"Rate limited on {url} - increasing delay")
                time.sleep(self.delay * 2)
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
        """Enhanced URL processing with comprehensive data extraction"""
        if self.stop_crawling:
            return None
            
        # Check max pages limit
        if self.max_pages and self.stats['pages_crawled'] >= self.max_pages:
            self.stop_crawling = True
            return None
        
        with self.visited_lock:
            if url in self.visited_urls:
                return None
            self.visited_urls.add(url)
        
        print(f"Crawling: {url}")
        page_data = self.fetch_page(url)
        if not page_data:
            return None

        # Save raw HTML to database
        scraped_at = datetime.datetime.utcnow().isoformat()
        save_scraped_page(url, page_data['content'], scraped_at)

        # Initialize page info
        page_info = {
            'url': url,
            'final_url': page_data.get('final_url', url),
            'title': '',
            'description': '',
            'links': set(),
            'files': defaultdict(set),
            'status_code': page_data['status_code'],
            'content_type': page_data['content_type'],
            'size': page_data['size'],
            'encoding': page_data.get('encoding'),
            'scraped_at': scraped_at,
            'extracted_data': {}
        }

        # Process HTML content
        if 'text/html' in page_data['content_type'].lower():
            try:
                soup = BeautifulSoup(page_data['content'], 'html.parser')
                
                # Extract basic metadata
                title_tag = soup.find('title')
                if title_tag:
                    page_info['title'] = title_tag.get_text().strip()
                
                desc_tag = soup.find('meta', attrs={'name': 'description'})
                if desc_tag:
                    page_info['description'] = desc_tag.get('content', '').strip()
                
                # Comprehensive data extraction
                extracted = self.extract_comprehensive_data(page_data['content'], url)
                page_info['extracted_data'] = extracted
                
                # Merge extracted data into global collections
                with self.data_lock:
                    self.extracted_data['emails'].update(extracted['emails'])
                    self.extracted_data['phones'].update(extracted['phones'])
                    self.extracted_data['social_links'].update(extracted['social_links'])
                    self.extracted_data['forms'].extend(extracted['forms'])
                    self.extracted_data['external_links'].update(extracted['external_links'])
                    self.extracted_data['api_endpoints'].update(extracted['api_endpoints'])
                    self.extracted_data['page_content'][url] = {
                        'title': page_info['title'],
                        'text': extracted['text_content'][:1000],  # First 1000 chars
                        'word_count': extracted['word_count'],
                        'headings': extracted['headings']
                    }
                    self.extracted_data['metadata'][url] = extracted['metadata']
                    self.stats['data_extracted'] += 1
                    self.stats['forms_found'] += len(extracted['forms'])
                
                # Extract and process links
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
                
                # Add new URLs to queue
                if new_urls and not self.stop_crawling:
                    with self.queue_lock:
                        for new_url in new_urls:
                            if new_url not in self.queued_urls:
                                self.url_queue.append(new_url)
                                self.queued_urls.add(new_url)
                                
            except Exception as e:
                print(f"Error processing HTML for {url}: {e}")

        # Update statistics
        with self.structure_lock:
            self.stats['pages_crawled'] += 1

        # Respect delay
        if self.delay > 0:
            time.sleep(self.delay)

        return page_info

    def crawl_website(self) -> Dict:
        """Enhanced crawling with better progress tracking and error handling"""
        print(f"Starting enhanced crawl of: {self.base_url}")
        print(f"Configuration:")
        print(f"   - Max workers: {self.max_workers}")
        print(f"   - Delay: {self.delay}s")
        print(f"   - Timeout: {self.timeout}s")
        print(f"   - Max pages: {self.max_pages or 'Unlimited'}")
        print(f"   - Use Selenium: {self.use_selenium}")
        print(f"   - Respect robots.txt: {self.respect_robots}")
        print("-" * 60)
        
        self.stats['start_time'] = time.time()
        self.queued_urls.add(self.base_url)

        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                while self.url_queue and not self.stop_crawling:
                    # Check max pages limit
                    if self.max_pages and self.stats['pages_crawled'] >= self.max_pages:
                        print(f"Reached maximum page limit: {self.max_pages}")
                        break
                    
                    current_batch = []
                    with self.queue_lock:
                        batch_size = min(self.max_workers * 2, len(self.url_queue))
                        for _ in range(batch_size):
                            if self.url_queue:
                                current_batch.append(self.url_queue.popleft())
                    
                    if not current_batch:
                        break
                    
                    # Submit batch for processing
                    future_to_url = {
                        executor.submit(self.process_url, url): url
                        for url in current_batch
                    }
                    
                    # Process completed futures
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
                    
                    # Print progress every batch
                    self.print_progress()
                    
        except KeyboardInterrupt:
            print("\nCrawling interrupted by user")
            self.stop_crawling = True
        finally:
            if self.driver:
                self.driver.quit()
        
        elapsed_time = time.time() - self.stats['start_time']
        print(f"\nCrawling completed in {elapsed_time:.2f} seconds")
        return self.site_structure

    def print_progress(self):
        """Enhanced progress reporting"""
        elapsed = time.time() - self.stats['start_time']
        pages_per_sec = self.stats['pages_crawled'] / elapsed if elapsed > 0 else 0
        
        with self.queue_lock:
            queue_size = len(self.url_queue)
        
        print(f"Progress: {self.stats['pages_crawled']} pages | "
              f"{self.stats['files_found']} files | "
              f"{self.stats['data_extracted']} data extractions | "
              f"{queue_size} queued | "
              f"{pages_per_sec:.1f} pages/sec | "
              f"{self.stats['errors']} errors | "
              f"{self.stats['redirects']} redirects")

    def build_comprehensive_site_map(self) -> Dict:
        """Build comprehensive site map with all extracted data"""
        site_map = {
            'root': self.base_url,
            'domain': self.domain,
            'crawl_info': {
                'started_at': datetime.datetime.fromtimestamp(self.stats['start_time']).isoformat(),
                'completed_at': datetime.datetime.utcnow().isoformat(),
                'crawler_config': {
                    'delay': self.delay,
                    'max_workers': self.max_workers,
                    'timeout': self.timeout,
                    'max_pages': self.max_pages,
                    'use_selenium': self.use_selenium,
                    'respect_robots': self.respect_robots
                }
            },
            'pages': {},
            'structure': {},
            'extracted_data': {
                'emails': list(self.extracted_data['emails']),
                'phones': list(self.extracted_data['phones']),
                'social_links': [{'platform': platform, 'url': url} for platform, url in self.extracted_data['social_links']],
                'forms': self.extracted_data['forms'],
                'external_links': list(self.extracted_data['external_links']),
                'api_endpoints': list(self.extracted_data['api_endpoints']),
                'page_content': dict(self.extracted_data['page_content']),
                'metadata': dict(self.extracted_data['metadata'])
            },
            'files': {},
            'statistics': self.get_comprehensive_statistics()
        }
        
        # Process pages data
        for url, page_info in self.site_structure.items():
            page_data = dict(page_info)
            # Convert sets to lists for JSON serialization
            page_data['links'] = list(page_info['links'])
            for file_type, files in page_info['files'].items():
                page_data['files'][file_type] = list(files)
                
            # Clean extracted data for serialization
            if 'extracted_data' in page_data:
                extracted = page_data['extracted_data']
                for key, value in extracted.items():
                    if isinstance(value, set):
                        extracted[key] = list(value)
                        
            site_map['pages'][url] = page_data
        
        # Process structure relationships
        for parent, children in self.page_relationships.items():
            site_map['structure'][parent] = list(children)
        
        # Process files by type
        for file_type, files in self.files_found.items():
            site_map['files'][file_type] = list(files)
            
        return site_map

    def get_comprehensive_statistics(self) -> Dict:
        """Get comprehensive crawling statistics"""
        elapsed = time.time() - self.stats['start_time'] if self.stats['start_time'] else 0
        
        # File statistics
        file_stats = {}
        total_files = 0
        for file_type, files in self.files_found.items():
            count = len(files)
            file_stats[file_type] = count
            total_files += count
        
        # Data extraction statistics
        data_stats = {
            'emails_found': len(self.extracted_data['emails']),
            'phones_found': len(self.extracted_data['phones']),
            'social_links_found': len(self.extracted_data['social_links']),
            'forms_found': len(self.extracted_data['forms']),
            'external_links_found': len(self.extracted_data['external_links']),
            'api_endpoints_found': len(self.extracted_data['api_endpoints'])
        }
        
        # Content statistics
        total_words = sum(content.get('word_count', 0) for content in self.extracted_data['page_content'].values())
        
        return {
            'pages_crawled': self.stats['pages_crawled'],
            'total_files': total_files,
            'files_by_type': file_stats,
            'data_extraction': data_stats,
            'content_stats': {
                'total_words': total_words,
                'pages_with_content': len(self.extracted_data['page_content']),
                'average_words_per_page': total_words / max(1, len(self.extracted_data['page_content']))
            },
            'performance': {
                'errors': self.stats['errors'],
                'redirects': self.stats['redirects'],
                'elapsed_time': elapsed,
                'pages_per_second': self.stats['pages_crawled'] / elapsed if elapsed > 0 else 0,
                'unique_urls_found': len(self.visited_urls)
            },
            'domain': self.domain
        }

    def print_comprehensive_summary(self):
        """Print comprehensive crawling summary"""
        stats = self.get_comprehensive_statistics()
        
        print("\n" + "="*80)
        print(f"COMPREHENSIVE CRAWL SUMMARY FOR: {self.domain}")
        print("="*80)
        
        # Basic statistics
        print(f"Pages crawled: {stats['pages_crawled']}")
        print(f"Total files found: {stats['total_files']}")
        print(f"Time elapsed: {stats['performance']['elapsed_time']:.2f} seconds")
        print(f"Average speed: {stats['performance']['pages_per_second']:.2f} pages/second")
        print(f"Errors encountered: {stats['performance']['errors']}")
        print(f"Redirects handled: {stats['performance']['redirects']}")
        
        # File statistics
        if stats['files_by_type']:
            print("\nFILES BY TYPE:")
            for file_type, count in sorted(stats['files_by_type'].items()):
                print(f"   {file_type.capitalize()}: {count}")
        
        # Data extraction statistics
        print("\nDATA EXTRACTION RESULTS:")
        data_stats = stats['data_extraction']
        print(f"   Emails found: {data_stats['emails_found']}")
        print(f"   Phone numbers found: {data_stats['phones_found']}")
        print(f"   Social media links: {data_stats['social_links_found']}")
        print(f"   Forms discovered: {data_stats['forms_found']}")
        print(f"   External links: {data_stats['external_links_found']}")
        print(f"   API endpoints: {data_stats['api_endpoints_found']}")
        
        # Content statistics
        content_stats = stats['content_stats']
        print(f"\nCONTENT ANALYSIS:")
        print(f"   Total words extracted: {content_stats['total_words']:,}")
        print(f"   Pages with content: {content_stats['pages_with_content']}")
        print(f"   Average words per page: {content_stats['average_words_per_page']:.0f}")
        
        # Top pages by links
        print("\nTOP PAGES BY OUTBOUND LINKS:")
        page_link_counts = []
        for url, page_info in self.site_structure.items():
            link_count = len(page_info.get('links', []))
            if link_count > 0:
                title = page_info.get('title', 'Untitled')
                page_link_counts.append((link_count, url, title))
        
        for count, url, title in sorted(page_link_counts, reverse=True)[:10]:
            print(f"   {count:3d} links - {title[:60]}...")
        
        # Sample extracted data
        if self.extracted_data['emails']:
            print(f"\nSAMPLE EMAILS FOUND:")
            for email in list(self.extracted_data['emails'])[:5]:
                print(f"   {email}")
            if len(self.extracted_data['emails']) > 5:
                print(f"   ... and {len(self.extracted_data['emails']) - 5} more")
        
        if self.extracted_data['social_links']:
            print(f"\nSOCIAL MEDIA LINKS:")
            social_by_platform = {}
            for platform, url in self.extracted_data['social_links']:
                if platform not in social_by_platform:
                    social_by_platform[platform] = []
                social_by_platform[platform].append(url)
            
            for platform, urls in social_by_platform.items():
                print(f"   {platform.capitalize()}: {len(urls)} links")
                for url in urls[:2]:  # Show first 2 URLs
                    print(f"     - {url}")
                if len(urls) > 2:
                    print(f"     ... and {len(urls) - 2} more")

    def save_comprehensive_data(self, base_filename: str = "website_crawl"):
        """Save all extracted data in multiple formats"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 1. Save complete JSON structure
            json_filename = f"{base_filename}_{timestamp}.json"
            site_map = self.build_comprehensive_site_map()
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(site_map, f, indent=2, ensure_ascii=False, default=str)
            print(f"Complete data saved to: {json_filename}")
            print(f"   File size: {os.path.getsize(json_filename) / 1024 / 1024:.2f} MB")
            
            # 2. Save extracted emails to CSV
            if self.extracted_data['emails']:
                emails_filename = f"{base_filename}_emails_{timestamp}.csv"
                with open(emails_filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Email'])
                    for email in self.extracted_data['emails']:
                        writer.writerow([email])
                print(f"Emails saved to: {emails_filename}")
            
            # 3. Save page content to CSV
            content_filename = f"{base_filename}_content_{timestamp}.csv"
            with open(content_filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['URL', 'Title', 'Word Count', 'Text Preview'])
                for url, content in self.extracted_data['page_content'].items():
                    writer.writerow([
                        url,
                        content.get('title', ''),
                        content.get('word_count', 0),
                        content.get('text', '')[:500]  # First 500 characters
                    ])
            print(f"Page content saved to: {content_filename}")
            
            # 4. Save forms data
            if self.extracted_data['forms']:
                forms_filename = f"{base_filename}_forms_{timestamp}.json"
                with open(forms_filename, 'w', encoding='utf-8') as f:
                    json.dump(self.extracted_data['forms'], f, indent=2, ensure_ascii=False)
                print(f"Forms data saved to: {forms_filename}")
            
            # 5. Save files inventory
            files_filename = f"{base_filename}_files_{timestamp}.csv"
            with open(files_filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['File Type', 'URL'])
                for file_type, urls in self.files_found.items():
                    for url in urls:
                        writer.writerow([file_type, url])
            print(f"Files inventory saved to: {files_filename}")
            
            # 6. Save sitemap XML
            self.save_sitemap_xml(f"{base_filename}_sitemap_{timestamp}.xml")
            
            return json_filename
            
        except Exception as e:
            print(f"Error saving comprehensive data: {e}")
            return None

    def save_sitemap_xml(self, filename: str = "sitemap.xml"):
        """Save XML sitemap with enhanced metadata"""
        try:
            xml_content = ['<?xml version="1.0" encoding="UTF-8"?>']
            xml_content.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
            
            for url, page_info in self.site_structure.items():
                xml_content.append('  <url>')
                xml_content.append(f'    <loc>{url}</loc>')
                
                # Add last modified if available
                if 'scraped_at' in page_info:
                    xml_content.append(f'    <lastmod>{page_info["scraped_at"][:10]}</lastmod>')
                
                # Add priority based on link count (rough heuristic)
                link_count = len(page_info.get('links', []))
                if link_count > 50:
                    priority = '1.0'
                elif link_count > 20:
                    priority = '0.8'
                elif link_count > 5:
                    priority = '0.6'
                else:
                    priority = '0.4'
                xml_content.append(f'    <priority>{priority}</priority>')
                
                xml_content.append('  </url>')
            
            xml_content.append('</urlset>')
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write('\n'.join(xml_content))
            print(f"XML Sitemap saved to: {filename}")
            
        except Exception as e:
            print(f"Error saving sitemap: {e}")

    def export_to_pandas(self) -> Dict[str, pd.DataFrame]:
        """Export crawled data to pandas DataFrames for analysis"""
        try:
            dataframes = {}
            
            # Pages DataFrame
            pages_data = []
            for url, page_info in self.site_structure.items():
                pages_data.append({
                    'url': url,
                    'title': page_info.get('title', ''),
                    'description': page_info.get('description', ''),
                    'status_code': page_info.get('status_code'),
                    'content_type': page_info.get('content_type', ''),
                    'size': page_info.get('size', 0),
                    'links_count': len(page_info.get('links', [])),
                    'word_count': page_info.get('extracted_data', {}).get('word_count', 0),
                    'scraped_at': page_info.get('scraped_at', '')
                })
            dataframes['pages'] = pd.DataFrame(pages_data)
            
            # Files DataFrame
            files_data = []
            for file_type, urls in self.files_found.items():
                for url in urls:
                    files_data.append({
                        'url': url,
                        'file_type': file_type,
                        'extension': os.path.splitext(urlparse(url).path)[1].lower()
                    })
            dataframes['files'] = pd.DataFrame(files_data)
            
            # Emails DataFrame
            if self.extracted_data['emails']:
                emails_data = [{'email': email} for email in self.extracted_data['emails']]
                dataframes['emails'] = pd.DataFrame(emails_data)
            
            # Social Links DataFrame
            if self.extracted_data['social_links']:
                social_data = [{'platform': platform, 'url': url} 
                              for platform, url in self.extracted_data['social_links']]
                dataframes['social_links'] = pd.DataFrame(social_data)
            
            return dataframes
            
        except Exception as e:
            print(f"Error exporting to pandas: {e}")
            return {}

    def cleanup(self):
        """Cleanup resources"""
        if self.driver:
            self.driver.quit()
        self.session.close()

def run_enhanced_crawler(base_url: str, delay: float = 1.0, max_workers: int = 20, 
                        timeout: int = 20, max_pages: int = None, use_selenium: bool = False,
                        respect_robots: bool = True, extract_emails: bool = True,
                        extract_phones: bool = True, extract_social_links: bool = True,
                        save_data: bool = True) -> dict:
    """
    Run the enhanced crawler with comprehensive data extraction
    
    Args:
        base_url: Starting URL for crawling
        delay: Delay between requests in seconds
        max_workers: Number of concurrent workers
        timeout: Request timeout in seconds
        max_pages: Maximum pages to crawl (None for unlimited)
        use_selenium: Use Selenium for JavaScript-heavy sites
        respect_robots: Respect robots.txt file
        extract_emails: Extract email addresses
        extract_phones: Extract phone numbers
        extract_social_links: Extract social media links
        save_data: Save extracted data to files
    
    Returns:
        Dictionary containing crawl results and extracted data
    """
    crawler = run_crawler(
        base_url=base_url,
        delay=delay,
        max_workers=max_workers,
        timeout=timeout,
        max_pages=max_pages,
        use_selenium=use_selenium,
        respect_robots=respect_robots,
        extract_emails=extract_emails,
        extract_phones=extract_phones,
        extract_social_links=extract_social_links
    )
    
    try:
        # Run the crawl
        structure = crawler.crawl_website()
        
        # Print comprehensive summary
        crawler.print_comprehensive_summary()
        
        # Save data if requested
        saved_file = None
        if save_data:
            saved_file = crawler.save_comprehensive_data()
        
        # Export to pandas for analysis
        dataframes = crawler.export_to_pandas()
        
        return {
            'structure': structure,
            'extracted_data': crawler.extracted_data,
            'statistics': crawler.get_comprehensive_statistics(),
            'page_urls': list(structure.keys()),
            'saved_file': saved_file,
            'dataframes': dataframes
        }
        
    except Exception as e:
        print(f"Error during crawling: {e}")
        return {'error': str(e)}
        
    finally:
        crawler.cleanup()

# Example usage
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Enhanced Deep Website Crawler')
    parser.add_argument('url', help='Base URL to crawl')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between requests')
    parser.add_argument('--workers', type=int, default=20, help='Number of workers')
    parser.add_argument('--timeout', type=int, default=20, help='Request timeout')
    parser.add_argument('--max-pages', type=int, help='Maximum pages to crawl')
    parser.add_argument('--selenium', action='store_true', help='Use Selenium for JS sites')
    parser.add_argument('--no-robots', action='store_true', help='Ignore robots.txt')
    parser.add_argument('--no-emails', action='store_true', help='Skip email extraction')
    parser.add_argument('--no-phones', action='store_true', help='Skip phone extraction')
    parser.add_argument('--no-social', action='store_true', help='Skip social links extraction')
    
    args = parser.parse_args()
    
    result = run_enhanced_crawler(
        base_url=args.url,
        delay=args.delay,
        max_workers=args.workers,
        timeout=args.timeout,
        max_pages=args.max_pages,
        use_selenium=args.selenium,
        respect_robots=not args.no_robots,
        extract_emails=not args.no_emails,
        extract_phones=not args.no_phones,
        extract_social_links=not args.no_social
    )
    
    if 'error' not in result:
        print(f"\nCrawling completed successfully!")
        print(f"Pages crawled: {len(result['page_urls'])}")
        print(f"Data saved to: {result.get('saved_file', 'Not saved')}")
    else:
        print(f"Crawling failed: {result['error']}")