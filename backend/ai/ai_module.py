import os
import json
from typing import List, Dict
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime

# Load .env variables
load_dotenv()

class ChatbotGenerator:
    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        input_paths: List[str] = None,
        text_data_path: str = None,
        tag_clustered_path: str = None,
        output_dir: str = "chatbot_output",
        validate_ui: bool = True
    ):
        api_key = api_key or os.getenv("API_KEY")
        base_url = base_url or os.getenv("BASE_URL")

        if not api_key:
            raise ValueError("API key is required. Set API_KEY as an environment variable.")

        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model_name = "nvidia/llama-3.3-nemotron-super-49b-v1"
        self.output_dir = output_dir
        self.qa_data = []
        self.website_type = "general"
        self.tag_clustered_path = tag_clustered_path
        self.validate_ui = validate_ui

        self.input_paths = [text_data_path] if text_data_path else input_paths or [
            r"C:\\Users\\alokp\\chatpy\\backend\\chatpy\\output\\css_only.json",
            r"C:\\Users\\alokp\\chatpy\\backend\\chatpy\\output\\html_only.json",
            r"C:\\Users\\alokp\\chatpy\\backend\\chatpy\\output\\extracted_text_data.json"
        ]

        os.makedirs(output_dir, exist_ok=True)

    def call_model_with_prompt(self, prompt: str) -> str:
        try:
            print("📡 Sending prompt to model...")
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1000
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ Model call failed: {e}")
            return ""

    def load_dataset(self) -> List[str]:
        print("🔄 Loading dataset from multiple JSON files...")
        lines = []
        for path in self.input_paths:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            lines.extend(filter(None, str(item).strip().split("\n")))
                    elif isinstance(data, dict):
                        for v in data.values():
                            lines.extend(filter(None, str(v).strip().split("\n")))
            except Exception as e:
                print(f"❌ Failed to load {path}: {e}")
        print(f"✅ Loaded {len(lines)} content lines after splitting by newline")
        return lines

    def detect_website_type(self, content_lines: List[str]) -> str:
        text = " ".join(content_lines).lower()
        types = {
            'portfolio': ['portfolio', 'resume', 'skills', 'projects'],
            'ecommerce': ['buy', 'product', 'cart'],
            'blog': ['blog', 'post', 'author'],
            'business': ['services', 'company', 'contact'],
            'educational': ['learn', 'course', 'student']
        }
        detected_type = max(types, key=lambda t: sum(k in text for k in types[t]), default="general")
        print(f"🎯 Detected website type: {detected_type}")
        return detected_type

    def generate_qa_pairs(self, content_lines: List[str]) -> List[Dict]:
        print("🤖 Generating Q&A pairs...")
        self.website_type = self.detect_website_type(content_lines)
        qa_set = set()
        qa_list = []
        for content in content_lines:
            if len(content) < 20:
                continue
            prompt = (
                f"You are an expert assistant helping build a chatbot for a `{self.website_type}` website.\n\n"
                "Your job: Generate 2–3 natural-sounding **Q&A pairs** based on the following content. "
                "Questions must be **specific to the product, service, or person** described in the content.\n\n"
                f"Content:\n\"\"\"\n{content}\n\"\"\"\n\n"
                "Return output in this format only:\n\n"
                "Q: ...\nA: ...\nQ: ...\nA: ..."
            )
            response = self.call_model_with_prompt(prompt)
            qas = self._parse_qa_response(response)
            for qa in qas:
                key = (qa["question"].lower(), qa["answer"].lower())
                if key not in qa_set:
                    qa_set.add(key)
                    qa_list.append({
                        "question": qa["question"],
                        "answer": qa["answer"],
                        "website_type": self.website_type
                    })
        self.qa_data = qa_list
        print(f"✅ Generated {len(qa_list)} Q&A pairs")
        return qa_list

    def _parse_qa_response(self, response: str) -> List[Dict]:
        qas = []
        q = a = None
        for line in response.splitlines():
            line = line.strip()
            if line.startswith("Q:"):
                q = line[2:].strip()
            elif line.startswith("A:") and q:
                a = line[2:].strip()
                qas.append({"question": q, "answer": a})
                q, a = None, None
        return qas

    def generate_ui(self) -> Dict[str, str]:
        print("🎨 Generating UI files using model prompts...")
        html_prompt = f"""Create minimal HTML for a chatbot UI for a {self.website_type} website. Include a chat box, input field, and send button. Use clean layout."""
        css_prompt = "Create matching CSS for the chatbot UI. Keep it clean, centered, and responsive."
        js_prompt = f"Use this Q&A JSON and generate JavaScript to match user input to the closest question and return its answer.\n{json.dumps(self.qa_data, indent=2)}"

        html = self.call_model_with_prompt(html_prompt)
        css = self.call_model_with_prompt(css_prompt)
        js = self.call_model_with_prompt(js_prompt)

        return {"index.html": html, "style.css": css, "script.js": js}

    def validate_ui_file(self, filename: str, content: str) -> None:
        print(f"🔍 Validating {filename}...")
        prompt = f"""
You are a code reviewer. Analyze the following `{filename}` and point out any:
- Syntax errors
- Best practice violations
- Accessibility or responsiveness issues
- Suggestions for improvement

Code:
\"\"\"
{content}
\"\"\"
"""
        report = self.call_model_with_prompt(prompt)
        print(f"\n🛠️ Validation Report for {filename}:\n{report or '✅ Looks good!'}\n")

    def select_best_framework(self) -> str:
        print("🧠 Selecting the best backend framework for chatbot...")
        mapping = {
            "portfolio": "Rasa",
            "ecommerce": "LangChain",
            "educational": "LlamaIndex",
            "blog": "LlamaIndex",
            "business": "CrewAI"
        }
        return mapping.get(self.website_type, "Hugging Face + Gradio")

    def generate_selected_modal_code(self, tool_name: str) -> Dict[str, str]:
        print(f"🤖 Generating interactive chatbot logic using: {tool_name}")

        prompt = f"""
You are an expert Python developer building a chatbot for a **{self.website_type}** website using **{tool_name}**.

Here is a sample Q&A dataset:
{json.dumps(self.qa_data[:5], indent=2)}  # Show only top 5

Requirements:
- Use best practices of {tool_name}
- Logic should take user input and return the closest question's answer
- Add helpful comments
- Show how to initialize or run the chatbot interactively

Wrap in a function or class and make it ready to use.
"""
        code = self.call_model_with_prompt(prompt)
        filename = f"chatbot_{tool_name.lower().replace(' ', '_').replace('+', '').replace('/', '')}.py"
        return {filename: code}

    def save_data(self, ui_files: Dict[str, str]) -> None:
        print("💾 Saving data...")
        qa_path = os.path.join(self.output_dir, "qa_data.json")
        with open(qa_path, "w", encoding="utf-8") as f:
            json.dump(self.qa_data, f, indent=2)
        print(f"✅ Saved: {qa_path}")

        for filename, content in ui_files.items():
            file_path = os.path.join(self.output_dir, filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✅ Saved: {file_path}")
            if self.validate_ui:
                self.validate_ui_file(filename, content)

        selected_tool = self.select_best_framework()
        modal_code = self.generate_selected_modal_code(selected_tool)

        backend_dir = os.path.join(self.output_dir, "backend_modals")
        Path(backend_dir).mkdir(exist_ok=True)
        for fname, code in modal_code.items():
            fpath = os.path.join(backend_dir, fname)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(code)
            print(f"🧠 Generated chatbot logic using {selected_tool}: {fpath}")

        print("✅ All data and backend logic saved.")

    def debug_and_validate(self):
        print("🔍 Validating Q&A output using model prompt...")
        debug_prompt = f"""
You are a QA validator. Review the following Q&A dataset and point out:
- Very short questions or answers
- Questions missing a '?' at the end

JSON:
{json.dumps(self.qa_data, indent=2)}
"""
        report = self.call_model_with_prompt(debug_prompt)
        print("\n⚠️ Debug Report:")
        print(report or "✅ No major issues found.")

    def print_day_reason(self):
        day = datetime.now().strftime("%A")
        reasons = {
            "Monday": "It's Monday! You need a smart chatbot to survive those weekend catch-up emails.",
            "Tuesday": "It's Tuesday! The perfect day to automate questions so you can do actual work.",
            "Wednesday": "It's Wednesday, hump day! Let a chatbot handle the questions while you glide downhill.",
            "Thursday": "It's Thursday, almost Friday. Time to offload repetitive tasks to a smart bot.",
            "Friday": "It's Friday! Automate the FAQs and start the weekend early.",
            "Saturday": "It's Saturday. Let your chatbot do the talking while you sip coffee and relax.",
            "Sunday": "It's Sunday, a day of rest — unless your chatbot has to hustle for you online."
        }
        print(f"📅 {reasons.get(day)}")

    def run_pipeline(self):
        self.print_day_reason()
        print("🚀 Running chatbot generator pipeline...")
        lines = self.load_dataset()
        if not lines:
            return
        self.generate_qa_pairs(lines)
        ui = self.generate_ui()
        self.save_data(ui)
        self.debug_and_validate()
        print("🎉 Pipeline complete!")


if __name__ == "__main__":
    generator = ChatbotGenerator(output_dir="chatbot_output")
    generator.run_pipeline()
