"""LangGraph astream_events -> SSE adapter.

Transforms LangGraph streaming events into SSE JSON events for the frontend.
"""

import json
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage


async def stream_agent(
    compiled_graph,
    message: str,
    brand_context: dict,
    thread_id: str,
) -> AsyncGenerator[str, None]:
    """Stream agent events as SSE-formatted strings.

    Args:
        compiled_graph: Compiled LangGraph StateGraph with checkpointer.
        message: User's message text.
        brand_context: Brand context dict to inject into state.
        thread_id: LangGraph thread ID for checkpointing.

    Yields:
        SSE event strings: "data: {json}\n\n"
    """
    config = {"configurable": {"thread_id": thread_id}}

    input_state = {
        "messages": [HumanMessage(content=message)],
        "brand_context": brand_context,
        "generated_assets": [],
    }

    last_status_sent = False  # Deduplicate consecutive "Thinking..." events

    try:
        async for event in compiled_graph.astream_events(
            input_state,
            config=config,
            version="v2",
        ):
            kind = event.get("event")

            if kind == "on_chat_model_start":
                node_name = event.get("metadata", {}).get("langgraph_node", "")
                if node_name == "orchestrator" and not last_status_sent:
                    last_status_sent = True
                    yield _sse_event({
                        "type": "status",
                        "message": "Thinking...",
                    })

            elif kind == "on_chat_model_stream":
                # Token-by-token streaming from the orchestrator LLM
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    # Only stream text from the orchestrator node (not sub-agents)
                    node_name = event.get("metadata", {}).get("langgraph_node", "")
                    if node_name == "orchestrator":
                        # Ensure content is a string (Gemini can return list of parts)
                        content = chunk.content
                        if not isinstance(content, str):
                            content = str(content)
                        yield _sse_event({
                            "type": "text",
                            "content": content,
                            "partial": True,
                        })

            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                last_status_sent = False  # Reset so next orchestrator round gets "Thinking..."

                # Skip internal tools that have their own event types
                if tool_name == "format_response":
                    continue

                # Show user-friendly progress message
                messages = {
                    "generate_image": "Creating your image...",
                    "edit_image": "Editing image...",
                    "generate_video": "Generating video (this may take a few minutes)...",
                    "animate_image": "Animating image...",
                    "write_caption": "Writing caption...",
                    "generate_hashtags": "Generating hashtags...",
                    "search_web": "Researching trends...",
                    "get_trending_topics": "Finding trending topics...",
                    "get_upcoming_events": "Checking upcoming events...",
                    "recommend_ideas": "Brainstorming ideas...",
                    "create_prompt": "Crafting image prompt...",
                }
                msg = messages.get(tool_name, f"Running {tool_name}...")

                yield _sse_event({
                    "type": "tool_start",
                    "tool": tool_name,
                    "message": msg,
                })

            elif kind == "on_tool_end":
                tool_name = event.get("name", "")
                output = event.get("data", {}).get("output")

                if tool_name == "format_response" and output:
                    # format_response output -> interactive event
                    content = output
                    if hasattr(output, "content"):
                        content = output.content
                    if isinstance(content, str):
                        try:
                            content = json.loads(content)
                        except (json.JSONDecodeError, TypeError):
                            pass

                    yield _sse_event({
                        "type": "interactive",
                        "content": content,
                    })
                else:
                    yield _sse_event({
                        "type": "tool_end",
                        "tool": tool_name,
                    })

    except Exception as e:
        yield _sse_event({
            "type": "error",
            "content": str(e)[:500],
        })

    yield _sse_event({"type": "done"})


def _sse_event(data: dict) -> str:
    """Format data as an SSE event string."""
    return f"data: {json.dumps(data)}\n\n"
