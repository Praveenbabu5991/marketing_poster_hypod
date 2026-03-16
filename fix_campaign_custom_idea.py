import os

prompt_file = "backend/agents/campaign/prompts.py"
if os.path.exists(prompt_file):
    with open(prompt_file, "r") as f:
        content = f.read()

    old_text = """If the user chose "Tell Your Idea" or typed their own idea directly:
Skip research. Use their idea and proceed to gather missing params."""
    
    new_text = """If the user types a free-text idea/topic (e.g., "ugadi", "summer sale") instead of selecting an existing 1-7 choice:
[CRITICAL DISTINCTION]: Look closely at the user's input.
1. If their input is a BROAD TOPIC (e.g. just "ugadi" or "new year"), do NOT skip to the next phase. Treat it as a theme and generate 6 new choices based on that theme.
2. If their input is a SPECIFIC, DETAILED CONCEPT (e.g. "ugadi: new year, new skin resolution" or a full sentence describing a scene), they are telling you EXACTLY what they want. Do NOT generate another list of 6 choices. Accept their idea and PROCEED IMMEDIATELY to gather missing params."""

    if old_text in content:
        content = content.replace(old_text, new_text)
        print(f"Patched campaign custom idea logic")
        with open(prompt_file, "w") as f:
            f.write(content)
