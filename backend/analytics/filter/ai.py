import json
import os
import requests
import time
from utils.data_handler import load_processed_pages, save_qa_pair

class GeminiAIQAGenerator:
    def __init__(self, api_key=None):
        """
        Initialize the Gemini AI QA Generator

        Args:
            api_key (str): Gemini API key. If not provided, will look for GEMINI_API_KEY env variable
        """
        if api_key:
            self.api_key = api_key  
        else:
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                raise ValueError("Please provide Gemini API key either as parameter or set GEMINI_API_KEY environment variable")
            self.api_key = api_key

        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

    def load_data(self, file_path):
        """
        Load JSON data from file

        Args:
            file_path (str): Path to the JSON file

        Returns:
            dict: Loaded JSON data
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        except FileNotFoundError:
            print(f"Error: File {file_path} not found")
            return None
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON format in {file_path}")
            return None

    def generate_qa_pairs(self, page_data, num_questions=5):
        """
        Generate Q&A pairs from page data using Gemini AI

        Args:
            page_data (dict): Single page data containing 'url' and 'text'
            num_questions (int): Number of Q&A pairs to generate

        Returns:
            list: List of Q&A pairs
        """
        url = page_data.get('url', '')
        text = page_data.get('text', '')

        # Truncate text if it's too long (to avoid token limits)
        max_text_length = 4000
        if len(text) > max_text_length:
            text = text[:max_text_length] + "..."

        prompt = f"""
Based on the following website content, generate {num_questions} question-answer pairs for a chatbot. 

Website URL: {url}
Content: {text}

Requirements:
1. Generate diverse questions that users might ask about this content
2. Answers should be precise, concise, and helpful (maximum 2-3 sentences)
3. Include the source URL in answers when relevant
4. Focus on the most important information
5. Make questions natural and conversational

Format your response as a JSON array with this structure:
[
  {{
    "question": "What is...",
    "answer": "Brief answer here. Source: {url}",
    "category": "general/product/service/etc"
  }}
]

