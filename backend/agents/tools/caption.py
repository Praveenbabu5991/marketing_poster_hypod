"""Caption writing tools using Gemini API.

Adapted from v2 — wrapped with LangChain @tool decorator.
"""

import concurrent.futures
import logging
import time

from langchain_core.tools import tool

logger = logging.getLogger(__name__)
_REQUEST_TIMEOUT = 30


def _get_config():
    from app.config import GOOGLE_API_KEY, CAPTION_MODEL
    return GOOGLE_API_KEY, CAPTION_MODEL


def _get_client():
    from google import genai
    api_key, _ = _get_config()
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not configured")
    return genai.Client(api_key=api_key)


def _retry_with_backoff(func, max_retries: int = 3, base_delay: float = 1.0):
    last_error = None
    for attempt in range(max_retries):
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(func)
                return future.result(timeout=_REQUEST_TIMEOUT)
        except concurrent.futures.TimeoutError:
            last_error = TimeoutError(f"Request timed out after {_REQUEST_TIMEOUT}s")
            logger.warning("[CAPTION] Attempt %d timed out", attempt + 1)
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            if "not found" in error_str and "model" in error_str:
                raise
            if "api" in error_str and "key" in error_str:
                raise
            logger.warning("[CAPTION] Attempt %d failed: %s", attempt + 1, str(e)[:200])
        if attempt < max_retries - 1:
            delay = base_delay * (2 ** attempt)
            time.sleep(delay)
    raise last_error


@tool
def write_caption(
    topic: str,
    brand_name: str = "",
    brand_tone: str = "engaging",
    platform: str = "Instagram",
    target_audience: str = "",
    include_cta: bool = True,
    emoji_level: str = "moderate",
) -> dict:
    """Generate an engaging social media caption.

    Args:
        topic: What the post is about.
        brand_name: Brand/company name.
        brand_tone: Tone of voice (engaging, professional, playful, inspirational).
        platform: Social media platform (Instagram, Facebook, LinkedIn, Twitter).
        target_audience: Description of target audience.
        include_cta: Whether to include a call-to-action.
        emoji_level: How many emojis (none, minimal, moderate, heavy).
    """
    try:
        client = _get_client()
        _, CAPTION_MODEL = _get_config()
        from google.genai import types

        prompt = f"""Write a {brand_tone} {platform} caption about: {topic}

Requirements:
- 50-150 words
- Hook in first line (attention-grabbing)
- Value in the body (inform, entertain, or inspire)
{f"- Include a call-to-action" if include_cta else ""}
- Emoji usage: {emoji_level}
{f"- Brand voice: {brand_name}" if brand_name else ""}
{f"- Speak to: {target_audience}" if target_audience else ""}

Output ONLY the caption text. No labels, no quotes, no explanation."""

        def make_request():
            return client.models.generate_content(
                model=CAPTION_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.8),
            )

        response = _retry_with_backoff(make_request)
        caption = response.text.strip().strip('"').strip("'")

        return {
            "status": "success",
            "caption": caption,
            "platform": platform,
            "tone": brand_tone,
        }

    except Exception as e:
        return {"status": "error", "message": f"Caption generation failed: {str(e)[:200]}"}


@tool
def improve_caption(
    caption: str,
    feedback: str,
    preserve_tone: bool = True,
) -> dict:
    """Refine an existing caption based on feedback.

    Args:
        caption: The current caption text.
        feedback: What to change or improve.
        preserve_tone: Whether to keep the original tone.
    """
    try:
        client = _get_client()
        _, CAPTION_MODEL = _get_config()
        from google.genai import types

        prompt = f"""Improve this social media caption based on the feedback:

CURRENT CAPTION:
{caption}

FEEDBACK:
{feedback}

{"Keep the same tone and style." if preserve_tone else ""}
Output ONLY the improved caption. No explanation."""

        def make_request():
            return client.models.generate_content(
                model=CAPTION_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.7),
            )

        response = _retry_with_backoff(make_request)
        improved = response.text.strip().strip('"').strip("'")

        return {"status": "success", "caption": improved, "feedback_applied": feedback}

    except Exception as e:
        return {"status": "error", "message": f"Caption improvement failed: {str(e)[:200]}"}
