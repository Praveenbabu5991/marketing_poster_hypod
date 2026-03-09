"""Integration tests for file upload endpoints."""

import io

import pytest
from PIL import Image


def _create_test_image() -> bytes:
    """Create a small test PNG image in memory."""
    img = Image.new("RGB", (100, 100), color=(26, 26, 46))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
class TestUploadAPI:

    async def test_upload_logo(self, client, auth_headers):
        image_data = _create_test_image()
        response = await client.post(
            "/api/v1/upload/logo",
            files={"file": ("logo.png", image_data, "image/png")},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "logo_path" in data
        assert "colors" in data
        assert isinstance(data["colors"], list)

    async def test_upload_product_image(self, client, auth_headers):
        image_data = _create_test_image()
        response = await client.post(
            "/api/v1/upload/product-image",
            files={"file": ("product.png", image_data, "image/png")},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "image_path" in data

    async def test_upload_non_image_rejected(self, client, auth_headers):
        response = await client.post(
            "/api/v1/upload/logo",
            files={"file": ("readme.txt", b"hello", "text/plain")},
            headers=auth_headers,
        )
        assert response.status_code == 400

    async def test_upload_unauthenticated(self, client):
        image_data = _create_test_image()
        response = await client.post(
            "/api/v1/upload/logo",
            files={"file": ("logo.png", image_data, "image/png")},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestUploadProductInChat:
    """Tests for the in-chat product upload endpoint."""

    async def _create_brand_and_session(self, client, auth_headers, sample_brand_data):
        brand_resp = await client.post("/api/v1/brands", json=sample_brand_data, headers=auth_headers)
        brand_id = brand_resp.json()["id"]
        session_resp = await client.post(
            "/api/v1/sessions",
            json={"brand_id": brand_id, "agent_type": "sales_poster"},
            headers=auth_headers,
        )
        session_id = session_resp.json()["id"]
        return brand_id, session_id

    async def test_upload_product_in_chat(self, client, auth_headers, sample_brand_data):
        brand_id, session_id = await self._create_brand_and_session(client, auth_headers, sample_brand_data)
        image_data = _create_test_image()
        response = await client.post(
            f"/api/v1/sessions/{session_id}/upload-product",
            files={"file": ("product.png", image_data, "image/png")},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "image_path" in data
        assert "url" in data
        assert data["url"].startswith("/uploads/products/")

        # Verify brand's product_images was updated
        brand_resp = await client.get(f"/api/v1/brands/{brand_id}", headers=auth_headers)
        brand_data = brand_resp.json()
        assert len(brand_data["product_images"]) == 1
        assert brand_data["product_images"][0] == data["image_path"]

    async def test_upload_non_image_rejected(self, client, auth_headers, sample_brand_data):
        _, session_id = await self._create_brand_and_session(client, auth_headers, sample_brand_data)
        response = await client.post(
            f"/api/v1/sessions/{session_id}/upload-product",
            files={"file": ("readme.txt", b"hello", "text/plain")},
            headers=auth_headers,
        )
        assert response.status_code == 400

    async def test_upload_invalid_session(self, client, auth_headers):
        response = await client.post(
            "/api/v1/sessions/00000000-0000-0000-0000-000000000000/upload-product",
            files={"file": ("product.png", _create_test_image(), "image/png")},
            headers=auth_headers,
        )
        assert response.status_code == 404
