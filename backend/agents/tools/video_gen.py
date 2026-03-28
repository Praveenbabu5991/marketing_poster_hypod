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
            # We explicitly do NOT append the brand_name to the text prompt 
            # because Veo will try to render it as floating text/gibberish.
            # The brand name is only used for logging or logo compositing.
            pass
        if target_audience:
            brand_narrative.append(f"The human subject should match the target audience: {target_audience}.")

        # Product prominence: when product images are reference assets, tell Veo to keep them central
        if reference_image_paths:
            brand_narrative.append(
                "The attached product must be the central visual element throughout the video. "
                "Keep the product in sharp focus and prominently visible in every frame — "
                "close-up details, center-framed, well-lit. The product should occupy at least "
                "40-50% of the frame during interaction shots. "
                "CRITICAL: The product design, logo, and label text must remain absolutely identical "
                "to the reference image. Do not modify, misspell, or regenerate any text on the product "
                "even during camera movement or rotation."
            )
        if logo_path and not image_path:
            brand_narrative.append(
                "The attached brand logo should appear clearly visible in the scene — "
                "on packaging, signage, clothing, or as a natural element in the environment."
            )

        # Anatomy & physics constraints (tool-level enforcement, not just LLM guidelines)
        brand_narrative.append(
            "ANATOMICAL CONSTRAINT: Show only one pair of normal human hands with exactly five fingers each. "
            "Never generate extra hands, floating hands, disembodied limbs, or merging limbs. "
            "Restrict to ONE single simple action per shot — only holding OR only pouring OR only applying. "
            "Never combine multiple hand actions (e.g., never show opening AND squeezing AND applying in one shot)."
        )
        brand_narrative.append(
            "PHYSICS CONSTRAINT: Maintain stable, consistent geometry, lighting, and proportions throughout. "
            "No morphing, warping, or scale changes on the product or human subject. "
            "Background must remain stable and fixed. All object interactions must follow real-world physics — "
            "caps open from the top, lids lift upward, products stay grounded on surfaces."
        )
        brand_narrative.append("Tell a good story based on the visual elements, creating a compelling narrative arc.")

        enhanced_prompt = prompt.rstrip()
        if brand_narrative:
            enhanced_prompt += " " + " ".join(brand_narrative)

        base_negatives = "text, titles, captions, words, letters, watermarks, subtitles, misspelled text, garbled text, distorted labels, illegible text, wrong spelling, extra hands, extra fingers, three hands, four hands, six fingers, mutated hands, mutated limbs, merging limbs, overlapping hands, floating hands, floating objects, clipping, unrealistic physics, deformed, distorted, animated, cartoon, opening from bottom, broken physics, morphing, flickering, jitter, warped face, asymmetrical eyes, disembodied limbs, scale issues, changing proportions, shifting background, melting background, inconsistent lighting"
        if negative_prompt:
            full_negative = f"{negative_prompt}, {base_negatives}"
        else:
            full_negative = base_negatives

        gen_kwargs = {"model": VIDEO_MODEL, "prompt": enhanced_prompt}

        if image_path:
            resolved_img = _resolve_image_path(image_path)
            if not os.path.exists(resolved_img):
                return {"status": "error", "message": f"Source image not found: {image_path}", "model": VIDEO_MODEL}

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
                # CRITICAL: negative_prompt API param is incompatible with reference_images.
                # Append negatives to prompt text as "Avoid: ..."
                # Use SAFE subset — words like "deformed", "mutated", "warped face" trigger
                # Vertex AI's RAI safety filter when embedded in prompt text.
                safe_negatives = (
                    "text, titles, captions, words, letters, watermarks, subtitles, "
                    "misspelled text, garbled labels, illegible text, wrong spelling, "
                    "extra hands, extra fingers, three hands, four hands, six fingers, "
                    "overlapping hands, floating hands, floating objects, "
                    "unrealistic physics, animated, cartoon, opening from bottom, "
                    "broken physics, morphing, flickering, jitter, "
                    "scale issues, changing proportions, shifting background, "
                    "melting background, inconsistent lighting"
                )
                if negative_prompt:
                    safe_negatives += f", {negative_prompt}"
                enhanced_prompt += f"\nAvoid: {safe_negatives}"
                gen_kwargs["prompt"] = enhanced_prompt

            mode = "text_to_video_with_refs"

        else:
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
            return {"status": "error", "message": msg, "model": VIDEO_MODEL}

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
    
    clamped_duration = max(5, min(16, duration_seconds))
    
    if clamped_duration <= 8:
        res = _generate_single_video(
            prompt, image_path, reference_image_paths, clamped_duration, aspect_ratio,
            logo_path, brand_name, brand_colors, company_overview, target_audience,
            products_services, cta_text, negative_prompt, output_dir
        )
    else:
        part1_duration = 8
        part2_duration = max(5, min(8, clamped_duration - 8))
        
        logger.info("[VIDEO] Generating part 1 (8s)")
        part1_res = _generate_single_video(
            prompt, image_path, reference_image_paths, part1_duration, aspect_ratio,
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
        
        last_frame_path = ""
        
        if reference_image_paths:
            logger.info("[VIDEO] Generating part 2 (%ss) using Multi-Shot Mode A", part2_duration)
            part2_prompt = (
                prompt + " [SMOOTH CONTINUATION: The camera smoothly transitions to a closer angle "
                "within the SAME scene and environment. Maintain identical lighting, color grading, "
                "and subject positioning. The visual flow must feel like one continuous unbroken shot — "
                "no jump cuts, no scene changes. Gradually push in for an intimate close-up of the product "
                "with the human still present in frame.]"
            )
            part2_res = _generate_single_video(
                prompt=part2_prompt,
                image_path="",
                reference_image_paths=reference_image_paths,
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
        else:
            last_frame_path = os.path.join(save_dir, f"frame_{uuid.uuid4().hex[:8]}.jpg")
            
            logger.info("[VIDEO] Extracting last frame from %s", part1_video)
            try:
                subprocess.run([
                    "ffmpeg", "-sseof", "-1", "-i", part1_video,
                    "-update", "1", "-q:v", "1", last_frame_path, "-y"
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                logger.error("[VIDEO] Failed to extract frame: %s", e)
                return {"status": "error", "message": f"Failed to extract frame for stitched video: {e}"}
                
            logger.info("[VIDEO] Generating part 2 (%ss) using Mode B Continuation", part2_duration)
            # Important: when generating part 2 from an image, reference_image_paths should be empty to ensure Mode B is used
            # Also pass logo_path="" and brand_name="" to avoid stamping a second logo on the middle frame
            part2_res = _generate_single_video(
                prompt=prompt, 
                image_path=last_frame_path, 
                reference_image_paths="", 
                duration_seconds=part2_duration, 
                aspect_ratio=aspect_ratio,
                logo_path="", 
                brand_name="", 
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
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_filename = f"video_{timestamp}_{uuid.uuid4().hex[:8]}.mp4"
        final_video = os.path.join(save_dir, final_filename)

        # Use xfade crossfade filter (0.5s) for smooth transition between parts
        crossfade_duration = 0.5
        logger.info("[VIDEO] Joining %s + %s with %.1fs crossfade into %s",
                     part1_video, part2_video, crossfade_duration, final_video)
        try:
            # Get Part 1 duration for xfade offset
            probe_result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", part1_video],
                capture_output=True, text=True
            )
            p1_dur = float(probe_result.stdout.strip()) if probe_result.stdout.strip() else float(part1_duration)
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
            logger.warning("[VIDEO] Crossfade failed (%s), falling back to concat", e)
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
                logger.error("[VIDEO] Concat also failed: %s", e2)
                return {"status": "error", "message": f"Failed to join video parts: {e2}"}
            finally:
                try:
                    os.remove(list_path)
                except:
                    pass

        try:
            if os.path.exists(last_frame_path): os.remove(last_frame_path)
        except:
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
            "branded": part1_res.get("branded", False),
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
