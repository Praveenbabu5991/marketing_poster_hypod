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
    from app.config import get_genai_client
    return get_genai_client()


def _retry_with_backoff(func, max_retries: int = 5, base_delay: float = 5.0):
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
            logger.warning("[CAPTION] Retrying in %.0fs...", delay)
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
    content_style: str = "default",
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
        content_style: Caption style per agent type. Options:
            "ugc" — Personal, testimonial-style. First 2 lines are the hook, then "Read more..." to encourage tap. Conversational, relatable.
            "creative_ad" — Creative ad copy. Punchy, brand-focused, cinematic feel. Aspirational and bold.
            "motion_graphics" — Premium product showcase. Professional, clean, highlight product features and craftsmanship.
            "default" — General engaging caption.
    """
    try:
        client = _get_client()
        _, CAPTION_MODEL = _get_config()
        from google.genai import types

        # Agent-specific style instructions
        style_instructions = ""
        if content_style == "ugc":
            style_instructions = """- Write as if a REAL PERSON is sharing their experience (testimonial style)
- First 2 lines: strong hook that stops the scroll
- After the hook, add a line break then "...Read more" or "..." to encourage tap-to-expand
- Body: personal, conversational, relatable — like talking to a friend
- Use first person ("I", "my") naturally"""
        elif content_style == "creative_ad":
            style_instructions = """- Write like a CREATIVE AD — punchy, cinematic, aspirational
- Bold opening statement that captures the brand's vision
- Short, impactful sentences — like ad copy, not a blog post
- Build desire and emotion, not just information
- End with a powerful brand statement or CTA"""
        elif content_style == "motion_graphics":
            style_instructions = """- Write for a PREMIUM PRODUCT SHOWCASE — professional and clean
- Highlight product features, craftsmanship, and quality
- Sophisticated tone — like a luxury brand's social media
- Focus on what makes the product special
- Minimal emojis, maximum elegance"""

        prompt = f"""Write a {brand_tone} {platform} caption about: {topic}

Requirements:
- 50-150 words
- Hook in first line (attention-grabbing)
- Value in the body (inform, entertain, or inspire)
{f"- Include a call-to-action" if include_cta else ""}
- Emoji usage: {emoji_level}
{f"- Brand voice: {brand_name}" if brand_name else ""}
{f"- Speak to: {target_audience}" if target_audience else ""}
{style_instructions}

Output ONLY the caption text. No labels, no quotes, no explanation."""

        def make_request():
            return client.models.generate_content(
                model=CAPTION_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.8),
            )

        response = _retry_with_backoff(make_request)
        caption = response.text.strip().strip('"').strip("'")

        # Extract usage metadata for cost tracking
        usage_meta = getattr(response, "usage_metadata", None)
        token_info = {}
        if usage_meta:
            token_info["prompt_tokens"] = getattr(usage_meta, "prompt_token_count", 0) or 0
            token_info["completion_tokens"] = getattr(usage_meta, "candidates_token_count", 0) or 0

        return {
            "status": "success",
            "caption": caption,
            "platform": platform,
            "tone": brand_tone,
            "model": CAPTION_MODEL,
            **token_info,
        }

    except Exception as e:
        return {"status": "error", "message": f"Caption generation failed: {str(e)[:200]}", "model": _get_config()[1]}


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

        # Extract usage metadata for cost tracking
        usage_meta = getattr(response, "usage_metadata", None)
        token_info = {}
        if usage_meta:
            token_info["prompt_tokens"] = getattr(usage_meta, "prompt_token_count", 0) or 0
            token_info["completion_tokens"] = getattr(usage_meta, "candidates_token_count", 0) or 0

        return {"status": "success", "caption": improved, "feedback_applied": feedback, "model": CAPTION_MODEL, **token_info}

    except Exception as e:
        return {"status": "error", "message": f"Caption improvement failed: {str(e)[:200]}", "model": _get_config()[1]}
