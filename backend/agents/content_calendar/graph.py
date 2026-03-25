"""Content Calendar Agent — LangGraph StateGraph definition."""

from langchain_core.language_models import BaseChatModel

from agents.base import build_agent_graph
from agents.content_calendar.prompts import CONTENT_CALENDAR_PROMPT
from agents.tools.format_response import format_response
from agents.tools.web_search import search_web, get_trending_topics
from agents.tools.calendar import get_upcoming_events


CONTENT_CALENDAR_TOOLS = [
    format_response,
    search_web,
    get_trending_topics,
    get_upcoming_events,
]


def build_content_calendar_graph(llm: BaseChatModel):
    """Build the Content Calendar agent graph."""
    return build_agent_graph(
        llm=llm,
        tools=CONTENT_CALENDAR_TOOLS,
        system_prompt=CONTENT_CALENDAR_PROMPT,
        graph_name="content_calendar",
    )
