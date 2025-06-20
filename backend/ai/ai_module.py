import os
import json
import logging
from collections import defaultdict
from typing import List, Dict
import google.generativeai as genai

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


class AIModule:
    def __init__(self,
                 api_key,
                 text_data_path,
                 tag_clustered_path,
                 reordered_path,
                 qa_output_path,
                 raw_homepage_path=None,
                 css_path=None,
                 ui_output_dir="chatbot_ui"):
        self.api_key = "API_KEY"
        self.tagged_data_path = text_data_path
        self.tag_clustered_path = tag_clustered_path
        self.reordered_path = reordered_path
        self.qa_output_path = qa_output_path
        self.raw_homepage_path = raw_homepage_path
        self.css_path = css_path
        self.ui_output_dir = ui_output_dir

        if not self.api_key:
            raise ValueError("[❌] Gemini API key not found. Pass via argument or set GEMINI_API_KEY.")

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel("gemini-2.0-flash")



    def load_tagged_data(self):
        try:
            with open(self.tagged_data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"[!] Failed to load tagged text data: {e}")
            return []

    def load_homepage_html_css(self):
        try:
            with open(self.raw_homepage_path, 'r', encoding='utf-8') as f:
                html_pages = json.load(f)
            with open(self.css_path, 'r', encoding='utf-8') as f:
                css_pages = json.load(f)

            homepage_html = html_pages[0]['html'] if html_pages else ''
            homepage_css = css_pages[0]['css'] if css_pages else ''
            return homepage_html, homepage_css
        except Exception as e:
            logging.error(f"[!] Failed to load homepage HTML/CSS: {e}")
            return "", ""

    def group_by_ai_tag(self, data: List[Dict]) -> Dict[str, List[Dict]]:
        grouped = defaultdict(list)
        for item in data:
            tag = item.get('ai_tag', 'general')
            grouped[tag].append(item)
        return grouped

    def generate_qa_pairs(self, grouped_data: Dict[str, List[Dict]]) -> List[Dict]:
        qa_results = []

        for tag, items in grouped_data.items():
            logging.info(f"[🧠] Generating Q&A for tag: {tag} ({len(items)} items)")
            for entry in sorted(items, key=lambda x: len(x.get("text", "")), reverse=True):
                text = entry.get("text", "")
                url = entry.get("url", "")
                html_tag = entry.get("html_tag", "")
                ai_tag = entry.get("ai_tag", tag)

                qa_list = self.prompt_ai_for_qa(text)

                qa_results.append({
                    "url": url,
                    "html_tag": html_tag,
                    "ai_tag": ai_tag,
                    "qa_pairs": qa_list
                })

        return qa_results

    def prompt_ai_for_qa(self, content: str) -> List[Dict[str, str]]:
        prompt = f"""
You are an intelligent AI assistant. Generate 2 useful Q&A pairs based on the following webpage content:

\"\"\"{content}\"\"\"

Return the result as:
Q: ...
A: ...
Q: ...
A: ...
        """.strip()

        try:
            response = self.model.generate_content(prompt)
            lines = response.text.strip().split("\n")
            qa_pairs = []
            current_q = None
            for line in lines:
                if line.startswith("Q:"):
                    current_q = {"question": line[2:].strip()}
                elif line.startswith("A:") and current_q:
                    current_q["answer"] = line[2:].strip()
                    qa_pairs.append(current_q)
                    current_q = None
            return qa_pairs if qa_pairs else self.default_qa(content)
        except Exception as e:
            logging.error(f"[Gemini QA Error] {e}")
            return self.default_qa(content)

    def generate_chatbot_ui(self, homepage_html, homepage_css):
        prompt = f"""
You are a UI design expert. Create a chatbot interface using HTML, CSS, and JS that matches the theme of the following homepage:

--- HTML ---
{homepage_html[:1500]}
--- CSS ---
{homepage_css[:1500]}

It must be:
- Responsive
- Clean design
- Same font & color tone
- Chat window, user input, and bot responses

Return three separate code blocks:
1. index.html
2. style.css
3. script.js
        """

        try:
            response = self.model.generate_content(prompt)
            code_blocks = self.extract_code_blocks(response.text)
            return code_blocks
        except Exception as e:
            logging.warning(f"[Gemini UI Error] {e}")
            return {
                "index.html": self.sample_html(),
                "style.css": self.sample_css(),
                "script.js": self.sample_js()
            }

    def extract_code_blocks(self, content: str) -> Dict[str, str]:
        blocks = {"index.html": "", "style.css": "", "script.js": ""}
        current = None
        for line in content.splitlines():
            if "index.html" in line:
                current = "index.html"
            elif "style.css" in line:
                current = "style.css"
            elif "script.js" in line:
                current = "script.js"
            elif current:
                blocks[current] += line + "\n"
        return blocks

    def save_chatbot_ui_files(self, code_dict):
        os.makedirs(self.ui_output_dir, exist_ok=True)
        for filename, code in code_dict.items():
            path = os.path.join(self.ui_output_dir, filename)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(code)
            logging.info(f"[💡] Saved chatbot UI file: {path}")

    def save_results(self, qa_data: List[Dict]):
        os.makedirs(os.path.dirname(self.qa_output_path), exist_ok=True)
        with open(self.qa_output_path, 'w', encoding='utf-8') as f:
            json.dump(qa_data, f, indent=2, ensure_ascii=False)
        logging.info(f"[💾] Saved Q&A pairs to {self.qa_output_path}")

    def run(self):
        logging.info("[AI Module] Starting full AI pipeline...")

        tagged_data = self.load_tagged_data()
        if not tagged_data:
            logging.error("[AI Module] No data to process.")
            return

        grouped_data = self.group_by_ai_tag(tagged_data)
        qa_output = self.generate_qa_pairs(grouped_data)
        self.save_results(qa_output)

        homepage_html, homepage_css = self.load_homepage_html_css()
        if homepage_html and homepage_css:
            chatbot_ui = self.generate_chatbot_ui(homepage_html, homepage_css)
            self.save_chatbot_ui_files(chatbot_ui)

        logging.info("[AI Module] Full pipeline complete.")

    def default_qa(self, content):
        return [
            {"question": "What is this content about?", "answer": truncate(content, 60)},
            {"question": "Why is this section important?", "answer": "It provides relevant information to the website visitors."}
        ]

    def sample_html(self):
        return """<!DOCTYPE html>
<html>
<head>
  <title>Chatbot</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div class="chatbot-container">
    <div class="chat-box" id="chat-box"></div>
    <input type="text" id="user-input" placeholder="Ask me something...">
    <button onclick="sendMessage()">Send</button>
  </div>
  <script src="script.js"></script>
</body>
</html>
"""

    def sample_css(self):
        return """.chatbot-container {
  width: 400px;
  margin: auto;
  border: 1px solid #ccc;
  padding: 1em;
  font-family: sans-serif;
  background-color: #f9f9f9;
}
.chat-box {
  height: 300px;
  overflow-y: auto;
  background: #fff;
  border: 1px solid #ddd;
  margin-bottom: 1em;
  padding: 1em;
}
"""

    def sample_js(self):
        return """function sendMessage() {
  const input = document.getElementById("user-input");
  const chatBox = document.getElementById("chat-box");
  const userMessage = input.value;
  chatBox.innerHTML += `<div>User: ${userMessage}</div>`;
  chatBox.innerHTML += `<div>Bot: I'm still learning!</div>`;
  input.value = "";
}
"""


def truncate(text, length=80):
    return text[:length] + "..." if len(text) > length else text


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", type=str, help="Your Gemini API key")
    args = parser.parse_args()

    AIModule(api_key=args.api_key).run()
