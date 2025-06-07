# Chatipy

Chatify is an AI-powered website and text scanner that crawls websites or local HTML files, extracts their content and structure, and generates chatbot-ready Q&A pairs using Google Gemini AI. The project features a modern frontend for user interaction and a robust Python backend for crawling, extraction, analytics, and training data generation.

## Features

- **Website & Local File Scanning:** Scan any website URL or local HTML file.
- **Deep Crawling:** Multi-threaded crawler explores all internal links and resources.
- **Content Extraction:** Extracts text, code blocks, and page structure from HTML.
- **Analytics & Preprocessing:** Cleans, organizes, and summarizes extracted data.
- **AI Q&A Generation:** Uses openai(default) or any other ai. to generate chatbot training data from website content.
- **Downloadable Results:** Download extracted text and structure as JSON files.
- **Modern UI:** Clean, responsive frontend built vanilla HTML/CSS.

## Project Structure

```
    A[User/Frontend] -->|POST /api/scan| B[Flask App (app.py)]
    B --> C[scan_blueprint (scan_routes.py)]
    C --> D[Clean Data Folders & Clear DB]
    D --> E[run_enhanced_crawler (crowler.py)]
    E --> F{For Each Page}
    F --> G[fetch_html (fetcher.py)]
    G --> H[extract_structure_and_text (extractor.py)]
    H --> I[save_scraped_page (data_handler.py)]
    H --> J[save_processed_page (data_handler.py)]
    F -->|Extracted Text/Code/Links| K[Aggregate Data]
    K --> L[Save text.json, code.json, navigation.json]
    L --> M[run_all_filters (analytics/filters.py)]
    M --> N[GeminiAIQAGenerator (ai.py)]
    N --> O[Generate Q&A Pairs]
    O --> P[Save qa.json & Import to qa_data.db]
    P --> Q[Return Scan Complete Response]
    Q -->|User Downloads or Chat| R[Download/Chatbot/Search Endpoints]
    R --> S[qa_data.db]
    S -->|/api/chat or /api/search| T[Chatbot Blueprint (chatbot/api.py)]
    T --> U[Return Answer or Search Results]
```

## How It Works

1. **User Input:** Enter a website URL or local HTML file path in the frontend.
2. **Crawling:** The backend crawls the site, collecting all reachable pages and resources.
3. **Extraction:** Text, code, and structure are extracted from each page.
4. **Analytics:** Data is cleaned, deduplicated, and organized into a folder structure.
5. **Q&A Generation:** Gemini AI generates chatbot Q&A pairs from the cleaned text.
6. **Download:** Users can download the extracted data and structure.

## Getting Started

### Prerequisites

- Python 3.8+
- HTML/CSS
- OpenAI API key (set `OpenAI_API_KEY` environment variable)

### Backend Setup

```sh
cd backend
pip install -r requirements.txt
python app.py
```

### Frontend Setup

```sh
cd frontend
start index.html
```

### Usage

1. Open the frontend in your browser (`http://localhost:3000` or as served).
2. Enter a website URL or local HTML file path.
3. Click "Scan" to start crawling and extraction.
4. Download results or use generated Q&A for chatbot training.

## Future Work

- **Support for More File Types:** Add PDF, DOCX, and markdown support.
- **Customizable Q&A Generation:** Allow users to set prompt templates and categories.
- **Multi-language Support:** Enable extraction and Q&A generation in multiple languages.
- **Improved Analytics:** Add more advanced text analytics and summarization.
- **Integration with More AI Models:** Support for other LLMs (OpenAI, Anthropic, etc).
- **User Authentication:** Allow users to save and manage their scans and Q&A sets.
- **Deployment Scripts:** Add Docker and cloud deployment options.

## Contributing

Contributions are welcome! To contribute:

1. Fork this repository.
2. Create a new branch for your feature or bugfix.
3. Make your changes and add tests if applicable.
4. Submit a pull request with a clear description.

For major changes, please open an issue first to discuss what you would like to change.

## Acknowledgements

- **OpenAI:** For powerful AI-driven Q&A generation.
- **Flask:** For the backend API framework.
- **HTML/CSS:** For building the modern frontend interface.
- **Beautiful Soup & Requests:** For web scraping and crawling capabilities.

---

MIT License
