"""Image generation tools using Gemini API.

Adapted from v2 — wrapped with LangChain @tool decorator.
Prompt construction follows official Gemini image generation guide:
  - Narrative descriptive paragraphs (not keyword lists)
  - Text rendering instructions placed prominently
  - Photography terms (camera, lens, lighting)
  - aspect_ratio and image_size via API config
"""

import concurrent.futures
import logging
import os
import io
import uuid
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool
from PIL import Image

logger = logging.getLogger(__name__)
_REQUEST_TIMEOUT = 60  # Image gen can be slower


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
    """Execute with exponential backoff and per-request timeout."""
    last_error = None
    for attempt in range(max_retries):
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(func)
                return future.result(timeout=_REQUEST_TIMEOUT)
        except concurrent.futures.TimeoutError:
            last_error = TimeoutError(f"Request timed out after {_REQUEST_TIMEOUT}s")
            logger.warning("[IMAGE] Attempt %d timed out", attempt + 1)
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            if "not found" in error_str and "model" in error_str:
                raise
            if "api" in error_str and "key" in error_str:
                raise
            logger.warning("[IMAGE] Attempt %d failed: %s", attempt + 1, str(e)[:200])
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


def _build_narrative_prompt(
    prompt: str,
    brand_name: str,
    brand_colors: str,
    style: str,
    industry: str,
    occasion: str,
    occasion_text: str,
    headline_text: str,
    subtext: str,
    cta_text: str,
    has_logo: bool,
    user_image_instructions: str,
    font_style: str = "bold sans-serif",
) -> str:
    """Build a narrative Gemini prompt following official prompting guide.

    Key principles from the guide:
    1. Describe the scene narratively, not as keyword lists
    2. Text rendering instructions placed prominently and early
    3. Use photography terms (camera, lens, lighting)
    4. Provide context and intent
    5. Be hyper-specific about details
    """
    colors_list = [c.strip() for c in brand_colors.split(",") if c.strip()] if brand_colors else []
    primary = colors_list[0] if colors_list else "#000000"
    secondary = colors_list[1] if len(colors_list) > 1 else primary
    all_colors = ", ".join(colors_list[:4]) if colors_list else ""

    style_map = {
        "creative": "artistic and visually striking",
        "professional": "clean, corporate, and polished",
        "playful": "fun, vibrant, and energetic",
        "minimal": "simple, clean, and focused with generous whitespace",
        "bold": "strong, impactful, and attention-grabbing with high contrast",
    }
    style_desc = style_map.get(style, style_map["creative"])

    # --- Part 1: Text rendering (guide says: generate the text first) ---
    text_paragraph = ""
    if occasion_text or headline_text or subtext or cta_text:
        text_parts = []
        if occasion_text:
            text_parts.append(
                f'At the top of the image, display the occasion greeting "{occasion_text}" '
                f"in an elegant, decorative font with a festive or celebratory feel"
            )
        if headline_text:
            text_parts.append(
                f'Display the headline text "{headline_text}" in a large, {font_style} font '
                f"as the most prominent text element on the image"
            )
        if subtext:
            text_parts.append(
                f'Below the headline, display the supporting text "{subtext}" in a smaller, '
                f"lighter weight font"
            )
        if cta_text:
            text_parts.append(
                f'Include a call-to-action that reads "{cta_text}" styled as a tappable button '
                f"with rounded corners and solid fill, placed in the lower portion of the image"
            )
        text_paragraph = (
            "The image must contain the following text rendered clearly and legibly. "
            + ". ".join(text_parts) + ". "
            "Display ONLY the exact text in quotes — do not add, change, or omit any words. "
        )
        if all_colors:
            text_paragraph += (
                f"All text colors must use the brand palette ({all_colors}) or white/black "
                f"for contrast. The headline should use {primary} or white on a contrasting "
                f"background. The CTA button fill should use {secondary} with white or "
                f"{primary} text. "
            )

    # --- Part 2: Scene description (narrative, with photography terms) ---
    brand_label = brand_name or "a brand"
    industry_label = industry or "general"

    scene_paragraph = (
        f"Create a premium, scroll-stopping social media image for {brand_label} "
        f"in the {industry_label} industry. "
        f"The visual style should be {style_desc}. "
    )
    if occasion:
        scene_paragraph += f"The theme is {occasion}. "
    scene_paragraph += (
        f"The scene should be: {prompt}. "
        "Use a photorealistic, eye-level medium shot with soft directional lighting "
        "that creates depth and dimension. The composition should have a single strong "
        "focal point with high contrast between the subject and background. "
    )

    # --- Part 3: Brand color palette (narrative, not bullet list) ---
    color_paragraph = ""
    if colors_list:
        color_paragraph = (
            f"The entire color scheme must unmistakably reflect the brand identity. "
            f"Use {primary} as the dominant color for backgrounds and major design elements. "
            f"Use {secondary} for supporting elements, accent borders, and contrast areas. "
            f"The full brand palette is {all_colors} — these colors should be instantly "
            f"recognizable as this brand's content. "
        )

    # --- Part 4: Logo (high-fidelity preservation, per guide template #5) ---
    logo_paragraph = ""
    if has_logo:
        logo_paragraph = (
            "I am attaching the brand logo image file. Using the provided logo image, "
            "place this EXACT logo in the bottom-right corner of the design. Ensure the "
            "logo features remain completely unchanged — do not redraw, recreate, or "
            "generate any logo. The logo should be clearly visible and properly sized. "
        )

    # --- Part 5: User images (combining multiple images, per guide template #4) ---
    user_img_paragraph = ""
    if user_image_instructions:
        user_img_paragraph = (
            f"I am also attaching product/reference images. {user_image_instructions}. "
            "Preserve the product's appearance, colors, and details faithfully. "
        )

    # Assemble in the optimal order: text first, then scene, then brand details
    full_prompt = text_paragraph + scene_paragraph + color_paragraph + logo_paragraph + user_img_paragraph
    return full_prompt.strip()


