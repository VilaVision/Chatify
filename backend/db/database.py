import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base, ScrapedPage, ProcessedPage, QAPair  # adjust as needed
from sqlalchemy.exc import IntegrityError

# Always use an absolute path for the database file
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Data'))
os.makedirs(BASE_DIR, exist_ok=True)
DATABASE_PATH = os.path.join(BASE_DIR, "chatify.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def upsert_processed_page(session, url, text, structure, processed_at):
    from .models import ProcessedPage  # adjust if needed
    page = session.query(ProcessedPage).filter_by(url=url).first()
    if page:
        page.text = text
        page.structure = structure
        page.processed_at = processed_at
    else:
        page = ProcessedPage(
            url=url,
            text=text,
            structure=structure,
            processed_at=processed_at
        )
        session.add(page)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        print(f"Duplicate entry for URL: {url}")

def clear_all_tables():
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        session.query(ScrapedPage).delete()
        session.query(ProcessedPage).delete()
        session.query(QAPair).delete()
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error clearing tables: {e}")
    finally:
        session.close()