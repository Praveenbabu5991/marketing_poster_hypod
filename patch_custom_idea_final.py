import os

agents_dir = "backend/agents"
for agent in os.listdir(agents_dir):
    prompt_file = os.path.join(agents_dir, agent, "prompts.py")
    if os.path.exists(prompt_file):
        with open(prompt_file, "r") as f:
            content = f.read()
        
        old_text = """If the user types a free-text topic or custom idea (e.g., "ugadi", "summer sale") instead of selecting an existing 1-7 choice:
[CRITICAL] Do NOT skip to the next phase. Do NOT generate the prompt yet.
Instead, treat their custom input as a core theme. You MUST stay in this phase and generate a BRAND NEW list of 6 distinct, highly creative concept choices based STRICTLY on their custom theme. 
Present these 6 custom choices (plus the 7th "Generate More Ideas" choice) using format_response, so the user can pick the exact angle they want for their topic."""

        old_text2 = """If the user types a free-text topic or custom description instead of selecting an existing 1-7 choice:
[CRITICAL] Do NOT skip to Phase C. Do NOT generate the prompt yet.
Instead, treat their custom input as a core theme. You MUST stay in this phase and generate a BRAND NEW list of 6 distinct, highly creative image concepts based STRICTLY on their custom input. 
Present these 6 custom choices (plus the 7th "Generate More Ideas" choice) using format_response, so the user can pick the exact angle they want for their topic."""

        old_text3 = """If the user types a free-text topic or custom concept instead of selecting an existing 1-7 choice:
[CRITICAL] Do NOT skip to Phase D. Do NOT generate the prompt yet.
Instead, treat their custom input as a core theme. You MUST stay in this phase and generate a BRAND NEW list of 6 distinct, highly creative concept choices based STRICTLY on their custom theme. 
Present these 6 custom choices (plus the 7th "Generate More Ideas" choice) using format_response, so the user can pick the exact angle they want for their topic."""

        old_text4 = """If the user types a free-text headline or custom concept instead of selecting an existing 1-7 choice:
[CRITICAL] Do NOT skip to Phase D. Do NOT move to the CTA step yet.
Instead, treat their custom input as a core theme. You MUST stay in this phase and generate a BRAND NEW list of 6 distinct, highly creative headline choices based STRICTLY on their custom input. 
Present these 6 custom choices (plus the 7th "Generate More Ideas" choice) using format_response, so the user can pick the exact angle they want for their topic."""

        new_text = """If the user types a free-text idea/topic (e.g., "ugadi", "summer sale") instead of selecting an existing 1-7 choice:
[CRITICAL DISTINCTION]: Look closely at the user's input.
1. If their input is a BROAD TOPIC (e.g. just "ugadi" or "new year"), do NOT skip to the next phase. Treat it as a theme and generate 6 new choices based on that theme.
2. If their input is a SPECIFIC, DETAILED CONCEPT (e.g. "ugadi: new year, new skin resolution" or a full sentence describing a scene), they are telling you EXACTLY what they want. Do NOT generate another list of 6 choices. Accept their idea and PROCEED IMMEDIATELY to the next phase (Show Prompt/Approval) using their specific concept."""

        changed = False
        if old_text in content:
            content = content.replace(old_text, new_text)
            changed = True
        if old_text2 in content:
            content = content.replace(old_text2, new_text)
            changed = True
        if old_text3 in content:
            content = content.replace(old_text3, new_text)
            changed = True
        if old_text4 in content:
            content = content.replace(old_text4, new_text)
            changed = True
            
        if changed:
            print(f"Patched strict broad vs specific logic in {prompt_file}")
            with open(prompt_file, "w") as f:
                f.write(content)
