"""Unified video generation tool using Veo 3.1 API.

Adapted from v2 — wrapped with LangChain @tool decorator.
Supports two mutually exclusive modes:
- Mode A (text-to-video + reference_images)
- Mode B (image-to-video + image=)
"""

import io
import logging
import os
import uuid
import time
from datetime import datetime
from pathlib import Path

from langchain_core.tools import tool
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)


def _get_config():
    from app.config import GOOGLE_API_KEY, VIDEO_MODEL, GENERATED_DIR
    return GOOGLE_API_KEY, VIDEO_MODEL, GENERATED_DIR


def _get_client():
    from google import genai
    api_key, _, _ = _get_config()
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not configured")
    return genai.Client(api_key=api_key)


def _resolve_image_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(os.getcwd(), path)


def _get_text_font(size: int):
    try:
        from PIL import ImageFont
        for font_path in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]:
            if os.path.exists(font_path):
                return ImageFont.truetype(font_path, size)
    except Exception:
        pass
    return None


def _composite_logo_onto_image(source_image: Image.Image, logo_path: str, brand_name: str = "") -> Image.Image:
    """Composite logo and brand name onto an image for Mode B."""
    resolved_logo = _resolve_image_path(logo_path)
    if not os.path.exists(resolved_logo):
        return source_image

    try:
        img_w, img_h = source_image.size
        logo_img = Image.open(resolved_logo)

        logo_target_w = int(img_w * 0.15)
        logo_w, logo_h = logo_img.size
        logo_scale = logo_target_w / logo_w
        logo_new_size = (logo_target_w, int(logo_h * logo_scale))
        logo_resized = logo_img.resize(logo_new_size, Image.LANCZOS)

        padding = int(img_w * 0.03)
        x = img_w - logo_new_size[0] - padding
        y = padding

        if logo_resized.mode == "RGBA":
            source_image.paste(logo_resized, (x, y), logo_resized)
        else:
            source_image.paste(logo_resized, (x, y))

        if brand_name:
            draw = ImageDraw.Draw(source_image)
            font_size = max(12, int(img_w * 0.025))
            font = _get_text_font(font_size)
            text_x = x + logo_new_size[0] // 2
            text_y = y + logo_new_size[1] + int(padding * 0.3)
            draw.text((text_x + 1, text_y + 1), brand_name, fill="#000000", font=font, anchor="mt")
            draw.text((text_x, text_y), brand_name, fill="#FFFFFF", font=font, anchor="mt")

    except Exception:
        pass

    return source_image


