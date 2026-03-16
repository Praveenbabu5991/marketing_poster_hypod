import os

prompt_file = "backend/agents/sales_poster/prompts.py"
if os.path.exists(prompt_file):
    with open(prompt_file, "r") as f:
        content = f.read()
    
    # Add uniqueness constraint
    if "repeat the idea generation step to generate 6 brand new concepts." not in content:
        # First add the "Generate More Ideas" handling if missing (it might have been missed by the first patcher due to naming)
        if "If the user chose \"Generate More Ideas\"" not in content:
             content = content.replace(
                "STOP and wait.",
                "STOP and wait.\n\nIf the user chose \"Generate More Ideas\" (or choice \"7\"):\n- Do NOT proceed to the next phase.\n- Instead, clear the previous ideas and repeat the idea generation step to generate 6 brand new concepts. CRITICAL: The new concepts MUST be unique and completely different from the ones previously suggested."
            )
    else:
        content = content.replace(
            "repeat the idea generation step to generate 6 brand new concepts.",
            "repeat the idea generation step to generate 6 brand new concepts. CRITICAL: The new concepts MUST be unique and completely different from the ones previously suggested."
        )

    with open(prompt_file, "w") as f:
        f.write(content)
