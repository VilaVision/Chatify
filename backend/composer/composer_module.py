import os
import shutil
import zipfile
import logging
import subprocess

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


class Composer:
    def __init__(self,
                 ui_dir="chatpy/backend/chatbot_ui/generated_ui",
                 qa_file="chatpy/backend/data/final_qa_output.json",
                 backend_script="chatpy/backend/chatbot_backend/chatbot_backend.py",
                 build_dir="chatpy_build",
                 zip_output="chatpy_bundle.zip"):
        self.ui_dir = ui_dir
        self.qa_file = qa_file
        self.backend_script = backend_script
        self.build_dir = build_dir
        self.zip_output = zip_output

    def clear_build_directory(self):
        if os.path.exists(self.build_dir):
            shutil.rmtree(self.build_dir)
        os.makedirs(self.build_dir)
        os.makedirs(os.path.join(self.build_dir, "frontend"))
        os.makedirs(os.path.join(self.build_dir, "backend"))
        logging.info("[🧹] Build directory prepared.")

    def copy_frontend_files(self):
        if not os.path.exists(self.ui_dir):
            logging.error(f"[✘] UI folder not found: {self.ui_dir}")
            return
        for file in os.listdir(self.ui_dir):
            src = os.path.join(self.ui_dir, file)
            dst = os.path.join(self.build_dir, "frontend", file)
            shutil.copyfile(src, dst)
        logging.info("[🎨] Frontend files copied.")

    def copy_backend_files(self):
        backend_dst = os.path.join(self.build_dir, "backend")
        if os.path.exists(self.qa_file):
            shutil.copyfile(self.qa_file, os.path.join(backend_dst, "final_qa_output.json"))
            logging.info("[📄] Q&A dataset copied.")

        if os.path.exists(self.backend_script):
            shutil.copyfile(self.backend_script, os.path.join(backend_dst, "chatbot_backend.py"))
            logging.info("[🧠] Backend script copied.")

    def zip_bundle(self):
        with zipfile.ZipFile(self.zip_output, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(self.build_dir):
                for file in files:
                    path = os.path.join(root, file)
                    arcname = os.path.relpath(path, self.build_dir)
                    zipf.write(path, arcname)
        logging.info(f"[🗜️] Project zipped into: {self.zip_output}")

    def run_pipeline(self):
        logging.info("[🚀] Starting full pipeline composition...")

        self.clear_build_directory()
        self.copy_frontend_files()
        self.copy_backend_files()
        self.zip_bundle()

        logging.info("[✅] Project successfully composed and bundled.")


if __name__ == "__main__":
    Composer().run_pipeline()
