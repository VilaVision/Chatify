from flask import Blueprint, request, jsonify
from utils.crowler import run_enhanced_crawler
from utils.extractor import extract_structure_and_text
from utils.file_handler import save_json
from config.paths import STRUCTURE_PATH
import re
import os
from analytics.filters import run_all_filters
from utils.fetcher import fetch_html
import traceback
from utils.data_handler import (
    load_scraped_pages,
    load_processed_pages,
    load_qa_pairs,
    export_qa_pairs_to_json,
    save_scraped_page,
    save_processed_page,
    clean_data_folders
)
from analytics.filter.ai import GeminiAIQAGenerator
from db.database import clear_all_tables
import datetime

scan_blueprint = Blueprint('scan', __name__)

@scan_blueprint.route('/api/scan', methods=['POST'])
def scan_route():
    print("scan_route activated")
    data = request.get_json()
    source_url = data.get('source_url')
    if not source_url:
        return jsonify({'error': 'No source URL provided.'}), 400
    try:
        # Clean previous data
        clean_data_folders()
        clear_all_tables()

        # 1. Crawl the website
        crawl_result = run_enhanced_crawler(source_url)
        structure = crawl_result['structure']
        page_urls = crawl_result.get('page_urls', list(structure.keys()))
        print(f"Pages found: {len(page_urls)}")
        save_json(structure, STRUCTURE_PATH)

        all_text = []
        all_code = []
        all_links = []

        url_pattern = re.compile(r'https?://[^\s]+')

        # 2. For each page, fetch HTML and extract content, save to DB and files
        primary_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Data', 'primary_data'))
        os.makedirs(primary_data_dir, exist_ok=True)
        text_path = os.path.join(primary_data_dir, "text.json")
        code_path = os.path.join(primary_data_dir, "code.json")
        navigation_path = os.path.join(primary_data_dir, "navigation.json")

        for page_url in page_urls:
            try:
                html = fetch_html(page_url)
                scraped_at = datetime.datetime.utcnow().isoformat()
                save_scraped_page(page_url, html, scraped_at)  # Save to DB

                text, code, structure_data = extract_structure_and_text(html)
                processed_at = datetime.datetime.utcnow().isoformat()
                save_processed_page(page_url, text, structure_data, processed_at)  # Save to DB

                all_text.append({'url': page_url, 'text': text})
                all_code.append({'url': page_url, 'code': code})

                # Extract links from the HTML text
                links = url_pattern.findall(text)
                for link in links:
                    all_links.append({'from': page_url, 'link': link})
            except Exception as e:
                print(f"Error processing {page_url}: {e}")
                continue  # Skip pages that fail

        # 3. Save aggregated results in the primary data folder
        save_json({'pages': all_text}, text_path)
        save_json({'pages': all_code}, code_path)
        save_json(all_links, navigation_path)

        # 4. Run all analytics filters in sequence
        data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Data'))
        run_all_filters(data_dir)

        # 5. Generate Q&A pairs using Gemini AI and save to DB and file
        generator = GeminiAIQAGenerator()
        generator.generate_chatbot_training_data_db(questions_per_page=4)
        final_data_dir = os.path.join(data_dir, "final_data")
        os.makedirs(final_data_dir, exist_ok=True)
        qa_json_path = os.path.join(final_data_dir, "qa.json")
        export_qa_pairs_to_json(qa_json_path)

        return jsonify({
            'message': 'Full site scan, extraction, analytics, and Q&A generation complete.',
            'qa_json': qa_json_path
        }), 200
    except Exception as e:
        print("Exception in /api/scan:", e)
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@scan_blueprint.route("/api/scraped_pages", methods=["GET"])
def get_scraped_pages():
    pages = load_scraped_pages()
    result = [
        {"url": p.url, "scraped_at": p.scraped_at}
        for p in pages
    ]
    return jsonify(result)

@scan_blueprint.route("/api/processed_pages", methods=["GET"])
def get_processed_pages():
    pages = load_processed_pages()
    result = [
        {"url": p.url, "processed_at": p.processed_at}
        for p in pages
    ]
    return jsonify(result)

@scan_blueprint.route("/api/qa_pairs", methods=["GET"])
def get_qa_pairs():
    qa_pairs = load_qa_pairs()
    result = [
        {
            "question": qa.question,
            "answer": qa.answer,
            "category": qa.category,
            "source_url": qa.source_url
        }
        for qa in qa_pairs
    ]
    return jsonify(result)

@scan_blueprint.route("/api/export_qa_json", methods=["GET"])
def export_qa_json():
    output_file = "backend/Data/final_data/qa.json"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    export_qa_pairs_to_json(output_file)
    return jsonify({"status": "exported", "file": output_file})

@scan_blueprint.route("/api/generate_qa", methods=["POST"])
def generate_qa():
    data = request.get_json()
    questions_per_page = data.get("questions_per_page", 3)
    generator = GeminiAIQAGenerator()
    generator.generate_chatbot_training_data_db(questions_per_page=questions_per_page)
    return jsonify({"status": "Q&A generation started"})
