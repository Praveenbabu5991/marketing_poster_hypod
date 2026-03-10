"""Knowledge and research tools using Gemini API.

Adapted from v2 — wrapped with LangChain @tool decorator.
"""

import time
from datetime import datetime

from langchain_core.tools import tool


def _get_config():
    from app.config import GOOGLE_API_KEY, CAPTION_MODEL
    return GOOGLE_API_KEY, CAPTION_MODEL


def _get_client():
    from google import genai
    api_key, _ = _get_config()
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not configured")
    return genai.Client(api_key=api_key)


def _retry_with_backoff(func, max_retries: int = 4, base_delay: float = 2.0):
    last_error = None
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))
    raise last_error


@tool
def search_web(query: str, context: str = "") -> dict:
    """Search for information about a topic using AI knowledge.

    Args:
        query: Topic or question to research.
        context: Additional context for the query.
    """
    try:
        client = _get_client()
        _, DEFAULT_MODEL = _get_config()
        prompt = f"""Provide helpful information about this topic for social media content creation:

Topic: {query}
{f"Context: {context}" if context else ""}
Current Date: {datetime.now().strftime("%B %d, %Y")}

Focus on: key facts, actionable takeaways, relevant trends."""

        def make_request():
            return client.models.generate_content(model=DEFAULT_MODEL, contents=prompt).text.strip()

        result = _retry_with_backoff(make_request)
        return {"status": "success", "query": query, "insights": result}

    except Exception as e:
        return {
            "status": "error",
            "message": f"Search temporarily unavailable. Use your knowledge of the brand to suggest ideas instead.",
            "query": query,
        }


@tool
def get_trending_topics(
    industry: str,
    platform: str = "instagram",
    region: str = "global",
) -> dict:
    """Get trending topic suggestions for an industry.

    Args:
        industry: Industry or niche to research.
        platform: Social media platform.
        region: Geographic region.
    """
    try:
        client = _get_client()
        _, DEFAULT_MODEL = _get_config()
        current_month = datetime.now().strftime("%B %Y")

        prompt = f"""As a social media strategist, suggest relevant topics for {platform} in the {industry} niche.

Region: {region}
Current Month: {current_month}

Provide:
1. 5 Evergreen Topics - consistently perform well
2. 3 Seasonal Ideas - relevant for {current_month}
3. Popular Content Formats - what works best
4. 10 Relevant Hashtags - mix of popular and niche
5. 3 Specific Post Ideas - actionable content concepts

Be specific and practical."""

        def make_request():
            return client.models.generate_content(model=DEFAULT_MODEL, contents=prompt).text.strip()

        result = _retry_with_backoff(make_request)
        return {
            "status": "success",
            "industry": industry,
            "platform": platform,
            "suggestions": result,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Trend research temporarily unavailable. Use your knowledge of the {industry} industry to suggest ideas instead.",
            "industry": industry,
        }
