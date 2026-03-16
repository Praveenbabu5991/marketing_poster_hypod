import os

agents_dir = "backend/agents"
for agent in os.listdir(agents_dir):
    prompt_file = os.path.join(agents_dir, agent, "prompts.py")
    if os.path.exists(prompt_file):
        with open(prompt_file, "r") as f:
            content = f.read()
        
        # We need to find the text that tells the agent what to do when user provides custom idea.
        # It's usually "Skip research. Go directly to Phase C with their idea." or similar.
        # Let's replace the whole block starting with "If the user chose "Tell Your Idea""
        
        old_text1 = "If the user chose \"Tell Your Idea\" or typed their own idea directly:\nSkip research. Go directly to Phase C with their idea."
        old_text2 = "If the user chose \"Tell Your Idea\" or typed their own idea directly:\nSkip research. Go directly to Phase D with their idea."
        old_text3 = "If the user typed their own idea directly:\nSkip research. Go directly to Phase C with their idea."

        new_text = "If the user chose \"Tell Your Idea\" or typed their own custom idea/topic directly (e.g., \"ugadi\", \"summer sale\"):\n- Do NOT proceed to the next phase (Prompt Approval) directly.\n- Instead, treat their input as a core theme. Generate 6 distinct, highly creative concept choices based STRICTLY on their custom theme.\n- Present these 6 choices (plus the 7th \"Generate More Ideas\" choice) using format_response, just like in the step above, so the user can pick the exact angle they want for their custom topic."

        changed = False
        if old_text1 in content:
            content = content.replace(old_text1, new_text)
            changed = True
        if old_text2 in content:
            content = content.replace(old_text2, new_text)
            changed = True
        if old_text3 in content:
            content = content.replace(old_text3, new_text)
            changed = True
            
        if changed:
            print(f"Patched custom idea logic in {prompt_file}")
            with open(prompt_file, "w") as f:
                f.write(content)
