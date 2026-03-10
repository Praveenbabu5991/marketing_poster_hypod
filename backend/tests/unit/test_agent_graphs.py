"""Tests that each of the 7 agent graphs builds correctly."""

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage


def _make_mock_llm():
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.invoke = MagicMock(return_value=AIMessage(content="test"))
    return llm


class TestAgentGraphs:

    def test_single_post_graph_builds(self):
        from agents.single_post.graph import build_single_post_graph
        graph = build_single_post_graph(_make_mock_llm())
        assert graph is not None
        compiled = graph.compile()
        assert compiled is not None

    def test_carousel_graph_builds(self):
        from agents.carousel.graph import build_carousel_graph
        graph = build_carousel_graph(_make_mock_llm())
        assert graph is not None
        compiled = graph.compile()
        assert compiled is not None

    def test_campaign_graph_builds(self):
        from agents.campaign.graph import build_campaign_graph
        graph = build_campaign_graph(_make_mock_llm())
        assert graph is not None
        compiled = graph.compile()
        assert compiled is not None

    def test_sales_poster_graph_builds(self):
        from agents.sales_poster.graph import build_sales_poster_graph
        graph = build_sales_poster_graph(_make_mock_llm())
        assert graph is not None
        compiled = graph.compile()
        assert compiled is not None

    def test_motion_graphics_graph_builds(self):
        from agents.motion_graphics.graph import build_motion_graphics_graph
        graph = build_motion_graphics_graph(_make_mock_llm())
        assert graph is not None
        compiled = graph.compile()
        assert compiled is not None

    def test_product_video_graph_builds(self):
        from agents.product_video.graph import build_product_video_graph
        graph = build_product_video_graph(_make_mock_llm())
        assert graph is not None
        compiled = graph.compile()
        assert compiled is not None

    def test_quick_image_graph_builds(self):
        from agents.quick_image.graph import build_quick_image_graph
        graph = build_quick_image_graph(_make_mock_llm())
        assert graph is not None
        compiled = graph.compile()
        assert compiled is not None


class TestAgentRegistry:

    def test_agent_configs_has_seven_agents(self):
        from agents.registry import AGENT_CONFIGS
        assert len(AGENT_CONFIGS) == 7
        assert "single_post" in AGENT_CONFIGS
        assert "carousel" in AGENT_CONFIGS
        assert "campaign" in AGENT_CONFIGS
        assert "sales_poster" in AGENT_CONFIGS
        assert "motion_graphics" in AGENT_CONFIGS
        assert "product_video" in AGENT_CONFIGS
        assert "quick_image" in AGENT_CONFIGS

    def test_product_agents_require_product_images(self):
        from agents.registry import AGENT_CONFIGS
        assert AGENT_CONFIGS["sales_poster"]["requires_product_images"] is True
        assert AGENT_CONFIGS["product_video"]["requires_product_images"] is True
        assert AGENT_CONFIGS["single_post"]["requires_product_images"] is False
