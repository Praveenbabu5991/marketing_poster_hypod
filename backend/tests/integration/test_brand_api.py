"""Integration tests for Brand CRUD endpoints."""

import pytest
import pytest_asyncio


@pytest.mark.asyncio
class TestBrandAPI:

    async def test_create_brand(self, client, auth_headers, sample_brand_data):
        response = await client.post("/api/v1/brands", json=sample_brand_data, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "TestBrand"
        assert data["tone"] == "professional"
        assert data["colors"] == ["#1a1a2e", "#16213e", "#e94560"]

    async def test_list_brands(self, client, auth_headers, sample_brand_data):
        await client.post("/api/v1/brands", json=sample_brand_data, headers=auth_headers)
        response = await client.get("/api/v1/brands", headers=auth_headers)
        assert response.status_code == 200
        brands = response.json()
        assert len(brands) >= 1

    async def test_get_brand(self, client, auth_headers, sample_brand_data):
        create_resp = await client.post("/api/v1/brands", json=sample_brand_data, headers=auth_headers)
        brand_id = create_resp.json()["id"]
        response = await client.get(f"/api/v1/brands/{brand_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["name"] == "TestBrand"

    async def test_update_brand(self, client, auth_headers, sample_brand_data):
        create_resp = await client.post("/api/v1/brands", json=sample_brand_data, headers=auth_headers)
        brand_id = create_resp.json()["id"]
        response = await client.put(
            f"/api/v1/brands/{brand_id}",
            json={"name": "UpdatedBrand", "tone": "bold"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "UpdatedBrand"
        assert response.json()["tone"] == "bold"

    async def test_delete_brand(self, client, auth_headers, sample_brand_data):
        create_resp = await client.post("/api/v1/brands", json=sample_brand_data, headers=auth_headers)
        brand_id = create_resp.json()["id"]
        response = await client.delete(f"/api/v1/brands/{brand_id}", headers=auth_headers)
        assert response.status_code == 204

        # Should be gone from list
        list_resp = await client.get("/api/v1/brands", headers=auth_headers)
        ids = [b["id"] for b in list_resp.json()]
        assert brand_id not in ids

    async def test_unauthenticated_access(self, client):
        response = await client.get("/api/v1/brands")
        assert response.status_code == 401

    async def test_brand_not_found(self, client, auth_headers):
        response = await client.get(
            "/api/v1/brands/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert response.status_code == 404
