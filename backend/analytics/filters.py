import os
import json
import re

from analytics.filter.ai import QAGenerator

def clean_text_to_bullets(text):
    """
    Cleans raw text to bullet-point format.
    Strips tags, extra spaces, and converts repetitive items to bullets.
    """
    if not text:
        return ""

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)

    # Break into lines if nav-like repeated structure is found
    lines = re.split(r'(?:\\n|\\r|[\u2022•])', text)
    lines = [line.strip() for line in lines if line.strip()]

    # Remove duplicates while preserving order
    seen = set()
    bullets = []
    for line in lines:
        if line not in seen:
            bullets.append(f"- {line}")
            seen.add(line)

    return "\n".join(bullets)

def run_all_filters(data_dir):
    """
    1. Loads extracted_dataset.json
    2. Cleans and restructures into: {url, title, text (as bullet points)}
    3. Saves cleaned version
    4. Generates Q&A pairs using Gemini
    """
    print("🚀 Starting full data processing pipeline...")
    
    extracted_path = os.path.join("extracted_dataset.json")
    cleaned_output_path = os.path.join(data_dir, "processed_data", "cleaned_text.json")
    qa_output_path = os.path.join(data_dir, "final_data", "qa.json")

    os.makedirs(os.path.dirname(cleaned_output_path), exist_ok=True)
    os.makedirs(os.path.dirname(qa_output_path), exist_ok=True)

    # Step 1: Load raw extracted data
    if not os.path.exists(extracted_path):
        raise FileNotFoundError("extracted_dataset.json not found.")

    with open(extracted_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)

    # Step 2: Clean and restructure
    cleaned_data = []
    for page in raw_data.get("pages", []):
        url = page.get("url")
        title = page.get("title", "")
        raw_text = page.get("text", "")

        cleaned_text = clean_text_to_bullets(raw_text)

        cleaned_data.append({
            "url": url,
            "title": title,
            "cleaned_text": cleaned_text
        })

    # Step 3: Save cleaned text
    with open(cleaned_output_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

    print(f"✅ Cleaned text saved to {cleaned_output_path}")

    # Step 4: Run Gemini Q&A generation
    print("🧠 Running Q&A generation...")
    generator = qagenerator()
    generator.generate_chatbot_training_data(
        input_file=cleaned_output_path,
        output_file=qa_output_path,
        questions_per_page=4
    )

    print(f"✅ Q&A generation saved to {qa_output_path}")

if __name__ == "__main__":
    base_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'Data'))
    run_all_filters(base_data_dir)
