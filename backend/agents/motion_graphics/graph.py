"""Motion Graphics Agent — LangGraph StateGraph definition."""

from langchain_core.language_models import BaseChatModel

from agents.base import build_agent_graph
from agents.motion_graphics.prompts import MOTION_GRAPHICS_PROMPT
from agents.tools.video_gen import generate_video
from agents.tools.caption import write_caption
from agents.tools.hashtag import generate_hashtags
from agents.tools.format_response import format_response
from agents.tools.web_search import search_web, get_trending_topics
from agents.tools.calendar import get_upcoming_events


MOTION_GRAPHICS_TOOLS = [
    generate_video,
    write_caption,
    generate_hashtags,
    format_response,
    search_web,
    get_trending_topics,
    get_upcoming_events,
]


def build_motion_graphics_graph(llm: BaseChatModel):
    """Build the Motion Graphics agent graph."""
    return build_agent_graph(
        llm=llm,
        tools=MOTION_GRAPHICS_TOOLS,
        system_prompt=MOTION_GRAPHICS_PROMPT,
        graph_name="motion_graphics",
    )
