"""Product Video Agent — LangGraph StateGraph definition."""

from langchain_core.language_models import BaseChatModel

from agents.base import build_agent_graph
from agents.product_video.prompts import PRODUCT_VIDEO_PROMPT
from agents.tools.video_gen import generate_video
from agents.tools.caption import write_caption
from agents.tools.hashtag import generate_hashtags
from agents.tools.format_response import format_response


PRODUCT_VIDEO_TOOLS = [
    generate_video,
    write_caption,
    generate_hashtags,
    format_response,
]


def build_product_video_graph(llm: BaseChatModel):
    """Build the Product Video agent graph."""
    return build_agent_graph(
        llm=llm,
        tools=PRODUCT_VIDEO_TOOLS,
        system_prompt=PRODUCT_VIDEO_PROMPT,
        graph_name="product_video",
    )
