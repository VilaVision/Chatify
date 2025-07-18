import os
import json
import ast
import re
from typing import List, Dict, Tuple, Any
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime


# Load .env variables
load_dotenv()

class DebuggerAgent:
    """AI-powered debugging agent for generated code"""
    
    def __init__(self, client: OpenAI, model_name: str):
        self.client = client
        self.model_name = model_name
        self.debug_prompts = {}
    
    def load_debug_prompts(self, prompt_file: str):
        """Load debugging prompts from JSON file"""
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompts = json.load(f)
                self.debug_prompts = prompts.get('debug_prompts', {})
        except Exception as e:
            print(f"⚠️ Could not load debug prompts: {e}")
            self._set_default_debug_prompts()
    
    def _set_default_debug_prompts(self):
        """Set default debug prompts if JSON file is not available"""
        self.debug_prompts = {
            "syntax_check": "Analyze the following {file_type} code for syntax errors, missing semicolons, brackets, or quotes. List all issues found:\n\n{code}",
            "logic_check": "Review the following {file_type} code for logical errors, potential runtime issues, and improvement suggestions:\n\n{code}",
            "security_check": "Check the following {file_type} code for security vulnerabilities, XSS risks, and unsafe practices:\n\n{code}",
            "performance_check": "Analyze the following {file_type} code for performance issues, optimization opportunities, and best practices:\n\n{code}",
            "accessibility_check": "Review the following HTML/CSS code for accessibility issues, ARIA compliance, and usability problems:\n\n{code}"
        }
    
    def call_ai(self, prompt: str) -> str:
        """Make API call to AI model"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1500
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ Debug AI call failed: {e}")
            return ""
    
    def debug_syntax(self, code: str, file_type: str) -> Dict[str, Any]:
        """Check for syntax errors in code"""
        print(f"🔍 Checking syntax for {file_type}...")
        
        # For Python files, use AST parsing
        if file_type.lower() == 'python':
            try:
                ast.parse(code)
                syntax_issues = []
            except SyntaxError as e:
                syntax_issues = [f"Syntax Error at line {e.lineno}: {e.msg}"]
        else:
            # Use AI for other file types
            prompt = self.debug_prompts.get('syntax_check', '').format(
                file_type=file_type, 
                code=code
            )
            ai_response = self.call_ai(prompt)
            syntax_issues = [ai_response] if ai_response else []
        
        return {
            "type": "syntax",
            "issues": syntax_issues,
            "severity": "high" if syntax_issues else "none"
        }
    
    def debug_logic(self, code: str, file_type: str) -> Dict[str, Any]:
        """Check for logical errors and improvements"""
        print(f"🧠 Checking logic for {file_type}...")
        
        prompt = self.debug_prompts.get('logic_check', '').format(
            file_type=file_type, 
            code=code
        )
        ai_response = self.call_ai(prompt)
        
        return {
            "type": "logic",
            "issues": [ai_response] if ai_response else [],
            "severity": "medium"
        }
    
    def debug_security(self, code: str, file_type: str) -> Dict[str, Any]:
        """Check for security vulnerabilities"""
        print(f"🛡️ Checking security for {file_type}...")
        
        prompt = self.debug_prompts.get('security_check', '').format(
            file_type=file_type, 
            code=code
        )
        ai_response = self.call_ai(prompt)
        
        return {
            "type": "security",
            "issues": [ai_response] if ai_response else [],
            "severity": "high"
        }
    
    def debug_performance(self, code: str, file_type: str) -> Dict[str, Any]:
        """Check for performance issues"""
        print(f"⚡ Checking performance for {file_type}...")
        
        prompt = self.debug_prompts.get('performance_check', '').format(
            file_type=file_type, 
            code=code
        )
        ai_response = self.call_ai(prompt)
        
        return {
            "type": "performance",
            "issues": [ai_response] if ai_response else [],
            "severity": "low"
        }
    
    def debug_accessibility(self, code: str, file_type: str) -> Dict[str, Any]:
        """Check for accessibility issues (HTML/CSS)"""
        if file_type.lower() not in ['html', 'css']:
            return {"type": "accessibility", "issues": [], "severity": "none"}
        
        print(f"♿ Checking accessibility for {file_type}...")
        
        prompt = self.debug_prompts.get('accessibility_check', '').format(
            file_type=file_type, 
            code=code
        )
        ai_response = self.call_ai(prompt)
        
        return {
            "type": "accessibility",
            "issues": [ai_response] if ai_response else [],
            "severity": "medium"
        }
    
    def comprehensive_debug(self, code: str, file_type: str) -> Dict[str, Any]:
        """Run all debugging checks"""
        print(f"🔧 Running comprehensive debug for {file_type}...")
        
        debug_results = {
            "file_type": file_type,
            "timestamp": datetime.now().isoformat(),
            "checks": []
        }
        
        # Run all debug checks
        checks = [
            self.debug_syntax(code, file_type),
            self.debug_logic(code, file_type),
            self.debug_security(code, file_type),
            self.debug_performance(code, file_type),
            self.debug_accessibility(code, file_type)
        ]
        
        debug_results["checks"] = checks
        
        # Calculate overall severity
        severities = [check["severity"] for check in checks]
        if "high" in severities:
            debug_results["overall_severity"] = "high"
        elif "medium" in severities:
            debug_results["overall_severity"] = "medium"
        else:
            debug_results["overall_severity"] = "low"
        
        return debug_results
    
    def generate_fix_suggestions(self, debug_results: Dict[str, Any]) -> str:
        """Generate fix suggestions based on debug results"""
        issues = []
        for check in debug_results["checks"]:
            if check["issues"]:
                issues.extend(check["issues"])
        
        if not issues:
            return "✅ No issues found!"
        
        prompt = f"""
