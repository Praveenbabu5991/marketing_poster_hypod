import os
import mimetypes
from PIL import Image
import io
import base64
import urllib.request
import json

key = ""
with open("backend/.env") as f:
    for line in f:
        if line.startswith("RUNWAY_API_KEY="):
            key = line.strip().split("=", 1)[1]

image_path = "test_runway_image.jpg"
# Create a dummy image
img = Image.new('RGB', (100, 100), color = 'red')
img.save(image_path)

payload = {
    "model": "gen3a_turbo",
    "promptText": "A test video",
}

if image_path:
    resolved_img = image_path
    if os.path.exists(resolved_img):
        mime_type, _ = mimetypes.guess_type(resolved_img)
        mime_type = mime_type or "image/jpeg"
        print(f"Mime type: {mime_type}")
        
        target_size = (768, 1280) 
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

headers = {
    "Authorization": f"Bearer {key}",
    "X-Runway-Version": "2024-11-06",
    "Content-Type": "application/json"
}

req = urllib.request.Request(
    "https://api.dev.runwayml.com/v1/image_to_video",
    data=json.dumps(payload).encode('utf-8'),
    headers=headers
)

try:
    with urllib.request.urlopen(req) as response:
        print(response.getcode())
        print(response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code)
    print(e.read().decode('utf-8'))
except Exception as e:
    print(f"Error: {e}")

