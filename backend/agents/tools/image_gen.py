"""Image generation tools using Gemini API.

Adapted from v2 — wrapped with LangChain @tool decorator.
"""

import os
import io
import uuid
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool
from PIL import Image


def _get_config():
    from app.config import GOOGLE_API_KEY, IMAGE_MODEL, EDIT_MODEL, GENERATED_DIR
    return GOOGLE_API_KEY, IMAGE_MODEL, EDIT_MODEL, GENERATED_DIR


def _get_client():
    from google import genai
    api_key, _, _, _ = _get_config()
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not configured")
    return genai.Client(api_key=api_key)


def _retry_with_backoff(func, max_retries: int = 3, base_delay: float = 2.0):
    """Execute with exponential backoff. Only skip retry for unrecoverable errors."""
    last_error = None
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            if "not found" in error_str and "model" in error_str:
                raise
            if "api" in error_str and "key" in error_str:
                raise
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
    raise last_error


def _format_error(error: Exception, context: str = "") -> dict:
    error_str = str(error).lower()
    if "quota" in error_str or "rate" in error_str:
        message = "Image generation service is busy. Please wait and try again."
    elif "safety" in error_str or "blocked" in error_str:
        message = "Image couldn't be generated due to content guidelines. Try adjusting your prompt."
    elif "api" in error_str and "key" in error_str:
        message = "API configuration issue. Please contact support."
    else:
        message = f"Image generation failed. {context}" if context else "Image generation failed."
    return {"status": "error", "message": message}


@tool
def generate_image(
    prompt: str,
    brand_name: str = "",
    brand_colors: str = "",
    logo_path: str = "",
    style: str = "creative",
    industry: str = "",
    occasion: str = "",
    headline_text: str = "",
    subtext: str = "",
    cta_text: str = "",
    user_images: str = "",
    user_image_instructions: str = "",
    output_dir: str = "",
) -> dict:
    """Generate a social media post image using Gemini.

    Args:
        prompt: Visual concept description.
        brand_name: Brand/company name.
        brand_colors: Comma-separated hex color codes.
        logo_path: Path to brand logo to incorporate.
        style: Visual style (creative, professional, playful, minimal, bold).
        industry: Brand industry/niche.
        occasion: Special occasion/event theme.
        headline_text: Main headline text for the image.
        subtext: Supporting tagline text.
        cta_text: Call-to-action text.
        user_images: Comma-separated paths to user-uploaded images.
        user_image_instructions: How to use user images.
        output_dir: Directory to save image.
    """
    _, IMAGE_MODEL, _, GENERATED_DIR = _get_config()
    save_dir = output_dir or str(GENERATED_DIR)

    try:
        client = _get_client()

        colors_list = [c.strip() for c in brand_colors.split(",") if c.strip()] if brand_colors else []
        primary_color = colors_list[0] if colors_list else "#000000"

        color_section = ""
        if colors_list:
            color_section = f"""
COLOR PALETTE (MUST USE PROMINENTLY):
- PRIMARY: {primary_color} — dominant color in the image
- SECONDARY: {', '.join(colors_list[1:4])}
- Overall color mood must reflect {primary_color}
"""

        style_map = {
            "creative": "Artistic, imaginative, visually striking",
            "professional": "Clean, corporate, polished",
            "playful": "Fun, vibrant, energetic",
            "minimal": "Simple, clean, focused",
            "bold": "Strong, impactful, attention-grabbing",
        }
        style_desc = style_map.get(style, style_map["creative"])

        text_elements = []
        if headline_text:
            text_elements.append(f'Main headline (prominent): "{headline_text}"')
        if subtext:
            text_elements.append(f'Supporting text (smaller): "{subtext}"')
        if cta_text:
            text_elements.append(f'Call-to-action (button or highlighted): "{cta_text}"')

        text_section = ""
        if text_elements:
            text_section = f"""
EXACT TEXT ON IMAGE:
{chr(10).join(f"- {t}" for t in text_elements)}
Display ONLY the text in quotes. Make it legible with good contrast.
"""

        full_prompt = f"""Create a premium Instagram post image for {brand_name or 'a brand'}.

VISUAL CONCEPT: {prompt}

BRAND: {brand_name or 'Brand'} | Industry: {industry or 'General'}
{color_section}
STYLE: {style_desc}
{f"OCCASION: {occasion}" if occasion else ""}
{text_section}

CRITICAL: Image MUST prominently feature {primary_color}.
Aspect ratio: 4:5 (Instagram optimal). Ultra high resolution.
{f"Include {brand_name} logo subtly in bottom-right corner." if logo_path else ""}
Create a scroll-stopping, magazine-quality image."""

        from google.genai import types

        contents = [full_prompt]

        if logo_path and os.path.exists(logo_path):
            try:
                contents.append(Image.open(logo_path))
            except Exception:
                pass

        if user_images:
            for user_img_path in [p.strip() for p in user_images.split(",") if p.strip()][:5]:
                if os.path.exists(user_img_path):
                    try:
                        contents.append(Image.open(user_img_path))
                    except Exception:
                        pass
            if user_image_instructions:
                contents[0] += f"\n\nUSER IMAGE INSTRUCTIONS:\n{user_image_instructions}"

        time.sleep(1)

        def make_request():
            return client.models.generate_content(
                model=IMAGE_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["image", "text"],
                ),
            )

        response = _retry_with_backoff(make_request)

        output_path = Path(save_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image_id = str(uuid.uuid4())[:8]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"post_{timestamp}_{image_id}.png"
                image_path = output_path / filename

                with open(image_path, "wb") as f:
                    f.write(part.inline_data.data)

                return {
                    "status": "success",
                    "image_path": str(image_path),
                    "filename": filename,
                    "url": f"/generated/{filename}",
                    "prompt_used": prompt,
                    "style": style,
                    "model": IMAGE_MODEL,
                }

        return {"status": "error", "message": "No image was generated. Try a different prompt."}

    except Exception as e:
        return _format_error(e, "Try simplifying your prompt.")


@tool
def edit_image(
    image_path: str,
    edit_instruction: str,
    output_dir: str = "",
) -> dict:
    """Edit an existing image based on text instructions.

    Args:
        image_path: Path to the image to edit.
        edit_instruction: Description of desired edits.
        output_dir: Directory to save edited image.
    """
    _, _, EDIT_MODEL, GENERATED_DIR = _get_config()
    save_dir = output_dir or str(GENERATED_DIR)

    try:
        if not os.path.exists(image_path):
            return {"status": "error", "message": f"Image not found: {image_path}"}

        client = _get_client()
        original = Image.open(image_path)

        from google.genai import types

        edit_prompt = f"""Edit this image with the following changes:
{edit_instruction}

Keep the overall composition and brand elements. Only modify what's requested."""

        time.sleep(1)

        def make_request():
            return client.models.generate_content(
                model=EDIT_MODEL,
                contents=[edit_prompt, original],
                config=types.GenerateContentConfig(
                    response_modalities=["image", "text"],
                ),
            )

        response = _retry_with_backoff(make_request)

        output_path = Path(save_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image_id = str(uuid.uuid4())[:8]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"edited_{timestamp}_{image_id}.png"
                new_path = output_path / filename

                with open(new_path, "wb") as f:
                    f.write(part.inline_data.data)

                return {
                    "status": "success",
                    "image_path": str(new_path),
                    "filename": filename,
                    "url": f"/generated/{filename}",
                    "edit_instruction": edit_instruction,
                }

        return {"status": "error", "message": "Edit produced no image. Try different instructions."}

    except Exception as e:
        return _format_error(e, "Try simpler edit instructions.")
