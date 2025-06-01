from flask import Blueprint, request, jsonify
from utils.crowler import run_crawler
from utils.extractor import extract_structure_and_text
from utils.file_handler import save_json
from config.paths import STRUCTURE_PATH
import re
import os
from analytics.filters import run_all_filters
from utils.fetcher import fetch_html
import traceback

scan_blueprint = Blueprint('scan', __name__)

@scan_blueprint.route('/scan', methods=['POST'])
def scan_route():
    data = request.get_json()
    source_url = data.get('source_url')
    if not source_url:
        return jsonify({'error': 'No source URL provided.'}), 400
    try:
        # 1. Crawl the website
        crawl_result = run_crawler(source_url)
        structure = crawl_result['structure']
        page_urls = crawl_result.get('page_urls', list(structure.keys()))
        save_json(structure, STRUCTURE_PATH)

        all_text = []
        all_code = []
        all_links = []

        
        url_pattern = re.compile(r'https?://[^\s]+')

        # 2. For each page, fetch HTML and extract content
        for page_url in page_urls:
            try:
                html = fetch_html(page_url)
                text, code, _ = extract_structure_and_text(html)
                all_text.append({'url': page_url, 'text': text})
                all_code.append({'url': page_url, 'code': code})

                # Extract links from the HTML text
                links = url_pattern.findall(text)
                for link in links:
                    all_links.append({'from': page_url, 'link': link})
            except Exception:
                continue  # Skip pages that fail

        # 3. Save aggregated results in the primary data folder
        primary_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Data', 'primary_data'))
        os.makedirs(primary_data_dir, exist_ok=True)
        text_path = os.path.join(primary_data_dir, "text.json")
        code_path = os.path.join(primary_data_dir, "code.json")
        navigation_path = os.path.join(primary_data_dir, "navigation.json")

        save_json({'pages': all_text}, text_path)
        save_json({'pages': all_code}, code_path)
        save_json(all_links, navigation_path)

        # 4. Run all analytics filters in sequence
        data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Data'))
        run_all_filters(data_dir)

        return jsonify({
            'message': 'Full site scan, extraction, and all filters complete.'
        }), 200
    except Exception as e:
        print("Exception in /api/scan:", e)
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
