import os

agents_dir = "backend/agents"
for agent in os.listdir(agents_dir):
    prompt_file = os.path.join(agents_dir, agent, "prompts.py")
    if os.path.exists(prompt_file):
        with open(prompt_file, "r") as f:
            content = f.read()
        
        # Look for Phase B or C where choices 1-6 are generated
        if "id: \"1\" through \"6\"" in content or "choices: SIX choices" in content:
            print(f"Patching {prompt_file}")
            
            # Replace format_response call to include 7th option
            content = content.replace(
                "Call format_response with 6 idea choices. Each choice must have:",
                "Call format_response with 7 idea choices. Each choice must have:"
            )
            content = content.replace(
                "choices: SIX choices. Each must have:",
                "choices: SEVEN choices. Each must have:"
            )
            
            # Update the description of choices 1-6 and add 7th
            if "- id: \"1\" through \"6\"" in content:
                content = content.replace(
                    "- id: \"1\" through \"6\"",
                    "- id: \"1\" through \"6\" (for the 6 generated concepts)\n   - ADD a 7th choice:\n     - id: \"7\"\n     - label: \"Generate More Ideas\"\n     - description: \"Click here if you want 6 completely fresh, new concepts.\""
                )
            elif "id: \"1\" through \"6\"" in content:
                 content = content.replace(
                    "id: \"1\" through \"6\"",
                    "id: \"1\" through \"6\" (for the 6 generated concepts)\n    ADD a 7th choice:\n    id: \"7\"\n    label: \"Generate More Ideas\"\n    description: \"Click here if you want 6 completely fresh, new concepts.\""
                )

            # Add handling for choice 7
            if "If the user chose \"Tell Your Idea\"" in content:
                content = content.replace(
                    "If the user chose \"Tell Your Idea\"",
                    "If the user chose \"Generate More Ideas\" (or choice \"7\"):\n- Do NOT proceed to the next phase.\n- Instead, clear the previous ideas and repeat the idea generation step to generate 6 brand new concepts.\n\nIf the user chose \"Tell Your Idea\""
                )

        with open(prompt_file, "w") as f:
            f.write(content)
