from flask import Flask, send_from_directory, jsonify, request
import os
from db.database import init_db
from dotenv import load_dotenv
import traceback
import requests
from bs4 import BeautifulSoup
import json
import csv
from datetime import datetime
import uuid
import sqlite3
from urllib.parse import urljoin, urlparse
import time
from typing import List, Dict, Any
import openai
from anthropic import Anthropic
import re

# Load environment variables from .env file
load_dotenv()

# Define base directory and data directory
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'Data')

# Ensure Data directory and subdirectories exist before DB initialization
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, 'primary_data'), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, 'processed_data'), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, 'final_data'), exist_ok=True)

app = Flask(__name__)

# Enable CORS for frontend-backend communication
from flask_cors import CORS

# Configure CORS with more specific settings
CORS(app, 
     origins=['*'],  # Allow all origins for development
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
     allow_headers=['Content-Type', 'Authorization', 'X-Requested-With'],
     supports_credentials=True)

# Handle OPTIONS requests globally
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add('Access-Control-Allow-Headers', "Content-Type,Authorization,X-Requested-With")
        response.headers.add('Access-Control-Allow-Methods', "GET,POST,PUT,DELETE,OPTIONS")
        return response

try:
    init_db()
    print("Database initialized successfully")
except Exception as e:
    print(f"Database initialization failed: {e}")
    traceback.print_exc()

# Database helper functions
def get_db_connection():
    """Get database connection"""
    try:
        conn = sqlite3.connect(os.path.join(DATA_DIR, 'scanner.db'))
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def create_tables_if_not_exist():
    """Create necessary tables if they don't exist"""
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            # Create scans table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scans (
                    id TEXT PRIMARY KEY,
                    source_url TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT
                )
            ''')
            
            # Create scraped_pages table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scraped_pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_id TEXT,
                    url TEXT NOT NULL,
                    title TEXT,
                    content TEXT,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (scan_id) REFERENCES scans (id)
                )
            ''')
            
            # Create processed_pages table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processed_pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scraped_page_id INTEGER,
                    processed_content TEXT,
                    summary TEXT,
                    keywords TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (scraped_page_id) REFERENCES scraped_pages (id)
                )
            ''')
            
            # Create qa_pairs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS qa_pairs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    processed_page_id INTEGER,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    confidence_score REAL,
                    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (processed_page_id) REFERENCES processed_pages (id)
                )
            ''')
            
            conn.commit()
        except Exception as e:
            print(f"Error creating tables: {e}")
        finally:
            conn.close()

# Initialize tables
create_tables_if_not_exist()

