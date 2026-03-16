import os

agents_dir = "backend/agents"
for agent in os.listdir(agents_dir):
    prompt_file = os.path.join(agents_dir, agent, "prompts.py")
    if os.path.exists(prompt_file):
        with open(prompt_file, "r") as f:
            content = f.read()
        
        old_text = """If the user chose "Tell Your Idea" or typed their own custom idea/topic directly (e.g., "ugadi", "summer sale"):
- Do NOT proceed to the next phase (Prompt Approval) directly.
- Instead, treat their input as a core theme. Generate 6 distinct, highly creative concept choices based STRICTLY on their custom theme.
- Present these 6 choices (plus the 7th "Generate More Ideas" choice) using format_response, just like in the step above, so the user can pick the exact angle they want for their custom topic."""

        new_text = """If the user types a free-text topic or custom idea (e.g., "ugadi", "summer sale") instead of selecting an existing 1-7 choice:
[CRITICAL] Do NOT skip to the next phase. Do NOT generate the prompt yet.
Instead, treat their custom input as a core theme. You MUST stay in this phase and generate a BRAND NEW list of 6 distinct, highly creative concept choices based STRICTLY on their custom theme. 
Present these 6 custom choices (plus the 7th "Generate More Ideas" choice) using format_response, so the user can pick the exact angle they want for their topic."""

        if old_text in content:
            content = content.replace(old_text, new_text)
            print(f"Patched {prompt_file}")
            with open(prompt_file, "w") as f:
                f.write(content)
