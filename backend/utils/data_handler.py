from db.database import SessionLocal
from db.models import ScrapedPage, ProcessedPage, QAPair

def save_scraped_page(url, raw_html, scraped_at):
    from db.database import SessionLocal
    from db.models import ScrapedPage
    session = SessionLocal()
    try:
        # Check if the URL already exists
        existing = session.query(ScrapedPage).filter_by(url=url).first()
        if existing:
            # Optionally update the existing record, or just skip
            # existing.raw_html = raw_html
            # existing.scraped_at = scraped_at
            # session.commit()
            return
        page = ScrapedPage(url=url, raw_html=raw_html, scraped_at=scraped_at)
        session.add(page)
        session.commit()
    except Exception as e:
        print(f"Error saving scraped page: {e}")
        session.rollback()
    finally:
        session.close()

def load_scraped_pages():
    session = SessionLocal()
    pages = session.query(ScrapedPage).all()
    session.close()
    return pages

def save_processed_page(url, text, structure, processed_at):
    session = SessionLocal()
    page = ProcessedPage(url=url, text=text, structure=structure, processed_at=processed_at)
    session.merge(page)
    session.commit()
    session.close()

def load_processed_pages():
    session = SessionLocal()
    pages = session.query(ProcessedPage).all()
    session.close()
    return pages

def save_qa_pair(question, answer, category, source_url):
    session = SessionLocal()
    qa = QAPair(question=question, answer=answer, category=category, source_url=source_url)
    session.add(qa)
    session.commit()
    session.close()

def load_qa_pairs():
    session = SessionLocal()
    qa_pairs = session.query(QAPair).all()
    session.close()
    return qa_pairs

def export_qa_pairs_to_json(output_file):
    qa_pairs = load_qa_pairs()
    data = [
        {
            "question": qa.question,
            "answer": qa.answer,
            "category": qa.category,
            "source_url": qa.source_url
        }
        for qa in qa_pairs
    ]
    import json
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({"qa_pairs": data, "total_pairs": len(data)}, f, indent=2, ensure_ascii=False)

# Clear all scraped pages (use with caution!)
def clear_scraped_pages():
    session = SessionLocal()
    session.query(ScrapedPage).delete()
    session.commit()
    session.close()