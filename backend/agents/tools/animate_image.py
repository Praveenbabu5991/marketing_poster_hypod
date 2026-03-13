"""Image animation tool using Veo 3.1 API.

Adapted from v2 — wrapped with LangChain @tool decorator.
"""

import os
import io
import uuid
import time
from datetime import datetime
from pathlib import Path

from langchain_core.tools import tool
from PIL import Image


def _get_config():
    from app.config import GOOGLE_API_KEY, VIDEO_MODEL, GENERATED_DIR
    return GOOGLE_API_KEY, VIDEO_MODEL, GENERATED_DIR


def _get_client():
    from app.config import get_genai_client
    return get_genai_client()


@tool
def animate_image(
    image_path: str,
    animation_prompt: str = "",
    duration_seconds: int = 5,
    output_dir: str = "",
) -> dict:
    """Animate a static image into a short video using Veo 3.1.

    Uses image-to-video mode. No reference_images allowed (mutually exclusive in Veo 3.1).

    Args:
        image_path: Path to the static image to animate.
        animation_prompt: Description of desired motion/animation.
        duration_seconds: Video length in seconds (5-8).
        output_dir: Directory to save the video.
    """
    _, VIDEO_MODEL, GENERATED_DIR = _get_config()
    save_dir = output_dir or str(GENERATED_DIR)

    if not os.path.exists(image_path):
        return {"status": "error", "message": f"Image not found: {image_path}"}

    try:
        client = _get_client()
        from google.genai import types

        source_image = Image.open(image_path)
        if source_image.mode in ("RGBA", "LA", "P"):
            source_image = source_image.convert("RGB")

        buf = io.BytesIO()
        source_image.save(buf, format="JPEG")

        prompt = animation_prompt or "Subtle, elegant animation with gentle movement. Professional quality."
        clamped_duration = max(5, min(8, duration_seconds))

        config = types.GenerateVideosConfig(
            aspect_ratio="9:16",
            number_of_videos=1,
            duration_seconds=clamped_duration,
        )

        operation = client.models.generate_videos(
            model=VIDEO_MODEL,
            prompt=prompt,
            image=types.Image(image_bytes=buf.getvalue(), mime_type="image/jpeg"),
            config=config,
        )

        max_wait = 300
        while not operation.done:
            time.sleep(10)
            operation = client.operations.get(operation)
            max_wait -= 10
            if max_wait <= 0:
                return {"status": "timeout", "message": "Video generation timed out after 5 minutes."}

        result = operation.result
        if not result or not result.generated_videos:
            return {"status": "error", "message": "No video was generated. Try a different animation prompt."}

        video = result.generated_videos[0]
        output_path = Path(save_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        video_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"animated_{timestamp}_{video_id}.mp4"
        video_path = output_path / filename

        client.files.download(file=video.video)
        video.video.save(str(video_path))

        return {
            "status": "success",
            "video_path": str(video_path),
            "filename": filename,
            "url": f"/generated/{filename}",
            "duration_seconds": clamped_duration,
            "source_image": image_path,
        }

    except Exception as e:
        return {"status": "error", "message": f"Animation failed: {str(e)[:300]}"}
