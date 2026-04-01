"""Product UGC Agent — LangGraph StateGraph definition."""

from langchain_core.language_models import BaseChatModel

from agents.base import build_agent_graph
from agents.product_ugc.prompts import PRODUCT_UGC_PROMPT
from agents.tools.video_gen import generate_video
from agents.tools.caption import write_caption
from agents.tools.hashtag import generate_hashtags
from agents.tools.format_response import format_response


PRODUCT_UGC_TOOLS = [
    generate_video,
    write_caption,
    generate_hashtags,
    format_response,
]


def build_product_ugc_graph(llm: BaseChatModel):
    """Build the Product UGC agent graph."""
    return build_agent_graph(
        llm=llm,
        tools=PRODUCT_UGC_TOOLS,
        system_prompt=PRODUCT_UGC_PROMPT,
        graph_name="product_ugc",
    )
