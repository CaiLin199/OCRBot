import os
import logging

logger = logging.getLogger(__name__)

def process_subtitle(input_file, output_file=None):
    """
    Process ASS subtitle file
    Returns: (success, output_file_path or error_message)
    """
    try:
        if output_file is None:
            output_file = f"processed_{os.path.basename(input_file)}"
            
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        processed_lines = []
        for line in lines:
            # Style formatting
            if line.startswith('Style: Default'):
                line = line.replace('Arial', 'Oath-Bold').replace(',16,', ',20,')
            
            # Dialog positioning
            if line.startswith('Dialogue:'):
                parts = line.split(',', 9)
                if len(parts) > 9:
                    parts[9] = f"{{\\pos(193,265)}}{parts[9]}"
                line = ','.join(parts)
            
            processed_lines.append(line)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.writelines(processed_lines)

        return True, output_file
    except Exception as e:
        logger.error(f"Error processing subtitle: {e}")
        return False, str(e)