import os

agents_dir = "backend/agents"
for agent in os.listdir(agents_dir):
    prompt_file = os.path.join(agents_dir, agent, "prompts.py")
    if os.path.exists(prompt_file):
        with open(prompt_file, "r") as f:
            content = f.read()
        
        old_text1 = "repeat the idea generation step to generate 6 brand new concepts. CRITICAL: The new concepts MUST be unique and completely different from the ones previously suggested."
        old_text2 = "repeat Phase C to generate 6 brand new concepts. CRITICAL: The new concepts MUST be unique and completely different from the ones previously suggested."
        old_text3 = "repeat Phase B to generate 6 brand new concepts. CRITICAL: The new concepts MUST be unique and completely different from the ones previously suggested."
        
        new_text = "repeat the generation step to provide 6 completely new concepts. CRITICAL UNIQUENESS RULE: You MUST read the chat history to see which specific events, holidays, trends, and product angles you ALREADY suggested. You are FORBIDDEN from using those same calendar events, trends, or angles again. Pick DIFFERENT upcoming events and DIFFERENT product features/trends."
        
        if old_text1 in content:
            content = content.replace(old_text1, new_text)
            print(f"Patched {prompt_file}")
        elif old_text2 in content:
            content = content.replace(old_text2, new_text)
            print(f"Patched {prompt_file}")
        elif old_text3 in content:
            content = content.replace(old_text3, new_text)
            print(f"Patched {prompt_file}")

        with open(prompt_file, "w") as f:
            f.write(content)
