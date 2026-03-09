"""Idea Recommender sub-agent graph builder.

Creates a mini StateGraph that researches trends and suggests 3 content ideas.
Invoked as a node by parent orchestrators, NOT as a tool.
"""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from agents.state import AgentState
from agents.tools.web_search import search_web, get_trending_topics
from agents.tools.calendar import get_upcoming_events
from brand.context import BrandContext


IDEA_TOOLS = [search_web, get_trending_topics, get_upcoming_events]


def _build_idea_prompt(content_type: str, brand_context: dict) -> str:
    bc = BrandContext.from_dict(brand_context)
    return f"""## ROLE
You are a content strategist specializing in {content_type} creation.

## WORKFLOW
1. RESEARCH: Use search_web and get_trending_topics to find current trends
   relevant to the brand's industry and target audience.
2. CHECK CALENDAR: Use get_upcoming_events to find relevant upcoming events.
3. ANALYZE: Cross-reference trends with brand context.
4. SUGGEST: Output exactly 3 unique content ideas.

## OUTPUT FORMAT
For each idea provide:
- **Title**: 3-5 word catchy name
- **Description**: 2-3 sentences describing the visual concept
- **Why it works**: 1 sentence connecting to this brand/audience

## RULES
- Always research before suggesting. Do NOT make up trends.
- All 3 ideas must be distinct approaches.
- Tailor ideas to the brand's industry, audience, and tone.
- If an upcoming event is relevant, include it in at least one idea.
- After outputting 3 ideas, STOP. Do not call any more tools.

╔════════════════════════════════════════════════════════════╗
║ ★ BRAND IDENTITY — TAILOR ALL IDEAS TO THIS BRAND ★       ║
║                                                            ║
║ {bc.to_prompt_text()}
║                                                            ║
║ → Suggest ideas that resonate with this audience           ║
║ → Match the brand's tone in idea descriptions              ║
║ → Consider industry trends specific to this brand          ║
╚════════════════════════════════════════════════════════════╝
"""


def build_idea_recommender_node(llm: BaseChatModel, content_type: str):
    """Build an idea recommender callable for use as a graph node.

    The returned function takes AgentState and returns a dict with messages
    containing the idea recommender's output.
    """
    llm_with_tools = llm.bind_tools(IDEA_TOOLS)
    tool_node = ToolNode(IDEA_TOOLS)

    def idea_recommender_subgraph(state: AgentState) -> dict:
        """Run the idea recommender as a synchronous sub-computation."""
        brand_context = state.get("brand_context", {})
        system_prompt = _build_idea_prompt(content_type, brand_context)

        # Get the user's request from the last human message
        user_request = ""
        for msg in reversed(state["messages"]):
            if hasattr(msg, "type") and msg.type == "human":
                user_request = msg.content
                break

        messages = [SystemMessage(content=system_prompt)]
        if user_request:
            from langchain_core.messages import HumanMessage
            messages.append(HumanMessage(content=f"Find content ideas for: {user_request}"))

        # Run LLM loop (max 5 iterations to prevent runaway)
        for _ in range(5):
            response = llm_with_tools.invoke(messages)
            messages.append(response)

            if not response.tool_calls:
                break

            # Execute tools
            tool_results = tool_node.invoke({"messages": messages})
            messages.extend(tool_results["messages"])

        # Return the final text as an AI message
        final_text = messages[-1].content if isinstance(messages[-1], AIMessage) else ""
        return {"messages": [AIMessage(content=f"[Idea Recommender Results]\n{final_text}")]}

    return idea_recommender_subgraph
