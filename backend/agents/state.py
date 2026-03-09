"""Agent state definition for all LangGraph agent graphs."""

from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """Shared state schema for all agent graphs.

    messages: Full conversation history (managed by add_messages reducer).
    brand_context: Brand identity dict (injected from DB per session).
    generated_assets: Paths to generated images/videos in this session.
    """
    messages: Annotated[list[AnyMessage], add_messages]
    brand_context: dict
    generated_assets: list[dict]
