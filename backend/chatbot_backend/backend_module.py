from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict
import uvicorn
import json
import os
import difflib


class ChatbotBackend:
    def __init__(self, qa_data_path: str = "chatpy/backend/data/final_qa_output.json"):
        self.qa_data_path = qa_data_path
        self.qa_dataset: List[Dict] = []
        self.app = FastAPI()
        self.configure_cors()
        self.define_routes()
        self.app.add_event_handler("startup", self.load_qa_data)

    def configure_cors(self):
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def load_qa_data(self):
        if os.path.exists(self.qa_data_path):
            with open(self.qa_data_path, "r", encoding="utf-8") as f:
                self.qa_dataset = json.load(f)
            print(f"[✅] Loaded {len(self.qa_dataset)} QA blocks.")
        else:
            print(f"[!] QA file not found at {self.qa_data_path}")

    def define_routes(self):
        @self.app.get("/")
        def root():
            return {"status": "Chatbot backend running 🚀"}

        @self.app.post("/chat")
        async def chatbot_endpoint(request: Request):
            data = await request.json()
            user_input = data.get("message", "").strip()

            if not user_input:
                return {"response": "Please enter a valid question."}

            best_response = self.find_best_answer(user_input)
            return {"response": best_response}

    def find_best_answer(self, user_input: str) -> str:
        candidates = []

        for block in self.qa_dataset:
            for qa in block.get("qa_pairs", []):
                question = qa.get("question", "")
                answer = qa.get("answer", "")
                if not question or not answer:
                    continue

                score = difflib.SequenceMatcher(None, user_input.lower(), question.lower()).ratio()
                candidates.append((score, answer))

        if not candidates:
            return "Sorry, I couldn’t find a relevant answer."

        candidates.sort(reverse=True)
        best_score, best_answer = candidates[0]

        if best_score < 0.3:
            return "Hmm, I’m not sure. Can you rephrase that?"

        return best_answer


# Instantiate the class and run
chatbot_instance = ChatbotBackend()
app = chatbot_instance.app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
