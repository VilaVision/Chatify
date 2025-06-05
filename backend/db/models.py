from sqlalchemy import Column, Integer, String, Text, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class ScrapedPage(Base):
    __tablename__ = 'scraped_pages'
    id = Column(Integer, primary_key=True)
    url = Column(String(500), unique=True)
    raw_html = Column(Text)
    scraped_at = Column(String(100))

class ProcessedPage(Base):
    __tablename__ = 'processed_pages'
    id = Column(Integer, primary_key=True)
    url = Column(String(500), unique=True)
    text = Column(Text)
    structure = Column(JSON)
    processed_at = Column(String(100))

class QAPair(Base):
    __tablename__ = 'qa_pairs'
    id = Column(Integer, primary_key=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    category = Column(String(100))
    source_url = Column(String(500))