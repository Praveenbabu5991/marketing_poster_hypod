"""Hashtag generation tool using Gemini API.

Adapted from v2 — wrapped with LangChain @tool decorator.
"""

import logging
import re
import sys
import time

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _get_config():
    from app.config import GOOGLE_API_KEY, CAPTION_MODEL
    return GOOGLE_API_KEY, CAPTION_MODEL


def _get_client():
    from app.config import get_genai_client
    return get_genai_client()


def _retry_with_backoff(func, max_retries: int = 3, base_delay: float = 2.0):
    """Simple retry with backoff — no thread pool, just direct calls."""
    last_error = None
    for attempt in range(max_retries):
        try:
            print(f"[HASHTAG] Attempt {attempt+1}/{max_retries} starting...", file=sys.stderr, flush=True)
            result = func()
            print(f"[HASHTAG] Attempt {attempt+1} succeeded", file=sys.stderr, flush=True)
            return result
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            if "not found" in error_str and "model" in error_str:
                raise
            if "api" in error_str and "key" in error_str:
                raise
            print(f"[HASHTAG] Attempt {attempt+1} failed: {str(e)[:200]}", file=sys.stderr, flush=True)
        if attempt < max_retries - 1:
            delay = base_delay * (2 ** attempt)
            print(f"[HASHTAG] Retrying in {delay:.0f}s...", file=sys.stderr, flush=True)
            time.sleep(delay)
    raise last_error


@tool
def generate_hashtags(
    topic: str,
    industry: str = "",
    brand_name: str = "",
    count: int = 10,
) -> dict:
    """Generate strategic hashtags for a social media post.

    Args:
        topic: What the post is about.
        industry: Brand's industry/niche.
        brand_name: Brand name for branded hashtag.
        count: Number of hashtags to generate (2-15).
    """
    count = max(2, min(15, count))

    try:
        client = _get_client()
        _, CAPTION_MODEL = _get_config()
        from google.genai import types

        prompt = f"""Generate exactly {count} strategic Instagram hashtags for a post about: {topic}

{f"Industry: {industry}" if industry else ""}
{f"Brand: {brand_name}" if brand_name else ""}

Requirements:
- Mix of high-volume (>100K posts) and niche hashtags
- All relevant to the topic and industry
- Include 1-2 trending hashtags if applicable
{f"- Include #{brand_name.replace(' ', '')} as a branded hashtag" if brand_name else ""}
- No banned or spammy hashtags

Output ONLY the hashtags, one per line, each starting with #. No explanations."""

        def make_request():
            return client.models.generate_content(
                model=CAPTION_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.7),
            )

        response = _retry_with_backoff(make_request)
        raw = response.text.strip()

        # Extract usage metadata for cost tracking
        usage_meta = getattr(response, "usage_metadata", None)
        token_info = {}
        if usage_meta:
            token_info["prompt_tokens"] = getattr(usage_meta, "prompt_token_count", 0) or 0
            token_info["completion_tokens"] = getattr(usage_meta, "candidates_token_count", 0) or 0

        hashtags = []
        seen = set()
        for line in raw.split("\n"):
            line = line.strip()
            tags = re.findall(r"#\w+", line)
            for tag in tags:
                tag_lower = tag.lower()
                if tag_lower not in seen:
                    seen.add(tag_lower)
                    hashtags.append(tag)

        if not hashtags:
            hashtags = [f"#{topic.replace(' ', '')}", f"#{industry.replace(' ', '')}"]

        return {
            "status": "success",
            "hashtags": hashtags[:count],
            "hashtag_string": " ".join(hashtags[:count]),
            "count": len(hashtags[:count]),
            "model": CAPTION_MODEL,
            **token_info,
        }

    except Exception as e:
        print(f"[HASHTAG] FINAL ERROR: {str(e)[:300]}", file=sys.stderr, flush=True)
        return {"status": "error", "message": f"Hashtag generation failed: {str(e)[:200]}", "model": _get_config()[1]}
