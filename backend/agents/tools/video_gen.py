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



def _get_api_keys():
    from app.config import GOOGLE_API_KEY
    runway_key = os.getenv("RUNWAY_API_KEY", "")
    kling_key = os.getenv("KLING_API_KEY", "")
    return GOOGLE_API_KEY, runway_key, kling_key

def _generate_runway_video(
    prompt: str,
    image_path: str = "",
    duration_seconds: int = 10,
    aspect_ratio: str = "9:16",
    output_dir: str = "",
) -> dict:
    _, RUNWAY_API_KEY, _ = _get_api_keys()
    _, VIDEO_MODEL, GENERATED_DIR = _get_config()
    save_dir = output_dir or str(GENERATED_DIR)
    
    if not RUNWAY_API_KEY:
        return {"status": "error", "message": "RUNWAY_API_KEY not configured", "model": VIDEO_MODEL}
        
    import base64
    import httpx
    
    clamped_duration = 10 if duration_seconds > 5 else 5
    
    headers = {
        "Authorization": f"Bearer {RUNWAY_API_KEY}",
        "X-Runway-Version": "2024-11-06"
    }
    
    payload = {
        "model": "gen3a_turbo",
        "promptText": prompt,
    }
    
    # Runway requires promptImage as a data URI
    if image_path:
        import mimetypes
        from PIL import Image
        import io
        resolved_img = _resolve_image_path(image_path)
        if os.path.exists(resolved_img):
            mime_type, _ = mimetypes.guess_type(resolved_img)
            mime_type = mime_type or "image/jpeg"
            
            target_size = (768, 1280) if aspect_ratio == "9:16" else (1280, 768) if aspect_ratio == "16:9" else (1024, 1024)
            img = Image.open(resolved_img)
            img_resized = img.resize(target_size, Image.LANCZOS)
            
            if img_resized.mode in ("RGBA", "LA", "P") and mime_type == "image/jpeg":
                img_resized = img_resized.convert("RGB")
                
            buf = io.BytesIO()
            if mime_type == "image/webp":
                format_str = "WEBP"
            elif "jpeg" in mime_type or "jpg" in mime_type:
                format_str = "JPEG"
            else:
                format_str = "PNG"
            
            img_resized.save(buf, format=format_str)
            b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            
            payload["promptImage"] = f"data:{mime_type};base64,{b64}"
            
    # For text-to-video, Runway requires ratio if no image
    if not image_path:
        ratio_map = {"9:16": "768:1280", "16:9": "1280:768", "1:1": "1024:1024"}
        payload["ratio"] = ratio_map.get(aspect_ratio, "768:1280")
        
    try:
        print(f"[RUNWAY] Starting task...", flush=True)
        res = httpx.post("https://api.dev.runwayml.com/v1/image_to_video", json=payload, headers=headers, timeout=120.0)
        if res.status_code != 200:
            return {"status": "error", "message": f"Runway API Error: {res.text}", "model": VIDEO_MODEL}
            
        task_id = res.json().get("id")
        
        # Poll for completion
        max_wait = 300
        while max_wait > 0:
            time.sleep(10)
            max_wait -= 10
            status_res = httpx.get(f"https://api.dev.runwayml.com/v1/tasks/{task_id}", headers=headers, timeout=120.0)
            if status_res.status_code == 200:
                status_data = status_res.json()
                status = status_data.get("status")
                if status == "SUCCEEDED":
                    video_url = status_data.get("output", [])[0]
                    
                    # Download the video
                    output_path = Path(save_dir)
                    output_path.mkdir(parents=True, exist_ok=True)
                    filename = f"runway_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}.mp4"
                    video_path = output_path / filename
                    
                    vid_res = httpx.get(video_url, timeout=120.0)
                    with open(video_path, 'wb') as f:
                        f.write(vid_res.content)
                        
                    print(f"[RUNWAY] Success: {filename}", flush=True)
                    return {
                        "status": "success",
                        "video_path": str(video_path),
                        "filename": filename,
                        "url": f"/generated/{filename}",
                        "duration_seconds": clamped_duration,
                        "model": "runwayml/gen3a-turbo"
                    }
                elif status in ["FAILED", "CANCELLED"]:
                    return {"status": "error", "message": f"Runway Task {status}: {status_data.get('failure', 'Unknown')}", "model": VIDEO_MODEL}
                    
        return {"status": "timeout", "message": "Runway generation timed out", "model": VIDEO_MODEL}
    except Exception as e:
        return {"status": "error", "message": f"Runway integration error: {str(e)}", "model": VIDEO_MODEL}


