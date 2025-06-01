import json
import os
from urllib.parse import urlparse, unquote
import re
from pathlib import Path

def clean_url(url):
    """Remove tracking parameters, fragments, and normalize the URL."""
    parsed = urlparse(url)
    # Remove query and fragment
    clean = parsed._replace(query="", fragment="")
    return clean.geturl()

def normalize_text(text):
    """Basic text normalization: strip, lower, remove extra spaces."""
    text = text or ""
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    return text

def reduce_duplicate_links(links_data):
    """Remove duplicate links based on cleaned URL."""
    seen = set()
    reduced = []
    for entry in links_data:
        url = clean_url(entry.get('link', ''))
        if url and url not in seen:
            seen.add(url)
            entry['link'] = url
            reduced.append(entry)
    return reduced

def integrate_sources(links_data):
    """Integrate multiple sources for the same link."""
    integrated = {}
    for entry in links_data:
        if not isinstance(entry, dict):
            print("Skipping non-dict entry in integrate_sources:", entry)
            continue  # Skip if not a dict
        url = entry.get('link', '')
        source = entry.get('from', '')
        if url not in integrated:
            integrated[url] = {'link': url, 'from': set()}
        if source:
            integrated[url]['from'].add(source)
    # Convert 'from' sets to lists
    for v in integrated.values():
        v['from'] = list(v['from'])
    return list(integrated.values())

def transform_link_to_path(link):
    """Transform a URL into a folder/file path."""
    parsed_url = urlparse(link)
    path = unquote(parsed_url.path.lstrip('/'))
    if not path or path.endswith('/'):
        path = os.path.join(path, 'index.html')
    elif '.' not in os.path.basename(path):
        path = path + '.html'
    return path

def create_folder_structure_from_links(json_file_path, output_dir):
    """
    Convert a JSON dataset of website links into a folder structure
    with preprocessing: cleaning, integration, transformation, reduction.
    """
    # Read the JSON data
    with open(json_file_path, 'r', encoding='utf-8') as file:
        links_data = json.load(file)

    # --- Data Cleaning ---
    for i, entry in enumerate(links_data):
        if not isinstance(entry, dict):
            continue
        entry['link'] = clean_url(entry.get('link', ''))
        entry['from'] = normalize_text(entry.get('from', ''))

    # --- Data Integration ---
    links_data = integrate_sources(links_data)

    # --- Data Reduction ---
    links_data = reduce_duplicate_links(links_data)

    # Create base output directory
    base_path = Path(output_dir)
    base_path.mkdir(exist_ok=True)

    # Track created files to avoid duplicates
    created_files = set()

    # --- Data Transformation & Structure Creation ---
    for entry in links_data:
        link = entry.get('link', '')
        sources = entry.get('from', [])
        if not link:
            continue

        parsed_url = urlparse(link)
        domain = parsed_url.netloc
        path = parsed_url.path

        # Skip external domains (keep only the main domain)
        if domain and not any(main_domain in domain for main_domain in ['resurge.org', 'localhost', '']):
            # Create external_links folder for external references
            external_dir = base_path / "external_links"
            external_dir.mkdir(exist_ok=True)
            # Create a text file with external links
            external_file = external_dir / "external_references.txt"
            with open(external_file, 'a', encoding='utf-8') as f:
                f.write(f"{link}\n")
            continue

        # Clean up the path
        if path:
            clean_path = transform_link_to_path(link)
            path_parts = clean_path.split('/')
            current_path = base_path
            for i, part in enumerate(path_parts):
                if i == len(path_parts) - 1:  # Last part (filename or page)
                    if part:
                        file_path = current_path / part
                        if str(file_path) not in created_files:
                            file_path.parent.mkdir(parents=True, exist_ok=True)
                            # Create file with basic content
                            if file_path.suffix in ['.html', '']:
                                create_html_file(file_path, link, sources)
                            elif file_path.suffix in ['.jpg', '.png', '.gif', '.webp']:
                                create_image_placeholder(file_path, link)
                            elif file_path.suffix in ['.css']:
                                create_css_file(file_path, link)
                            elif file_path.suffix in ['.js']:
                                create_js_file(file_path, link)
                            else:
                                create_generic_file(file_path, link)
                            created_files.add(str(file_path))
                else:
                    if part:
                        current_path = current_path / part
                        current_path.mkdir(exist_ok=True)
        else:
            # Root level file
            index_file = base_path / "index.html"
            if str(index_file) not in created_files:
                create_html_file(index_file, link, sources)
                created_files.add(str(index_file))

    print(f"Folder structure created successfully in '{output_dir}'")
    print(f"Total files created: {len(created_files)}")

    # Create a summary file
    create_summary_file(base_path, created_files, links_data)

    # Save the structure as JSON for further processing
    structure_json_path = os.path.join(
        os.path.dirname(__file__),
        '..', '..', 'Data', 'processed_data', 'structure.json'
    )
    structure_json_path = os.path.abspath(structure_json_path)
    structure_data = {
        "files_created": sorted(list(created_files)),
        "total_files": len(created_files)
    }
    with open(structure_json_path, 'w', encoding='utf-8') as f:
        json.dump(structure_data, f, indent=2)
    print(f"Structure data also saved to: {structure_json_path}")