Generate {num_questions} Q&A pairs now:
"""

        try:
            # Prepare the request payload
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ]
            }

            # Make the API request
            headers = {
                'Content-Type': 'application/json'
            }

            response = requests.post(
                f"{self.base_url}?key={self.api_key}",
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                response_data = response.json()

                # Extract text from Gemini response
                if 'candidates' in response_data and len(response_data['candidates']) > 0:
                    candidate = response_data['candidates'][0]
                    if 'content' in candidate and 'parts' in candidate['content']:
                        response_text = candidate['content']['parts'][0]['text']

                        # Try to extract JSON from response
                        try:
                            # Find JSON array in response
                            start_idx = response_text.find('[')
                            end_idx = response_text.rfind(']') + 1

                            if start_idx != -1 and end_idx != -1:
                                json_str = response_text[start_idx:end_idx]
                                qa_pairs = json.loads(json_str)
                                return qa_pairs
                            else:
                                print("Warning: Could not find valid JSON in response")
                                return []

                        except json.JSONDecodeError:
                            print("Warning: Could not parse JSON from AI response")
                            print(f"Response text: {response_text[:500]}...")
                            return []
                else:
                    print("Warning: No candidates in response")
                    return []
            else:
                print(f"Error: API request failed with status {response.status_code}")
                print(f"Response: {response.text}")
                return []

        except requests.exceptions.Timeout:
            print("Error: Request timed out")
            return []
        except requests.exceptions.RequestException as e:
            print(f"Error making API request: {str(e)}")
            return []
        except Exception as e:
            print(f"Error generating Q&A pairs: {str(e)}")
            return []

    def process_all_pages(self, data, questions_per_page=3, delay=1):
        """
        Process all pages in the data to generate Q&A pairs

        Args:
            data (dict): Complete JSON data with 'pages' array
            questions_per_page (int): Number of questions to generate per page
            delay (int): Delay between API calls in seconds

        Returns:
            list: All generated Q&A pairs
        """
        if not data or 'pages' not in data:
            print("Error: Invalid data structure. Expected 'pages' key.")
            return []

        all_qa_pairs = []
        pages = data['pages']

        print(f"Processing {len(pages)} pages...")

        for i, page in enumerate(pages):
            print(f"Processing page {i+1}/{len(pages)}: {page.get('url', 'No URL')}")

            qa_pairs = self.generate_qa_pairs(page, questions_per_page)

            if qa_pairs:
                # Add source URL and page index to each Q&A pair
                for qa in qa_pairs:
                    qa['source_url'] = page.get('url', '')
                    qa['page_index'] = i

                all_qa_pairs.extend(qa_pairs)
                print(f"Generated {len(qa_pairs)} Q&A pairs")
            else:
                print("No Q&A pairs generated for this page")

            # Add delay to avoid rate limiting
            if i < len(pages) - 1:  # Don't delay after the last page
                time.sleep(delay)

        return all_qa_pairs

    def save_qa_pairs(self, qa_pairs, output_file):
        """
        Save Q&A pairs to JSON file

        Args:
            qa_pairs (list): List of Q&A pairs
            output_file (str): Output file path
        """
        try:
            with open(output_file, 'w', encoding='utf-8') as file:
                json.dump({
                    "qa_pairs": qa_pairs,
                    "total_pairs": len(qa_pairs),
                    "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }, file, indent=2, ensure_ascii=False)

            print(f"Successfully saved {len(qa_pairs)} Q&A pairs to {output_file}")

        except Exception as e:
            print(f"Error saving Q&A pairs: {str(e)}")

    def generate_chatbot_training_data(self, input_file, output_file, questions_per_page=3):
        """
        Complete pipeline to generate chatbot training data

        Args:
            input_file (str): Path to input JSON file
            output_file (str): Path to output JSON file  
            questions_per_page (int): Number of questions per page
        """
        print("Starting Q&A generation pipeline...")

        # Load data
        data = self.load_data(input_file)
        if not data:
            return

        # Generate Q&A pairs
        qa_pairs = self.process_all_pages(data, questions_per_page)

        if qa_pairs:
            # Save results
            self.save_qa_pairs(qa_pairs, output_file)

            # Print summary
            print(f"\n=== Generation Summary ===")
            print(f"Total pages processed: {len(data.get('pages', []))}")
            print(f"Total Q&A pairs generated: {len(qa_pairs)}")
            print(f"Output saved to: {output_file}")

            # Show sample Q&A pairs
            print(f"\n=== Sample Q&A Pairs ===")
            for i, qa in enumerate(qa_pairs[:3]):
                print(f"\nQ{i+1}: {qa.get('question', 'N/A')}")
                print(f"A{i+1}: {qa.get('answer', 'N/A')}")
                print(f"Category: {qa.get('category', 'N/A')}")
        else:
            print("No Q&A pairs were generated.")

    def generate_chatbot_training_data_db(self, questions_per_page=3):
        pages = load_processed_pages()
        for i, page in enumerate(pages):
            page_data = {"url": page.url, "text": page.text}
            qa_pairs = self.generate_qa_pairs(page_data, questions_per_page)
            for qa in qa_pairs:
                save_qa_pair(
                    question=qa.get("question"),
                    answer=qa.get("answer"),
                    category=qa.get("category"),
                    source_url=page.url
                )

def main():
    # Load from processed_data and save to final_data
    processed_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'Data', 'processed_data'))
    final_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'Data', 'final_data'))
    os.makedirs(final_data_dir, exist_ok=True)

    input_file = os.path.join(processed_data_dir, "cleaned_text.json")
    output_file = os.path.join(final_data_dir, "qa.json")

    # You can set your API key here or use the GEMINI_API_KEY environment variable
    generator = GeminiAIQAGenerator()

    # Generate Q&A pairs
    generator.generate_chatbot_training_data(
        input_file=input_file,
        output_file=output_file,
        questions_per_page=4  # Generate 4 Q&A pairs per page
    )

if __name__ == "__main__":
    main()