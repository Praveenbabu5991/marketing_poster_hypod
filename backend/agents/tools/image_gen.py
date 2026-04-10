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
_REQUEST_TIMEOUT = 120  # Image gen can be slower, especially under quota pressure


def _get_config():
    from app.config import GOOGLE_API_KEY, IMAGE_MODEL, EDIT_MODEL, GENERATED_DIR
    return GOOGLE_API_KEY, IMAGE_MODEL, EDIT_MODEL, GENERATED_DIR


def _get_client():
    from app.config import get_genai_client
    return get_genai_client()


def _retry_with_backoff(func, max_retries: int = 5, base_delay: float = 5.0):
    """Execute with exponential backoff and per-request timeout."""
    last_error = None
    for attempt in range(max_retries):
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(func)
                return future.result(timeout=_REQUEST_TIMEOUT)
        except concurrent.futures.TimeoutError:
            last_error = TimeoutError(f"Request timed out after {_REQUEST_TIMEOUT}s")
            print(f"[IMAGE] Attempt {attempt + 1} timed out after {_REQUEST_TIMEOUT}s", file=sys.stderr, flush=True)
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            if "not found" in error_str and "model" in error_str:
                raise
            if "api" in error_str and "key" in error_str:
                raise
            print(f"[IMAGE] Attempt {attempt + 1} failed: {str(e)[:200]}", file=sys.stderr, flush=True)
        if attempt < max_retries - 1:
            delay = base_delay * (2 ** attempt)
            print(f"[IMAGE] Retrying in {delay:.0f}s...", file=sys.stderr, flush=True)
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
    has_product_image: bool = False,
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

    # --- Part 1: Product image anchor (HIGHEST PRIORITY when product image attached) ---
    product_paragraph = ""
    if has_product_image:
        product_paragraph = (
            "I am attaching the ACTUAL PRODUCT PHOTO. This is the most important element. "
            "You MUST build the entire poster design AROUND this exact product. "
            "Place this product as the central visual anchor — it should be the hero of the image, "
            "prominently visible and occupying 30-50% of the poster area. "
            "Keep the product's exact appearance, colors, shape, and details — do NOT replace it "
            "with a different or AI-generated product. Construct a complementary background scene, "
            "lighting, and environment that enhances and showcases this specific product. "
        )
        if user_image_instructions:
            product_paragraph += f"{user_image_instructions}. "

    # --- Part 2: Text rendering (guide says: generate the text first) ---
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

    # --- Part 3: Scene description (narrative, with photography terms) ---
    brand_label = brand_name or "a brand"
    industry_label = industry or "general"

    scene_paragraph = (
        f"Create a premium, scroll-stopping social media poster for {brand_label} "
        f"in the {industry_label} industry. "
        f"The visual style should be {style_desc}. "
    )
    if occasion:
        scene_paragraph += f"The theme is {occasion}. "
    scene_paragraph += f"The scene should be: {prompt}. "
    if has_product_image:
        scene_paragraph += (
            "Build the entire background, lighting, and environment to complement and "
            "showcase the attached product photo. The product should feel naturally integrated "
            "into the scene — not pasted on. Use soft directional lighting that matches the "
            "product's lighting. "
        )
    else:
        scene_paragraph += (
            "Use a photorealistic, eye-level medium shot with soft directional lighting "
            "that creates depth and dimension. The composition should have a single strong "
            "focal point with high contrast between the subject and background. "
        )

    # --- Part 4: Brand color palette (narrative, not bullet list) ---
    color_paragraph = ""
    if colors_list:
        color_paragraph = (
            f"The entire color scheme must unmistakably reflect the brand identity. "
            f"Use {primary} as the dominant color for backgrounds and major design elements. "
            f"Use {secondary} for supporting elements, accent borders, and contrast areas. "
            f"The full brand palette is {all_colors} — these colors should be instantly "
            f"recognizable as this brand's content. "
        )

    # --- Part 5: Logo (high-fidelity preservation, per guide template #5) ---
    logo_paragraph = ""
    if has_logo:
        logo_paragraph = (
            "I am also attaching the brand logo image file. Place this EXACT logo in the "
            "bottom-right corner of the design. Ensure the logo features remain completely "
            "unchanged — do not redraw, recreate, or generate any logo. "
        )

    # Assemble: product anchor first, then text, scene, brand, logo
    full_prompt = product_paragraph + text_paragraph + scene_paragraph + color_paragraph + logo_paragraph
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

    # Debug: log all arguments received from LLM
    import sys
    print(f"[IMAGE_GEN] prompt='{prompt[:80]}...' logo_path='{logo_path}' user_images='{user_images}' user_image_instructions='{user_image_instructions}' aspect_ratio='{aspect_ratio}'", file=sys.stderr, flush=True)

    try:
        client = _get_client()

        has_logo = bool(logo_path and os.path.exists(logo_path))

        # Load product images first to know if we have them
        # Upscale tiny images — Gemini ignores images < ~512px
        MIN_PRODUCT_DIM = 768
        product_pil_images = []
        if user_images:
            for user_img_path in [p.strip() for p in user_images.split(",") if p.strip()][:5]:
                exists = os.path.exists(user_img_path)
                print(f"[IMAGE_GEN] user_img_path='{user_img_path}' exists={exists}", file=sys.stderr, flush=True)
                if exists:
                    try:
                        img = Image.open(user_img_path).convert("RGB")
                        original_size = img.size
                        # Upscale if too small — preserves aspect ratio
                        w, h = img.size
                        if max(w, h) < MIN_PRODUCT_DIM:
                            scale = MIN_PRODUCT_DIM / max(w, h)
                            new_w, new_h = int(w * scale), int(h * scale)
                            img = img.resize((new_w, new_h), Image.LANCZOS)
                            print(f"[IMAGE_GEN] Upscaled product image: {original_size} -> {img.size}", file=sys.stderr, flush=True)
                        product_pil_images.append(img)
                        print(f"[IMAGE_GEN] Product image loaded: {img.size} {img.mode} (original={original_size})", file=sys.stderr, flush=True)
                    except Exception as e:
                        print(f"[IMAGE_GEN] Failed to open product image: {e}", file=sys.stderr, flush=True)

        has_product = len(product_pil_images) > 0

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
            has_product_image=has_product,
        )

        from google.genai import types

        # Build contents: product image FIRST (hero element), then prompt, then logo
        contents = []

        # Product image first — Gemini should build the scene around it
        for pimg in product_pil_images:
            contents.append(pimg)

        # Text prompt that instructs Gemini to use the attached product
        contents.append(full_prompt)

        # Logo last
        if has_logo:
            try:
                contents.append(Image.open(logo_path))
            except Exception:
                pass

        print(f"[IMAGE_GEN] Full prompt (first 500 chars): {full_prompt[:500]}", file=sys.stderr, flush=True)
        print(f"[IMAGE_GEN] has_product_image={has_product} has_logo={has_logo}", file=sys.stderr, flush=True)
        print(f"[IMAGE_GEN] Sending to Gemini: {len(contents)} items (product={len(product_pil_images)}, prompt=1, logo={1 if has_logo else 0})", file=sys.stderr, flush=True)
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

        # Extract usage metadata for cost tracking
        usage_meta = getattr(response, "usage_metadata", None)
        token_info = {}
        if usage_meta:
            token_info["prompt_tokens"] = getattr(usage_meta, "prompt_token_count", 0) or 0
            token_info["completion_tokens"] = getattr(usage_meta, "candidates_token_count", 0) or 0

        output_path = Path(save_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        parts = response.candidates[0].content.parts
        part_types = [("image" if p.inline_data else "text") for p in parts]
        print(f"[IMAGE_GEN] Response parts: {part_types}", file=sys.stderr, flush=True)

        for part in parts:
            if part.inline_data is not None:
                image_id = str(uuid.uuid4())[:8]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"post_{timestamp}_{image_id}.png"
                image_path = output_path / filename

                with open(image_path, "wb") as f:
                    f.write(part.inline_data.data)

                print(f"[IMAGE_GEN] SUCCESS saved={filename} size={len(part.inline_data.data)}", file=sys.stderr, flush=True)
                return {
                    "status": "success",
                    "image_path": str(image_path),
                    "filename": filename,
                    "url": f"/generated/{filename}",
                    "prompt_used": prompt,
                    "style": style,
                    "aspect_ratio": ar,
                    "model": IMAGE_MODEL,
                    **token_info,
                }

        # Log text parts for debugging
        text_parts = [p.text for p in parts if hasattr(p, "text") and p.text]
        if text_parts:
            print(f"[IMAGE_GEN] NO IMAGE — text response: {text_parts[0][:200]}", file=sys.stderr, flush=True)
        return {"status": "error", "message": "No image was generated. Try a different prompt.", "model": IMAGE_MODEL}

    except Exception as e:
        print(f"[IMAGE_GEN] EXCEPTION: {type(e).__name__}: {str(e)[:300]}", file=sys.stderr, flush=True)
        result = _format_error(e, "Try simplifying your prompt.")
        result["model"] = _get_config()[1]  # IMAGE_MODEL
        return result


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

        # Extract usage metadata for cost tracking
        usage_meta = getattr(response, "usage_metadata", None)
        token_info = {}
        if usage_meta:
            token_info["prompt_tokens"] = getattr(usage_meta, "prompt_token_count", 0) or 0
            token_info["completion_tokens"] = getattr(usage_meta, "candidates_token_count", 0) or 0

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
                    "model": EDIT_MODEL,
                    **token_info,
                }

        return {"status": "error", "message": "Edit produced no image. Try different instructions.", "model": EDIT_MODEL}

    except Exception as e:
        result = _format_error(e, "Try simpler edit instructions.")
        result["model"] = _get_config()[2]  # EDIT_MODEL
        return result
