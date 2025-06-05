from flask import Blueprint, request, jsonify
from .qa_db import get_best_answer

chatbot_blueprint = Blueprint('chatbot', __name__)

@chatbot_blueprint.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    question = data.get('question')
    if not question:
        return jsonify({'error': 'No question provided'}), 400
    answer = get_best_answer(question)
    if answer:
        return jsonify({'answer': answer}), 200
    else:
        return jsonify({'answer': "Sorry, I couldn't find an answer."}), 200