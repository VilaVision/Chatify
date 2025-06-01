import multiprocessing
from flask import Flask
from flask_cors import CORS
from routes.scan_routes import scan_blueprint


multiprocessing.set_start_method("spawn", force=True)
app = Flask(__name__)
CORS(app)
app.register_blueprint(scan_blueprint, url_prefix='/api')

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)