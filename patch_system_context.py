import glob
import os

files = glob.glob("backend/agents/*/prompts.py")

context_block = """### SYSTEM CONTEXT HANDLING (CRITICAL)
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

You MUST prioritize these System Context values over any general defaults in every generation turn.
"""

for filepath in files:
    with open(filepath, "r") as f:
        content = f.read()
    
    if "SYSTEM CONTEXT HANDLING" not in content:
        content = content.replace("## WORKFLOW\n", f"## WORKFLOW\n\n{context_block}\n")
        
        # Also fix the start prompt bug
        content = content.replace(
            '### Phase A — Welcome (triggered by "start" message)',
            '### Phase A — Welcome (triggered by "start" message)\nCRITICAL: If the user message is literally just "start" (or "start" followed by a System Context block), you MUST immediately execute Phase A and call `format_response` with the welcome message. Do not perform any research or tool calls yet.'
        )
        content = content.replace(
            'When the user\'s message is "start":', 
            'When the user\'s message is "start" (ignoring any [System Context: ...] block):'
        )
        content = content.replace(
            'When the user\'s message is "start", call format_response with:', 
            'When the user\'s message is "start" (ignoring any [System Context: ...] block), call format_response with:'
        )
        content = content.replace(
            'The "start" trigger is sent automatically by the frontend, not by the user.',
            'The "start" trigger is sent automatically by the frontend (it may contain a [System Context] block, which you should parse but otherwise treat the message as just "start"), not by the user.'
        )
        content = content.replace(
            'The "start" trigger is sent automatically by the frontend',
            'The "start" trigger is sent automatically by the frontend (it may contain a [System Context] block, which you should parse but otherwise treat the message as just "start")'
        )
        
        with open(filepath, "w") as f:
            f.write(content)
        print(f"Patched {filepath}")
    else:
        print(f"Already patched {filepath}")
