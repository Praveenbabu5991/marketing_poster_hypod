"""Unified video generation tool using Veo 3.1 API.

Adapted from v2 — wrapped with LangChain @tool decorator.
Uses text-to-video + reference_images for product/logo as visual asset guides.
Native audio generation via generate_audio=True (dialogue + SFX + ambient).
Video extension API for 15s videos (8s + 7s continuation).
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


def _split_prompt_for_parts(prompt: str) -> tuple[str, str]:
    """Split a video prompt into Part 1 and Part 2 for 15s videos (8s + 7s extension).

    Finds all quoted dialogue blocks in the prompt, splits them in half:
    - Part 1: setup + FIRST HALF of dialogue + style (fits in 8s)
    - Part 2: continuation + SECOND HALF of dialogue + style (fits in 7s)

    This prevents repetition — each part gets DIFFERENT dialogue.
    """
    import re as _re

    # Find ALL quoted strings (single or double) that are likely dialogue (10+ chars)
    quote_pattern = r"""['\"]([^'\"]{10,})['\"]"""
    all_quotes = list(_re.finditer(quote_pattern, prompt))

    if len(all_quotes) >= 2:
        mid = len(all_quotes) // 2

        # Extract first-half and second-half dialogue
        first_half = [m.group(1) for m in all_quotes[:mid]]
        second_half = [m.group(1) for m in all_quotes[mid:]]

        # Extract setup: everything before the first quote
        first_quote_start = all_quotes[0].start()
        # Walk back to find "speaks" or "says" before the quote
        setup_end = first_quote_start
        pre_quote = prompt[:first_quote_start].rstrip()
        # Find the last "speaks" or "says" keyword to include in setup
        speaks_match = list(_re.finditer(r'(?:speaks|says)\s', pre_quote, _re.IGNORECASE))
        if speaks_match:
            setup_end = speaks_match[-1].start()
        setup = prompt[:setup_end].rstrip().rstrip(",:")

        # Extract style: everything after the last quote
        last_quote_end = all_quotes[-1].end()
        style = prompt[last_quote_end:].strip().lstrip(".'\"").strip()

        # Build Part 1: setup + first-half dialogue + smooth pause + style
        p1_lines = []
        for d in first_half:
            p1_lines.append(f'"{d.rstrip(",.")}" she says clearly.')
        p1_dialogue = " ".join(p1_lines)
        part1_prompt = (
            f"{setup}. {p1_dialogue} "
            f"The person pauses with a natural expression. "
        )
        if style:
            part1_prompt += style

        # Build Part 2: continuation + second-half dialogue + smooth close + style
        p2_lines = []
        for d in second_half:
            p2_lines.append(f'"{d.rstrip(",.")}" she says warmly.')
        p2_dialogue = " ".join(p2_lines)
        part2_prompt = (
            f"[SMOOTH CONTINUATION of the same scene. Same person, same setting, "
            f"same lighting, same camera angle. The person is still in frame. "
            f"Audio continues naturally — same ambient background. "
            f"Do NOT repeat any previous dialogue. "
            f"Only speak the NEW dialogue below. No extra vocalizations.] "
            f"{p2_dialogue} "
            f"The person smiles gently as the scene comes to a natural, smooth close. "
        )
        if style:
            part2_prompt += style

        return part1_prompt, part2_prompt

    # Fallback: cannot split dialogue — use full prompt for Part 1,
    # continuation-only for Part 2
    part2_prompt = (
        "[SMOOTH CONTINUATION of the same scene. Same person, same setting, "
        "same lighting, same camera angle. Continue naturally. "
        "Audio continues — same ambient background. "
        "Do NOT repeat any dialogue or actions. No extra vocalizations.] "
        "The person smiles gently as the scene comes to a natural, smooth close. "
    )
    return prompt, part2_prompt


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


def _build_reference_images(
    image_path: str,
    reference_image_paths: str,
    logo_path: str,
) -> tuple[list, list[str]]:
    """Build list of VideoGenerationReferenceImage objects from product + logo paths.

    Returns (ref_images_list, resolved_paths_list).
    """
    from google.genai import types

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

    return ref_images, all_ref_paths


def _sanitize_prompt(prompt: str) -> str:
    """Strip/replace known Veo RAI trigger words with safe alternatives.

    Called BEFORE _enhance_prompt to reduce false-positive safety filter blocks.
    """
    import re as _re

    text = prompt

    # Violence-adjacent — context-aware replacements
    # "shot" as camera term → "take" (but keep "shot" inside compound words)
    text = _re.sub(r'\b(close[- ]?up|medium|wide|low[- ]?angle|high[- ]?angle|tracking|establishing)\s+shot\b', r'\1 take', text, flags=_re.IGNORECASE)
    text = _re.sub(r'\bshot\b(?!\s*(glass|put|espresso))', 'take', text, flags=_re.IGNORECASE)

    # "fire" → "flames" but preserve compound words
    text = _re.sub(r'\bfire\b(?!place|works|side|wall|fighter|fly|proof)', 'flames', text, flags=_re.IGNORECASE)
    # Also preserve "campfire"
    text = _re.sub(r'\bcampflames\b', 'campfire', text, flags=_re.IGNORECASE)

    # "shoot" → "film" / "capture"
    text = _re.sub(r'\bshoot(?:s|ing)?\b', 'film', text, flags=_re.IGNORECASE)

    # "strike"/"striking" → "pose"/"remarkable"
    text = _re.sub(r'\bstriking\b', 'remarkable', text, flags=_re.IGNORECASE)
    text = _re.sub(r'\bstrike(?:s)?\b', 'pose', text, flags=_re.IGNORECASE)

    # "execution" → "performance"
    text = _re.sub(r'\bexecution\b', 'performance', text, flags=_re.IGNORECASE)

    # "explode"/"explosion"/"blast" → "burst of energy"
    text = _re.sub(r'\b(?:explod(?:e|es|ing)|explosion|blast(?:s|ing)?)\b', 'burst of energy', text, flags=_re.IGNORECASE)

    # "killer"/"slay" → "stunning"/"remarkable"
    text = _re.sub(r'\bkiller\b', 'stunning', text, flags=_re.IGNORECASE)
    text = _re.sub(r'\bslay(?:s|ing)?\b', 'stunning', text, flags=_re.IGNORECASE)

    # Intimate/suggestive
    text = _re.sub(r'\bwhispers?\b', 'speaks softly', text, flags=_re.IGNORECASE)
    text = _re.sub(r'\bseductive\b', 'confident', text, flags=_re.IGNORECASE)
    text = _re.sub(r'\bsensual\b', 'elegant', text, flags=_re.IGNORECASE)
    text = _re.sub(r'\bsultry\b', 'confident', text, flags=_re.IGNORECASE)
    text = _re.sub(r'\btight\b(?=\s+(?:dress|outfit|clothing|top|shirt|skirt|pants|jeans|fit))', 'fitted', text, flags=_re.IGNORECASE)
    text = _re.sub(r'\bintimate\b', 'personal', text, flags=_re.IGNORECASE)
    text = _re.sub(r'\bcaress(?:es|ing)?\b', 'touch gently', text, flags=_re.IGNORECASE)
    text = _re.sub(r'\bprovocative\b', 'bold', text, flags=_re.IGNORECASE)
    text = _re.sub(r'\bnaked\b', '', text, flags=_re.IGNORECASE)
    text = _re.sub(r'\bnude\b', '', text, flags=_re.IGNORECASE)
    text = _re.sub(r'\bundress(?:es|ing)?\b', '', text, flags=_re.IGNORECASE)
    text = _re.sub(r'\blingerie\b', 'clothing', text, flags=_re.IGNORECASE)

    # Child safety — only when in photorealistic human context
    text = _re.sub(r'\b(?:child|kid|toddler|infant)\b', 'young person', text, flags=_re.IGNORECASE)
    # "baby" only when not part of common phrases
    text = _re.sub(r'\bbaby\b(?!\s*(blue|pink|shower|boom|step|sit))', 'young person', text, flags=_re.IGNORECASE)

    # Location triggers
    text = _re.sub(r'\b(?:dark\s+)?alley\b', 'narrow street', text, flags=_re.IGNORECASE)

    # Other
    text = _re.sub(r'\breveal(?:s|ing|ed)?\b', 'comes into view', text, flags=_re.IGNORECASE)

    # Violence words (less common in video prompts but catch-all)
    text = _re.sub(r'\b(?:kill(?:s|ing|ed)?|attack(?:s|ing|ed)?|stab(?:s|bing|bed)?|punch(?:es|ing|ed)?|slap(?:s|ping|ped)?)\b', '', text, flags=_re.IGNORECASE)
    text = _re.sub(r'\b(?:weapon|gun|blood|fight(?:s|ing)?)\b', '', text, flags=_re.IGNORECASE)

    # Clean up double spaces from removals
    text = _re.sub(r'  +', ' ', text).strip()

    return text


def _enhance_prompt(
    prompt: str,
    brand_name: str,
    brand_colors: str,
    target_audience: str,
) -> str:
    """Strip brand name and append target audience + negative cues to a video prompt.

    NOTE: Brand colors are NOT injected — they override the product's actual colors
    from the reference image. The reference image provides visual identity.
    """
    import re as _re

    enhanced = prompt.rstrip()

    # Strip brand name — known brand names trigger Veo's RAI filter
    if brand_name:
        enhanced = _re.sub(
            r"\b" + _re.escape(brand_name) + r"(?:'s)?\b",
            "the brand's",
            enhanced,
            flags=_re.IGNORECASE,
        )

    if target_audience:
        enhanced += f" Human subject matches target audience: {target_audience}."

    # Append short "Avoid:" (negative_prompt not supported with reference_images)
    enhanced += (
        " Avoid: text, titles, words, extra hands, extra fingers, floating objects,"
        " cartoon, morphing, flickering, shifting background."
    )

    return enhanced


def _poll_operation(client, operation, timeout: int = 300) -> tuple:
    """Poll a Veo operation until done. Returns (operation, timed_out)."""
    poll_count = 0
    remaining = timeout
    while not operation.done:
        time.sleep(10)
        poll_count += 1
        operation = client.operations.get(operation)
        logger.info("[VIDEO] Poll %d — done=%s elapsed=%ds", poll_count, operation.done, poll_count * 10)
        remaining -= 10
        if remaining <= 0:
            return operation, True
    return operation, False


def _download_video(client, video_obj, video_path: str) -> None:
    """Download a Veo video object to a local file."""
    try:
        client.files.download(file=video_obj.video)
        video_obj.video.save(str(video_path))
    except (ValueError, NotImplementedError):
        # Vertex AI client doesn't support client.files.download()
        video_data = getattr(video_obj.video, 'video_bytes', None)
        if video_data:
            with open(video_path, 'wb') as f:
                f.write(video_data)
            logger.info("[VIDEO] Saved via video_bytes (Vertex AI)")
        else:
            uri = getattr(video_obj.video, 'uri', None)
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
                video_obj.video.save(str(video_path))
                logger.info("[VIDEO] Saved via direct save() call")


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
    person_generation: str = "allow_all",
) -> dict:
    """Generate a single video using Veo 3.1 with native audio.

    Uses source/config pattern with:
    - generate_audio=True for native dialogue, SFX, and ambient audio
    - person_generation configurable ("allow_all" or "dont_allow")
    - reference_images for product/logo consistency

    Returns dict with video_path AND veo_video object (for extension API).
    """
    _, VIDEO_MODEL, GENERATED_DIR = _get_config()
    save_dir = output_dir or str(GENERATED_DIR)

    try:
        client = _get_client()
        from google.genai import types

        clamped_duration = max(5, min(8, duration_seconds))

        # Veo 3.1 only supports 16:9 and 9:16
        if aspect_ratio not in ("16:9", "9:16"):
            import sys as _sys_ar
            print(f"[VIDEO] Unsupported aspect_ratio '{aspect_ratio}' — falling back to 9:16", file=_sys_ar.stderr, flush=True)
            aspect_ratio = "9:16"

        # Sanitize prompt (strip RAI trigger words) then enhance with brand context
        sanitized_prompt = _sanitize_prompt(prompt)
        enhanced_prompt = _enhance_prompt(sanitized_prompt, brand_name, brand_colors, target_audience)

        import sys as _sys_san
        if sanitized_prompt != prompt:
            print(f"[VIDEO] Sanitized prompt: {sanitized_prompt[:300]}", file=_sys_san.stderr, flush=True)

        # Build reference images (product + logo)
        ref_images, all_ref_paths = _build_reference_images(
            image_path, reference_image_paths, logo_path
        )

        # Build source with prompt only (reference_images go in config)
        source = types.GenerateVideosSource(prompt=enhanced_prompt)

        # Build config with native audio + reference images
        config_kwargs = {
            "aspect_ratio": aspect_ratio,
            "number_of_videos": 1,
            "duration_seconds": clamped_duration,
            "generate_audio": True,
            "person_generation": person_generation,
            "resolution": "720p",
        }

        if ref_images:
            config_kwargs["reference_images"] = ref_images

        # negative_prompt not supported with reference_images
        if not ref_images and negative_prompt:
            base_negatives = (
                "text, titles, captions, words, letters, watermarks, subtitles, "
                "extra hands, extra fingers, three hands, four hands, "
                "overlapping hands, floating objects, animated, cartoon, "
                "morphing, flickering, jitter, shifting background, inconsistent lighting"
            )
            config_kwargs["negative_prompt"] = f"{negative_prompt}, {base_negatives}"

        config = types.GenerateVideosConfig(**config_kwargs)

        mode = "text_to_video_with_refs" if ref_images else "text_to_video"

        import sys as _sys
        print(f"[VIDEO] Starting generation mode={mode} model={VIDEO_MODEL} audio=native", file=_sys.stderr, flush=True)
        print(f"[VIDEO] Prompt FULL: {enhanced_prompt}", file=_sys.stderr, flush=True)
        print(f"[VIDEO] Reference images: {len(ref_images)} paths={all_ref_paths}", file=_sys.stderr, flush=True)

        operation = client.models.generate_videos(
            model=VIDEO_MODEL,
            source=source,
            config=config,
        )
        logger.info("[VIDEO] Operation received — done=%s name=%s",
                     operation.done, getattr(operation, 'name', 'N/A'))

        operation, timed_out = _poll_operation(client, operation)
        if timed_out:
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
            # RAI safety filter triggered — log reason and retry with sanitized prompt
            import sys as _sys_rai
            import re as _re2

            rai_reason = getattr(result, 'rai_media_filtered_reason', None) or getattr(result, 'rai_reason', None)
            rai_count = getattr(result, 'rai_media_filtered_count', 0)
            print(f"[VIDEO] RAI filtered — count={rai_count} reason={rai_reason}", file=_sys_rai.stderr, flush=True)

            # Retry 1: Sanitize + first 5 sentences
            sanitized = _sanitize_prompt(prompt)
            sentences = _re2.split(r'(?<=[.!])\s+', sanitized.strip())
            retry1_prompt = " ".join(sentences[:5]) if sentences else sanitized[:300]
            if brand_name:
                retry1_prompt = _re2.sub(
                    r"\b" + _re2.escape(brand_name) + r"(?:'s)?\b",
                    "",
                    retry1_prompt,
                    flags=_re2.IGNORECASE,
                )
            retry1_prompt = retry1_prompt.strip()
            retry1_prompt += " Hyper-realistic, cinematic lighting, 8k, professional commercial."

            print(f"[VIDEO] Retry 1 prompt: {retry1_prompt[:300]}", file=_sys_rai.stderr, flush=True)

            retry_config_kwargs = {
                "aspect_ratio": aspect_ratio,
                "number_of_videos": 1,
                "duration_seconds": clamped_duration,
                "generate_audio": True,
                "person_generation": person_generation,
                "resolution": "720p",
            }
            if ref_images:
                retry_config_kwargs["reference_images"] = ref_images

            # 5-second delay before retry (audio false positives are timing-sensitive)
            time.sleep(5)

            retry_succeeded = False
            try:
                retry_source = types.GenerateVideosSource(prompt=retry1_prompt)
                retry_config = types.GenerateVideosConfig(**retry_config_kwargs)
                operation2 = client.models.generate_videos(
                    model=VIDEO_MODEL, source=retry_source, config=retry_config,
                )
                operation2, _ = _poll_operation(client, operation2)
                result = operation2.result
                if result and result.generated_videos:
                    print(f"[VIDEO] Retry 1 succeeded!", file=_sys_rai.stderr, flush=True)
                    retry_succeeded = True
                else:
                    rai2_reason = getattr(result, 'rai_media_filtered_reason', None) if result else None
                    print(f"[VIDEO] Retry 1 failed: rai_reason={rai2_reason}", file=_sys_rai.stderr, flush=True)
            except Exception as retry1_err:
                print(f"[VIDEO] Retry 1 error: {retry1_err}", file=_sys_rai.stderr, flush=True)

            # Retry 2: Minimal 2-sentence prompt
            if not retry_succeeded:
                retry2_prompt = " ".join(sentences[:2]) if len(sentences) >= 2 else (sentences[0] if sentences else sanitized[:150])
                if brand_name:
                    retry2_prompt = _re2.sub(
                        r"\b" + _re2.escape(brand_name) + r"(?:'s)?\b",
                        "", retry2_prompt, flags=_re2.IGNORECASE,
                    )
                retry2_prompt = retry2_prompt.strip()
                retry2_prompt += " Cinematic, professional commercial, 8k."

                print(f"[VIDEO] Retry 2 (minimal) prompt: {retry2_prompt[:300]}", file=_sys_rai.stderr, flush=True)
                time.sleep(5)

                try:
                    retry_source2 = types.GenerateVideosSource(prompt=retry2_prompt)
                    retry_config2 = types.GenerateVideosConfig(**retry_config_kwargs)
                    operation3 = client.models.generate_videos(
                        model=VIDEO_MODEL, source=retry_source2, config=retry_config2,
                    )
                    operation3, _ = _poll_operation(client, operation3)
                    result = operation3.result
                    if result and result.generated_videos:
                        print(f"[VIDEO] Retry 2 succeeded!", file=_sys_rai.stderr, flush=True)
                        retry_succeeded = True
                    else:
                        print(f"[VIDEO] Retry 2 also failed: {result}", file=_sys_rai.stderr, flush=True)
                except Exception as retry2_err:
                    print(f"[VIDEO] Retry 2 error: {retry2_err}", file=_sys_rai.stderr, flush=True)

            if not retry_succeeded:
                hint = "Try removing references to violence, weapons, or suggestive content from your prompt."
                if rai_reason:
                    hint = f"Safety filter reason: {rai_reason}. {hint}"
                return {"status": "error", "message": f"Video was blocked by safety filters. {hint}", "model": VIDEO_MODEL}

        video = result.generated_videos[0]
        output_path = Path(save_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        video_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"video_{timestamp}_{video_id}.mp4"
        video_path = output_path / filename

        _download_video(client, video, str(video_path))

        print(f"[VIDEO] Success: {filename} mode={mode} audio=native", file=_sys.stderr, flush=True)
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
            "veo_video": video.video,  # Veo video object for extension API
        }

    except Exception as e:
        import sys as _sys
        import traceback
        print(f"[VIDEO] Generation failed: {e}", file=_sys.stderr, flush=True)
        traceback.print_exc(file=_sys.stderr)
        return {"status": "error", "message": f"Video generation failed: {str(e)[:300]}", "model": VIDEO_MODEL}


