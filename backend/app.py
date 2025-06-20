from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import os
import zipfile
import logging

# Your internal modules
from crawler.crawler_module import run_crawler
from scraper.scraper_module import WebScraper
from analytics.analytics_module import AnalyticsModule
from ai.ai_module import AIModule
from chatbot_backend.backend_module import ChatbotBackend
from chatbot_ui.chat_ui_generator import ChatbotUIBuilder
from composer.composer_module import Composer

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

        # 1. Crawl
        crawled_data, _, _ = run_crawler(url, max_pages=30, save_json=True,
                                         json_filename=f"{working_dir}/crawled_links.json")

        # 2. Scrape
        scraper = WebScraper(
            json_file=f"{working_dir}/crawled_links.json",
            output_file=f"{working_dir}/extracted_text_data.json",
            raw_output=f"{working_dir}/raw_html_css_data.json"
        )
        scraper.run()

        # 3. Analytics
        analytics = AnalyticsModule(
            raw_data_path=f"{working_dir}/raw_html_css_data.json",
            html_output=f"{working_dir}/html_only.json",
            css_output=f"{working_dir}/css_only.json",
            text_output=f"{working_dir}/text_extracted.json",
            sql_db=f"{working_dir}/text_data.db"
        )
        analytics.run()

        # 4. AI Module
        ai = AIModule(
            api_key=os.getenv("AIzaSyBQD78QbtoTskQgJDf_8aU1_IRGvJiQylY"),
            text_data_path=f"{working_dir}/text_extracted.json",
            tag_clustered_path=f"{working_dir}/clustered_by_tag.json",
            reordered_path=f"{working_dir}/ordered_content.json",
            qa_output_path=f"{working_dir}/final_qa_output.json",
            css_path=f"{working_dir}/css_only.json",
            ui_output_dir=f"{working_dir}/chatbot_ui"
        )
        ai.run()

        # 5. Backend
        backend = ChatbotBackend(data_path=f"{working_dir}/final_qa_output.json")
        backend.generate()

        # 6. UI
        ui = ChatbotUIBuilder(
            html_path=f"{working_dir}/html_only.json",
            css_path=f"{working_dir}/css_only.json"
        )
        ui.generate()

        # 7. Composer
        composer = Composer(
            input_dirs=[
                f"{working_dir}/chatbot_ui",
                "chatpy/backend/chatbot_backend/output"
            ],
            output_dir=f"{working_dir}/final_package"
        )
        composer.run()

        # 8. Zip package
        zip_path = f"{working_dir}/chatbot_package.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(f"{working_dir}/final_package"):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, f"{working_dir}/final_package")
                    zipf.write(full_path, rel_path)

        return {"message": "Website processed successfully.", "download_url": "/download/chatbot_package.zip"}

    except Exception as e:
        logging.error(f"❌ Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/download/chatbot_package.zip")
def download_zip():
    zip_path = "chatpy/output/chatbot_package.zip"
    if os.path.exists(zip_path):
        return FileResponse(zip_path, media_type="application/zip", filename="chatbot_package.zip")
    return JSONResponse(status_code=404, content={"error": "File not found."})

@app.get("/")
def root():
    return {"message": "✅ Chatify backend ready"}
