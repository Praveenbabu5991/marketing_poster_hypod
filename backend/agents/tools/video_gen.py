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

        brand_narrative.append("Tell a good story based on the visual elements, creating a compelling narrative arc.")

        enhanced_prompt = prompt.rstrip()
        if brand_narrative:
            enhanced_prompt += " " + " ".join(brand_narrative)

        base_negatives = "text, titles, captions, words, letters, watermarks, subtitles, extra hands, extra fingers, three hands, four hands, mutated limbs, merging limbs, floating objects, clipping, unrealistic physics, deformed, distorted, animated, cartoon, opening from bottom, broken physics, morphing, flickering, jitter, warped face, asymmetrical eyes, disembodied limbs, scale issues, changing proportions, shifting background"
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

import subprocess
import tempfile
from langchain_core.tools import tool

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
            part2_prompt = prompt + " [CUT TO SHOT 2: Different dynamic camera angle, close-up hero shot of the product.]"
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
                return {"status": "error", "message": f"Failed to extract frame for 16s video: {e}"}
                
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
        
        list_path = os.path.join(save_dir, f"list_{uuid.uuid4().hex[:8]}.txt")
        with open(list_path, "w") as f:
            f.write(f"file '{os.path.abspath(part1_video)}'\n")
            f.write(f"file '{os.path.abspath(part2_video)}'\n")
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_filename = f"video_{timestamp}_{uuid.uuid4().hex[:8]}.mp4"
        final_video = os.path.join(save_dir, final_filename)
        
        logger.info("[VIDEO] Concatenating %s and %s into %s", part1_video, part2_video, final_video)
        try:
            subprocess.run([
                "ffmpeg", "-f", "concat", "-safe", "0", "-i", list_path,
                "-c", "copy", final_video, "-y"
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.error("[VIDEO] Failed to concatenate videos: %s", e)
            return {"status": "error", "message": f"Failed to concatenate videos: {e}"}
            
        try:
            if os.path.exists(last_frame_path): os.remove(last_frame_path)
            if os.path.exists(list_path): os.remove(list_path)
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
        logger.info("[VIDEO] Generating audio for script...")
        
        try:
            # We assume edge-tts is in the venv
            edge_tts_bin = os.path.join(os.getcwd(), ".venv", "bin", "edge-tts")
            if not os.path.exists(edge_tts_bin):
                # Fallback to global if venv not found
                edge_tts_bin = "edge-tts"
                
            subprocess.run([
                edge_tts_bin, "--text", audio_script, "--write-media", audio_path
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if os.path.exists(audio_path):
                video_with_audio_path = os.path.join(save_dir, f"with_audio_{uuid.uuid4().hex[:8]}.mp4")
                
                # We use -shortest to ensure the video stops playing exactly when the audio finishes, 
                # eliminating any awkward silence at the end of the clip.
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
