"""Campaign Planner sub-agent for Campaign agent.

Plans multi-week campaign schedule with post themes.
"""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agents.state import AgentState
from brand.context import BrandContext


def build_campaign_planner_node(llm: BaseChatModel):
    """Build a campaign planner callable for use as a graph node."""

    def campaign_planner_subgraph(state: AgentState) -> dict:
        brand_context = state.get("brand_context", {})
        bc = BrandContext.from_dict(brand_context)

        system_prompt = f"""## ROLE
You are a campaign planner. You plan 2-4 week social media campaigns.

## OUTPUT FORMAT
For each week, output:
- **Week N**: Theme
- For each post (2-3 per week):
  - **Post title**: Catchy name
  - **Visual concept**: What the image should look like
  - **Caption theme**: Key message
  - **Best posting day**: Suggested day of week

## RULES
- 2-4 weeks of content
- 2-3 posts per week
- Maximum 20 posts total
- Build momentum: start with awareness, end with conversion
- Consistent brand identity across all posts
- Consider upcoming events and seasonal relevance

╔════════════════════════════════════════════════════════════╗
║ ★ BRAND: {bc.name} | Industry: {bc.industry} | Tone: {bc.tone} ★ ║
╚════════════════════════════════════════════════════════════╝
"""

        last_content = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage) and msg.content:
                last_content = msg.content
                break

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Plan a campaign based on this theme:\n{last_content}"),
        ]

        response = llm.invoke(messages)
        return {"messages": [AIMessage(content=f"[Campaign Plan]\n{response.content}")]}

    return campaign_planner_subgraph
