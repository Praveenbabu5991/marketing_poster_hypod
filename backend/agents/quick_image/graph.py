"""Quick Image Agent — LangGraph StateGraph definition."""

from langchain_core.language_models import BaseChatModel

from agents.base import build_agent_graph
from agents.quick_image.prompts import QUICK_IMAGE_PROMPT
from agents.tools.image_gen import generate_image, edit_image
from agents.tools.caption import write_caption
from agents.tools.hashtag import generate_hashtags
from agents.tools.format_response import format_response
from agents.tools.web_search import search_web, get_trending_topics
from agents.tools.calendar import get_upcoming_events


QUICK_IMAGE_TOOLS = [
    generate_image,
    edit_image,
    write_caption,
    generate_hashtags,
    format_response,
    search_web,
    get_trending_topics,
    get_upcoming_events,
]


def build_quick_image_graph(llm: BaseChatModel):
    """Build the Quick Image agent graph."""
    return build_agent_graph(
        llm=llm,
        tools=QUICK_IMAGE_TOOLS,
        system_prompt=QUICK_IMAGE_PROMPT,
        graph_name="quick_image",
    )
