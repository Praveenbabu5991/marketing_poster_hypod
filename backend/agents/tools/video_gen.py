"""Unified video generation tool using Veo 3.1 API.

Adapted from v2 — wrapped with LangChain @tool decorator.
Supports two mutually exclusive modes:
- Mode A (text-to-video + reference_images)
- Mode B (image-to-video + image=)
"""

import io
import logging
import os
import subprocess
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
    from app.config import get_genai_client
    return get_genai_client()


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


def _get_media_duration(path: str) -> float:
    """Get duration of a media file in seconds using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True
        )
        return float(result.stdout.strip()) if result.stdout.strip() else 0.0
    except Exception:
        return 0.0


def _build_atempo_chain(ratio: float) -> str:
    """Build chained atempo filters for ffmpeg.

    atempo only supports 0.5-2.0 per filter. For ratios outside this range,
    chain multiple filters (e.g., 3.0 → atempo=2.0,atempo=1.5).
    """
    if ratio <= 0:
        return "atempo=1.0"
    filters = []
    remaining = ratio
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    filters.append(f"atempo={remaining:.4f}")
    return ",".join(filters)


def _split_prompt_for_parts(prompt: str) -> tuple[str, str]:
    """Split a scene-based prompt into Part 1 and Part 2 for 16s videos.

    If the prompt has scene markers (SCENE 1, SCENE 2, etc.), split the scenes:
    - Part 1: AD NARRATIVE + first half of scenes + Global specs
    - Part 2: second half of scenes + Global specs + continuation instructions

    If no scene markers, returns (full_prompt, full_prompt + continuation).
    """
    import re as _re

    # Find all scene markers
    scene_pattern = r'(SCENE\s+\d+[^\n]*)'
    scene_matches = list(_re.finditer(scene_pattern, prompt, _re.IGNORECASE))

    if len(scene_matches) < 3:
        # Not a scene-based prompt — return full prompt for both parts
        continuation = (
            " [SMOOTH CONTINUATION from the previous shot within the SAME scene. "
            "Maintain identical lighting, color grading, subject, and environment. "
            "The visual flow must feel like one continuous unbroken shot.]"
        )
        return prompt, prompt + continuation

    # Extract sections
    # Everything before first scene = preamble (AD NARRATIVE, etc.)
    preamble = prompt[:scene_matches[0].start()].strip()

    # Split scenes into first half and second half
    mid = len(scene_matches) // 2
    # Ensure at least 2 scenes in Part 1
    if mid < 2:
        mid = 2

    # Get scene text blocks
    scenes = []
    for i, match in enumerate(scene_matches):
        start = match.start()
        end = scene_matches[i + 1].start() if i + 1 < len(scene_matches) else len(prompt)
        scenes.append(prompt[start:end].strip())

    # Find Global Technical Specifications section
    global_pattern = r'(Global Technical Specifications.*)'
    global_match = _re.search(global_pattern, prompt, _re.IGNORECASE | _re.DOTALL)
    global_specs = ""
    if global_match:
        global_specs = global_match.group(1).strip()
        # Remove global specs from the last scene if it was captured there
        last_scene = scenes[-1]
        global_idx = _re.search(r'Global Technical Specifications', last_scene, _re.IGNORECASE)
        if global_idx:
            scenes[-1] = last_scene[:global_idx.start()].strip()

    # Build Part 1: preamble + first half scenes + global specs
    part1_scenes = "\n\n".join(scenes[:mid])
    part1_prompt = f"{preamble}\n\n{part1_scenes}"
    if global_specs:
        part1_prompt += f"\n\n{global_specs}"

    # Build Part 2: continuation context + second half scenes + global specs
    part2_scenes = "\n\n".join(scenes[mid:])
    part2_prompt = (
        f"[SMOOTH CONTINUATION from the previous shot. Maintain identical lighting, "
        f"color grading, environment, and subject. The visual flow must feel like one "
        f"continuous unbroken shot.]\n\n{part2_scenes}"
    )
    if global_specs:
        part2_prompt += f"\n\n{global_specs}"

    return part1_prompt, part2_prompt


def _overlay_logo_on_video(video_path: str, logo_path: str, output_path: str) -> bool:
    """Overlay brand logo as a persistent watermark on the video using ffmpeg.

    Places logo in top-right corner at ~12% of video width with slight padding
    and partial transparency. Returns True on success.
    """
    resolved_logo = _resolve_image_path(logo_path)
    if not os.path.exists(resolved_logo):
        return False

    try:
        # ffmpeg overlay: scale logo to 12% of video width, position top-right with padding,
        # apply 85% opacity so it's visible but not distracting
        filter_complex = (
            "[1:v]scale=iw*0.12:-1,format=rgba,colorchannelmixer=aa=0.85[logo];"
            "[0:v][logo]overlay=W-w-W*0.03:H*0.03[out]"
        )
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-i", resolved_logo,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-map", "0:a?",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "copy",
            output_path, "-y"
        ]
        import sys as _sys_logo
        print(f"[VIDEO] Overlaying logo watermark: {resolved_logo}", file=_sys_logo.stderr, flush=True)
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        import sys as _sys_logo
        print(f"[VIDEO] Logo overlay failed: {e}", file=_sys_logo.stderr, flush=True)
        return False


def _generate_single_video(
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
    audio_script: str = "",
) -> dict:
    """Generate a video using Veo 3.1 with reference images.

    Uses text-to-video + reference_images for product/logo as visual asset guides.
    Product image and logo are passed as VideoGenerationReferenceImage(reference_type="asset").

    Args:
        prompt: Video generation prompt.
        image_path: Product image path (used as reference_image asset).
        reference_image_paths: Comma-separated paths to additional reference images.
        duration_seconds: Video length 5-8 seconds.
        aspect_ratio: "9:16" (Reels), "16:9" (YouTube), "1:1" (Feed).
        logo_path: Brand logo path (used as reference_image asset).
        brand_name: Company name for prompt enhancement.
        brand_colors: Comma-separated hex colors.
        company_overview: Company description.
        target_audience: Target audience description.
        products_services: Products/services description.
        cta_text: Call-to-action text.
        negative_prompt: Elements to exclude.
        output_dir: Directory to save video.
        audio_script: Voiceover text to generate and merge into the video.
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

        # Build MINIMAL brand enhancement — keep prompt concise to avoid RAI filter triggers.
        colors_list = [c.strip() for c in brand_colors.split(",") if c.strip()] if brand_colors else []
        primary = colors_list[0] if colors_list else ""
        secondary = colors_list[1] if len(colors_list) > 1 else ""

        brand_narrative = []
        if colors_list:
            color_str = ", ".join(colors_list[:3])
            brand_narrative.append(
                f"Scene color palette: brand colors {color_str}. "
                f"Use {primary} as dominant tone."
                + (f" {secondary} as accent." if secondary else "")
            )
        if target_audience:
            brand_narrative.append(f"Human subject matches target audience: {target_audience}.")

        brand_narrative.append(
            "One pair of hands, one simple action per shot. Stable background, consistent lighting."
        )

        enhanced_prompt = prompt.rstrip()
        # Strip brand name from prompt — known brand names (e.g. "H&M", "Nike")
        # trigger Veo's RAI filter for brand impersonation.
        if brand_name:
            import re as _re
            enhanced_prompt = _re.sub(
                r"\b" + _re.escape(brand_name) + r"(?:'s)?\b",
                "the brand's",
                enhanced_prompt,
                flags=_re.IGNORECASE,
            )
        if brand_narrative:
            enhanced_prompt += " " + " ".join(brand_narrative)

        # Build negative prompt text — negative_prompt API param is NOT supported
        # with reference_images, so we append it to the prompt as "Avoid: ..."
        base_negatives = (
            "text, titles, captions, words, letters, watermarks, subtitles, "
            "extra hands, extra fingers, three hands, four hands, "
            "overlapping hands, floating objects, animated, cartoon, "
            "morphing, flickering, jitter, shifting background, inconsistent lighting"
        )
        if negative_prompt:
            full_negative = f"{negative_prompt}, {base_negatives}"
        else:
            full_negative = base_negatives

        # Build reference images list — product image + logo as assets
        ref_images = []
        all_ref_paths = []

        # Add product image as reference
        if image_path:
            resolved_img = _resolve_image_path(image_path)
            if os.path.exists(resolved_img):
                img = Image.open(resolved_img)
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="JPEG")
                ref_images.append(
                    types.VideoGenerationReferenceImage(
                        image=types.Image(image_bytes=buf.getvalue(), mime_type="image/jpeg"),
                        reference_type="asset",
                    )
                )
                all_ref_paths.append(resolved_img)

        # Add any additional reference image paths
        if reference_image_paths:
            for ref_path in reference_image_paths.split(","):
                ref_path = ref_path.strip()
                if not ref_path:
                    continue
                resolved = _resolve_image_path(ref_path)
                if os.path.exists(resolved) and resolved not in all_ref_paths:
                    img = Image.open(resolved)
                    if img.mode in ("RGBA", "LA", "P"):
                        img = img.convert("RGB")
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG")
                    ref_images.append(
                        types.VideoGenerationReferenceImage(
                            image=types.Image(image_bytes=buf.getvalue(), mime_type="image/jpeg"),
                            reference_type="asset",
                        )
                    )
                    all_ref_paths.append(resolved)

        # Add logo as reference image
        if logo_path:
            resolved_logo = _resolve_image_path(logo_path)
            if os.path.exists(resolved_logo) and resolved_logo not in all_ref_paths:
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
                all_ref_paths.append(resolved_logo)

        gen_kwargs = {"model": VIDEO_MODEL, "prompt": enhanced_prompt}

        if ref_images:
            # Text-to-video with reference images (product + logo as assets)
            # negative_prompt is NOT supported with reference_images — append to prompt
            config_kwargs["reference_images"] = ref_images
            # Append short "Avoid:" to prompt (keep it brief to avoid RAI triggers)
            safe_negatives = (
                "text, titles, words, extra hands, extra fingers, floating objects, "
                "cartoon, morphing, flickering, shifting background"
            )
            enhanced_prompt += f" Avoid: {safe_negatives}."
            gen_kwargs["prompt"] = enhanced_prompt
            mode = "text_to_video_with_refs"
        else:
            # Pure text-to-video (no reference images at all)
            config_kwargs["negative_prompt"] = full_negative
            mode = "text_to_video"

        gen_kwargs["config"] = types.GenerateVideosConfig(**config_kwargs)

        import sys as _sys
        print(f"[VIDEO] Starting generation mode={mode} model={VIDEO_MODEL}", file=_sys.stderr, flush=True)
        print(f"[VIDEO] Prompt FULL: {enhanced_prompt}", file=_sys.stderr, flush=True)
        print(f"[VIDEO] Reference images: {len(ref_images)} paths={all_ref_paths}", file=_sys.stderr, flush=True)

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
                return {"status": "timeout", "message": "Video generation timed out after 5 minutes.", "model": VIDEO_MODEL}

        # Log full operation details for debugging
        op_error = getattr(operation, 'error', None)
        op_metadata = getattr(operation, 'metadata', None)
        result = operation.result
        logger.info("[VIDEO] Operation complete — result=%s error=%s metadata=%s",
                     type(result).__name__ if result else None, op_error, op_metadata)

        rai_filtered = (
            result
            and not result.generated_videos
            and getattr(result, 'rai_media_filtered_count', 0) > 0
        )

        if not result or (not result.generated_videos and not rai_filtered):
            error_detail = ""
            if op_error:
                error_detail = f" Error: {op_error}"
            for attr in ['_raw', 'response', '_response']:
                raw = getattr(operation, attr, None)
                if raw:
                    logger.warning("[VIDEO] Operation.%s = %s", attr, str(raw)[:500])
            logger.warning("[VIDEO] No video in result: result=%s error=%s", result, op_error)
            msg = f"No video was generated.{error_detail} Try a different prompt."
            return {"status": "error", "message": msg, "model": VIDEO_MODEL}

        if rai_filtered:
            # RAI safety filter triggered — retry with a generic, safe prompt.
            # Strip brand names, product specifics, and constraint text that may
            # have triggered the filter. Keep only the core visual description.
            import sys as _sys_rai
            print(f"[VIDEO] RAI filtered — retrying with simplified prompt", file=_sys_rai.stderr, flush=True)

            # Extract just the first 2 sentences of the original prompt (the visual hook)
            import re as _re2
            sentences = _re2.split(r'(?<=[.!])\s+', prompt.strip())
            simple_prompt = " ".join(sentences[:3]) if sentences else prompt[:200]
            # Remove any remaining brand references
            if brand_name:
                simple_prompt = _re2.sub(
                    r"\b" + _re2.escape(brand_name) + r"(?:'s)?\b",
                    "",
                    simple_prompt,
                    flags=_re2.IGNORECASE,
                )
            simple_prompt = simple_prompt.strip()
            simple_prompt += " Hyper-realistic, cinematic lighting, 8k, professional commercial."

            print(f"[VIDEO] Retry prompt: {simple_prompt[:200]}", file=_sys_rai.stderr, flush=True)

            retry_kwargs = {"model": VIDEO_MODEL, "prompt": simple_prompt}
            retry_config = {
                "aspect_ratio": aspect_ratio,
                "number_of_videos": 1,
                "duration_seconds": clamped_duration,
            }
            if ref_images:
                # Re-use same reference images
                retry_config["reference_images"] = ref_images
            else:
                retry_config["negative_prompt"] = full_negative

            retry_kwargs["config"] = types.GenerateVideosConfig(**retry_config)

            try:
                operation2 = client.models.generate_videos(**retry_kwargs)
                while not operation2.done:
                    time.sleep(10)
                    operation2 = client.operations.get(operation2)
                result = operation2.result
                if not result or not result.generated_videos:
                    print(f"[VIDEO] Retry also failed: {result}", file=_sys_rai.stderr, flush=True)
                    return {"status": "error", "message": "Video was filtered by safety guidelines. Try a simpler prompt.", "model": VIDEO_MODEL}
                print(f"[VIDEO] Retry succeeded!", file=_sys_rai.stderr, flush=True)
            except Exception as retry_err:
                print(f"[VIDEO] Retry error: {retry_err}", file=_sys_rai.stderr, flush=True)
                return {"status": "error", "message": f"Video filtered by safety guidelines: {str(retry_err)[:200]}", "model": VIDEO_MODEL}

        video = result.generated_videos[0]
        output_path = Path(save_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        video_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"video_{timestamp}_{video_id}.mp4"
        video_path = output_path / filename

        # Download video — different methods for Developer vs Vertex AI clients
        try:
            client.files.download(file=video.video)
            video.video.save(str(video_path))
        except (ValueError, NotImplementedError):
            # Vertex AI client doesn't support client.files.download()
            # Try saving directly (video bytes may already be in the response)
            video_data = getattr(video.video, 'video_bytes', None)
            if video_data:
                with open(video_path, 'wb') as f:
                    f.write(video_data)
                logger.info("[VIDEO] Saved via video_bytes (Vertex AI)")
            else:
                # Try the URI-based approach for Vertex AI
                uri = getattr(video.video, 'uri', None)
                if uri:
                    logger.info("[VIDEO] Downloading from URI: %s", uri)
                    if uri.startswith("gs://"):
                        from google.cloud import storage as gcs_storage
                        from app.config import GOOGLE_SERVICE_ACCOUNT_FILE
                        from google.oauth2.service_account import Credentials as SACredentials
                        creds = SACredentials.from_service_account_file(
                            GOOGLE_SERVICE_ACCOUNT_FILE,
                            scopes=["https://www.googleapis.com/auth/cloud-platform"],
                        )
                        gcs_client = gcs_storage.Client(credentials=creds)
                        # Parse gs://bucket/path
                        parts = uri.replace("gs://", "").split("/", 1)
                        bucket = gcs_client.bucket(parts[0])
                        blob = bucket.blob(parts[1])
                        blob.download_to_filename(str(video_path))
                        logger.info("[VIDEO] Downloaded from GCS")
                    else:
                        import urllib.request
                        urllib.request.urlretrieve(uri, str(video_path))
                        logger.info("[VIDEO] Downloaded from HTTP URI")
                else:
                    # Last resort: try save() directly
                    video.video.save(str(video_path))
                    logger.info("[VIDEO] Saved via direct save() call")

        print(f"[VIDEO] Success: {filename} mode={mode}", file=_sys.stderr, flush=True)
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
        import sys as _sys
        import traceback
        print(f"[VIDEO] Generation failed: {e}", file=_sys.stderr, flush=True)
        traceback.print_exc(file=_sys.stderr)
        return {"status": "error", "message": f"Video generation failed: {str(e)[:300]}", "model": VIDEO_MODEL}

@tool
def generate_video(
    prompt: str,
    image_path: str = "",
    reference_image_paths: str = "",
    duration_seconds: int = 16,
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
    audio_script: str = "",
) -> dict:
    """Generate a video using Veo 3.1 with reference images.

    Product image and logo are passed as reference_images (reference_type="asset")
    to guide Veo's generation while keeping product and brand consistency.

    Args:
        prompt: Video generation prompt (50-175 words).
        image_path: Product image path (used as reference_image asset).
        reference_image_paths: Comma-separated paths to product images (used as reference_image assets).
        duration_seconds: Video length 5-16 seconds.
        aspect_ratio: "9:16" (Reels), "16:9" (YouTube), "1:1" (Feed).
        logo_path: Brand logo path (used as reference_image asset).
        brand_name: Company name for prompt enhancement.
        brand_colors: Comma-separated hex colors.
        company_overview: Company description.
        target_audience: Target audience description.
        products_services: Products/services description.
        cta_text: Call-to-action text.
        negative_prompt: Elements to exclude.
        output_dir: Directory to save video.
        audio_script: Voiceover text to generate and merge into the video.
    """

    import sys as _sys2

    clamped_duration = max(5, min(16, duration_seconds))

    # Merge image_path and reference_image_paths into a single reference list.
    # Both product images and logo are passed as reference_images (asset type).
    effective_image_path = image_path
    if reference_image_paths and not image_path:
        ref_list = [p.strip() for p in reference_image_paths.split(",") if p.strip()]
        first_product = _resolve_image_path(ref_list[0]) if ref_list else ""
        if first_product and os.path.exists(first_product):
            effective_image_path = first_product
            print(f"[VIDEO] Using product image as reference: {first_product}", file=_sys2.stderr, flush=True)

    if clamped_duration <= 8:
        res = _generate_single_video(
            prompt, effective_image_path, "", clamped_duration, aspect_ratio,
            logo_path, brand_name, brand_colors, company_overview, target_audience,
            products_services, cta_text, negative_prompt, output_dir
        )
    else:
        part1_duration = 8
        part2_duration = max(5, min(8, clamped_duration - 8))

        # Split prompt for 16s: Part 1 gets first-half scenes, Part 2 gets second-half.
        # This prevents both parts from trying to render ALL scenes.
        part1_prompt, part2_prompt = _split_prompt_for_parts(prompt)
        print(f"[VIDEO] 16s split — Part 1 prompt: {len(part1_prompt)} chars, Part 2 prompt: {len(part2_prompt)} chars", file=_sys2.stderr, flush=True)

        print(f"[VIDEO] Generating part 1 (8s) mode={'image_to_video' if effective_image_path else 'text'}", file=_sys2.stderr, flush=True)
        part1_res = _generate_single_video(
            part1_prompt, effective_image_path, "", part1_duration, aspect_ratio,
            logo_path, brand_name, brand_colors, company_overview, target_audience,
            products_services, cta_text, negative_prompt, output_dir
        )

        if part1_res.get("status") != "success":
            return part1_res

        part1_video = part1_res["video_path"]

        import uuid
        from datetime import datetime

        _, _, GENERATED_DIR = _get_config()
        save_dir = output_dir or str(GENERATED_DIR)

        # Part 2: Extract last frame from Part 1 for visual continuity.
        # Part 2 gets 3 reference images: last frame + original product + logo.
        last_frame_path = os.path.join(save_dir, f"frame_{uuid.uuid4().hex[:8]}.jpg")
        print(f"[VIDEO] Extracting last frame from Part 1 for Part 2 reference", file=_sys2.stderr, flush=True)
        try:
            subprocess.run([
                "ffmpeg", "-sseof", "-1", "-i", part1_video,
                "-update", "1", "-q:v", "1", last_frame_path, "-y"
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"[VIDEO] Failed to extract frame: {e}", file=_sys2.stderr, flush=True)
            return {"status": "error", "message": f"Failed to extract frame for Part 2: {e}"}

        # Part 2 needs BOTH the last frame (for visual continuity) AND the original
        # product image (so Veo knows what the product looks like). Without the product
        # image, Veo hallucinates a different product (e.g. bottle instead of saree).
        part2_extra_refs = last_frame_path
        if effective_image_path and effective_image_path != last_frame_path:
            part2_extra_refs = f"{last_frame_path}, {effective_image_path}"
        print(f"[VIDEO] Generating part 2 ({part2_duration}s) with refs: {part2_extra_refs} + logo", file=_sys2.stderr, flush=True)
        part2_res = _generate_single_video(
            prompt=part2_prompt,
            image_path="",
            reference_image_paths=part2_extra_refs,
            duration_seconds=part2_duration,
            aspect_ratio=aspect_ratio,
            logo_path=logo_path,
            brand_name=brand_name,
            brand_colors=brand_colors,
            company_overview=company_overview,
            target_audience=target_audience,
            products_services=products_services,
            cta_text=cta_text,
            negative_prompt=negative_prompt,
            output_dir=output_dir
        )

        if part2_res.get("status") != "success":
            return part2_res

        part2_video = part2_res["video_path"]

        # Clean up extracted frame
        try:
            if os.path.exists(last_frame_path):
                os.remove(last_frame_path)
        except Exception:
            pass

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_filename = f"video_{timestamp}_{uuid.uuid4().hex[:8]}.mp4"
        final_video = os.path.join(save_dir, final_filename)

        # Use xfade crossfade filter (0.5s) for smooth transition between parts
        crossfade_duration = 0.5
        print(f"[VIDEO] Joining parts with {crossfade_duration}s crossfade", file=_sys2.stderr, flush=True)
        try:
            p1_dur = _get_media_duration(part1_video) or float(part1_duration)
            xfade_offset = max(0, p1_dur - crossfade_duration)

            subprocess.run([
                "ffmpeg",
                "-i", part1_video,
                "-i", part2_video,
                "-filter_complex",
                f"[0:v][1:v]xfade=transition=fade:duration={crossfade_duration}:offset={xfade_offset},format=yuv420p[v]",
                "-map", "[v]",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                final_video, "-y"
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            # Fallback to simple concat if xfade fails
            print(f"[VIDEO] Crossfade failed ({e}), falling back to concat", file=_sys2.stderr, flush=True)
            list_path = os.path.join(save_dir, f"list_{uuid.uuid4().hex[:8]}.txt")
            with open(list_path, "w") as f:
                f.write(f"file '{os.path.abspath(part1_video)}'\n")
                f.write(f"file '{os.path.abspath(part2_video)}'\n")
            try:
                subprocess.run([
                    "ffmpeg", "-f", "concat", "-safe", "0", "-i", list_path,
                    "-c", "copy", final_video, "-y"
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e2:
                return {"status": "error", "message": f"Failed to join video parts: {e2}"}
            finally:
                try:
                    os.remove(list_path)
                except Exception:
                    pass

        res = {
            "status": "success",
            "video_path": final_video,
            "filename": final_filename,
            "url": f"/generated/{final_filename}",
            "duration_seconds": clamped_duration,
            "aspect_ratio": aspect_ratio,
            "model": part1_res.get("model", ""),
            "mode": "stitched",
            "branded": bool(logo_path or brand_name),
        }

    if res.get("status") == "success" and audio_script:
        import uuid
        import wave
        from datetime import datetime

        _, _, GENERATED_DIR = _get_config()
        save_dir = output_dir or str(GENERATED_DIR)

        video_path = res["video_path"]

        # Warn if audio script seems too short for the video duration
        word_count = len(audio_script.split())
        expected_min = 25 if clamped_duration > 8 else 12
        if word_count < expected_min:
            print(f"[VIDEO] WARNING: audio script only {word_count} words for {clamped_duration}s video (expected >= {expected_min}). Audio may be stretched.", file=_sys2.stderr, flush=True)
        print(f"[VIDEO] Audio script ({word_count} words for {clamped_duration}s): {audio_script[:150]}", file=_sys2.stderr, flush=True)

        try:
            # Generate voiceover using Gemini TTS — expressive, emotional ad voice
            from app.config import TTS_MODEL, TTS_VOICE
            from google.genai import types as tts_types

            tts_client = _get_client()
            # The audio_script already contains inline emotion/pacing cues
            # like [short pause], [medium pause], [whispering] etc.
            # Just add a light style prefix to set the overall tone.
            tts_prompt = (
                f"Speak as a professional marketing voiceover artist "
                f"with a warm, confident tone: {audio_script}"
            )
            print(f"[VIDEO] Generating TTS with {TTS_MODEL} voice={TTS_VOICE}", file=_sys2.stderr, flush=True)

            tts_response = tts_client.models.generate_content(
                model=TTS_MODEL,
                contents=tts_prompt,
                config=tts_types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=tts_types.SpeechConfig(
                        voice_config=tts_types.VoiceConfig(
                            prebuilt_voice_config=tts_types.PrebuiltVoiceConfig(
                                voice_name=TTS_VOICE,
                            )
                        )
                    ),
                ),
            )

            audio_data = tts_response.candidates[0].content.parts[0].inline_data.data

            # Save as WAV (Gemini TTS returns 24kHz 16-bit PCM)
            audio_path = os.path.join(save_dir, f"audio_{uuid.uuid4().hex[:8]}.wav")
            with wave.open(audio_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(audio_data)

            print(f"[VIDEO] TTS generated: {audio_path}", file=_sys2.stderr, flush=True)

            if os.path.exists(audio_path):
                # Measure video and audio durations for sync
                video_dur = _get_media_duration(video_path)
                audio_dur = _get_media_duration(audio_path)
                print(f"[VIDEO] Duration — video={video_dur:.2f}s audio={audio_dur:.2f}s", file=_sys2.stderr, flush=True)

                video_with_audio_path = os.path.join(save_dir, f"with_audio_{uuid.uuid4().hex[:8]}.mp4")

                if video_dur > 0 and audio_dur > 0 and abs(video_dur - audio_dur) > 0.5:
                    # Stretch/compress audio to match video duration using atempo filter
                    tempo_ratio = audio_dur / video_dur
                    atempo_filters = _build_atempo_chain(tempo_ratio)
                    print(f"[VIDEO] Adjusting audio tempo: ratio={tempo_ratio:.3f} filters={atempo_filters}", file=_sys2.stderr, flush=True)

                    subprocess.run([
                        "ffmpeg", "-i", video_path, "-i", audio_path,
                        "-c:v", "copy", "-filter:a", atempo_filters,
                        "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0",
                        video_with_audio_path, "-y"
                    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    # Durations close enough — merge directly
                    subprocess.run([
                        "ffmpeg", "-i", video_path, "-i", audio_path,
                        "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0",
                        "-shortest", video_with_audio_path, "-y"
                    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                if os.path.exists(video_with_audio_path):
                    try:
                        os.remove(video_path)
                    except:
                        pass
                    res["video_path"] = video_with_audio_path
                    res["filename"] = os.path.basename(video_with_audio_path)
                    res["url"] = f"/generated/{res['filename']}"

                try:
                    os.remove(audio_path)
                except:
                    pass
        except Exception as e:
            import traceback
            print(f"[VIDEO] Failed to generate/merge audio: {e}", file=_sys2.stderr, flush=True)
            traceback.print_exc(file=_sys2.stderr)

    return res
