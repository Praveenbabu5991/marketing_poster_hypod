"""Slide Planner sub-agent for Carousel agent.

Plans N slides with themes, maintaining visual consistency across all slides.
"""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agents.state import AgentState
from brand.context import BrandContext


def build_slide_planner_node(llm: BaseChatModel):
    """Build a slide planner callable for use as a graph node."""

    def slide_planner_subgraph(state: AgentState) -> dict:
        brand_context = state.get("brand_context", {})
        bc = BrandContext.from_dict(brand_context)

        system_prompt = f"""## ROLE
You are a carousel slide planner. You plan 5-10 slides for an Instagram carousel.

## OUTPUT FORMAT
For each slide, output:
- **Slide N**: Title
- **Visual**: Description of the visual concept
- **Text overlay**: Exact text to appear on the slide
- **Notes**: Any special instructions

## RULES
- First slide = attention-grabbing hook
- Last slide = call-to-action
- Same color palette ({', '.join(bc.colors) if bc.colors else 'brand colors'}) across ALL slides
- Same style and typography throughout
- Each slide should flow logically to the next
- 5-10 slides total

╔════════════════════════════════════════════════════════════╗
║ ★ BRAND: {bc.name} | Tone: {bc.tone} | Colors: {', '.join(bc.colors[:3]) if bc.colors else 'Not set'} ★ ║
╚════════════════════════════════════════════════════════════╝
"""

        last_content = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage) and msg.content:
                last_content = msg.content
                break

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Plan carousel slides for this idea:\n{last_content}"),
        ]

        response = llm.invoke(messages)
        return {"messages": [AIMessage(content=f"[Slide Plan]\n{response.content}")]}

    return slide_planner_subgraph
