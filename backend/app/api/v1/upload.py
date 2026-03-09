"""File upload endpoints: logo and product images."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.config import UPLOAD_DIR
from app.security.dependencies import require_authenticated_user
from app.security.models import UserDetails
from brand.colors import extract_colors_from_logo

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/logo")
async def upload_logo(
    file: UploadFile,
    user: UserDetails = Depends(require_authenticated_user),
):
    """Upload brand logo and extract dominant colors."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    ext = Path(file.filename or "logo.png").suffix or ".png"
    filename = f"logo_{user.user_id}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = UPLOAD_DIR / "logos" / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "wb") as f:
        f.write(content)

    colors = extract_colors_from_logo(str(file_path))

    return {
        "logo_path": str(file_path),
        "url": f"/uploads/logos/{filename}",
        "colors": colors.get("colors", []),
    }


@router.post("/product-image")
async def upload_product_image(
    file: UploadFile,
    user: UserDetails = Depends(require_authenticated_user),
):
    """Upload a product image."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    ext = Path(file.filename or "product.png").suffix or ".png"
    filename = f"product_{user.user_id}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = UPLOAD_DIR / "products" / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "wb") as f:
        f.write(content)

    return {
        "image_path": str(file_path),
        "url": f"/uploads/products/{filename}",
    }