def create_html_file(file_path, original_link, sources):
    """Create an HTML file with basic structure"""
    if isinstance(sources, list):
        sources_str = ', '.join(sources)
    else:
        sources_str = str(sources)
    content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{file_path.stem.replace('-', ' ').title()}</title>
    <!-- Original URL: {original_link} -->
    <!-- Source: {sources_str} -->
</head>
<body>
    <h1>{file_path.stem.replace('-', ' ').title()}</h1>
    <p>This page was generated from: <code>{original_link}</code></p>
    <p>Source feed: <code>{sources_str}</code></p>
    <!-- Add your content here -->
</body>
</html>"""
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

def create_image_placeholder(file_path, original_link):
    """Create a placeholder file for images"""
    content = f"""# Image Placeholder
Original URL: {original_link}
File: {file_path.name}

This is a placeholder for an image file.
The actual image would need to be downloaded from the original URL.
"""
    
    placeholder_file = file_path.with_suffix(file_path.suffix + '.info')
    with open(placeholder_file, 'w', encoding='utf-8') as f:
        f.write(content)

def create_css_file(file_path, original_link):
    """Create a basic CSS file"""
    content = f"""/* CSS File generated from {original_link} */

body {{
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 20px;
    background-color: #f5f5f5;
}}

.container {{
    max-width: 1200px;
    margin: 0 auto;
    background-color: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}}

h1, h2, h3 {{
    color: #333;
}}

/* Add your styles here */
"""
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

def create_js_file(file_path, original_link):
    """Create a basic JavaScript file"""
    content = f"""// JavaScript file generated from {original_link}

document.addEventListener('DOMContentLoaded', function() {{
    console.log('Page loaded: {file_path.name}');
    // Add your JavaScript code here
}});
// Generated from: {original_link}
"""
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

def create_generic_file(file_path, original_link):
    """Create a generic file with metadata"""
    content = f"""File: {file_path.name}
Original URL: {original_link}
Generated: {__import__('datetime').datetime.now().isoformat()}

This file was created from the website structure analysis.
The actual content would need to be obtained from the original URL.
"""
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

def create_summary_file(base_path, created_files, original_data):
    """Create a summary file with statistics"""
    summary_content = f"""# Website Structure Summary

## Statistics
- Total links processed: {len(original_data)}
- Total files created: {len(created_files)}
- Generated on: {__import__('datetime').datetime.now().isoformat()}

## File Types Created
"""
    
    # Count file types
    file_types = {}
    for file_path in created_files:
        ext = Path(file_path).suffix or '.html'
        file_types[ext] = file_types.get(ext, 0) + 1
    
    for ext, count in sorted(file_types.items()):
        summary_content += f"- {ext}: {count} files\n"
    
    summary_content += "\n## Directory Structure\n"
    
    # Add directory tree (simplified)
    for file_path in sorted(created_files):
        rel_path = Path(file_path).relative_to(base_path)
        summary_content += f"- {rel_path}\n"
    
    with open(base_path / "STRUCTURE_SUMMARY.md", 'w', encoding='utf-8') as f:
        f.write(summary_content)

if __name__ == "__main__":
    # Replace with your actual JSON file path if needed
    json_file = os.path.join(os.path.dirname(__file__), '..', 'Data', 'navigation.json')
    output_directory = os.path.join(os.path.dirname(__file__), '..', 'Data', 'site_structure')
    
    try:
        create_folder_structure_from_links(json_file, output_directory)
        print(f"\n✅ Conversion completed!")
        print(f"📁 Check the '{output_directory}' folder for your website structure")
        print(f"📋 See 'STRUCTURE_SUMMARY.md' for detailed information")
        
    except FileNotFoundError:
        print(f"❌ Error: Could not find the file '{json_file}'")
        print("Make sure the file path is correct and the file exists.")
    except json.JSONDecodeError:
        print(f"❌ Error: Invalid JSON format in '{json_file}'")
        print("Please check that your file contains valid JSON data.")
    except Exception as e:
        print(f"❌ An error occurred: {str(e)}")