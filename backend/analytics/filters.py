import os
from analytics.filter.cleaner import create_folder_structure_from_links
from analytics.filter.ai import GeminiAIQAGenerator

def run_all_filters(data_dir):
    """
    Runs the cleaner filter (folder structure creation with preprocessing)
    for both text.json and navigation.json, saving output in processed_data.
    Also generates Q&A pairs using Gemini AI and saves them in final_data.
    Args:
        data_dir (str): Base data directory (e.g., backend/Data)
    """
    # Input paths (from primary_data)
    text_json = os.path.join(data_dir, 'primary_data', 'text.json')
    navigation_json = os.path.join(data_dir, 'primary_data', 'navigation.json')

    # Output directory (processed_data)
    processed_data_dir = os.path.join(data_dir, 'processed_data')
    os.makedirs(processed_data_dir, exist_ok=True)

    # Folder structure output for text.json
    site_structure_text = os.path.join(processed_data_dir, 'site_structure_text')
    create_folder_structure_from_links(text_json, site_structure_text)

    # Folder structure output for navigation.json
    site_structure_nav = os.path.join(processed_data_dir, 'site_structure_navigation')
    create_folder_structure_from_links(navigation_json, site_structure_nav)

    print("Cleaner filter executed successfully for both text.json and navigation.json.")

    # Q&A Generation using Gemini AI
    final_data_dir = os.path.join(data_dir, 'final_data')
    os.makedirs(final_data_dir, exist_ok=True)
    input_file = os.path.join(processed_data_dir, "cleaned_text.json")
    output_file = os.path.join(final_data_dir, "qa.json")

    generator = GeminiAIQAGenerator()
    generator.generate_chatbot_training_data(
        input_file=input_file,
        output_file=output_file,
        questions_per_page=4
    )
    print("Q&A generation completed and saved to final_data/qa.json.")

if __name__ == "__main__":
    # Example usage: set your base data directory here
    base_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'Data'))
    run_all_filters(base_data_dir)