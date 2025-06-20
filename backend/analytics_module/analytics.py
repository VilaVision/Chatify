import json
import os
import sqlite3
import logging
import re
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from bs4 import BeautifulSoup, Comment
import html as html_lib
from urllib.parse import urljoin, urlparse
import hashlib

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('analytics.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Directories
DATA_DIR = "data"
OUTPUT_DIR = "output"
REPORTS_DIR = "reports"

# Create directories
for directory in [DATA_DIR, OUTPUT_DIR, REPORTS_DIR]:
    os.makedirs(directory, exist_ok=True)

# File paths
SCRAPED_DATA_FILE = os.path.join(DATA_DIR, "scraped_dataset.json")
HTML_FILE = os.path.join(OUTPUT_DIR, "html_data.json")
CSS_FILE = os.path.join(OUTPUT_DIR, "css_data.json")
TEXT_FILE = os.path.join(OUTPUT_DIR, "text_data.json")
LINKS_FILE = os.path.join(OUTPUT_DIR, "links_data.json")
IMAGES_FILE = os.path.join(OUTPUT_DIR, "images_data.json")
METADATA_FILE = os.path.join(OUTPUT_DIR, "metadata.json")
DB_FILE = os.path.join(OUTPUT_DIR, "content.db")

class WebContentAnalyzer:
    def __init__(self):
        self.stats = {
            'total_entries': 0,
            'successful_parses': 0,
            'failed_parses': 0,
            'total_html_entries': 0,
            'total_css_entries': 0,
            'total_text_entries': 0,
            'total_links': 0,
            'total_images': 0,
            'processing_time': 0
        }
    
    def load_scraped_data(self, file_path: str = SCRAPED_DATA_FILE) -> List[Dict]:
        """Load and validate scraped data from JSON file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"The file '{file_path}' does not exist.")
        
        if os.path.getsize(file_path) == 0:
            raise ValueError(f"The file '{file_path}' is empty.")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"Loaded JSON data of type: {type(data)}")
            
            # Handle different JSON formats
            if isinstance(data, list):
                logger.info(f"Data is already a list with {len(data)} entries")
                return data
            
            elif isinstance(data, dict):
                logger.info("Data is a dictionary, attempting to convert...")
                
                # Check for common patterns
                if 'pages' in data and isinstance(data['pages'], list):
                    logger.info(f"Found 'pages' key with {len(data['pages'])} entries")
                    return data['pages']
                
                elif 'data' in data and isinstance(data['data'], list):
                    logger.info(f"Found 'data' key with {len(data['data'])} entries")
                    return data['data']
                
                elif 'results' in data and isinstance(data['results'], list):
                    logger.info(f"Found 'results' key with {len(data['results'])} entries")
                    return data['results']
                
                elif 'items' in data and isinstance(data['items'], list):
                    logger.info(f"Found 'items' key with {len(data['items'])} entries")
                    return data['items']
                
                elif 'entries' in data and isinstance(data['entries'], list):
                    logger.info(f"Found 'entries' key with {len(data['entries'])} entries")
                    return data['entries']
                
                else:
                    # If it's a single object, wrap it in a list
                    if 'url' in data or 'html' in data:
                        logger.info("Data appears to be a single entry, wrapping in list")
                        return [data]
                    
                    # Check if values are the entries
                    dict_values = list(data.values())
                    if dict_values and isinstance(dict_values[0], dict) and ('url' in dict_values[0] or 'html' in dict_values[0]):
                        logger.info(f"Data appears to be keyed entries, extracting {len(dict_values)} values")
                        return dict_values
                    
                    # Print structure for debugging
                    logger.info(f"Dictionary keys: {list(data.keys())}")
                    if data:
                        first_key = list(data.keys())[0]
                        logger.info(f"Sample value type for key '{first_key}': {type(data[first_key])}")
                    
                    raise ValueError(f"Dictionary format not recognized. Keys: {list(data.keys())}")
            
            else:
                raise ValueError(f"Unexpected data type: {type(data)}. Expected list or dict.")
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format in '{file_path}': {e}")
        except Exception as e:
            raise Exception(f"Error loading data from '{file_path}': {e}")
    
    def clean_html_content(self, raw_html: str) -> str:
        """Clean and decode HTML content."""
        if not raw_html:
            return ""
        
        # Unescape HTML entities and fix quotes
        html_content = html_lib.unescape(
            raw_html.replace('\\"', '"').replace("\\'", "'")
        )
        
        return html_content
    
    def extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict:
        """Extract metadata from HTML."""
        metadata = {
            'url': url,
            'title': '',
            'description': '',
            'keywords': '',
            'author': '',
            'language': '',
            'charset': '',
            'viewport': '',
            'og_tags': {},
            'twitter_tags': {},
            'canonical_url': '',
            'robots': '',
            'word_count': 0,
            'content_hash': ''
        }
        
        # Title
        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.get_text(strip=True)
        
        # Meta tags
        meta_tags = soup.find_all('meta')
        for meta in meta_tags:
            name = meta.get('name', '').lower()
            property_attr = meta.get('property', '').lower()
            content = meta.get('content', '')
            
            if name == 'description':
                metadata['description'] = content
            elif name == 'keywords':
                metadata['keywords'] = content
            elif name == 'author':
                metadata['author'] = content
            elif name == 'robots':
                metadata['robots'] = content
            elif name == 'viewport':
                metadata['viewport'] = content
            elif property_attr.startswith('og:'):
                metadata['og_tags'][property_attr] = content
            elif name.startswith('twitter:'):
                metadata['twitter_tags'][name] = content
            elif meta.get('charset'):
                metadata['charset'] = meta.get('charset')
        
        # Language
        html_tag = soup.find('html')
        if html_tag:
            metadata['language'] = html_tag.get('lang', '')
        
        # Canonical URL
        canonical = soup.find('link', {'rel': 'canonical'})
        if canonical:
            metadata['canonical_url'] = canonical.get('href', '')
        
        # Calculate word count and content hash
        text_content = soup.get_text(strip=True)
        metadata['word_count'] = len(text_content.split())
        metadata['content_hash'] = hashlib.md5(text_content.encode()).hexdigest()
        
        return metadata
    
    def extract_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract all links from HTML."""
        links = []
        
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not href or href.startswith('#'):
                continue
            
            # Convert relative URLs to absolute
            absolute_url = urljoin(base_url, href)
            
            link_data = {
                'url': base_url,
                'link_url': absolute_url,
                'link_text': link.get_text(strip=True),
                'link_title': link.get('title', ''),
                'is_external': urlparse(absolute_url).netloc != urlparse(base_url).netloc,
                'rel': link.get('rel', []),
                'target': link.get('target', '')
            }
            links.append(link_data)
        
        return links
    
    def extract_images(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract all images from HTML."""
        images = []
        
        for img in soup.find_all('img'):
            src = img.get('src', '').strip()
            if not src:
                continue
            
            # Convert relative URLs to absolute
            absolute_url = urljoin(base_url, src)
            
            image_data = {
                'url': base_url,
                'image_url': absolute_url,
                'alt_text': img.get('alt', ''),
                'title': img.get('title', ''),
                'width': img.get('width', ''),
                'height': img.get('height', ''),
                'loading': img.get('loading', ''),
                'srcset': img.get('srcset', '')
            }
            images.append(image_data)
        
        return images
    
    def extract_css(self, soup: BeautifulSoup, url: str) -> List[Dict]:
        """Extract CSS from style tags and linked stylesheets."""
        css_data = []
        
        # Inline CSS from <style> tags
        for i, style in enumerate(soup.find_all("style")):
            css_text = style.get_text(strip=True)
            if css_text:
                css_data.append({
                    'url': url,
                    'type': 'inline',
                    'source': f'style_tag_{i}',
                    'css': css_text,
                    'media': style.get('media', 'all')
                })
        
        # External CSS from <link> tags
        for link in soup.find_all('link', {'rel': 'stylesheet'}):
            href = link.get('href', '')
            if href:
                css_data.append({
                    'url': url,
                    'type': 'external',
                    'source': urljoin(url, href),
                    'css': '',  # Content would need to be fetched separately
                    'media': link.get('media', 'all')
                })
        
        return css_data
    
    def extract_text_content(self, soup: BeautifulSoup, url: str) -> List[Dict]:
        """Extract text content with improved filtering."""
        text_data = []
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        
        # Extract text from specific tags
        important_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'td', 'th', 'blockquote', 'pre']
        
        for tag_name in important_tags:
            for tag in soup.find_all(tag_name):
                text = tag.get_text(strip=True)
                if text and len(text) > 2:  # Filter out very short text
                    text_data.append({
                        'url': url,
                        'tag': tag_name,
                        'text': text,
                        'class': ' '.join(tag.get('class', [])),
                        'id': tag.get('id', ''),
                        'length': len(text)
                    })
        
        return text_data
    
    def extract_all_content(self, scraped_data: List[Dict]) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict], List[Dict], List[Dict]]:
        """Extract all content types from scraped data."""
        html_data = []
        css_data = []
        text_data = []
        links_data = []
        images_data = []
        metadata_list = []
        
        self.stats['total_entries'] = len(scraped_data)
        
        for i, entry in enumerate(scraped_data):
            if not isinstance(entry, dict):
                logger.warning(f"Skipping invalid entry at index {i}")
                self.stats['failed_parses'] += 1
                continue
            
            url = entry.get("url", f"unknown_{i}")
            raw_html = entry.get("html", "")
            
            if not raw_html:
                logger.warning(f"No HTML content found for URL: {url}")
                self.stats['failed_parses'] += 1
                continue
            
            try:
                # Clean HTML content
                html_content = self.clean_html_content(raw_html)
                
                # Parse with BeautifulSoup
                soup = BeautifulSoup(html_content, "html.parser")
                
                # Store raw HTML
                html_data.append({
                    "url": url,
                    "html": html_content,
                    "size": len(html_content)
                })
                
                # Extract metadata
                metadata = self.extract_metadata(soup, url)
                metadata_list.append(metadata)
                
                # Extract CSS
                css_entries = self.extract_css(soup, url)
                css_data.extend(css_entries)
                
                # Extract text content
                text_entries = self.extract_text_content(soup, url)
                text_data.extend(text_entries)
                
                # Extract links
                link_entries = self.extract_links(soup, url)
                links_data.extend(link_entries)
                
                # Extract images
                image_entries = self.extract_images(soup, url)
                images_data.extend(image_entries)
                
                self.stats['successful_parses'] += 1
                
                if (i + 1) % 100 == 0:
                    logger.info(f"Processed {i + 1}/{len(scraped_data)} entries")
                
            except Exception as e:
                logger.error(f"Error processing entry {i} (URL: {url}): {e}")
                self.stats['failed_parses'] += 1
        
        # Update stats
        self.stats['total_html_entries'] = len(html_data)
        self.stats['total_css_entries'] = len(css_data)
        self.stats['total_text_entries'] = len(text_data)
        self.stats['total_links'] = len(links_data)
        self.stats['total_images'] = len(images_data)
        
        return html_data, css_data, text_data, links_data, images_data, metadata_list
    
    def save_json(self, data: List[Dict], filepath: str) -> None:
        """Save data to JSON file with error handling."""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(data)} entries to {filepath}")
        except Exception as e:
            logger.error(f"Error saving to {filepath}: {e}")
            raise
    
    def setup_database(self, db_path: str = DB_FILE) -> sqlite3.Connection:
        """Setup SQLite database with consolidated dataset table."""
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Main consolidated dataset table
        c.execute("""
            CREATE TABLE IF NOT EXISTS dataset (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                tag TEXT,
                text_content TEXT,
                external_links TEXT,
                image_urls TEXT,
                title TEXT,
                description TEXT,
                word_count INTEGER,
                content_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Text content table (separate detailed table)
        c.execute("""
            CREATE TABLE IF NOT EXISTS text_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                tag TEXT,
                text TEXT,
                class TEXT,
                element_id TEXT,
                length INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Metadata table
        c.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                title TEXT,
                description TEXT,
                keywords TEXT,
                author TEXT,
                language TEXT,
                word_count INTEGER,
                content_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Links table
        c.execute("""
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url TEXT,
                target_url TEXT,
                link_text TEXT,
                is_external BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Images table
        c.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url TEXT,
                image_url TEXT,
                alt_text TEXT,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # CSS table
        c.execute("""
            CREATE TABLE IF NOT EXISTS css (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                type TEXT,
                source TEXT,
                css_content TEXT,
                media TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for better performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_dataset_url ON dataset(url)",
            "CREATE INDEX IF NOT EXISTS idx_dataset_tag ON dataset(tag)",
            "CREATE INDEX IF NOT EXISTS idx_text_url ON text_content(url)",
            "CREATE INDEX IF NOT EXISTS idx_text_tag ON text_content(tag)",
            "CREATE INDEX IF NOT EXISTS idx_metadata_url ON metadata(url)",
            "CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_url)",
            "CREATE INDEX IF NOT EXISTS idx_images_source ON images(source_url)",
            "CREATE INDEX IF NOT EXISTS idx_css_url ON css(url)"
        ]
        
        for index in indexes:
            c.execute(index)
        
        conn.commit()
        return conn
    
    def consolidate_dataset_for_db(self, text_data: List[Dict], metadata_list: List[Dict], 
                                  links_data: List[Dict], images_data: List[Dict]) -> List[Dict]:
        """Consolidate all data into the requested database format."""
        consolidated_data = {}
        
        # Group data by URL
        for metadata in metadata_list:
            url = metadata['url']
            consolidated_data[url] = {
                'url': url,
                'title': metadata.get('title', ''),
                'description': metadata.get('description', ''),
                'word_count': metadata.get('word_count', 0),
                'content_hash': metadata.get('content_hash', ''),
                'text_by_tag': {},
                'external_links': [],
                'image_urls': []
            }
        
        # Group text content by URL and tag
        for text_entry in text_data:
            url = text_entry['url']
            tag = text_entry['tag']
            text = text_entry['text']
            
            if url in consolidated_data:
                if tag not in consolidated_data[url]['text_by_tag']:
                    consolidated_data[url]['text_by_tag'][tag] = []
                consolidated_data[url]['text_by_tag'][tag].append(text)
        
        # Add external links
        for link_entry in links_data:
            url = link_entry['url']
            if url in consolidated_data and link_entry.get('is_external', False):
                consolidated_data[url]['external_links'].append(link_entry['link_url'])
        
        # Add image URLs
        for image_entry in images_data:
            url = image_entry['url']
            if url in consolidated_data:
                consolidated_data[url]['image_urls'].append(image_entry['image_url'])
        
        # Convert to the format needed for database insertion
        dataset_entries = []
        for url, data in consolidated_data.items():
            # Create entries for each tag type
            for tag, texts in data['text_by_tag'].items():
                combined_text = ' '.join(texts[:5])  # Limit to first 5 texts per tag to avoid too long entries
                
                dataset_entries.append({
                    'url': url,
                    'tag': tag,
                    'text_content': combined_text,
                    'external_links': '|'.join(data['external_links'][:10]),  # Limit to first 10 external links
                    'image_urls': '|'.join(data['image_urls'][:10]),  # Limit to first 10 images
                    'title': data['title'],
                    'description': data['description'],
                    'word_count': data['word_count'],
                    'content_hash': data['content_hash']
                })
            
            # If no text content, create at least one entry with metadata
            if not data['text_by_tag']:
                dataset_entries.append({
                    'url': url,
                    'tag': '',
                    'text_content': '',
                    'external_links': '|'.join(data['external_links'][:10]),
                    'image_urls': '|'.join(data['image_urls'][:10]),
                    'title': data['title'],
                    'description': data['description'],
                    'word_count': data['word_count'],
                    'content_hash': data['content_hash']
                })
        
        return dataset_entries
    
    def save_to_database(self, text_data: List[Dict], metadata_list: List[Dict], 
                        links_data: List[Dict], images_data: List[Dict], 
                        css_data: List[Dict], db_path: str = DB_FILE) -> None:
        """Save all data to SQLite database."""
        conn = self.setup_database(db_path)
        c = conn.cursor()
        
        try:
            # Consolidate dataset for the main table
            logger.info("Consolidating dataset for database...")
            dataset_entries = self.consolidate_dataset_for_db(text_data, metadata_list, links_data, images_data)
            
            # Insert consolidated dataset
            if dataset_entries:
                c.executemany("""
                    INSERT INTO dataset (url, tag, text_content, external_links, image_urls, 
                                       title, description, word_count, content_hash) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [(entry["url"], entry["tag"], entry["text_content"], 
                      entry["external_links"], entry["image_urls"], entry["title"],
                      entry["description"], entry["word_count"], entry["content_hash"]) 
                     for entry in dataset_entries])
                logger.info(f"Inserted {len(dataset_entries)} entries into dataset table")
            
            # Insert text content
            if text_data:
                c.executemany("""
                    INSERT INTO text_content (url, tag, text, class, element_id, length) 
                    VALUES (?, ?, ?, ?, ?, ?)
                """, [(entry["url"], entry["tag"], entry["text"], 
                      entry.get("class", ""), entry.get("id", ""), entry["length"]) 
                     for entry in text_data])
                logger.info(f"Inserted {len(text_data)} entries into text_content table")
            
            # Insert metadata
            if metadata_list:
                c.executemany("""
                    INSERT OR REPLACE INTO metadata 
                    (url, title, description, keywords, author, language, word_count, content_hash) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, [(entry["url"], entry["title"], entry["description"], 
                      entry["keywords"], entry["author"], entry["language"], 
                      entry["word_count"], entry["content_hash"]) 
                     for entry in metadata_list])
                logger.info(f"Inserted {len(metadata_list)} entries into metadata table")
            
            # Insert links
            if links_data:
                c.executemany("""
                    INSERT INTO links (source_url, target_url, link_text, is_external) 
                    VALUES (?, ?, ?, ?)
                """, [(entry["url"], entry["link_url"], entry["link_text"], 
                      entry["is_external"]) for entry in links_data])
                logger.info(f"Inserted {len(links_data)} entries into links table")
            
            # Insert images
            if images_data:
                c.executemany("""
                    INSERT INTO images (source_url, image_url, alt_text, title) 
                    VALUES (?, ?, ?, ?)
                """, [(entry["url"], entry["image_url"], entry["alt_text"], 
                      entry["title"]) for entry in images_data])
                logger.info(f"Inserted {len(images_data)} entries into images table")
            
            # Insert CSS
            if css_data:
                c.executemany("""
                    INSERT INTO css (url, type, source, css_content, media) 
                    VALUES (?, ?, ?, ?, ?)
                """, [(entry["url"], entry["type"], entry["source"], 
                      entry["css"], entry["media"]) for entry in css_data])
                logger.info(f"Inserted {len(css_data)} entries into css table")
            
            conn.commit()
            logger.info("Successfully saved all data to database")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error saving to database: {e}")
            raise
        finally:
            conn.close()
    
    def generate_report(self) -> None:
        """Generate a summary report."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'statistics': self.stats,
            'files_created': [
                HTML_FILE,
                CSS_FILE,
                TEXT_FILE,
                LINKS_FILE,
                IMAGES_FILE,
                METADATA_FILE,
                DB_FILE
            ]
        }
        
        report_file = os.path.join(REPORTS_DIR, f"analytics_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Report saved to {report_file}")
        
        # Print summary
        print("\n" + "="*50)
        print("ANALYTICS SUMMARY")
        print("="*50)
        print(f"Total entries processed: {self.stats['total_entries']}")
        print(f"Successful parses: {self.stats['successful_parses']}")
        print(f"Failed parses: {self.stats['failed_parses']}")
        print(f"HTML entries: {self.stats['total_html_entries']}")
        print(f"CSS entries: {self.stats['total_css_entries']}")
        print(f"Text entries: {self.stats['total_text_entries']}")
        print(f"Links extracted: {self.stats['total_links']}")
        print(f"Images extracted: {self.stats['total_images']}")
        print("="*50)

def main():
    """Main execution function."""
    start_time = datetime.now()
    analyzer = WebContentAnalyzer()
    
    try:
        logger.info("Starting web content analysis...")
        
        # Load scraped data
        logger.info("Loading scraped dataset...")
        scraped_data = analyzer.load_scraped_data()
        
        # Extract all content
        logger.info("Extracting content...")
        html_data, css_data, text_data, links_data, images_data, metadata_list = analyzer.extract_all_content(scraped_data)
        
        # Save to JSON files
        logger.info("Saving to JSON files...")
        analyzer.save_json(html_data, HTML_FILE)
        analyzer.save_json(css_data, CSS_FILE)
        analyzer.save_json(text_data, TEXT_FILE)
        analyzer.save_json(links_data, LINKS_FILE)
        analyzer.save_json(images_data, IMAGES_FILE)
        analyzer.save_json(metadata_list, METADATA_FILE)
        
        # Save to database
        logger.info("Saving to database...")
        analyzer.save_to_database(text_data, metadata_list, links_data, images_data, css_data)
        
        # Calculate processing time
        end_time = datetime.now()
        analyzer.stats['processing_time'] = (end_time - start_time).total_seconds()
        
        # Generate report
        analyzer.generate_report()
        
        logger.info("Analytics module completed successfully!")
        
    except Exception as e:
        logger.error(f"Analytics module failed: {e}")
        raise

if __name__ == "__main__":
    main()