@tool
def generate_video(
    prompt: str,
    image_path: str = "",
    reference_image_paths: str = "",
    duration_seconds: int = 8,
    aspect_ratio: str = "9:16",
    logo_path: str = "",
    brand_name: str = "",
    brand_colors: str = "",
    company_overview: str = "",
    target_audience: str = "",
    products_services: str = "",
    cta_text: str = "",
    negative_prompt: str = "",
    output_dir: str = "",
) -> dict:
    """Generate a video using Veo 3.1.

    Supports two mutually exclusive modes:
    - Mode A: text-to-video + reference_images (logos/assets as visual guides)
    - Mode B: image-to-video + image= (starting frame, logo composited via PIL)

    Args:
        prompt: Video generation prompt (50-175 words).
        image_path: Source image for image-to-video mode (Mode B).
        reference_image_paths: Comma-separated paths to reference images (Mode A only).
        duration_seconds: Video length 5-8 seconds.
        aspect_ratio: "9:16" (Reels), "16:9" (YouTube), "1:1" (Feed).
        logo_path: Brand logo path.
        brand_name: Company name for prompt enhancement.
        brand_colors: Comma-separated hex colors.
        company_overview: Company description.
        target_audience: Target audience description.
        products_services: Products/services description.
        cta_text: Call-to-action text.
        negative_prompt: Elements to exclude.
        output_dir: Directory to save video.
    """
    _, VIDEO_MODEL, GENERATED_DIR = _get_config()
    save_dir = output_dir or str(GENERATED_DIR)

    try:
        client = _get_client()
        from google.genai import types

        clamped_duration = max(5, min(8, duration_seconds))

        config_kwargs = {
            "aspect_ratio": aspect_ratio,
            "number_of_videos": 1,
            "duration_seconds": clamped_duration,
        }

        # Build narrative brand enhancement (not flat metadata)
        colors_list = [c.strip() for c in brand_colors.split(",") if c.strip()] if brand_colors else []
        primary = colors_list[0] if colors_list else ""
        secondary = colors_list[1] if len(colors_list) > 1 else ""

        brand_narrative = []
        if colors_list:
            color_str = ", ".join(colors_list[:3])
            brand_narrative.append(
                f"The entire color palette of the scene must reflect the brand colors "
                f"({color_str}). Use {primary} as the dominant tone in backgrounds, "
                f"clothing, props, or lighting gels."
                + (f" Use {secondary} as accent color in secondary elements." if secondary else "")
            )
        if brand_name:
            brand_narrative.append(f"This is a marketing video for {brand_name}.")
        if target_audience:
            brand_narrative.append(f"The human subject should match the target audience: {target_audience}.")

        enhanced_prompt = prompt.rstrip()
        if brand_narrative:
            enhanced_prompt += " " + " ".join(brand_narrative)

        base_negatives = "text, titles, captions, words, letters, watermarks, subtitles"
        if negative_prompt:
            full_negative = f"{negative_prompt}, {base_negatives}"
        else:
            full_negative = base_negatives

        gen_kwargs = {"model": VIDEO_MODEL, "prompt": enhanced_prompt}

        if image_path:
            resolved_img = _resolve_image_path(image_path)
            if not os.path.exists(resolved_img):
                return {"status": "error", "message": f"Source image not found: {image_path}"}

            source_image = Image.open(resolved_img)
            if source_image.mode in ("RGBA", "LA", "P"):
                source_image = source_image.convert("RGB")

            if logo_path:
                source_image = _composite_logo_onto_image(source_image, logo_path, brand_name)

            buf = io.BytesIO()
            source_image.save(buf, format="JPEG")
            gen_kwargs["image"] = types.Image(image_bytes=buf.getvalue(), mime_type="image/jpeg")
            config_kwargs["negative_prompt"] = full_negative
            mode = "image_to_video"

        elif reference_image_paths or logo_path:
            ref_images = []

            if logo_path:
                resolved_logo = _resolve_image_path(logo_path)
                if os.path.exists(resolved_logo):
                    try:
                        logo_img = Image.open(resolved_logo)
                        if logo_img.mode in ("RGBA", "LA", "P"):
                            logo_img = logo_img.convert("RGB")
                        buf = io.BytesIO()
                        logo_img.save(buf, format="JPEG")
                        ref_images.append(
                            types.VideoGenerationReferenceImage(
                                image=types.Image(image_bytes=buf.getvalue(), mime_type="image/jpeg"),
                                reference_type="asset",
                            )
                        )
                    except Exception:
                        pass

            if reference_image_paths:
                for ref_path in [p.strip() for p in reference_image_paths.split(",") if p.strip()][:2]:
                    resolved = _resolve_image_path(ref_path)
                    if os.path.exists(resolved):
                        try:
                            ref_img = Image.open(resolved)
                            if ref_img.mode in ("RGBA", "LA", "P"):
                                ref_img = ref_img.convert("RGB")
                            buf = io.BytesIO()
                            ref_img.save(buf, format="JPEG")
                            ref_images.append(
                                types.VideoGenerationReferenceImage(
                                    image=types.Image(image_bytes=buf.getvalue(), mime_type="image/jpeg"),
                                    reference_type="asset",
                                )
                            )
                        except Exception:
                            pass

            if ref_images:
                config_kwargs["reference_images"] = ref_images[:3]
                if negative_prompt:
                    enhanced_prompt += f"\nAvoid: {negative_prompt}"
                    gen_kwargs["prompt"] = enhanced_prompt

            mode = "text_to_video_with_refs"

        else:
            config_kwargs["negative_prompt"] = full_negative
            mode = "text_to_video"

        gen_kwargs["config"] = types.GenerateVideosConfig(**config_kwargs)

        logger.info("[VIDEO] Starting generation mode=%s model=%s", mode, VIDEO_MODEL)
        logger.info("[VIDEO] Prompt (first 200 chars): %s", enhanced_prompt[:200])
        if "reference_images" in config_kwargs:
            logger.info("[VIDEO] Reference images: %d", len(config_kwargs["reference_images"]))

        operation = client.models.generate_videos(**gen_kwargs)
        logger.info("[VIDEO] Operation received — done=%s name=%s",
                     operation.done, getattr(operation, 'name', 'N/A'))

        max_wait = 300
        poll_count = 0
        while not operation.done:
            time.sleep(10)
            poll_count += 1
            operation = client.operations.get(operation)
            logger.info("[VIDEO] Poll %d — done=%s elapsed=%ds", poll_count, operation.done, poll_count * 10)
            max_wait -= 10
            if max_wait <= 0:
                logger.warning("[VIDEO] Timed out after 5 minutes")
                return {"status": "timeout", "message": "Video generation timed out after 5 minutes."}

        # Log full operation details for debugging
        op_error = getattr(operation, 'error', None)
        op_metadata = getattr(operation, 'metadata', None)
        result = operation.result
        logger.info("[VIDEO] Operation complete — result=%s error=%s metadata=%s",
                     type(result).__name__ if result else None, op_error, op_metadata)

        if not result or not result.generated_videos:
            error_detail = ""
            if op_error:
                error_detail = f" Error: {op_error}"
            # Try to get any additional info from the operation
            for attr in ['_raw', 'response', '_response']:
                raw = getattr(operation, attr, None)
                if raw:
                    logger.warning("[VIDEO] Operation.%s = %s", attr, str(raw)[:500])
            logger.warning("[VIDEO] No video in result: result=%s error=%s", result, op_error)
            msg = f"No video was generated.{error_detail} Try a different prompt."
            return {"status": "error", "message": msg}

        video = result.generated_videos[0]
        output_path = Path(save_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        video_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"video_{timestamp}_{video_id}.mp4"
        video_path = output_path / filename

        client.files.download(file=video.video)
        video.video.save(str(video_path))

        logger.info("[VIDEO] Success: %s", filename)
        return {
            "status": "success",
            "video_path": str(video_path),
            "filename": filename,
            "url": f"/generated/{filename}",
            "duration_seconds": clamped_duration,
            "aspect_ratio": aspect_ratio,
            "model": VIDEO_MODEL,
            "mode": mode,
            "branded": bool(logo_path or brand_name),
        }

    except Exception as e:
        logger.error("[VIDEO] Generation failed: %s", str(e), exc_info=True)
        return {"status": "error", "message": f"Video generation failed: {str(e)[:300]}"}
