"""Integration tests for Session management endpoints."""

import pytest


@pytest.mark.asyncio
class TestSessionAPI:

    async def _create_brand(self, client, auth_headers, sample_brand_data) -> str:
        resp = await client.post("/api/v1/brands", json=sample_brand_data, headers=auth_headers)
        return resp.json()["id"]

    async def test_create_session(self, client, auth_headers, sample_brand_data):
        brand_id = await self._create_brand(client, auth_headers, sample_brand_data)
        response = await client.post(
            "/api/v1/sessions",
            json={"brand_id": brand_id, "agent_type": "single_post"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["agent_type"] == "single_post"
        assert data["thread_id"].startswith("thread_")
        assert data["status"] == "active"

    async def test_list_sessions(self, client, auth_headers, sample_brand_data):
        brand_id = await self._create_brand(client, auth_headers, sample_brand_data)
        await client.post(
            "/api/v1/sessions",
            json={"brand_id": brand_id, "agent_type": "single_post"},
            headers=auth_headers,
        )
        response = await client.get("/api/v1/sessions", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) >= 1

    async def test_create_session_invalid_agent(self, client, auth_headers, sample_brand_data):
        brand_id = await self._create_brand(client, auth_headers, sample_brand_data)
        response = await client.post(
            "/api/v1/sessions",
            json={"brand_id": brand_id, "agent_type": "nonexistent"},
            headers=auth_headers,
        )
        assert response.status_code == 400

    async def test_archive_session(self, client, auth_headers, sample_brand_data):
        brand_id = await self._create_brand(client, auth_headers, sample_brand_data)
        create_resp = await client.post(
            "/api/v1/sessions",
            json={"brand_id": brand_id, "agent_type": "carousel"},
            headers=auth_headers,
        )
        session_id = create_resp.json()["id"]
        response = await client.delete(f"/api/v1/sessions/{session_id}", headers=auth_headers)
        assert response.status_code == 204
