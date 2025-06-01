import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "Data")
PRIMARY_DATA_DIR = os.path.join(DATA_DIR, "primary_data")
PROCESSED_DATA_DIR = os.path.join(DATA_DIR, "processed_data")
FINAL_DATA_DIR = os.path.join(DATA_DIR, "final_data")

CODE_PATH = os.path.join(PRIMARY_DATA_DIR, "code.json")
LINK_DATA_PATH = os.path.join(PROCESSED_DATA_DIR, "link_data.json")
STRUCTURE_PATH = os.path.join(PROCESSED_DATA_DIR, "structure.json")
TEXT_PATH = os.path.join(PRIMARY_DATA_DIR, "text.json")
NAVIGATION_PATH = os.path.join(PRIMARY_DATA_DIR, "navigation.json")
CLEANED_TEXT_PATH = os.path.join(PROCESSED_DATA_DIR, "cleaned_text.json")
QA_PATH = os.path.join(FINAL_DATA_DIR, "qa.json")