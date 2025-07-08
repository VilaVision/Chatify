import os
import json
from typing import List, Dict
from openai import OpenAI
from dotenv import load_dotenv

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
        output_dir: str = "chatbot_output"
    ):
        # Load from environment if not explicitly passed
        api_key = api_key or os.getenv("API_KEY")
        base_url = base_url or os.getenv("BASE_URL")

        if not api_key:
            raise ValueError("API key is required. Set NVIDIA_API_KEY as an environment variable.")

        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model_name = "nvidia/llama-3.3-nemotron-super-49b-v1"
        self.output_dir = output_dir
        self.qa_data = []
        self.website_type = "general"
        self.tag_clustered_path = tag_clustered_path

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

    def save_data(self, ui_files: Dict[str, str]) -> None:
        print("💾 Saving data...")
        with open(os.path.join(self.output_dir, "qa_data.json"), "w", encoding="utf-8") as f:
            json.dump(self.qa_data, f, indent=2)
        for filename, content in ui_files.items():
            with open(os.path.join(self.output_dir, filename), "w", encoding="utf-8") as f:
                f.write(content)
        print("✅ Data saved successfully.")

    def debug_and_validate(self):
        print("🔍 Validating output using model prompt...")
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

    def run_pipeline(self):
        print("🚀 Running chatbot generator pipeline...")
        lines = self.load_dataset()
        if not lines:
            return
        self.generate_qa_pairs(lines)
        ui = self.generate_ui()
        self.save_data(ui)
        self.debug_and_validate()
        print("🎉 Pipeline complete!")


# Run only if this script is the main file
if __name__ == "__main__":
    generator = ChatbotGenerator(
        # No hardcoded API key or URL here!
        output_dir="chatbot_output"
    )
    generator.run_pipeline()