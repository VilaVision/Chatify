import requests
from pathlib import Path

def fetch_html(source: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/114.0.0.0 Safari/537.36"
        )
    }

    if source.startswith(("http://", "https://")):
        response = requests.get(source, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    else:
        path = Path(source)
        return path.read_text(encoding='utf-8')
