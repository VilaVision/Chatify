from flask import Flask, request, jsonify
from flask_cors import CORS
from routes.scan_routes import scan_blueprint  # Import scan blueprint from scanroutes.py

app = Flask(__name__)
CORS(app, origins=['*'])  # Allow requests from frontend

# Register the blueprint that contains scan logic
app.register_blueprint(scan_blueprint)

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'message': 'Gateway is up and connected to scan routes',
        'main_endpoint': '/api/scan (POST)',
        'status_check': '/api/status (GET)'
    })

# Root endpoint
@app.route('/')
def index():
    return jsonify({
        'message': 'Web Scanner Gateway',
        'workflow': [
            'Frontend sends URL to /api/scan',
            'Gateway forwards to scanroutes.py',
            'scanroutes.py handles crawl, scrape, clean, AI',
            'Response is sent back to frontend'
        ]
    })

# Global error handler
@app.errorhandler(Exception)
def handle_exception(e):
    return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Gateway running at http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
