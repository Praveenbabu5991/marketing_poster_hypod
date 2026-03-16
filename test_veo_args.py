from google import genai
from google.genai import types
from app.config import GOOGLE_API_KEY, VIDEO_MODEL
import io
from PIL import Image

client = genai.Client(api_key=GOOGLE_API_KEY)
img = Image.new('RGB', (64, 64), color='red')
buf = io.BytesIO()
img.save(buf, format='JPEG')
img_bytes = buf.getvalue()

try:
    client.models.generate_videos(
        model=VIDEO_MODEL,
        prompt="A test video",
        image=types.Image(image_bytes=img_bytes, mime_type="image/jpeg"),
        config=types.GenerateVideosConfig(
            aspect_ratio="16:9",
            duration_seconds=5,
            reference_images=[
                types.VideoGenerationReferenceImage(
                    image=types.Image(image_bytes=img_bytes, mime_type="image/jpeg"),
                    reference_type="asset"
                )
            ]
        )
    )
    print("SUCCESS")
except Exception as e:
    print(f"FAILED: {e}")