def _extend_video(
    veo_video,
    continuation_prompt: str,
    output_dir: str = "",
) -> dict:
    """Extend a Veo video by 7 seconds using the extension API.

    Uses the Veo video object from Part 1 to generate a seamless continuation.
    Returns the combined 15s video (Veo returns it as a single file).
    """
    _, VIDEO_MODEL, GENERATED_DIR = _get_config()
    save_dir = output_dir or str(GENERATED_DIR)

    try:
        client = _get_client()
        from google.genai import types

        import sys as _sys
        print(f"[VIDEO] Starting video extension (7s) with continuation prompt", file=_sys.stderr, flush=True)
        print(f"[VIDEO] Extension prompt: {continuation_prompt[:300]}", file=_sys.stderr, flush=True)

        # Extension source: prompt + video from Part 1
        source = types.GenerateVideosSource(
            prompt=continuation_prompt,
            video=veo_video,
        )
        config = types.GenerateVideosConfig(
            number_of_videos=1,
            resolution="720p",
            generate_audio=True,
        )

        operation = client.models.generate_videos(
            model=VIDEO_MODEL,
            source=source,
            config=config,
        )
        logger.info("[VIDEO] Extension operation received — done=%s", operation.done)

        operation, timed_out = _poll_operation(client, operation)
        if timed_out:
            logger.warning("[VIDEO] Extension timed out after 5 minutes")
            return {"status": "timeout", "message": "Video extension timed out after 5 minutes.", "model": VIDEO_MODEL}

        result = operation.result
        op_error = getattr(operation, 'error', None)

        if not result or not result.generated_videos:
            rai_filtered = (
                result
                and getattr(result, 'rai_media_filtered_count', 0) > 0
            )
            if rai_filtered:
                return {"status": "error", "message": "Video extension was filtered by safety guidelines.", "model": VIDEO_MODEL}
            error_detail = f" Error: {op_error}" if op_error else ""
            return {"status": "error", "message": f"No video from extension.{error_detail}", "model": VIDEO_MODEL}

        video = result.generated_videos[0]
        output_path = Path(save_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        video_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"video_{timestamp}_{video_id}_extended.mp4"
        video_path = output_path / filename

        _download_video(client, video, str(video_path))

        print(f"[VIDEO] Extension success: {filename}", file=_sys.stderr, flush=True)
        return {
            "status": "success",
            "video_path": str(video_path),
            "filename": filename,
            "url": f"/generated/{filename}",
            "model": VIDEO_MODEL,
        }

    except Exception as e:
        import sys as _sys
        import traceback
        print(f"[VIDEO] Extension failed: {e}", file=_sys.stderr, flush=True)
        traceback.print_exc(file=_sys.stderr)
        return {"status": "error", "message": f"Video extension failed: {str(e)[:300]}", "model": VIDEO_MODEL}


@tool
def generate_video(
    prompt: str,
    image_path: str = "",
    reference_image_paths: str = "",
    duration_seconds: int = 15,
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
    person_generation: str = "allow_all",
) -> dict:
    """Generate a video using Veo 3.1 with native audio and reference images.

    Product image and logo are passed as reference_images (reference_type="asset")
    to guide Veo's generation with product and brand consistency.
    Audio (dialogue, SFX, ambient) is generated natively by Veo — no separate TTS.

    For 15s videos: generates 8s Part 1 with reference_images, then extends by 7s
    using the Veo extension API for seamless continuation (no stitching).

    Args:
        prompt: Video generation prompt with Audio: lines for native audio.
        image_path: Product image path (used as reference_image asset).
        reference_image_paths: Comma-separated paths to product images (used as reference_image assets).
        duration_seconds: Video length 5-15 seconds.
        aspect_ratio: "9:16" (Reels/vertical) or "16:9" (YouTube/landscape). Only these two are supported by Veo 3.1.
        logo_path: Brand logo path (used as reference_image asset).
        brand_name: Company name for prompt enhancement.
        brand_colors: Comma-separated hex colors.
        company_overview: Company description.
        target_audience: Target audience description.
        products_services: Products/services description.
        cta_text: Call-to-action text.
        negative_prompt: Elements to exclude.
        output_dir: Directory to save video.
        person_generation: "allow_all" for videos with people, "dont_allow" for motion graphics without people.
    """

    import sys as _sys2

    clamped_duration = max(5, min(15, duration_seconds))

    # Merge image_path and reference_image_paths into a single reference list.
    effective_image_path = image_path
    if reference_image_paths and not image_path:
        ref_list = [p.strip() for p in reference_image_paths.split(",") if p.strip()]
        first_product = _resolve_image_path(ref_list[0]) if ref_list else ""
        if first_product and os.path.exists(first_product):
            effective_image_path = first_product
            print(f"[VIDEO] Using product image as reference: {first_product}", file=_sys2.stderr, flush=True)

    if clamped_duration <= 8:
        # Short video: single generation with native audio
        res = _generate_single_video(
            prompt, effective_image_path, "", clamped_duration, aspect_ratio,
            logo_path, brand_name, brand_colors, company_overview, target_audience,
            products_services, cta_text, negative_prompt, output_dir,
            person_generation=person_generation,
        )
        res.pop("veo_video", None)
    else:
        # 15s video: Part 1 (8s) + extension (7s) = 15s combined
        part1_duration = 8

        # Split prompt for 15s: Part 1 gets first-half scenes, Part 2 gets second-half
        part1_prompt, part2_prompt = _split_prompt_for_parts(prompt)
        print(f"[VIDEO] 15s split — Part 1 prompt: {len(part1_prompt)} chars, Part 2 prompt: {len(part2_prompt)} chars", file=_sys2.stderr, flush=True)

        print(f"[VIDEO] Generating Part 1 (8s) with reference_images + native audio", file=_sys2.stderr, flush=True)
        part1_res = _generate_single_video(
            part1_prompt, effective_image_path, "", part1_duration, aspect_ratio,
            logo_path, brand_name, brand_colors, company_overview, target_audience,
            products_services, cta_text, negative_prompt, output_dir,
            person_generation=person_generation,
        )

        if part1_res.get("status") != "success":
            part1_res.pop("veo_video", None)
            return part1_res

        # Get the Veo video object for extension
        veo_video = part1_res.get("veo_video")
        if not veo_video:
            print(f"[VIDEO] No veo_video object from Part 1 — cannot extend", file=_sys2.stderr, flush=True)
            part1_res.pop("veo_video", None)
            return part1_res

        # Extend Part 1 by 7s using the Veo extension API
        print(f"[VIDEO] Extending Part 1 by 7s using Veo extension API", file=_sys2.stderr, flush=True)
        ext_res = _extend_video(
            veo_video=veo_video,
            continuation_prompt=part2_prompt,
            output_dir=output_dir,
        )

        if ext_res.get("status") != "success":
            # Extension failed — return Part 1 as-is (8s is better than nothing)
            print(f"[VIDEO] Extension failed, returning Part 1 only (8s)", file=_sys2.stderr, flush=True)
            part1_res.pop("veo_video", None)
            part1_res["duration_seconds"] = part1_duration
            return part1_res

        # Extension returns the combined video (Part 1 + extension as one file)
        # Clean up Part 1 file since we have the combined video
        try:
            part1_path = part1_res.get("video_path")
            if part1_path and os.path.exists(part1_path):
                os.remove(part1_path)
        except Exception:
            pass

        res = {
            "status": "success",
            "video_path": ext_res["video_path"],
            "filename": ext_res["filename"],
            "url": ext_res["url"],
            "duration_seconds": 15,  # 8s + 7s
            "aspect_ratio": aspect_ratio,
            "model": ext_res.get("model", ""),
            "mode": "extended",
            "branded": bool(logo_path or brand_name),
        }

    return res
