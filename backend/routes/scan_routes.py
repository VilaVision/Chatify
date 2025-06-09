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
from analytics.filter.ai import MultimodalQAGenerator  # Updated import
from db.database import clear_all_tables
import datetime

scan_blueprint = Blueprint('scan', __name__)

def get_qa_generator(provider_configs=None):
    """
    Factory function to create QA generator with error handling
    
    Args:
        provider_configs (dict): Optional provider configurations
        
    Returns:
        MultimodalQAGenerator: Configured generator instance
    """
    try:
        if provider_configs:
            return MultimodalQAGenerator(provider_configs)
        else:
            # Try to initialize from environment variables
            return MultimodalQAGenerator()
    except Exception as e:
        print(f"Warning: Failed to initialize multimodal generator: {str(e)}")
        print("Make sure at least one AI provider API key is configured.")
        raise e

@scan_blueprint.route('/api/scan', methods=['POST'])
def scan_route():
    """Enhanced scan route with multimodal AI support"""
    print("scan_route activated")
    data = request.get_json()
    source_url = data.get('source_url')
    
    # New parameters for AI configuration
    questions_per_page = data.get('questions_per_page', 50)
    preferred_provider = data.get('preferred_provider')  # Optional: "gemini", "openai", "claude", "deepseek"
    provider_configs = data.get('provider_configs')  # Optional: custom API keys
    
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

        # 5. Generate Q&A pairs using Multimodal AI Generator
        try:
            generator = get_qa_generator(provider_configs)
            
            # Generate Q&A pairs with multimodal support
            generator.generate_chatbot_training_data_db(
                questions_per_page=questions_per_page,
                preferred_provider=preferred_provider
            )
            
            # Export to JSON file
            final_data_dir = os.path.join(data_dir, "final_data")
            os.makedirs(final_data_dir, exist_ok=True)
            qa_json_path = os.path.join(final_data_dir, "qa_multimodal.json")
            export_qa_pairs_to_json(qa_json_path)
            
            # Get provider statistics
            qa_pairs = load_qa_pairs()
            provider_stats = {}
            for qa in qa_pairs:
                # Assuming you add a generated_by field to your database model
                provider = getattr(qa, 'generated_by', 'unknown')
                provider_stats[provider] = provider_stats.get(provider, 0) + 1
            
            return jsonify({
                'message': 'Full site scan, extraction, analytics, and multimodal Q&A generation complete.',
                'qa_json': qa_json_path,
                'total_qa_pairs': len(qa_pairs),
                'provider_statistics': provider_stats,
                'available_providers': list(generator.providers.keys())
            }), 200
            
        except Exception as e:
            print(f"Q&A Generation failed: {str(e)}")
            return jsonify({
                'message': 'Site scan and extraction complete, but Q&A generation failed.',
                'error': f'Q&A Generation Error: {str(e)}',
                'suggestion': 'Please check your AI provider API keys and try the /api/generate_qa endpoint separately.'
            }), 206  # Partial success

    except Exception as e:
        print("Exception in /api/scan:", e)
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@scan_blueprint.route("/api/scraped_pages", methods=["GET"])
def get_scraped_pages():
    """Get list of scraped pages"""
    pages = load_scraped_pages()
    result = [
        {"url": p.url, "scraped_at": p.scraped_at}
        for p in pages
    ]
    return jsonify(result)

@scan_blueprint.route("/api/processed_pages", methods=["GET"])
def get_processed_pages():
    """Get list of processed pages"""
    pages = load_processed_pages()
    result = [
        {"url": p.url, "processed_at": p.processed_at}
        for p in pages
    ]
    return jsonify(result)

@scan_blueprint.route("/api/qa_pairs", methods=["GET"])
def get_qa_pairs():
    """Get all Q&A pairs with enhanced metadata"""
    qa_pairs = load_qa_pairs()
    result = []
    
    for qa in qa_pairs:
        qa_data = {
            "question": qa.question,
            "answer": qa.answer,
            "category": qa.category,
            "source_url": qa.source_url
        }
        
        # Add provider information if available
        if hasattr(qa, 'generated_by'):
            qa_data['generated_by'] = qa.generated_by
            
        result.append(qa_data)
    
    return jsonify(result)

@scan_blueprint.route("/api/export_qa_json", methods=["GET"])
def export_qa_json():
    """Export Q&A pairs to JSON file"""
    output_file = "backend/Data/final_data/qa_multimodal.json"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    export_qa_pairs_to_json(output_file)
    return jsonify({"status": "exported", "file": output_file})

