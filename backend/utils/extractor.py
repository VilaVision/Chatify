from bs4 import BeautifulSoup
import requests

def extract_structure_and_text(html: str) -> tuple:
    soup = BeautifulSoup(html, 'html.parser')
    
    for tag in soup(['script', 'style']):
        tag.decompose()

    text_content = soup.get_text(separator='\n', strip=True)

    code_blocks = []
    for code_tag in soup.find_all('code'):
        code_blocks.append(code_tag.get_text())

    def get_structure(element):
        children = [get_structure(child) for child in element.find_all(recursive=False)]
        return {
            'tag': element.name,
            'attrs': element.attrs,
            'children': children
        } if element.name else None

    structure = get_structure(soup.body if soup.body else soup)
    return text_content, code_blocks, structure

def extract_text_from_links(links):
    """
    Given a list of URLs, fetch and extract text from each.
    Returns a list of dicts: [{'url': ..., 'text': ...}, ...]
    """
    results = []
    for url in links:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            text, _, _ = extract_structure_and_text(resp.text)
            results.append({'url': url, 'text': text})
        except Exception as e:
            results.append({'url': url, 'text': '', 'error': str(e)})
    return results
