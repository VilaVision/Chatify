from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import zipfile
import logging

# Load environment variables
load_dotenv()

# Your internal modules
from crawler.crawler_module import run_crawler
from scraper.scraper_module import WebScraper
from analytics.analytics_module import AnalyticsModule
from ai.ai_module import ChatbotGenerator  # AI Module should import dotenv
# from chatbot_backend.backend_module import ChatbotBackend
# from chatbot_ui.chat_ui_generator import ChatbotUIBuilder
# from composer.composer_module import Composer

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScanRequest(BaseModel):
    source_url: str

@app.post("/api/scan")
async def scan_website(request: ScanRequest):
    url = request.source_url
    working_dir = "chatpy/output"
    os.makedirs(working_dir, exist_ok=True)

    try:
        logging.info(f"🔗 Processing site: {url}")

        # Step 1: Crawl the website
        logging.info("📡 Step 1: Crawling website...")
        crawled_data, _, _ = run_crawler(url, max_pages=30, save_json=True,
                                         json_filename=f"{working_dir}/crawled_links.json")
        logging.info(f"✅ Crawled {len(crawled_data) if crawled_data else 0} pages")

        # Step 2: Scrape content from crawled pages
        logging.info("🔍 Step 2: Scraping content...")
        scraper = WebScraper(
            json_file=f"{working_dir}/crawled_links.json",
            output_file=f"{working_dir}/extracted_text_data.json",
            raw_output=f"{working_dir}/raw_html_css_data.json"
        )
        scraper.run()
        logging.info("✅ Content scraping completed")

        # Step 3: Analytics - Extract and organize text data
        logging.info("📊 Step 3: Processing and analyzing content...")
        analytics = AnalyticsModule(
            raw_data_path=f"{working_dir}/raw_html_css_data.json",
            html_output=f"{working_dir}/html_only.json",
            css_output=f"{working_dir}/css_only.json",
            text_output=f"{working_dir}/text_extracted.json",
            sql_db=f"{working_dir}/text_data.db"
        )
        analytics.run()
        logging.info("✅ Text extraction and analysis completed")

        # ✅ Step 4: AI Module only — let it run the full pipeline
        logging.info("🤖 Step 4: Letting AI module run the full Q&A pipeline...")
        ai = ChatbotGenerator(
            text_data_path=f"{working_dir}/text_extracted.json",
            tag_clustered_path=f"{working_dir}/clustered_by_tag.json",
            reordered_path=f"{working_dir}/ordered_content.json",
            qa_output_path=f"{working_dir}/final_qa_output.json",
            css_path=f"{working_dir}/css_only.json",
            ui_output_dir=f"{working_dir}/chatbot_ui"
        )
        ai.run_pipeline()
        logging.info("✅ AI module completed full Q&A + UI pipeline")

        # Final check
        qa_file = f"{working_dir}/final_qa_output.json"
        if not os.path.exists(qa_file):
            raise Exception("AI module failed to generate Q&A data")

        qa_file_size = os.path.getsize(qa_file)
        logging.info(f"📝 Generated Q&A file size: {qa_file_size} bytes")

        # Zip results
        logging.info("🗜️ Step 5: Creating zip package...")
        zip_path = f"{working_dir}/chatbot_package.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(f"{working_dir}/chatbot_ui"):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, f"{working_dir}/chatbot_ui")
                    zipf.write(full_path, rel_path)

        zip_size = os.path.getsize(zip_path)
        logging.info(f"✅ Zip package created: {zip_size} bytes")

        return {
            "message": "Website processed successfully with AI-generated Q&A",
            "download_url": "/download/chatbot_package.zip",
            "qa_generated": True,
            "qa_file_size": qa_file_size
        }

    except Exception as e:
        logging.error(f"❌ Error during processing: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/download/chatbot_package.zip")
def download_zip():
    zip_path = "chatpy/output/chatbot_package.zip"
    if os.path.exists(zip_path):
        return FileResponse(zip_path, media_type="application/zip", filename="chatbot_package.zip")
    return JSONResponse(status_code=404, content={"error": "File not found."})

@app.get("/api/status")
def get_status():
    working_dir = "chatpy/output"
    status = {
        "service": "running",
        "files_present": {}
    }
    key_files = [
        "crawled_links.json",
        "text_extracted.json",
        "final_qa_output.json",
        "chatbot_package.zip"
    ]
    for file in key_files:
        file_path = os.path.join(working_dir, file)
        status["files_present"][file] = os.path.exists(file_path)
        if os.path.exists(file_path):
            status["files_present"][f"{file}_size"] = os.path.getsize(file_path)
    return status

@app.get("/")
def root():
    return {"message": "✅ Chatify backend ready - AI Q&A generation enabled"}