def _generate_kling_video(
    prompt: str,
    image_path: str = "",
    duration_seconds: int = 10,
    aspect_ratio: str = "9:16",
    output_dir: str = "",
) -> dict:
    _, _, KLING_API_KEY = _get_api_keys()
    _, VIDEO_MODEL, GENERATED_DIR = _get_config()
    save_dir = output_dir or str(GENERATED_DIR)
    
    if not KLING_API_KEY:
        return {"status": "error", "message": "KLING_API_KEY not configured", "model": VIDEO_MODEL}
        
    # Kling uses AK/SK separated by colon
    if ":" not in KLING_API_KEY:
        return {"status": "error", "message": "KLING_API_KEY must be format AccessKey:SecretKey", "model": VIDEO_MODEL}
        
    ak, sk = KLING_API_KEY.split(":", 1)
    
    import jwt
    import httpx
    import base64
    
    # Generate JWT for Kling
    now = int(time.time())
    headers = {"alg": "HS256", "typ": "JWT"}
    payload = {"iss": ak, "exp": now + 1800, "nbf": now - 5}
    token = jwt.encode(payload, sk, algorithm="HS256", headers=headers)
    
    clamped_duration = "10" if duration_seconds > 5 else "5"
    ratio_map = {"9:16": "9:16", "16:9": "16:9", "1:1": "1:1"}
    
    req_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    if image_path:
        endpoint = "https://open.klingai.com/v1/videos/image2video"
        resolved_img = _resolve_image_path(image_path)
        with open(resolved_img, "rb") as f:
            b64 = base64.b64encode(f.read()).decode('utf-8')
        payload_data = {
            "model": "kling-v1",
            "image": b64,
            "prompt": prompt,
            "duration": clamped_duration
        }
    else:
        endpoint = "https://open.klingai.com/v1/videos/text2video"
        payload_data = {
            "model": "kling-v1",
            "prompt": prompt,
            "aspect_ratio": ratio_map.get(aspect_ratio, "9:16"),
            "duration": clamped_duration
        }
        
    try:
        print(f"[KLING] Starting task...", flush=True)
        res = httpx.post(endpoint, json=payload_data, headers=req_headers, timeout=120.0)
        if res.status_code != 200:
            return {"status": "error", "message": f"Kling API Error: {res.text}", "model": VIDEO_MODEL}
            
        task_id = res.json().get("data", {}).get("task_id")
        if not task_id:
            return {"status": "error", "message": f"Kling API Error: No task ID returned. {res.text}", "model": VIDEO_MODEL}
            
        # Poll for completion
        max_wait = 300
        while max_wait > 0:
            time.sleep(10)
            max_wait -= 10
            # Token might expire if polling takes >30min, regenerate if needed
            now = int(time.time())
            poll_token = jwt.encode({"iss": ak, "exp": now + 1800, "nbf": now - 5}, sk, algorithm="HS256", headers={"alg": "HS256", "typ": "JWT"})
            poll_headers = {"Authorization": f"Bearer {poll_token}", "Content-Type": "application/json"}
            
            status_res = httpx.get(f"{endpoint}/{task_id}", headers=poll_headers, timeout=120.0)
            if status_res.status_code == 200:
                status_data = status_res.json().get("data", {})
                status = status_data.get("task_status")
                
                if status == "succeed":
                    video_url = status_data.get("task_result", {}).get("videos", [{}])[0].get("url")
                    
                    # Download the video
                    output_path = Path(save_dir)
                    output_path.mkdir(parents=True, exist_ok=True)
                    filename = f"kling_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}.mp4"
                    video_path = output_path / filename
                    
                    vid_res = httpx.get(video_url, timeout=120.0)
                    with open(video_path, 'wb') as f:
                        f.write(vid_res.content)
                        
                    print(f"[KLING] Success: {filename}", flush=True)
                    return {
                        "status": "success",
                        "video_path": str(video_path),
                        "filename": filename,
                        "url": f"/generated/{filename}",
                        "duration_seconds": int(clamped_duration),
                        "model": "kling/kling-v1"
                    }
                elif status in ["failed", "killed"]:
                    return {"status": "error", "message": f"Kling Task {status}: {status_data.get('task_status_msg', 'Unknown')}", "model": VIDEO_MODEL}
                    
        return {"status": "timeout", "message": "Kling generation timed out", "model": VIDEO_MODEL}
    except Exception as e:
        return {"status": "error", "message": f"Kling integration error: {str(e)}", "model": VIDEO_MODEL}

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
    _, VIDEO_MODEL, _ = _get_config()
    
    # Add logo using PIL for Mode B if logo exists (Runway/Kling/Veo all benefit from this)
    effective_image_path = image_path
    if image_path and logo_path:
        try:
            resolved_img = _resolve_image_path(image_path)
            if os.path.exists(resolved_img):
                source_image = Image.open(resolved_img)
                if source_image.mode in ("RGBA", "LA", "P"):
                    source_image = source_image.convert("RGB")
                composited = _composite_logo_onto_image(source_image, logo_path, brand_name)
                # Save composited to a temp file
                import uuid
                temp_img = os.path.join(output_dir or os.getcwd(), f"temp_{uuid.uuid4().hex[:8]}.jpg")
                composited.save(temp_img, format="JPEG")
                effective_image_path = temp_img
        except Exception as e:
            print(f"[VIDEO] Logo composite warning: {e}", flush=True)

    try:
        if VIDEO_MODEL.startswith("runway"):
            res = _generate_runway_video(prompt, effective_image_path, duration_seconds, aspect_ratio, output_dir)
        elif VIDEO_MODEL.startswith("kling"):
            res = _generate_kling_video(prompt, effective_image_path, duration_seconds, aspect_ratio, output_dir)
        else:
            res = _generate_veo_video(
                prompt, effective_image_path, reference_image_paths, duration_seconds, aspect_ratio,
                "", brand_name, brand_colors, company_overview, target_audience,
                products_services, cta_text, negative_prompt, output_dir, audio_script
            )
            
        # Clean up temp image
        if effective_image_path and effective_image_path != image_path and os.path.exists(effective_image_path):
            try:
                os.remove(effective_image_path)
            except:
                pass
                
        return res
    except Exception as e:
        return {"status": "error", "message": f"Router exception: {str(e)}", "model": VIDEO_MODEL}


