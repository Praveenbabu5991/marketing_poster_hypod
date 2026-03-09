"""Product Video Agent — LangGraph StateGraph definition."""

from langchain_core.language_models import BaseChatModel

from agents.base import build_agent_graph
from agents.product_video.prompts import PRODUCT_VIDEO_PROMPT
from agents.tools.video_gen import generate_video
from agents.tools.caption import write_caption
from agents.tools.hashtag import generate_hashtags
from agents.tools.format_response import format_response
from agents.tools.web_search import search_web, get_trending_topics
from agents.tools.calendar import get_upcoming_events


PRODUCT_VIDEO_TOOLS = [
    generate_video,
    write_caption,
    generate_hashtags,
    format_response,
    search_web,
    get_trending_topics,
    get_upcoming_events,
]


def build_product_video_graph(llm: BaseChatModel):
    """Build the Product Video agent graph."""
    return build_agent_graph(
        llm=llm,
        tools=PRODUCT_VIDEO_TOOLS,
        system_prompt=PRODUCT_VIDEO_PROMPT,
        graph_name="product_video",
    )