@tool
def generate_image(
    prompt: str,
    brand_name: str = "",
    brand_colors: str = "",
    logo_path: str = "",
    style: str = "creative",
    industry: str = "",
    occasion: str = "",
    occasion_text: str = "",
    headline_text: str = "",
    subtext: str = "",
    cta_text: str = "",
    user_images: str = "",
    user_image_instructions: str = "",
    aspect_ratio: str = "1:1",
    output_dir: str = "",
    font_style: str = "bold sans-serif",
) -> dict:
    """Generate a social media post image using Gemini.

    Args:
        prompt: Narrative description of the visual scene and composition.
        brand_name: Brand/company name.
        brand_colors: Comma-separated hex color codes.
        logo_path: Path to brand logo to incorporate.
        style: Visual style (creative, professional, playful, minimal, bold).
        industry: Brand industry/niche.
        occasion: Special occasion/event theme.
        occasion_text: Festive greeting text for special days (e.g. "Happy Republic Day").
        headline_text: Main headline text for the image.
        subtext: Supporting tagline text.
        cta_text: Call-to-action text.
        user_images: Comma-separated paths to user-uploaded images.
        user_image_instructions: How to use user images.
        aspect_ratio: Image aspect ratio (1:1, 4:5, 16:9, 9:16). Default 1:1.
        output_dir: Directory to save image.
    """
    _, IMAGE_MODEL, _, GENERATED_DIR = _get_config()
    save_dir = output_dir or str(GENERATED_DIR)

    try:
        client = _get_client()

        has_logo = bool(logo_path and os.path.exists(logo_path))

        full_prompt = _build_narrative_prompt(
            prompt=prompt,
            brand_name=brand_name,
            brand_colors=brand_colors,
            style=style,
            industry=industry,
            occasion=occasion,
            occasion_text=occasion_text,
            headline_text=headline_text,
            subtext=subtext,
            cta_text=cta_text,
            has_logo=has_logo,
            user_image_instructions=user_image_instructions,
            font_style=font_style,
        )

        from google.genai import types

        contents = [full_prompt]

        # Attach logo image (guide: high-fidelity detail preservation)
        if has_logo:
            try:
                contents.append(Image.open(logo_path))
            except Exception:
                pass

        # Attach user/product images (guide: combining multiple images)
        if user_images:
            for user_img_path in [p.strip() for p in user_images.split(",") if p.strip()][:5]:
                if os.path.exists(user_img_path):
                    try:
                        contents.append(Image.open(user_img_path))
                    except Exception:
                        pass

        time.sleep(1)

        # Validate aspect ratio
        valid_ratios = {"1:1", "4:5", "5:4", "16:9", "9:16", "3:2", "2:3", "3:4", "4:3"}
        ar = aspect_ratio if aspect_ratio in valid_ratios else "1:1"

        def make_request():
            return client.models.generate_content(
                model=IMAGE_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["image", "text"],
                    image_config=types.ImageConfig(
                        aspect_ratio=ar,
                    ),
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
                    "aspect_ratio": ar,
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

        # Narrative edit prompt (guide: describe the change conversationally)
        edit_prompt = (
            f"Using the provided image, please make the following changes: "
            f"{edit_instruction}. "
            f"Keep everything else in the image exactly the same, preserving the "
            f"original style, lighting, composition, and brand elements."
        )

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
