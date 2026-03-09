"""Sales Poster Agent — LangGraph StateGraph definition."""

from langchain_core.language_models import BaseChatModel

from agents.base import build_agent_graph
from agents.sales_poster.prompts import SALES_POSTER_PROMPT
from agents.tools.image_gen import generate_image, edit_image
from agents.tools.caption import write_caption
from agents.tools.hashtag import generate_hashtags
from agents.tools.format_response import format_response


SALES_POSTER_TOOLS = [
    generate_image,
    edit_image,
    write_caption,
    generate_hashtags,
    format_response,
]


def build_sales_poster_graph(llm: BaseChatModel):
    """Build the Sales Poster agent graph."""
    return build_agent_graph(
        llm=llm,
        tools=SALES_POSTER_TOOLS,
        system_prompt=SALES_POSTER_PROMPT,
        graph_name="sales_poster",
    )
