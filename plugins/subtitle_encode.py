import os
import logging
import re

logger = logging.getLogger(__name__)

def process_subtitle(input_file, output_file=None):
    """
    Process ASS subtitle file:
    1. Set font to Oath-Bold and size to 20 in Style section
    2. Add position tag and remove all other tags in Dialogue lines
    Returns: (success, output_file_path or error_message)
    """
    try:
        if output_file is None:
            output_file = f"processed_{os.path.basename(input_file)}"
            
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        processed_lines = []
        in_style_section = False
        
        for line in lines:
            # Track style section
            if '[V4+ Styles]' in line:
                in_style_section = True
            elif line.startswith('[') and 'Styles' not in line:
                in_style_section = False
            
            # Modify the Default style
            if in_style_section and line.startswith('Style: Default'):
                style_parts = line.split(',')
                if len(style_parts) >= 3:
                    style_parts[1] = 'Oath-Bold'  # Font name
                    style_parts[2] = '20'         # Font size
                    line = ','.join(style_parts)
            
            # Process dialogue lines
            elif line.startswith('Dialogue:'):
                parts = line.split(',', 9)
                if len(parts) > 9:
                    text = parts[9]
                    
                    # Remove all existing tags
                    # This pattern matches any {...} including nested ones
                    text = re.sub(r'{[^{}]*}', '', text)
                    
                    # Add position tag
                    text = f"{{\\pos(193,265)}}{text}"
                    
                    # Update the line
                    parts[9] = text
                    line = ','.join(parts)
            
            processed_lines.append(line)

        # Write the processed lines
        with open(output_file, 'w', encoding='utf-8') as f:
            f.writelines(processed_lines)

        logger.info(f"Successfully processed subtitle: {output_file}")
        return True, output_file
        
    except Exception as e:
        logger.error(f"Error processing subtitle: {e}")
        return False, str(e)