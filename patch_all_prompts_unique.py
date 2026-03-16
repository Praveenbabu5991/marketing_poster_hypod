import os

agents_dir = "backend/agents"
for agent in os.listdir(agents_dir):
    prompt_file = os.path.join(agents_dir, agent, "prompts.py")
    if os.path.exists(prompt_file):
        with open(prompt_file, "r") as f:
            content = f.read()
        
        if "If the user chose \"Generate More Ideas\"" in content:
            print(f"Updating uniqueness constraint in {prompt_file}")
            content = content.replace(
                "repeat the idea generation step to generate 6 brand new concepts.",
                "repeat the idea generation step to generate 6 brand new concepts. CRITICAL: The new concepts MUST be unique and completely different from the ones previously suggested."
            )

        with open(prompt_file, "w") as f:
            f.write(content)
