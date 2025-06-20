import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
import openai
import os

# Load your OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")  # Recommended: Set this in your environment

def load_data(filename="text_data.json"):
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def cluster_data(data, num_clusters=5):
    texts = [item["text"] for item in data]
    vectorizer = TfidfVectorizer(stop_words="english")
    X = vectorizer.fit_transform(texts)

    kmeans = KMeans(n_clusters=num_clusters, random_state=42)
    labels = kmeans.fit_predict(X)

    for i, item in enumerate(data):
        item["cluster"] = int(labels[i])

    sorted_data = sorted(data, key=lambda x: x["cluster"])
    return sorted_data

def generate_qa(text):
    prompt = f"Generate a question and answer based on this text:\n\n{text}"
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",  # or gpt-3.5-turbo
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300
        )
        content = response['choices'][0]['message']['content'].strip()
        if "Q:" in content and "A:" in content:
            parts = content.split("A:")
            question = parts[0].replace("Q:", "").strip()
            answer = parts[1].strip()
            return question, answer
        else:
            return "What is the content about?", content
    except Exception as e:
        return "Error generating question", str(e)

def generate_all_qa(data):
    qa_data = []
    for item in data:
        question, answer = generate_qa(item["text"])
        qa_data.append({
            "link": item.get("link", ""),
            "tag": item.get("tag", ""),
            "text": item["text"],
            "question": question,
            "answer": answer
        })
    return qa_data

def main():
    print("[1] Loading data...")
    raw_data = load_data()

    print("[2] Clustering and organizing...")
    structured = cluster_data(raw_data)
    save_data(structured, "structured_data.json")

    print("[3] Generating Q&A using AI...")
    qa_results = generate_all_qa(structured)
    save_data(qa_results, "final_data.json")

    print("[✔] Done! Data saved to final_data.json")

if __name__ == "__main__":
    main()
