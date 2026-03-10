"""Agent registry: metadata and lazy graph creation."""

from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langgraph.graph import StateGraph

from app.config import ORCHESTRATOR_MODEL


AGENT_CONFIGS = {
    "single_post": {
        "name": "Single Post",
        "description": "Create a branded social media post with image, caption, and hashtags",
        "icon": "image",
        "requires_product_images": False,
    },
    "carousel": {
        "name": "Carousel",
        "description": "Create a multi-slide Instagram carousel with consistent branding",
        "icon": "layers",
        "requires_product_images": False,
    },
    "campaign": {
        "name": "Campaign",
        "description": "Plan and create a multi-week social media campaign",
        "icon": "calendar",
        "requires_product_images": False,
    },
    "sales_poster": {
        "name": "Sales Poster",
        "description": "Create product sales posters with pricing and CTAs",
        "icon": "tag",
        "requires_product_images": True,
    },
    "motion_graphics": {
        "name": "Motion Graphics",
        "description": "Create short branded motion graphics videos",
        "icon": "film",
        "requires_product_images": False,
    },
    "product_video": {
        "name": "Product Video",
        "description": "Create product showcase videos from product images",
        "icon": "video",
        "requires_product_images": True,
    },
    "quick_image": {
        "name": "Quick Image",
        "description": "Generate images instantly from a description — no approval steps",
        "icon": "zap",
        "requires_product_images": False,
    },
}


def _parse_model_string(model_string: str) -> tuple[str, str]:
    """Parse 'provider/model-name' into (model, provider)."""
    if "/" in model_string:
        provider, model = model_string.split("/", 1)
        return model, provider
    return model_string, ""


def _get_llm() -> BaseChatModel:
    """Create the orchestrator LLM from config."""
    from langchain.chat_models import init_chat_model
    model, provider = _parse_model_string(ORCHESTRATOR_MODEL)
    if provider:
        return init_chat_model(model, model_provider=provider)
    return init_chat_model(model)


def get_agent_graph(agent_type: str) -> StateGraph:
    """Get the uncompiled StateGraph for an agent type.

    The graph is compiled with a checkpointer at runtime (per session).
    """
    if agent_type not in AGENT_CONFIGS:
        raise ValueError(f"Unknown agent type: {agent_type}")

    llm = _get_llm()

    if agent_type == "single_post":
        from agents.single_post.graph import build_single_post_graph
        return build_single_post_graph(llm)
    elif agent_type == "carousel":
        from agents.carousel.graph import build_carousel_graph
        return build_carousel_graph(llm)
    elif agent_type == "campaign":
        from agents.campaign.graph import build_campaign_graph
        return build_campaign_graph(llm)
    elif agent_type == "sales_poster":
        from agents.sales_poster.graph import build_sales_poster_graph
        return build_sales_poster_graph(llm)
    elif agent_type == "motion_graphics":
        from agents.motion_graphics.graph import build_motion_graphics_graph
        return build_motion_graphics_graph(llm)
    elif agent_type == "product_video":
        from agents.product_video.graph import build_product_video_graph
        return build_product_video_graph(llm)
    elif agent_type == "quick_image":
        from agents.quick_image.graph import build_quick_image_graph
        return build_quick_image_graph(llm)
    else:
        raise ValueError(f"Unknown agent type: {agent_type}")
