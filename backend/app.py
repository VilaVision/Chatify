from flask import Flask
import os
from db.database import init_db
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Ensure Data directory exists before DB initialization
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'Data'))
os.makedirs(BASE_DIR, exist_ok=True)

app = Flask(__name__)

# Enable CORS for frontend-backend communication
from flask_cors import CORS
CORS(app)

# Initialize the database before the app starts
init_db()

# Import your routes after initializing the DB
from routes.scan_routes import scan_blueprint
app.register_blueprint(scan_blueprint)

# Optionally: add download endpoint for files
from flask import send_from_directory

@app.route('/download/<path:filename>')
def download_file(filename):
    data_dir = os.path.join(BASE_DIR)
    # Search in all relevant subfolders
    for subfolder in ["primary_data", "processed_data", "final_data"]:
        folder = os.path.join(data_dir, subfolder)
        file_path = os.path.join(folder, filename)
        if os.path.exists(file_path):
            return send_from_directory(folder, filename, as_attachment=True)
    # Fallback: search in Data root
    file_path = os.path.join(data_dir, filename)
    if os.path.exists(file_path):
        return send_from_directory(data_dir, filename, as_attachment=True)
    return "File not found", 404

if __name__ == "__main__":
    app.run(debug=True)