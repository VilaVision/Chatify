

from sentence_transformers import SentenceTransformer, util
from .qa_db import get_all_qa_pairs

class ChatbotAI:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.refresh_qa_data()

    def refresh_qa_data(self):
        self.qa_pairs = get_all_qa_pairs()
        self.questions = [qa['question'] for qa in self.qa_pairs]
        if self.questions:
            self.embeddings = self.model.encode(self.questions, convert_to_tensor=True)
        else:
            self.embeddings = None

    def get_best_answer(self, user_prompt, top_k=1):
        if not self.embeddings or not self.qa_pairs:
            return "No Q&A data available."
        query_embedding = self.model.encode(user_prompt, convert_to_tensor=True)
        hits = util.semantic_search(query_embedding, self.embeddings, top_k=top_k)[0]
        if hits:
            idx = hits[0]['corpus_id']
            return self.qa_pairs[idx]['answer']
        return "Sorry, I couldn't find an answer to your question."