def _generate_veo_video(
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
        # The LLM agent prompt already writes detailed video prompts; tool-level additions
        # should be brief (brand colors, target audience) not multi-paragraph constraints.
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

        # Short guidance (no RAI-triggering words)
        if image_path:
            brand_narrative.append(
                "The starting image shows the actual product — keep it clearly visible and "
                "recognizable throughout. Animate around it without replacing or transforming it. "
                "CRITICAL COLOR CONSISTENCY: The product's exact colors from the starting image "
                "must remain identical in every frame — do not change, shift, lighten, or darken "
                "the product's colors at any point. The product in frame 100 must look exactly "
                "the same color as in frame 1."
            )

        brand_narrative.append(
            "One pair of hands, one simple action per shot. Stable background, consistent lighting."
        )

        enhanced_prompt = prompt.rstrip()
        # Strip brand name from prompt — known brand names (e.g. "H&M", "Nike")
        # trigger Veo's RAI filter for brand impersonation. Veo can't render text
        # anyway; the logo is composited via PIL in Mode B.
        if brand_name:
            import re as _re
            # Remove brand name (case-insensitive, whole word or with possessives)
            enhanced_prompt = _re.sub(
                r"\b" + _re.escape(brand_name) + r"(?:'s)?\b",
                "the brand's",
                enhanced_prompt,
                flags=_re.IGNORECASE,
            )
        if brand_narrative:
            enhanced_prompt += " " + " ".join(brand_narrative)

        # Two tiers of negatives:
        # - base_negatives: RAI-safe, can go in negative_prompt API param (Mode B)
        # - For Mode A (refs), only a SHORT "Avoid:" is appended to prompt text
        base_negatives = (
            "text, titles, captions, words, letters, watermarks, subtitles, "
            "misspelled text, extra hands, extra fingers, three hands, four hands, "
            "overlapping hands, floating objects, animated, cartoon, "
            "morphing, flickering, jitter, shifting background, inconsistent lighting"
        )
        if negative_prompt:
            full_negative = f"{negative_prompt}, {base_negatives}"
        else:
            full_negative = base_negatives

        gen_kwargs = {"model": VIDEO_MODEL, "prompt": enhanced_prompt}

        if image_path:
            # Mode B: image-to-video — product image as starting frame
            resolved_img = _resolve_image_path(image_path)
            if not os.path.exists(resolved_img):
                return {"status": "error", "message": f"Source image not found: {image_path}", "model": VIDEO_MODEL}

            source_image = Image.open(resolved_img)
            if source_image.mode in ("RGBA", "LA", "P"):
                source_image = source_image.convert("RGB")

            # Composite logo onto the product image so both appear in the starting frame
            if logo_path:
                source_image = _composite_logo_onto_image(source_image, logo_path, brand_name)

            buf = io.BytesIO()
            source_image.save(buf, format="JPEG")
            gen_kwargs["image"] = types.Image(image_bytes=buf.getvalue(), mime_type="image/jpeg")
            config_kwargs["negative_prompt"] = full_negative
            mode = "image_to_video"

        else:
            # Pure text-to-video (no product image)
            config_kwargs["negative_prompt"] = full_negative
            mode = "text_to_video"

        gen_kwargs["config"] = types.GenerateVideosConfig(**config_kwargs)

        import sys as _sys
        print(f"[VIDEO] Starting generation mode={mode} model={VIDEO_MODEL}", file=_sys.stderr, flush=True)
        print(f"[VIDEO] Prompt (first 300 chars): {enhanced_prompt[:300]}", file=_sys.stderr, flush=True)
        if "reference_images" in config_kwargs:
            print(f"[VIDEO] Reference images: {len(config_kwargs['reference_images'])}", file=_sys.stderr, flush=True)
        else:
            print(f"[VIDEO] No reference images in config", file=_sys.stderr, flush=True)

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
            if image_path:
                # Re-use the same image for Mode B
                retry_kwargs["image"] = gen_kwargs.get("image")
                retry_config["negative_prompt"] = full_negative
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
        audio_script: Voiceover text to generate and merge into the video.
    """
    
    import sys as _sys2

    clamped_duration = max(5, min(16, duration_seconds))

    # Convert Mode A → Mode B: use the product image as the starting frame.
    # Mode A reference_images is unreliable — Veo generates different colored products.
    # Mode B (image=) guarantees the exact uploaded product appears in the video.
    # Logo is composited onto the product image via PIL so both appear in starting frame.
    effective_image_path = image_path
    if reference_image_paths and not image_path:
        ref_list = [p.strip() for p in reference_image_paths.split(",") if p.strip()]
        first_product = _resolve_image_path(ref_list[0]) if ref_list else ""
        if first_product and os.path.exists(first_product):
            effective_image_path = first_product
            print(f"[VIDEO] Mode A → Mode B: product image as starting frame: {first_product}", file=_sys2.stderr, flush=True)

    _, VIDEO_MODEL, _ = _get_config()
    max_native_duration = 10 if (VIDEO_MODEL.startswith("runway") or VIDEO_MODEL.startswith("kling")) else 8
    
    if clamped_duration <= max_native_duration:
        res = _generate_single_video(
            prompt, effective_image_path, "", clamped_duration, aspect_ratio,
            logo_path, brand_name, brand_colors, company_overview, target_audience,
            products_services, cta_text, negative_prompt, output_dir
        )
    else:
        part1_duration = max_native_duration
        part2_duration = max(5, min(max_native_duration, clamped_duration - max_native_duration))

        print(f"[VIDEO] Generating part 1 (8s) mode={'image_to_video' if effective_image_path else 'text'}", file=_sys2.stderr, flush=True)
        part1_res = _generate_single_video(
            prompt, effective_image_path, "", part1_duration, aspect_ratio,
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

        # Part 2: Extract last frame from Part 1 → Mode B continuation.
        # Same product image ensures visual consistency between parts.
        last_frame_path = os.path.join(save_dir, f"frame_{uuid.uuid4().hex[:8]}.jpg")
        print(f"[VIDEO] Extracting last frame from Part 1 for continuation", file=_sys2.stderr, flush=True)
        try:
            subprocess.run([
                "ffmpeg", "-sseof", "-1", "-i", part1_video,
                "-update", "1", "-q:v", "1", last_frame_path, "-y"
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"[VIDEO] Failed to extract frame: {e}", file=_sys2.stderr, flush=True)
            return {"status": "error", "message": f"Failed to extract frame for Part 2: {e}"}

        part2_prompt = (
            prompt + " [SMOOTH CONTINUATION from the previous shot within the SAME scene. "
            "Maintain identical lighting, color grading, subject, and environment. "
            "The visual flow must feel like one continuous unbroken shot. "
            "Push in for an intimate close-up of the product.]"
        )
        print(f"[VIDEO] Generating part 2 ({part2_duration}s) using Mode B continuation", file=_sys2.stderr, flush=True)
        part2_res = _generate_single_video(
            prompt=part2_prompt,
            image_path=last_frame_path,
            reference_image_paths="",
            duration_seconds=part2_duration,
            aspect_ratio=aspect_ratio,
            logo_path="",
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
        from datetime import datetime

        _, _, GENERATED_DIR = _get_config()
        save_dir = output_dir or str(GENERATED_DIR)

        video_path = res["video_path"]
        audio_path = os.path.join(save_dir, f"audio_{uuid.uuid4().hex[:8]}.mp3")
        logger.info("[VIDEO] Generating audio for script: %s", audio_script[:100])

        try:
            edge_tts_bin = os.path.join(os.getcwd(), ".venv", "bin", "edge-tts")
            if not os.path.exists(edge_tts_bin):
                edge_tts_bin = "edge-tts"

            subprocess.run([
                edge_tts_bin, "--voice", "en-US-JennyNeural",
                "--text", audio_script, "--write-media", audio_path
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if os.path.exists(audio_path):
                # Measure video and audio durations for sync
                video_dur = _get_media_duration(video_path)
                audio_dur = _get_media_duration(audio_path)
                logger.info("[VIDEO] Duration — video=%.2fs audio=%.2fs", video_dur, audio_dur)

                video_with_audio_path = os.path.join(save_dir, f"with_audio_{uuid.uuid4().hex[:8]}.mp4")

                if video_dur > 0 and audio_dur > 0 and abs(video_dur - audio_dur) > 0.5:
                    # Stretch/compress audio to match video duration using atempo filter
                    tempo_ratio = audio_dur / video_dur
                    # atempo only supports 0.5-2.0 range; chain filters for extreme ratios
                    atempo_filters = _build_atempo_chain(tempo_ratio)
                    logger.info("[VIDEO] Adjusting audio tempo: ratio=%.3f filters=%s", tempo_ratio, atempo_filters)

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
            logger.error("[VIDEO] Failed to merge audio: %s", e)

    return res
