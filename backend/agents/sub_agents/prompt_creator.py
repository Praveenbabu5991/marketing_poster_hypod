"""Prompt Creator sub-agent.

Creates detailed image/video generation prompts from content ideas.
Single LLM call (no tools needed) — invoked as a node by parent orchestrators.
"""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agents.state import AgentState
from brand.context import BrandContext


def _build_prompt_creator_prompt(output_type: str, brand_context: dict) -> str:
    bc = BrandContext.from_dict(brand_context)
    return f"""## ROLE
You are an expert at writing {output_type} generation prompts for AI models.

## WORKFLOW
1. Read the content idea from the conversation.
2. Read the brand context below.
3. Create a detailed {output_type} generation prompt.

## OUTPUT FORMAT
Output ONLY the prompt text. No explanations, markdown, or wrapping.
Must include:
- Subject and composition description
- Color palette: use brand colors as primary/accent (list hex codes)
- Logo placement: specify where and how large
- Style: photography, illustration, flat design, etc. (match brand tone)
- Mood and lighting description
- Text overlay: exact text + font style (if needed)
- Aspect ratio recommendation

## RULES
- ALWAYS incorporate brand colors explicitly (list hex codes in prompt).
- ALWAYS include logo placement instructions.
- Match visual style to brand tone (professional=clean/minimal, playful=vibrant/bold).
- Do NOT output anything except the generation prompt.

╔════════════════════════════════════════════════════════════╗
║ ★ BRAND IDENTITY — EMBED IN EVERY PROMPT ★                ║
║                                                            ║
║ {bc.to_prompt_text()}
║                                                            ║
║ → Mention brand colors by hex code in the prompt           ║
║ → Describe logo placement (corner, watermark, center)      ║
║ → Visual style must reflect brand tone                     ║
╚════════════════════════════════════════════════════════════╝
"""


def build_prompt_creator_node(llm: BaseChatModel, output_type: str):
    """Build a prompt creator callable for use as a graph node.

    Single LLM call — no tool loop needed.
    """
    def prompt_creator_subgraph(state: AgentState) -> dict:
        brand_context = state.get("brand_context", {})
        system_prompt = _build_prompt_creator_prompt(output_type, brand_context)

        # Get context from conversation
        last_content = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage) and msg.content:
                last_content = msg.content
                break

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Create a {output_type} generation prompt based on this idea:\n{last_content}"),
        ]

        response = llm.invoke(messages)
        return {"messages": [AIMessage(content=f"[Visual Prompt]\n{response.content}")]}

    return prompt_creator_subgraph
