"""Base agent graph builder.

Builds a LangGraph StateGraph with:
- orchestrator node (LLM with system prompt + brand context)
- tools node (ToolNode with agent-specific tools)
- conditional routing: format_response -> END, tool_calls -> tools, else -> END

This is the core architecture that prevents the infinite looping problem:
format_response always routes to END, forcing the agent to stop and wait for user input.
"""

import sys
import time
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from agents.state import AgentState
from brand.context import BrandContext


def _build_system_message(prompt_template: str, brand_context: dict) -> str:
    """Inject brand context into the prompt template."""
    bc = BrandContext.from_dict(brand_context)
    brand_text = bc.to_prompt_text()
    result = prompt_template.replace("{brand_context}", brand_text)
    result = result.replace("{max_posts_per_month}", str(bc.max_posts_per_month))
    return result


def build_agent_graph(
    *,
    llm: BaseChatModel,
    tools: list[BaseTool],
    system_prompt: str,
    sub_agent_nodes: dict[str, callable] | None = None,
    graph_name: str = "agent",
) -> StateGraph:
    """Build a LangGraph StateGraph for an agent.

    Args:
        llm: The chat model to use for the orchestrator.
        tools: List of LangChain tools available to the orchestrator.
        system_prompt: System prompt template with {brand_context} placeholder.
        sub_agent_nodes: Optional dict of node_name -> callable(state) for sub-agents.
        graph_name: Name for the graph (for tracing).

    Returns:
        Compiled StateGraph.
    """
    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools)

    # -- Orchestrator node --
    def orchestrator(state: AgentState) -> dict:
        brand_ctx = state.get("brand_context", {})
        system_msg = _build_system_message(system_prompt, brand_ctx)
        messages = [SystemMessage(content=system_msg)] + state["messages"]

        # Debug: log brand context summary
        product_imgs = brand_ctx.get("product_images", [])
        brand_name = brand_ctx.get("name", "?")
        brand_products = brand_ctx.get("products_services", "")
        print(f"[ORCH] brand='{brand_name}' products_services='{brand_products}' product_images={len(product_imgs)} imgs={product_imgs}", file=sys.stderr, flush=True)

        # Retry on empty responses — Gemini sometimes returns empty content
        # with no tool calls, likely due to rate limiting after tool API calls.
        max_retries = 4
        for attempt in range(max_retries):
            if attempt > 0:
                # Exponential backoff: 2s, 4s, 8s
                delay = 2 ** attempt
                print(f"[ORCH] attempt={attempt+1}/{max_retries} retrying after {delay}s...", file=sys.stderr, flush=True)
                time.sleep(delay)
            response = llm_with_tools.invoke(messages)
            # Gemini can return content as a list of parts — normalize to string
            if isinstance(response.content, list):
                text_parts = []
                for part in response.content:
                    if isinstance(part, str):
                        text_parts.append(part)
                    elif isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                response.content = "".join(text_parts)
            has_content = bool(response.content and response.content.strip())
            has_tools = bool(response.tool_calls) if hasattr(response, 'tool_calls') else False
            if has_content or has_tools:
                tool_names = [tc["name"] for tc in (response.tool_calls or [])]
                print(f"[ORCH] attempt={attempt+1} msgs={len(messages)} content='{(response.content or '')[:80]}' tools={has_tools} tool_names={tool_names}", file=sys.stderr, flush=True)
                break
            # Log raw response details to debug why Gemini returns empty
            resp_meta = {}
            if hasattr(response, 'response_metadata'):
                resp_meta = response.response_metadata
            print(f"[ORCH] attempt={attempt+1}/{max_retries} EMPTY response content_type={type(response.content).__name__} content_repr={repr(response.content)[:200]} meta={resp_meta}", file=sys.stderr, flush=True)
        else:
            print(f"[ORCH] ALL {max_retries} retries returned empty!", file=sys.stderr, flush=True)
        return {"messages": [response]}

    # -- Route decision after orchestrator --
    def route_after_orchestrator(state: AgentState) -> Literal["tools", "__end__"]:
        last_message = state["messages"][-1]
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return END

        return "tools"

    # -- Route decision after tools --
    def route_after_tools(state: AgentState) -> Literal["orchestrator", "__end__"]:
        """After tools execute, check if the tool that ran was format_response.
        If so, route to END. Otherwise, route back to orchestrator.

        Important: Only check the AIMessage immediately before the latest batch
        of ToolMessages. Previous turns may also contain format_response calls
        from earlier interactions — those must be ignored.
        """
        # Walk backwards: skip ToolMessages to find the triggering AIMessage
        messages = state["messages"]
        found_tool_msg = False
        for msg in reversed(messages):
            if hasattr(msg, "tool_call_id"):  # ToolMessage
                found_tool_msg = True
                continue
            if found_tool_msg and isinstance(msg, AIMessage) and msg.tool_calls:
                # This is the AIMessage that triggered the current tool batch
                for tc in msg.tool_calls:
                    if tc["name"] == "format_response":
                        return END
                return "orchestrator"
        return "orchestrator"

    # -- Custom tools node that auto-injects product images into generate_image --
    tool_node = ToolNode(tools)

    # Only these agents should have product images auto-injected
    _PRODUCT_IMAGE_AGENTS = {"sales_poster", "product_video"}

    def tools_with_injection(state: AgentState) -> dict:
        """Wrap ToolNode to inject product images from brand context.

        Only applies to sales_poster and product_video agents.
        Other agents (single_post, campaign, carousel, etc.) should NOT
        get product images injected — they generate original creative content.
        """
        brand_ctx = state.get("brand_context", {})
        product_images = brand_ctx.get("product_images", [])

        if product_images and graph_name in _PRODUCT_IMAGE_AGENTS:
            # Mutate the last AIMessage's tool_calls to inject user_images
            messages = list(state["messages"])
            last_ai = messages[-1] if messages and isinstance(messages[-1], AIMessage) else None
            if last_ai and last_ai.tool_calls:
                for tc in last_ai.tool_calls:
                    if tc["name"] == "generate_image":
                        args = tc["args"]
                        # Only inject if LLM didn't provide user_images
                        if not args.get("user_images"):
                            args["user_images"] = ", ".join(product_images)
                            print(f"[TOOLS] Auto-injected user_images into generate_image: {args['user_images']}", file=sys.stderr, flush=True)
                        if not args.get("user_image_instructions"):
                            args["user_image_instructions"] = "Feature this product prominently as the visual anchor of the poster"
                    elif tc["name"] == "generate_video":
                        args = tc["args"]
                        print(f"[TOOLS] generate_video args BEFORE injection: reference_image_paths='{args.get('reference_image_paths', '')}' logo_path='{args.get('logo_path', '')}' image_path='{args.get('image_path', '')}'", file=sys.stderr, flush=True)
                        if not args.get("reference_image_paths"):
                            args["reference_image_paths"] = ", ".join(product_images)
                            print(f"[TOOLS] Auto-injected reference_image_paths into generate_video: {args['reference_image_paths']}", file=sys.stderr, flush=True)
                        else:
                            print(f"[TOOLS] LLM already set reference_image_paths, skipping injection", file=sys.stderr, flush=True)

        return tool_node.invoke(state)

    # -- Build graph --
    graph = StateGraph(AgentState)

    graph.add_node("orchestrator", orchestrator)
    graph.add_node("tools", tools_with_injection)

    # Add sub-agent nodes if provided
    if sub_agent_nodes:
        for node_name, node_fn in sub_agent_nodes.items():
            graph.add_node(node_name, node_fn)

    graph.set_entry_point("orchestrator")

    graph.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        {"tools": "tools", END: END},
    )

    graph.add_conditional_edges(
        "tools",
        route_after_tools,
        {"orchestrator": "orchestrator", END: END},
    )

    return graph