Based on the following debugging issues found in {debug_results['file_type']} code, 
provide specific, actionable fix suggestions:

Issues found:
{chr(10).join(f"- {issue}" for issue in issues)}

Provide clear, numbered steps to fix these issues.
"""
        
        return self.call_ai(prompt)


class ChatbotGenerator:
    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        input_paths: List[str] = None,
        text_data_path: str = None,
        tag_clustered_path: str = None,
        output_dir: str = "chatbot_output",
        validate_ui: bool = True,
        prompt_file: str = "prompts.json"
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
        self.prompt_file = prompt_file
        self.prompts = {}
        
        # Initialize debugger agent
        self.debugger = DebuggerAgent(self.client, self.model_name)
        self.debugger.load_debug_prompts(prompt_file)

        # Step 1: Define named paths
        self.text_path = r"C:\Users\alokp\Chatify\backend\chatpy\output\extracted_text_data.json"
        self.html_path = r"C:\Users\alokp\Chatify\backend\chatpy\output\html_only.json"
        self.css_path = r"C:\Users\alokp\Chatify\backend\chatpy\output\css_only.json"

        # Step 2: Make sure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Load prompts from JSON
        self.load_prompts()

    def load_prompts(self):
        """Load prompts from JSON file"""
        try:
            with open(self.prompt_file, 'r', encoding='utf-8') as f:
                self.prompts = json.load(f)
                print(f"✅ Loaded prompts from {self.prompt_file}")
        except Exception as e:
            print(f"⚠️ Could not load prompts from {self.prompt_file}: {e}")
            self._set_default_prompts()

    def _set_default_prompts(self):
        """Set default prompts if JSON file is not available"""
        self.prompts = {
            "content_classification": """You are an AI assistant trained to deeply understand and classify website content extracted from a text file.

📄 This text comes from the visible parts of a website (headers, paragraphs, buttons, etc.) and was extracted as plain text using automated tools.
Your task is to analyze it **step-by-step** and determine the correct **Category** and **Sub-category** for the type of website it came from.

🧠 Think in multiple stages:
1. Read the entire content carefully.
2. Identify repeated themes, product names, services, goals, or industries.
3. Reflect multiple times if needed to ensure accuracy (simulate iterative internal thought).
4. Match the content to one of the following general categories:
   - E-commerce
   - SaaS
   - Personal
   - Educational
   - Non-profit
   - Blog
   - Media / News
   - Entertainment
   - Healthcare
   - Other
5. Then, based on the context, pick a more specific **Sub-category** (e.g., Fashion, CRM, Portfolio, etc.).

📝 Content extracted from text file:
\"\"\"
{content}
\"\"\"

✅ Final Answer (use this exact format):
Category: <category>
Sub-category: <sub-category>""",
            
            "qa_generation": """You are an expert assistant helping build a chatbot for a `{website_type}` website.

Your job: Generate 2–3 natural-sounding **Q&A pairs** based on the following content. 
Questions must be **specific to the product, service, or person** described in the content.

Content:
\"\"\"
{content}
\"\"\"

Return output in this format only:

Q: ...
A: ...
Q: ...
A: ...""",
            
            "ui_generation": {
                "html": "Create minimal HTML for a chatbot UI for a {website_type} website. Include a chat box, input field, and send button. Use clean layout. Reference the following HTML structure for theme consistency:\n\n{html_reference}",
                "css": "Create matching CSS for the chatbot UI. Keep it clean, centered, and responsive. Use the following CSS as reference for consistent theming:\n\n{css_reference}",
                "js": "Use this Q&A JSON and generate JavaScript to match user input to the closest question and return its answer. Make it interactive and user-friendly.\n{qa_data}"
            },
            
            "backend_generation": """You are an expert Python developer building a chatbot for a **{website_type}** website using **{tool_name}**.