@scan_blueprint.route("/api/generate_qa", methods=["POST"])
def generate_qa():
    """
    Enhanced Q&A generation endpoint with multimodal support
    
    Expected JSON payload:
    {
        "questions_per_page": 3,
        "preferred_provider": "gemini",  // Optional
        "provider_configs": {  // Optional
            "gemini": {"api_key": "key", "model": "gemini-2.0-flash"},
            "openai": {"api_key": "key", "model": "gpt-4"}
        }
    }
    """
    try:
        data = request.get_json() or {}
        questions_per_page = data.get("questions_per_page", 10)
        preferred_provider = data.get("preferred_provider")
        provider_configs = data.get("provider_configs")
        
        # Initialize multimodal generator
        generator = get_qa_generator(provider_configs)
        
        # Generate Q&A pairs
        generator.generate_chatbot_training_data_db(
            questions_per_page=questions_per_page,
            preferred_provider=preferred_provider
        )
        
        # Get statistics
        qa_pairs = load_qa_pairs()
        provider_stats = {}
        for qa in qa_pairs:
            provider = getattr(qa, 'generated_by', 'unknown')
            provider_stats[provider] = provider_stats.get(provider, 0) + 1
        
        return jsonify({
            "status": "Q&A generation completed successfully",
            "total_pairs": len(qa_pairs),
            "provider_statistics": provider_stats,
            "available_providers": list(generator.providers.keys())
        })
        
    except Exception as e:
        print(f"Q&A Generation error: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "error": f"Q&A Generation failed: {str(e)}",
            "suggestion": "Check your AI provider API keys and ensure at least one is configured."
        }), 500

@scan_blueprint.route("/api/providers", methods=["GET"])
def get_available_providers():
    """Get information about available AI providers"""
    try:
        generator = get_qa_generator()
        
        provider_info = {}
        for provider_name, provider in generator.providers.items():
            provider_info[provider_name] = {
                "name": provider.get_provider_name(),
                "status": "available"
            }
        
        return jsonify({
            "available_providers": provider_info,
            "total_count": len(provider_info),
            "fallback_order": generator.fallback_order
        })
        
    except Exception as e:
        return jsonify({
            "error": f"Could not initialize providers: {str(e)}",
            "suggestion": "Please configure at least one AI provider API key via environment variables or request body."
        }), 500

@scan_blueprint.route("/api/providers/test", methods=["POST"])
def test_providers():
    """Test AI providers with a simple prompt"""
    try:
        data = request.get_json() or {}
        provider_configs = data.get("provider_configs")
        test_prompt = data.get("test_prompt", "Generate a simple greeting message.")
        
        generator = get_qa_generator(provider_configs)
        
        test_results = {}
        
        for provider_name in generator.providers.keys():
            try:
                response, used_provider = generator.generate_with_fallback(
                    test_prompt, 
                    preferred_provider=provider_name,
                    max_tokens=100,
                    timeout=10
                )
                
                test_results[provider_name] = {
                    "status": "success",
                    "response_preview": response[:100] + "..." if len(response) > 100 else response,
                    "used_provider": used_provider
                }
                
            except Exception as e:
                test_results[provider_name] = {
                    "status": "failed",
                    "error": str(e)
                }
        
        return jsonify({
            "test_results": test_results,
            "test_prompt": test_prompt
        })
        
    except Exception as e:
        return jsonify({
            "error": f"Provider test failed: {str(e)}"
        }), 500

@scan_blueprint.route("/api/qa_stats", methods=["GET"])
def get_qa_statistics():
    """Get detailed statistics about Q&A pairs"""
    try:
        qa_pairs = load_qa_pairs()
        
        # Basic statistics
        total_pairs = len(qa_pairs)
        
        # Category distribution
        category_stats = {}
        provider_stats = {}
        source_stats = {}
        
        for qa in qa_pairs:
            # Category stats
            category = qa.category or 'uncategorized'
            category_stats[category] = category_stats.get(category, 0) + 1
            
            # Provider stats (if available)
            provider = getattr(qa, 'generated_by', 'unknown')
            provider_stats[provider] = provider_stats.get(provider, 0) + 1
            
            # Source URL stats
            source = qa.source_url or 'unknown'
            source_stats[source] = source_stats.get(source, 0) + 1
        
        return jsonify({
            "total_pairs": total_pairs,
            "category_distribution": category_stats,
            "provider_distribution": provider_stats,
            "source_distribution": source_stats,
            "top_categories": sorted(category_stats.items(), key=lambda x: x[1], reverse=True)[:5],
            "top_sources": sorted(source_stats.items(), key=lambda x: x[1], reverse=True)[:5]
        })
        
    except Exception as e:
        return jsonify({
            "error": f"Failed to get Q&A statistics: {str(e)}"
        }), 500