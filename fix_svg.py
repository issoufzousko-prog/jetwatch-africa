import re

def fix_svg(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # The first path currently contains many sub-paths.
    # We want to:
    # 1. Close the first sub-path (the background rectangle) and hide it.
    # 2. Open a new path for the remaining sub-paths and color it blue/purple.

    # Find the end of the background rectangle coordinates
    # It ends at 865.000000,1255.000000
    # Let's find the first M after that.
    
    match = re.search(r'(C1125\.166626,1255\.000000 995\.333313,1255\.000000 865\.000000,1255\.000000\s+)(M915\.976746)', content)
    if match:
        # Split here
        # Background path ends at match.group(1)
        # New path starts at match.group(2)
        
        # Replace the first path tag and insert the split
        # Original: <path fill="#FEFEFE" opacity="0" ... d=" ... [coords] ... M...
        
        # Let's find the start of the first path d attribute
        d_start = content.find('d="')
        if d_start == -1: return
        
        pre_d = content[:d_start]
        after_d = content[d_start+3:]
        
        # In after_d, find the split point
        split_point = after_d.find('M915.976746')
        if split_point == -1: return
        
        bg_coords = after_d[:split_point]
        remaining = after_d[split_point:]
        
        # New content:
        # <path fill="#FEFEFE" opacity="0" stroke="none" d=" [bg_coords] z"/>
        # <path fill="#298AFA" opacity="1.0" stroke="none" d=" [remaining]
        
        new_content = pre_d + 'd="' + bg_coords + 'z"/>\n'
        new_content += '<path fill="#298AFA" opacity="1.000000" stroke="none" d="' + remaining
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("Successfully fixed SVG structure.")
    else:
        print("Could not find the split point in the SVG.")

fix_svg('c:/Users/HP/.gemini/antigravity/scratch/jetwatch-africa/frontend/public/vip-detect.svg', 
        'c:/Users/HP/.gemini/antigravity/scratch/jetwatch-africa/frontend/public/vip-detect.svg')