Here is a sample Q&A dataset:
{qa_sample}

Requirements:
- Use best practices of {tool_name}
- Logic should take user input and return the closest question's answer
- Add helpful comments
- Show how to initialize or run the chatbot interactively

Wrap in a function or class and make it ready to use.""",
            
            "debug_prompts": {
                "syntax_check": "Analyze the following {file_type} code for syntax errors, missing semicolons, brackets, or quotes. List all issues found:\n\n{code}",
                "logic_check": "Review the following {file_type} code for logical errors, potential runtime issues, and improvement suggestions:\n\n{code}",
                "security_check": "Check the following {file_type} code for security vulnerabilities, XSS risks, and unsafe practices:\n\n{code}",
                "performance_check": "Analyze the following {file_type} code for performance issues, optimization opportunities, and best practices:\n\n{code}",
                "accessibility_check": "Review the following HTML/CSS code for accessibility issues, ARIA compliance, and usability problems:\n\n{code}"
            }
        }

    def call_AI(self, prompt: str) -> str:
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
        print("🔄 Loading dataset from text, HTML, and CSS files...")

        lines = []

        for name, path in {
            "text": self.text_path,
            "html": self.html_path,
            "css": self.css_path
        }.items():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                    if isinstance(data, list):
                        for item in data:
                            lines.extend(filter(None, str(item).strip().split("\n")))
                    elif isinstance(data, dict):
                        for v in data.values():
                            lines.extend(filter(None, str(v).strip().split("\n")))
                    else:
                        print(f"⚠️ Unexpected format in {name} file.")
            except Exception as e:
                print(f"❌ Failed to load {name} file from {path}: {e}")

        print(f"✅ Loaded {len(lines)} content lines after splitting by newline")
        return lines

    def load_html_css_references(self) -> Tuple[str, str]:
        """Load HTML and CSS content to use as references for theme consistency"""
        html_content = ""
        css_content = ""
        
        try:
            with open(self.html_path, 'r', encoding='utf-8') as f:
                html_data = json.load(f)
                if isinstance(html_data, dict):
                    html_content = str(list(html_data.values())[0])[:2000]  # First 2000 chars
                elif isinstance(html_data, list) and html_data:
                    html_content = str(html_data[0])[:2000]
        except Exception as e:
            print(f"⚠️ Could not load HTML reference: {e}")
            
        try:
            with open(self.css_path, 'r', encoding='utf-8') as f:
                css_data = json.load(f)
                if isinstance(css_data, dict):
                    css_content = str(list(css_data.values())[0])[:2000]  # First 2000 chars
                elif isinstance(css_data, list) and css_data:
                    css_content = str(css_data[0])[:2000]
        except Exception as e:
            print(f"⚠️ Could not load CSS reference: {e}")
            
        return html_content, css_content

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

    def classify_content_with_ai(self, content_lines: List[str]) -> List[Dict[str, str]]:
        print("🧠 Classifying content into categories...")
        classified_results = []
    
        for content in content_lines:
            content = content.strip()
    
            # Skip empty or too short lines, or lines with no alphanumeric characters
            if len(content) < 30 or not any(c.isalnum() for c in content):
                continue

            prompt = self.prompts.get('content_classification', '').format(content=content)
            response = self.call_AI(prompt)
            category, sub_category = self._parse_category_response(response)
            classified_results.append({
                "content": content,
                "category": category,
                "sub_category": sub_category
            })
    
        print(f"✅ Classified {len(classified_results)} content blocks")
        return classified_results

    def _parse_category_response(self, response: str) -> Tuple[str, str]:
        category = "Unknown"
        sub_category = "Unknown"
        for line in response.strip().splitlines():
            if line.lower().startswith("category:"):
                category = line.split(":", 1)[1].strip()
            elif line.lower().startswith("sub-category:"):
                sub_category = line.split(":", 1)[1].strip()
        return category, sub_category

    def generate_qa_pairs(self, content_lines: List[str]) -> List[Dict]:
        print("🤖 Generating Q&A pairs...")
        self.website_type = self.detect_website_type(content_lines)
        qa_set = set()
        qa_list = []
        
        for content in content_lines:
            if len(content) < 20:
                continue
            
            prompt = self.prompts.get('qa_generation', '').format(
                website_type=self.website_type,
                content=content
            )
            response = self.call_AI(prompt)
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
        print("🎨 Generating UI files using model prompts with theme references...")
        
        # Load HTML/CSS references for theme consistency
        html_ref, css_ref = self.load_html_css_references()
        
        # Get UI prompts
        ui_prompts = self.prompts.get('ui_generation', {})
        
        html_prompt = ui_prompts.get('html', '').format(
            website_type=self.website_type,
            html_reference=html_ref
        )
        
        css_prompt = ui_prompts.get('css', '').format(
            css_reference=css_ref
        )
        
        js_prompt = ui_prompts.get('js', '').format(
            qa_data=json.dumps(self.qa_data, indent=2)
        )

        html = self.call_AI(html_prompt)
        css = self.call_AI(css_prompt)
        js = self.call_AI(js_prompt)

        return {"index.html": html, "style.css": css, "script.js": js}

    def debug_generated_files(self, ui_files: Dict[str, str]) -> Dict[str, Any]:
        """Debug all generated files using the debugger agent"""
        print("🔧 Starting comprehensive debugging of generated files...")
        
        debug_results = {}
        
        file_type_mapping = {
            "index.html": "HTML",
            "style.css": "CSS", 
            "script.js": "JavaScript"
        }
        
        for filename, content in ui_files.items():
            file_type = file_type_mapping.get(filename, "Unknown")
            debug_result = self.debugger.comprehensive_debug(content, file_type)
            debug_results[filename] = debug_result
            
            # Generate fix suggestions
            fix_suggestions = self.debugger.generate_fix_suggestions(debug_result)
            debug_result["fix_suggestions"] = fix_suggestions
        
        return debug_results

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

        prompt = self.prompts.get('backend_generation', '').format(
            website_type=self.website_type,
            tool_name=tool_name,
            qa_sample=json.dumps(self.qa_data[:5], indent=2)
        )
        
        code = self.call_AI(prompt)
        filename = f"chatbot_{tool_name.lower().replace(' ', '_').replace('+', '').replace('/', '')}.py"
        return {filename: code}

    def save_data(self, ui_files: Dict[str, str]) -> None:
        print("💾 Saving data...")
        
        # Save Q&A data
        qa_path = os.path.join(self.output_dir, "qa_data.json")
        with open(qa_path, "w", encoding="utf-8") as f:
            json.dump(self.qa_data, f, indent=2)
        print(f"✅ Saved: {qa_path}")

        # Debug generated files
        debug_results = self.debug_generated_files(ui_files)
        
        # Save debug results
        debug_path = os.path.join(self.output_dir, "debug_results.json")
        with open(debug_path, "w", encoding="utf-8") as f:
            json.dump(debug_results, f, indent=2)
        print(f"✅ Saved debug results: {debug_path}")

        # Save UI files
        for filename, content in ui_files.items():
            file_path = os.path.join(self.output_dir, filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✅ Saved: {file_path}")
            
            # Print debug summary for each file
            if filename in debug_results:
                debug_info = debug_results[filename]
                print(f"🔍 Debug Summary for {filename}:")
                print(f"   Overall Severity: {debug_info['overall_severity']}")
                for check in debug_info['checks']:
                    if check['issues']:
                        print(f"   {check['type'].capitalize()}: {check['severity']} severity")

        # Generate and save backend code
        selected_tool = self.select_best_framework()
        modal_code = self.generate_selected_modal_code(selected_tool)

        backend_dir = os.path.join(self.output_dir, "backend_modals")
        Path(backend_dir).mkdir(exist_ok=True)
        
        for fname, code in modal_code.items():
            fpath = os.path.join(backend_dir, fname)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(code)
            print(f"🧠 Generated chatbot logic using {selected_tool}: {fpath}")
            
            # Debug backend code
            backend_debug = self.debugger.comprehensive_debug(code, "Python")
            backend_debug_path = os.path.join(backend_dir, f"debug_{fname}.json")
            with open(backend_debug_path, "w", encoding="utf-8") as f:
                json.dump(backend_debug, f, indent=2)
            print(f"🔧 Backend debug results saved: {backend_debug_path}")

        print("✅ All data, debug results, and backend logic saved.")

    def debug_and_validate(self):
        print("🔍 Validating Q&A output using model prompt...")
        debug_prompt = f"""
You are a QA validator. Review the following Q&A dataset and point out:
- Very short questions or answers
- Questions missing a '?' at the end
- Duplicate or similar questions
- Answers that don't match the questions

JSON:
{json.dumps(self.qa_data, indent=2)}
"""
        report = self.call_AI(debug_prompt)
        print("\n⚠️ Q&A Debug Report:")
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
        print("🚀 Running enhanced chatbot generator pipeline with debugging...")
        
        lines = self.load_dataset()
        if not lines:
            return
            
        self.generate_qa_pairs(lines)
        ui = self.generate_ui()
        self.save_data(ui)
        self.debug_and_validate()
        
        print("🎉 Enhanced pipeline with debugging complete!")


if __name__ == "__main__":
    generator = ChatbotGenerator(
        output_dir="chatbot_output",
        prompt_file="prompts.json"
    )
    generator.run_pipeline()
