import os
import shutil
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class ChatbotUIBuilder:
    def __init__(self,
                 ai_ui_code_dir="chatpy/backend/data/chatbot_ui_code",
                 output_ui_dir="chatpy/backend/chatbot_ui/generated_ui"):
        self.ai_ui_code_dir = ai_ui_code_dir
        self.output_ui_dir = output_ui_dir
        self.required_files = ["index.html", "style.css", "script.js"]

    def validate_files_exist(self):
        missing = [f for f in self.required_files if not os.path.exists(os.path.join(self.ai_ui_code_dir, f))]
        if missing:
            logging.error(f"Missing AI-generated files: {missing}")
            return False
        return True

    def prepare_output_directory(self):
        os.makedirs(self.output_ui_dir, exist_ok=True)
        logging.info(f"[📁] Output directory ready: {self.output_ui_dir}")

    def copy_files(self):
        for file in self.required_files:
            src = os.path.join(self.ai_ui_code_dir, file)
            dst = os.path.join(self.output_ui_dir, file)
            shutil.copyfile(src, dst)
            logging.info(f"[📄] Copied {file} to {self.output_ui_dir}")

    def inject_metadata(self):
        index_path = os.path.join(self.output_ui_dir, "index.html")
        if not os.path.exists(index_path):
            logging.warning(f"[!] index.html not found for metadata injection.")
            return

        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()

        if "<!-- chatbot metadata -->" not in html:
            html = html.replace("</head>", "<!-- chatbot metadata -->\n</head>")

        html = html.replace("<title>", "<title>ChatBot UI | ")

        with open(index_path, "w", encoding="utf-8") as f:
            f.write(html)
        logging.info(f"[✨] Metadata injected into index.html")

    def run(self):
        logging.info("[🎨] Starting Chatbot UI Builder...")

        if not self.validate_files_exist():
            logging.error("[✘] Cannot proceed without AI-generated UI files.")
            return

        self.prepare_output_directory()
        self.copy_files()
        self.inject_metadata()

        logging.info("[✅] Chatbot UI successfully built at: " + self.output_ui_dir)


if __name__ == "__main__":
    ChatbotUIBuilder().run()