# Web scraping functions
def scrape_website(url: str, max_pages: int = 10) -> List[Dict[str, Any]]:
    """
    Scrape website content
    """
    scraped_data = []
    visited_urls = set()
    to_visit = [url]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    while to_visit and len(scraped_data) < max_pages:
        current_url = to_visit.pop(0)
        
        if current_url in visited_urls:
            continue
            
        visited_urls.add(current_url)
        
        try:
            response = requests.get(current_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract text content
            for script in soup(["script", "style"]):
                script.decompose()
            
            title = soup.find('title')
            title_text = title.get_text().strip() if title else ''
            
            # Extract main content
            content = soup.get_text()
            content = ' '.join(content.split())  # Clean whitespace
            
            page_data = {
                'url': current_url,
                'title': title_text,
                'content': content[:10000],  # Limit content length
                'scraped_at': datetime.now().isoformat()
            }
            
            scraped_data.append(page_data)
            
            # Find internal links to scrape
            base_domain = urlparse(url).netloc
            for link in soup.find_all('a', href=True):
                href = urljoin(current_url, link['href'])
                parsed_href = urlparse(href)
                
                if (parsed_href.netloc == base_domain and 
                    href not in visited_urls and 
                    href not in to_visit and
                    len(to_visit) < max_pages):
                    to_visit.append(href)
            
            time.sleep(1)  # Be respectful to the server
            
        except Exception as e:
            print(f"Error scraping {current_url}: {e}")
            continue
    
    return scraped_data

def process_content(content: str) -> Dict[str, Any]:
    """
    Process scraped content to extract key information
    """
    # Simple text processing
    words = content.split()
    word_count = len(words)
    
    # Extract keywords (simple frequency analysis)
    word_freq = {}
    for word in words:
        word = word.lower().strip('.,!?;:"()[]{}')
        if len(word) > 3 and word.isalpha():
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # Get top keywords
    keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
    keywords = [word for word, freq in keywords]
    
    # Create summary (first 500 characters)
    summary = content[:500] + "..." if len(content) > 500 else content
    
    return {
        'processed_content': content,
        'summary': summary,
        'keywords': ', '.join(keywords),
        'word_count': word_count,
        'processed_at': datetime.now().isoformat()
    }

def generate_qa_pairs_simple(content: str, title: str = "") -> List[Dict[str, Any]]:
    """
    Generate Q&A pairs from content using simple rule-based approach
    """
    qa_pairs = []
    
    # Split content into sentences
    sentences = re.split(r'[.!?]+', content)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    
    # Generate basic Q&A pairs
    for i, sentence in enumerate(sentences[:5]):  # Limit to 5 pairs
        if len(sentence) > 30:
            # Simple question generation
            if title:
                question = f"What can you tell me about {title.lower()}?"
                answer = sentence
            else:
                # Extract key phrases for questions
                words = sentence.split()
                if len(words) > 5:
                    question = f"What is mentioned about {' '.join(words[:3]).lower()}?"
                    answer = sentence
                else:
                    continue
            
            qa_pairs.append({
                'question': question,
                'answer': answer,
                'confidence_score': 0.7,  # Simple confidence score
                'generated_at': datetime.now().isoformat()
            })
    
    return qa_pairs

def generate_qa_pairs_ai(content: str, title: str = "", provider: str = "simple") -> List[Dict[str, Any]]:
    """
    Generate Q&A pairs using AI providers
    """
    if provider == "openai" and os.getenv('OPENAI_API_KEY'):
        return generate_qa_openai(content, title)
    elif provider == "anthropic" and os.getenv('ANTHROPIC_API_KEY'):
        return generate_qa_anthropic(content, title)
    else:
        return generate_qa_pairs_simple(content, title)

def generate_qa_openai(content: str, title: str = "") -> List[Dict[str, Any]]:
    """Generate Q&A pairs using OpenAI"""
    try:
        client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        prompt = f"""
        Based on the following content, generate 5 relevant question-answer pairs.
        Title: {title}
        Content: {content[:2000]}
        
        Format each Q&A pair as:
        Q: [question]
        A: [answer]
        
        Make sure questions are diverse and answers are informative.
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000
        )
        
        qa_text = response.choices[0].message.content
        return parse_qa_response(qa_text)
        
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return generate_qa_pairs_simple(content, title)

def generate_qa_anthropic(content: str, title: str = "") -> List[Dict[str, Any]]:
    """Generate Q&A pairs using Anthropic"""
    try:
        client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        
        prompt = f"""
        Based on the following content, generate 5 relevant question-answer pairs.
        Title: {title}
        Content: {content[:2000]}
        
        Format each Q&A pair as:
        Q: [question]
        A: [answer]
        
        Make sure questions are diverse and answers are informative.
        """
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        qa_text = response.content[0].text
        return parse_qa_response(qa_text)
        
    except Exception as e:
        print(f"Anthropic API error: {e}")
        return generate_qa_pairs_simple(content, title)

def parse_qa_response(qa_text: str) -> List[Dict[str, Any]]:
    """Parse AI-generated Q&A response"""
    qa_pairs = []
    lines = qa_text.split('\n')
    
    current_q = None
    current_a = None
    
    for line in lines:
        line = line.strip()
        if line.startswith('Q:'):
            current_q = line[2:].strip()
        elif line.startswith('A:') and current_q:
            current_a = line[2:].strip()
            qa_pairs.append({
                'question': current_q,
                'answer': current_a,
                'confidence_score': 0.8,
                'generated_at': datetime.now().isoformat()
            })
            current_q = None
            current_a = None
    
    return qa_pairs

# COMPLETED: Enhanced scan route with actual scanning logic
@app.route('/api/scan', methods=['POST'])
def scan_website():
    """
    Website scanning endpoint with complete implementation
    """
    try:
        data = request.get_json()
        if not data or 'source_url' not in data:
            return jsonify({
                'error': 'Missing source_url in request body'
            }), 400
        
        source_url = data['source_url']
        max_pages = data.get('max_pages', 10)
        
        # Validate URL format
        if not source_url.startswith(('http://', 'https://')):
            return jsonify({
                'error': 'Invalid URL format. URL must start with http:// or https://'
            }), 400
        
        # Generate scan ID
        scan_id = str(uuid.uuid4())
        
        # Save scan to database
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO scans (id, source_url, status) VALUES (?, ?, ?)",
                (scan_id, source_url, 'in_progress')
            )
            conn.commit()
            
            # Perform actual scraping
            scraped_data = scrape_website(source_url, max_pages)
            
            # Save scraped data to database and files
            files_created = []
            
            for page_data in scraped_data:
                # Save to database
                cursor.execute(
                    "INSERT INTO scraped_pages (scan_id, url, title, content) VALUES (?, ?, ?, ?)",
                    (scan_id, page_data['url'], page_data['title'], page_data['content'])
                )
            
            # Save raw data to JSON file
            raw_file = f'scraped_data_{scan_id}.json'
            raw_path = os.path.join(DATA_DIR, 'primary_data', raw_file)
            with open(raw_path, 'w', encoding='utf-8') as f:
                json.dump(scraped_data, f, indent=2, ensure_ascii=False)
            
            files_created.append({
                'name': raw_file,
                'type': 'primary_data',
                'download_url': f'/download/{raw_file}'
            })
            
            # Process data and save to CSV
            processed_file = f'processed_data_{scan_id}.csv'
            processed_path = os.path.join(DATA_DIR, 'processed_data', processed_file)
            
            with open(processed_path, 'w', newline='', encoding='utf-8') as f:
                if scraped_data:
                    writer = csv.DictWriter(f, fieldnames=scraped_data[0].keys())
                    writer.writeheader()
                    writer.writerows(scraped_data)
            
            files_created.append({
                'name': processed_file,
                'type': 'processed_data',
                'download_url': f'/download/{processed_file}'
            })
            
            # Update scan status
            cursor.execute(
                "UPDATE scans SET status = ?, completed_at = ? WHERE id = ?",
                ('completed', datetime.now(), scan_id)
            )
            conn.commit()
            
            return jsonify({
                'message': f'Scan completed for {source_url}',
                'status': 'success',
                'source_url': source_url,
                'scan_id': scan_id,
                'pages_scraped': len(scraped_data),
                'files': files_created
            }), 200
            
        except Exception as e:
            # Update scan status to failed
            cursor.execute(
                "UPDATE scans SET status = ?, error_message = ? WHERE id = ?",
                ('failed', str(e), scan_id)
            )
            conn.commit()
            raise e
        finally:
            conn.close()
        
    except Exception as e:
        print(f"Scan error: {e}")
        traceback.print_exc()
        return jsonify({
            'error': f'Scan failed: {str(e)}'
        }), 500

# Import and register blueprints after defining the fallback route
import sys
print(f"Python path: {sys.path}")
print(f"Current working directory: {os.getcwd()}")

try:
    # Try different import paths
    try:
        from routes.scan_routes import scan_blueprint
        print("Successfully imported from routes.scan_routes")
        app.register_blueprint(scan_blueprint)
        print("External scan routes registered successfully")
    except ImportError:
        try:
            # Try importing from current directory
            from scan_routes import scan_blueprint
            print("Successfully imported from scan_routes (current directory)")
            app.register_blueprint(scan_blueprint)
            print("External scan routes registered successfully")
        except ImportError:
            print("External scan routes not found - using built-in scan route")
    
    # Print all registered routes for debugging
    print("Registered routes:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.rule} -> {rule.methods}")
        
except ImportError as e:
    print(f"Failed to import external scan routes: {e}")
    print("Using built-in scan route")

# Register chatbot API
try:
    try:
        from chatbot.api import chatbot_blueprint
    except ImportError:
        from api import chatbot_blueprint
    app.register_blueprint(chatbot_blueprint)
    print("Chatbot routes registered successfully")
except ImportError as e:
    print(f"Failed to import chatbot routes: {e}")
    print("Chatbot routes not available - this is optional")

# COMPLETED: Get scraped pages data with actual database query
@app.route('/api/scraped_pages', methods=['GET'])
def get_scraped_pages():
    """Get scraped pages data from database"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sp.*, s.source_url 
            FROM scraped_pages sp 
            LEFT JOIN scans s ON sp.scan_id = s.id 
            ORDER BY sp.scraped_at DESC
        """)
        
        rows = cursor.fetchall()
        data = []
        
        for row in rows:
            data.append({
                'id': row['id'],
                'scan_id': row['scan_id'],
                'url': row['url'],
                'title': row['title'],
                'content_preview': row['content'][:200] + '...' if len(row['content']) > 200 else row['content'],
                'scraped_at': row['scraped_at'],
                'source_url': row['source_url']
            })
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'data': data,
            'total_count': len(data),
            'message': f'Found {len(data)} scraped pages'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# COMPLETED: Get processed pages data with actual database query
@app.route('/api/processed_pages', methods=['GET'])
def get_processed_pages():
    """Get processed pages data from database"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pp.*, sp.url, sp.title 
            FROM processed_pages pp 
            LEFT JOIN scraped_pages sp ON pp.scraped_page_id = sp.id 
            ORDER BY pp.processed_at DESC
        """)
        
        rows = cursor.fetchall()
        data = []
        
        for row in rows:
            data.append({
                'id': row['id'],
                'scraped_page_id': row['scraped_page_id'],
                'url': row['url'],
                'title': row['title'],
                'summary': row['summary'],
                'keywords': row['keywords'],
                'processed_at': row['processed_at']
            })
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'data': data,
            'total_count': len(data),
            'message': f'Found {len(data)} processed pages'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# COMPLETED: Get Q&A pairs data with actual database query
@app.route('/api/qa_pairs', methods=['GET'])
def get_qa_pairs():
    """Get Q&A pairs data from database"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT qa.*, pp.summary, sp.url, sp.title 
            FROM qa_pairs qa 
            LEFT JOIN processed_pages pp ON qa.processed_page_id = pp.id
            LEFT JOIN scraped_pages sp ON pp.scraped_page_id = sp.id 
            ORDER BY qa.generated_at DESC
        """)
        
        rows = cursor.fetchall()
        data = []
        
        for row in rows:
            data.append({
                'id': row['id'],
                'processed_page_id': row['processed_page_id'],
                'question': row['question'],
                'answer': row['answer'],
                'confidence_score': row['confidence_score'],
                'generated_at': row['generated_at'],
                'source_url': row['url'],
                'source_title': row['title']
            })
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'data': data,
            'total_count': len(data),
            'message': f'Found {len(data)} Q&A pairs'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# COMPLETED: Q&A generation logic implementation
@app.route('/api/generate_qa', methods=['POST'])
def generate_qa():
    """Generate Q&A pairs from scraped content"""
    try:
        data = request.get_json()
        scan_id = data.get('scan_id')
        provider = data.get('provider', 'simple')
        
        if not scan_id:
            return jsonify({'error': 'scan_id is required'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        
        # Get scraped pages for this scan
        cursor.execute("SELECT * FROM scraped_pages WHERE scan_id = ?", (scan_id,))
        pages = cursor.fetchall()
        
        if not pages:
            return jsonify({'error': 'No scraped pages found for this scan'}), 404
        
        total_qa_generated = 0
        
        for page in pages:
            # Process content
            processed_data = process_content(page['content'])
            
            # Save processed data
            cursor.execute("""
                INSERT INTO processed_pages 
                (scraped_page_id, processed_content, summary, keywords) 
                VALUES (?, ?, ?, ?)
            """, (page['id'], processed_data['processed_content'], 
                  processed_data['summary'], processed_data['keywords']))
            
            processed_page_id = cursor.lastrowid
            
            # Generate Q&A pairs
            qa_pairs = generate_qa_pairs_ai(page['content'], page['title'], provider)
            
            # Save Q&A pairs
            for qa in qa_pairs:
                cursor.execute("""
                    INSERT INTO qa_pairs 
                    (processed_page_id, question, answer, confidence_score) 
                    VALUES (?, ?, ?, ?)
                """, (processed_page_id, qa['question'], qa['answer'], qa['confidence_score']))
                
                total_qa_generated += 1
        
        conn.commit()
        
        # Export Q&A pairs to file
        qa_file = f'qa_pairs_{scan_id}.json'
        qa_path = os.path.join(DATA_DIR, 'final_data', qa_file)
        
        cursor.execute("""
            SELECT qa.*, sp.url, sp.title 
            FROM qa_pairs qa 
            JOIN processed_pages pp ON qa.processed_page_id = pp.id
            JOIN scraped_pages sp ON pp.scraped_page_id = sp.id
            WHERE sp.scan_id = ?
        """, (scan_id,))
        
        qa_data = []
        for row in cursor.fetchall():
            qa_data.append({
                'question': row['question'],
                'answer': row['answer'],
                'confidence_score': row['confidence_score'],
                'source_url': row['url'],
                'source_title': row['title'],
                'generated_at': row['generated_at']
            })
        
        with open(qa_path, 'w', encoding='utf-8') as f:
            json.dump(qa_data, f, indent=2, ensure_ascii=False)
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': f'Generated {total_qa_generated} Q&A pairs',
            'scan_id': scan_id,
            'total_qa_pairs': total_qa_generated,
            'pages_processed': len(pages),
            'export_file': qa_file
        })
        
    except Exception as e:
        print(f"Q&A generation error: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/providers', methods=['GET'])
def get_providers():
    """Get available AI providers"""
    providers = [
        {
            'name': 'Simple', 
            'id': 'simple',
            'available': True,
            'description': 'Rule-based Q&A generation'
        },
        {
            'name': 'OpenAI', 
            'id': 'openai',
            'available': bool(os.getenv('OPENAI_API_KEY')),
            'description': 'GPT-powered Q&A generation'
        },
        {
            'name': 'Anthropic', 
            'id': 'anthropic',
            'available': bool(os.getenv('ANTHROPIC_API_KEY')),
            'description': 'Claude-powered Q&A generation'
        }
    ]
    
    return jsonify({
        'status': 'success',
        'providers': providers
    })

@app.route('/api/qa_stats', methods=['GET'])
def get_qa_stats():
    """Get Q&A statistics from database"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        
        # Get total Q&A pairs
        cursor.execute("SELECT COUNT(*) as count FROM qa_pairs")
        total_qa = cursor.fetchone()['count']
        
        # Get total processed pages
        cursor.execute("SELECT COUNT(*) as count FROM processed_pages")
        total_processed = cursor.fetchone()['count']
        
        # Get last scan info
        cursor.execute("""
            SELECT source_url, completed_at 
            FROM scans 
            WHERE status = 'completed' 
            ORDER BY completed_at DESC 
            LIMIT 1
        """)
        last_scan = cursor.fetchone()
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'stats': {
                'total_qa_pairs': total_qa,
                'total_pages_processed': total_processed,
                'last_scan': {
                    'url': last_scan['source_url'] if last_scan else None,
                    'completed_at': last_scan['completed_at'] if last_scan else None
                } if last_scan else None
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Debug endpoint to list all routes
@app.route('/api/debug/routes', methods=['GET'])
def list_routes():
    """Debug endpoint to list all registered routes"""
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods),
            'rule': rule.rule
        })
    return jsonify({
        'total_routes': len(routes),
        'routes': routes
    })

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint to verify API is running"""
    return jsonify({
        'status': 'healthy',
        'message': 'API is running',
        'data_dir': DATA_DIR,
        'base_dir': BASE_DIR
    }), 200

# File download endpoint with enhanced search functionality
@app.route('/download/<path:filename>')
def download_file(filename):
    """
    Enhanced file download endpoint that searches across multiple data folders
    """
    try:
        # Search in all relevant subfolders
        search_folders = [
            "primary_data", 
            "processed_data", 
            "final_data",
            "analytics",
            "exports"
        ]
        
        for subfolder in search_folders:
            folder = os.path.join(DATA_DIR, subfolder)
            if os.path.exists(folder):
                file_path = os.path.join(folder, filename)
                if os.path.exists(file_path):
                    print(f"Serving file: {file_path}")
                    return send_from_directory(folder, filename, as_attachment=True)
        
        # Fallback: search in Data root
        file_path = os.path.join(DATA_DIR, filename)
        if os.path.exists(file_path):
            print(f"Serving file from root: {file_path}")
            return send_from_directory(DATA_DIR, filename, as_attachment=True)
        
        print(f"File not found: {filename}")
        return jsonify({'error': f'File not found: {filename}'}), 404
        
    except Exception as e:
        print(f"Error serving file {filename}: {e}")
        return jsonify({'error': f'Error serving file: {str(e)}'}), 500

# List available files endpoint
@app.route('/api/files', methods=['GET'])
def list_files():
    """
    List all available files in the data directories
    """
    try:
        files_info = {}
        search_folders = [
            "primary_data", 
            "processed_data", 
            "final_data",
            "analytics",
            "exports"
        ]
        
        for subfolder in search_folders:
            folder = os.path.join(DATA_DIR, subfolder)
            if os.path.exists(folder):
                files = []
                for file in os.listdir(folder):
                    if os.path.isfile(os.path.join(folder, file)):
                        file_path = os.path.join(folder, file)
                        file_size = os.path.getsize(file_path)
                        files.append({
                            'name': file,
                            'size': file_size,
                            'download_url': f'/download/{file}'
                        })
                files_info[subfolder] = files
        
        # Also check root data directory
        root_files = []
        for file in os.listdir(DATA_DIR):
            file_path = os.path.join(DATA_DIR, file)
            if os.path.isfile(file_path):
                file_size = os.path.getsize(file_path)
                root_files.append({
                    'name': file,
                    'size': file_size,
                    'download_url': f'/download/{file}'
                })
        
        if root_files:
            files_info['root'] = root_files
        
        return jsonify({
            'status': 'success',
            'files': files_info,
            'data_directory': DATA_DIR
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to list files: {str(e)}'
        }), 500

# Data directory info endpoint
@app.route('/api/data-info', methods=['GET'])
def data_info():
    """
    Get information about the data directory structure
    """
    try:
        dir_info = {
            'base_dir': BASE_DIR,
            'data_dir': DATA_DIR,
            'directories': {}
        }
        
        # Check each subdirectory
        subdirs = ["primary_data", "processed_data", "final_data", "analytics", "exports"]
        
        for subdir in subdirs:
            path = os.path.join(DATA_DIR, subdir)
            dir_info['directories'][subdir] = {
                'exists': os.path.exists(path),
                'path': path,
                'file_count': len(os.listdir(path)) if os.path.exists(path) else 0
            }
        
        return jsonify(dir_info)
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to get data info: {str(e)}'
        }), 500

# Additional utility endpoints
@app.route('/api/scan_status/<scan_id>', methods=['GET'])
def get_scan_status(scan_id):
    """Get status of a specific scan"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scans WHERE id = ?", (scan_id,))
        scan = cursor.fetchone()
        
        if not scan:
            return jsonify({'error': 'Scan not found'}), 404
        
        # Get related data counts
        cursor.execute("SELECT COUNT(*) as count FROM scraped_pages WHERE scan_id = ?", (scan_id,))
        scraped_count = cursor.fetchone()['count']
        
        cursor.execute("""
            SELECT COUNT(*) as count FROM processed_pages pp
            JOIN scraped_pages sp ON pp.scraped_page_id = sp.id
            WHERE sp.scan_id = ?
        """, (scan_id,))
        processed_count = cursor.fetchone()['count']
        
        cursor.execute("""
            SELECT COUNT(*) as count FROM qa_pairs qa
            JOIN processed_pages pp ON qa.processed_page_id = pp.id
            JOIN scraped_pages sp ON pp.scraped_page_id = sp.id
            WHERE sp.scan_id = ?
        """, (scan_id,))
        qa_count = cursor.fetchone()['count']
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'scan': {
                'id': scan['id'],
                'source_url': scan['source_url'],
                'status': scan['status'],
                'created_at': scan['created_at'],
                'completed_at': scan['completed_at'],
                'error_message': scan['error_message'],
                'scraped_pages_count': scraped_count,
                'processed_pages_count': processed_count,
                'qa_pairs_count': qa_count
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scans', methods=['GET'])
def get_all_scans():
    """Get all scans with their status"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scans ORDER BY created_at DESC")
        scans = cursor.fetchall()
        
        data = []
        for scan in scans:
            # Get counts for each scan
            cursor.execute("SELECT COUNT(*) as count FROM scraped_pages WHERE scan_id = ?", (scan['id'],))
            scraped_count = cursor.fetchone()['count']
            
            data.append({
                'id': scan['id'],
                'source_url': scan['source_url'],
                'status': scan['status'],
                'created_at': scan['created_at'],
                'completed_at': scan['completed_at'],
                'error_message': scan['error_message'],
                'scraped_pages_count': scraped_count
            })
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'scans': data,
            'total_count': len(data)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export_data/<scan_id>', methods=['GET'])
def export_scan_data(scan_id):
    """Export all data for a specific scan"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        
        # Get scan info
        cursor.execute("SELECT * FROM scans WHERE id = ?", (scan_id,))
        scan = cursor.fetchone()
        
        if not scan:
            return jsonify({'error': 'Scan not found'}), 404
        
        # Get all related data
        cursor.execute("""
            SELECT sp.*, pp.summary, pp.keywords, pp.processed_at
            FROM scraped_pages sp
            LEFT JOIN processed_pages pp ON sp.id = pp.scraped_page_id
            WHERE sp.scan_id = ?
        """, (scan_id,))
        
        pages_data = []
        for row in cursor.fetchall():
            pages_data.append({
                'url': row['url'],
                'title': row['title'],
                'content': row['content'],
                'scraped_at': row['scraped_at'],
                'summary': row['summary'],
                'keywords': row['keywords'],
                'processed_at': row['processed_at']
            })
        
        # Get Q&A pairs
        cursor.execute("""
            SELECT qa.question, qa.answer, qa.confidence_score, qa.generated_at, sp.url, sp.title
            FROM qa_pairs qa
            JOIN processed_pages pp ON qa.processed_page_id = pp.id
            JOIN scraped_pages sp ON pp.scraped_page_id = sp.id
            WHERE sp.scan_id = ?
        """, (scan_id,))
        
        qa_data = []
        for row in cursor.fetchall():
            qa_data.append({
                'question': row['question'],
                'answer': row['answer'],
                'confidence_score': row['confidence_score'],
                'generated_at': row['generated_at'],
                'source_url': row['url'],
                'source_title': row['title']
            })
        
        conn.close()
        
        # Create export data
        export_data = {
            'scan_info': {
                'id': scan['id'],
                'source_url': scan['source_url'],
                'status': scan['status'],
                'created_at': scan['created_at'],
                'completed_at': scan['completed_at']
            },
            'pages': pages_data,
            'qa_pairs': qa_data,
            'exported_at': datetime.now().isoformat()
        }
        
        # Save to file
        export_file = f'export_{scan_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        export_path = os.path.join(DATA_DIR, 'exports', export_file)
        
        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'status': 'success',
            'message': 'Data exported successfully',
            'export_file': export_file,
            'download_url': f'/download/{export_file}',
            'data_summary': {
                'total_pages': len(pages_data),
                'total_qa_pairs': len(qa_data)
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    """Handle uncaught exceptions"""
    print(f"Unhandled exception: {e}")
    traceback.print_exc()
    return jsonify({
        'error': 'An unexpected error occurred',
        'message': str(e)
    }), 500

# Root endpoint
@app.route('/')
def index():
    """Root endpoint with API information"""
    return jsonify({
        'message': 'Web Scanner API',
        'version': '1.0.0',
        'endpoints': {
            'scan': '/api/scan - POST - Start website scanning process',
            'health': '/api/health - GET - Health check',
            'files': '/api/files - GET - List available files',
            'data_info': '/api/data-info - GET - Data directory information',
            'scraped_pages': '/api/scraped_pages - GET - Get scraped pages',
            'processed_pages': '/api/processed_pages - GET - Get processed pages',
            'qa_pairs': '/api/qa_pairs - GET - Get Q&A pairs',
            'generate_qa': '/api/generate_qa - POST - Generate Q&A pairs',
            'providers': '/api/providers - GET - Get available AI providers',
            'qa_stats': '/api/qa_stats - GET - Get Q&A statistics',
            'scans': '/api/scans - GET - Get all scans',
            'scan_status': '/api/scan_status/<scan_id> - GET - Get scan status',
            'export_data': '/api/export_data/<scan_id> - GET - Export scan data'
        }
    })

if __name__ == "__main__":
    print(f"Starting Flask application...")
    print(f"Base directory: {BASE_DIR}")
    print(f"Data directory: {DATA_DIR}")
    print(f"Scan endpoint available at: /api/scan")
    
    # Create additional directories
    os.makedirs(os.path.join(DATA_DIR, 'analytics'), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, 'exports'), exist_ok=True)
    
    app.run(debug=True, host='0.0.0.0', port=5000)