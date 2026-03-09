"""Single Post Agent — LangGraph StateGraph definition."""

from langchain_core.language_models import BaseChatModel

from agents.base import build_agent_graph
from agents.single_post.prompts import SINGLE_POST_PROMPT
from agents.tools.image_gen import generate_image, edit_image
from agents.tools.caption import write_caption
from agents.tools.hashtag import generate_hashtags
from agents.tools.animate_image import animate_image
from agents.tools.format_response import format_response
from agents.tools.web_search import search_web, get_trending_topics
from agents.tools.calendar import get_upcoming_events


SINGLE_POST_TOOLS = [
    generate_image,
    edit_image,
    write_caption,
    generate_hashtags,
    animate_image,
    format_response,
    search_web,
    get_trending_topics,
    get_upcoming_events,
]


def build_single_post_graph(llm: BaseChatModel):
    """Build the Single Post agent graph."""
    return build_agent_graph(
        llm=llm,
        tools=SINGLE_POST_TOOLS,
        system_prompt=SINGLE_POST_PROMPT,
        graph_name="single_post",
    )
