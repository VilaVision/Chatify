import json
import os
import requests
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from utils.data_handler import load_processed_pages, save_qa_pair

class AIProvider(ABC):
    """Abstract base class for AI providers"""
    
    @abstractmethod
    def generate_content(self, prompt: str, **kwargs) -> str:
        """Generate content using the AI provider"""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the name of the provider"""
        pass

class GeminiProvider(AIProvider):
    """Google Gemini AI Provider"""
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model = model
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    
    def generate_content(self, prompt: str, **kwargs) -> str:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": kwargs.get("temperature", 0.7),
                "maxOutputTokens": kwargs.get("max_tokens", 2048)
            }
        }
        
        headers = {'Content-Type': 'application/json'}
        
        response = requests.post(
            f"{self.base_url}?key={self.api_key}",
            headers=headers,
            json=payload,
            timeout=kwargs.get("timeout", 30)
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'candidates' in data and len(data['candidates']) > 0:
                candidate = data['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    return candidate['content']['parts'][0]['text']
        
        raise Exception(f"Gemini API error: {response.status_code} - {response.text}")
    
    def get_provider_name(self) -> str:
        return "Google Gemini"

class OpenAIProvider(AIProvider):
    """OpenAI GPT Provider"""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.openai.com/v1/chat/completions"
    
    def generate_content(self, prompt: str, **kwargs) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2048)
        }
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
        
        response = requests.post(
            self.base_url,
            headers=headers,
            json=payload,
            timeout=kwargs.get("timeout", 30)
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'choices' in data and len(data['choices']) > 0:
                return data['choices'][0]['message']['content']
        
        raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")
    
    def get_provider_name(self) -> str:
        return "OpenAI GPT"

class ClaudeProvider(AIProvider):
    """Anthropic Claude Provider"""
    
    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.anthropic.com/v1/messages"
    
    def generate_content(self, prompt: str, **kwargs) -> str:
        payload = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", 2048),
            "temperature": kwargs.get("temperature", 0.7),
            "messages": [{"role": "user", "content": prompt}]
        }
        
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': self.api_key,
            'anthropic-version': '2023-06-01'
        }
        
        response = requests.post(
            self.base_url,
            headers=headers,
            json=payload,
            timeout=kwargs.get("timeout", 30)
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'content' in data and len(data['content']) > 0:
                return data['content'][0]['text']
        
        raise Exception(f"Claude API error: {response.status_code} - {response.text}")
    
    def get_provider_name(self) -> str:
        return "Anthropic Claude"

class DeepSeekProvider(AIProvider):
    """DeepSeek AI Provider"""
    
    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.deepseek.com/chat/completions"
    
    def generate_content(self, prompt: str, **kwargs) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2048)
        }
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
        
        response = requests.post(
            self.base_url,
            headers=headers,
            json=payload,
            timeout=kwargs.get("timeout", 30)
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'choices' in data and len(data['choices']) > 0:
                return data['choices'][0]['message']['content']
        
        raise Exception(f"DeepSeek API error: {response.status_code} - {response.text}")
    
    def get_provider_name(self) -> str:
        return "DeepSeek"

class MultimodalQAGenerator:
    """Enhanced QA Generator supporting multiple AI providers"""
    
    def __init__(self, provider_configs: Dict[str, Dict] = None):
        """
        Initialize the Multimodal QA Generator
        
        Args:
            provider_configs (dict): Configuration for AI providers
                Example:
                {
                    "gemini": {"api_key": "key", "model": "gemini-2.0-flash"},
                    "openai": {"api_key": "key", "model": "gpt-4"},
                    "claude": {"api_key": "key", "model": "claude-3-sonnet-20240229"},
                    "deepseek": {"api_key": "key", "model": "deepseek-chat"}
                }
        """
        self.providers = {}
        self.fallback_order = []
        
        if provider_configs:
            self._initialize_providers(provider_configs)
        else:
            self._initialize_from_env()
    
    def _initialize_providers(self, configs: Dict[str, Dict]):
        """Initialize providers from configuration"""
        provider_classes = {
            "gemini": GeminiProvider,
            "openai": OpenAIProvider,
            "claude": ClaudeProvider,
            "deepseek": DeepSeekProvider
        }
        
        for provider_name, config in configs.items():
            if provider_name in provider_classes and config.get("api_key"):
                try:
                    provider_class = provider_classes[provider_name]
                    self.providers[provider_name] = provider_class(
                        api_key=config["api_key"],
                        model=config.get("model", self._get_default_model(provider_name))
                    )
                    self.fallback_order.append(provider_name)
                    print(f"Initialized {provider_name} provider")
                except Exception as e:
                    print(f"Failed to initialize {provider_name}: {str(e)}")
    
    def _initialize_from_env(self):
        """Initialize providers from environment variables"""
        env_configs = {
            "gemini": {
                "api_key": os.getenv('GEMINI_API_KEY'),
                "model": os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
            },
            "openai": {
                "api_key": os.getenv('OPENAI_API_KEY'),
                "model": os.getenv('OPENAI_MODEL', 'gpt-4')
            },
            "claude": {
                "api_key": os.getenv('CLAUDE_API_KEY'),
                "model": os.getenv('CLAUDE_MODEL', 'claude-3-sonnet-20240229')
            },
            "deepseek": {
                "api_key": os.getenv('DEEPSEEK_API_KEY'),
                "model": os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
            }
        }
        
        # Filter out providers without API keys
        valid_configs = {k: v for k, v in env_configs.items() if v["api_key"]}
        
        if not valid_configs:
            raise ValueError("No valid API keys found. Please set environment variables or provide provider configs.")
        
        self._initialize_providers(valid_configs)
    
    def _get_default_model(self, provider_name: str) -> str:
        """Get default model for a provider"""
        defaults = {
            "gemini": "gemini-2.0-flash",
            "openai": "gpt-4",
            "claude": "claude-3-sonnet-20240229",
            "deepseek": "deepseek-chat"
        }
        return defaults.get(provider_name, "")
    
    def generate_with_fallback(self, prompt: str, preferred_provider: str = None, **kwargs) -> tuple[str, str]:
        """
        Generate content with automatic fallback to other providers
        
        Args:
            prompt (str): The prompt to send to AI
            preferred_provider (str): Preferred provider name
            **kwargs: Additional parameters for generation
            
        Returns:
            tuple: (generated_content, used_provider)
        """
        # Determine the order of providers to try
        if preferred_provider and preferred_provider in self.providers:
            providers_to_try = [preferred_provider] + [p for p in self.fallback_order if p != preferred_provider]
        else:
            providers_to_try = self.fallback_order
        
        last_error = None
        
        for provider_name in providers_to_try:
            try:
                provider = self.providers[provider_name]
                content = provider.generate_content(prompt, **kwargs)
                print(f"Successfully generated content using {provider.get_provider_name()}")
                return content, provider_name
            except Exception as e:
                last_error = e
                print(f"Failed to generate with {provider_name}: {str(e)}")
                continue
        
        raise Exception(f"All providers failed. Last error: {str(last_error)}")
    
    def load_data(self, file_path: str) -> Optional[Dict]:
        """Load JSON data from file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        except FileNotFoundError:
            print(f"Error: File {file_path} not found")
            return None
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON format in {file_path}")
            return None
    
    def generate_qa_pairs(self, page_data: Dict, num_questions: int = 20, preferred_provider: str = None) -> List[Dict]:
        """Generate Q&A pairs from page data using available AI providers"""
        url = page_data.get('url', '')
        text = page_data.get('text', '')
        
        # Truncate text if it's too long
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
            response_text, used_provider = self.generate_with_fallback(
                prompt, 
                preferred_provider=preferred_provider,
                temperature=0.7,
                max_tokens=2048,
                timeout=30
            )
            
            # Extract JSON from response
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx]
                qa_pairs = json.loads(json_str)
                
                # Add metadata about the AI provider used
                for qa in qa_pairs:
                    qa['generated_by'] = used_provider
                
                return qa_pairs
            else:
                print("Warning: Could not find valid JSON in response")
                return []
                
        except json.JSONDecodeError:
            print("Warning: Could not parse JSON from AI response")
            print(f"Response text: {response_text[:500]}...")
            return []
        except Exception as e:
            print(f"Error generating Q&A pairs: {str(e)}")
            return []
    
    def process_all_pages(self, data: Dict, questions_per_page: int = 3, delay: int = 1, preferred_provider: str = None) -> List[Dict]:
        """Process all pages to generate Q&A pairs with load balancing"""
        if not data or 'pages' not in data:
            print("Error: Invalid data structure. Expected 'pages' key.")
            return []
        
        all_qa_pairs = []
        pages = data['pages']
        
        print(f"Processing {len(pages)} pages using {len(self.providers)} AI providers...")
        
        # Load balance across providers if multiple are available
        provider_names = list(self.providers.keys())
        
        for i, page in enumerate(pages):
            print(f"Processing page {i+1}/{len(pages)}: {page.get('url', 'No URL')}")
            
            # Round-robin provider selection if no preferred provider
            if not preferred_provider and len(provider_names) > 1:
                current_provider = provider_names[i % len(provider_names)]
            else:
                current_provider = preferred_provider
            
            qa_pairs = self.generate_qa_pairs(page, questions_per_page, current_provider)
            
            if qa_pairs:
                # Add source URL and page index to each Q&A pair
                for qa in qa_pairs:
                    qa['source_url'] = page.get('url', '')
                    qa['page_index'] = i
                
                all_qa_pairs.extend(qa_pairs)
                print(f"Generated {len(qa_pairs)} Q&A pairs using {qa_pairs[0].get('generated_by', 'unknown')}")
            else:
                print("No Q&A pairs generated for this page")
            
            # Add delay to avoid rate limiting
            if i < len(pages) - 1:
                time.sleep(delay)
        
        return all_qa_pairs
    
    def save_qa_pairs(self, qa_pairs: List[Dict], output_file: str):
        """Save Q&A pairs to JSON file with metadata"""
        try:
            # Generate provider usage statistics
            provider_stats = {}
            for qa in qa_pairs:
                provider = qa.get('generated_by', 'unknown')
                provider_stats[provider] = provider_stats.get(provider, 0) + 1
            
            output_data = {
                "qa_pairs": qa_pairs,
                "total_pairs": len(qa_pairs),
                "provider_statistics": provider_stats,
                "available_providers": list(self.providers.keys()),
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            with open(output_file, 'w', encoding='utf-8') as file:
                json.dump(output_data, file, indent=2, ensure_ascii=False)
            
            print(f"Successfully saved {len(qa_pairs)} Q&A pairs to {output_file}")
            print(f"Provider usage: {provider_stats}")
            
        except Exception as e:
            print(f"Error saving Q&A pairs: {str(e)}")
    
    def generate_chatbot_training_data(self, input_file: str, output_file: str, questions_per_page: int = 3, preferred_provider: str = None):
        """Complete pipeline to generate chatbot training data"""
        print("Starting Multimodal Q&A generation pipeline...")
        print(f"Available providers: {list(self.providers.keys())}")
        
        # Load data
        data = self.load_data(input_file)
        if not data:
            return
        
        # Generate Q&A pairs
        qa_pairs = self.process_all_pages(data, questions_per_page, preferred_provider=preferred_provider)
        
        if qa_pairs:
            # Save results
            self.save_qa_pairs(qa_pairs, output_file)
            
            # Print summary
            provider_stats = {}
            for qa in qa_pairs:
                provider = qa.get('generated_by', 'unknown')
                provider_stats[provider] = provider_stats.get(provider, 0) + 1
            
            print(f"\n=== Generation Summary ===")
            print(f"Total pages processed: {len(data.get('pages', []))}")
            print(f"Total Q&A pairs generated: {len(qa_pairs)}")
            print(f"Provider usage: {provider_stats}")
            print(f"Output saved to: {output_file}")
            
            # Show sample Q&A pairs
            print(f"\n=== Sample Q&A Pairs ===")
            for i, qa in enumerate(qa_pairs[:3]):
                print(f"\nQ{i+1}: {qa.get('question', 'N/A')}")
                print(f"A{i+1}: {qa.get('answer', 'N/A')}")
                print(f"Category: {qa.get('category', 'N/A')}")
                print(f"Generated by: {qa.get('generated_by', 'N/A')}")
        else:
            print("No Q&A pairs were generated.")
    
    def generate_chatbot_training_data_db(self, questions_per_page: int = 3, preferred_provider: str = None):
        """Generate Q&A pairs and save to database"""
        pages = load_processed_pages()
        
        # Load balance across providers
        provider_names = list(self.providers.keys())
        
        for i, page in enumerate(pages):
            # Round-robin provider selection if no preferred provider
            if not preferred_provider and len(provider_names) > 1:
                current_provider = provider_names[i % len(provider_names)]
            else:
                current_provider = preferred_provider
            
            page_data = {"url": page.url, "text": page.text}
            qa_pairs = self.generate_qa_pairs(page_data, questions_per_page, current_provider)
            
            for qa in qa_pairs:
                save_qa_pair(
                    question=qa.get("question"),
                    answer=qa.get("answer"),
                    category=qa.get("category"),
                    source_url=page.url
                )

def main():
    """Example usage with multiple providers"""
    # Setup directories
    processed_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'Data', 'processed_data'))
    final_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'Data', 'final_data'))
    os.makedirs(final_data_dir, exist_ok=True)
    
    input_file = os.path.join(processed_data_dir, "cleaned_text.json")
    output_file = os.path.join(final_data_dir, "qa_multimodal.json")
    
    # Option 1: Initialize from environment variables
    generator = MultimodalQAGenerator()
    
    # Option 2: Initialize with explicit configuration
    # provider_configs = {
    #     "gemini": {"api_key": "your-gemini-key", "model": "gemini-2.0-flash"},
    #     "openai": {"api_key": "your-openai-key", "model": "gpt-4"},
    #     "claude": {"api_key": "your-claude-key", "model": "claude-3-sonnet-20240229"},
    #     "deepseek": {"api_key": "your-deepseek-key", "model": "deepseek-chat"}
    # }
    # generator = MultimodalQAGenerator(provider_configs)
    
    # Generate Q&A pairs with automatic provider fallback
    generator.generate_chatbot_training_data(
        input_file=input_file,
        output_file=output_file,
        questions_per_page=20,  # Generate 20 Q&A pairs per page
        preferred_provider="gemini"  # Optional: prefer a specific provider
    )

if __name__ == "__main__":
    main()