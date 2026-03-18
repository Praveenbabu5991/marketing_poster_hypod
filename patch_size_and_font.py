import glob
import re

files = glob.glob("backend/agents/*/prompts.py")

new_text = """### SYSTEM CONTEXT HANDLING (CRITICAL)
In any phase, if the user's message contains a block starting with `[System Context: ... ]`, you MUST parse the following values and apply them when calling `generate_image`:

1.  **Size Mapping (apply to aspect_ratio):**
    - "1080x1080 (Square)" -> aspect_ratio: "1:1"
    - "1080x1920 (Story)" -> aspect_ratio: "9:16"
    - "1080x1350 (Portrait)" -> aspect_ratio: "4:5"
    - "1920x1080 (Landscape)" -> aspect_ratio: "16:9"

2.  **Font Mapping (apply to font_style):**
    - "Bold Sans-Serif (Default)" -> font_style: "bold sans-serif"
    - "Elegant Serif" -> font_style: "elegant, high-contrast serif"
    - "Playful Handwriting" -> font_style: "casual, handwritten script"
    - "Modern Minimalist" -> font_style: "clean, geometric thin sans-serif"
    - "Heavy Impact" -> font_style: "ultra-bold, blocky display"

You MUST prioritize these System Context values over any general defaults in every generation turn."""

for file in files:
    with open(file, 'r') as f:
        content = f.read()
    
    # We want to replace everything from "### SYSTEM CONTEXT HANDLING" to "in every generation turn."
    pattern = re.compile(r"### SYSTEM CONTEXT HANDLING \(CRITICAL\).*?in every generation turn\.", re.DOTALL)
    
    new_content = pattern.sub(new_text, content)
    
    if new_content != content:
        with open(file, 'w') as f:
            f.write(new_content)
        print(f"Patched Size and Font handling into {file}")
