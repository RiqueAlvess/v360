"""Testes de integração para o endpoint /health."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_retorna_ok(client: AsyncClient) -> None:
    """GET /health deve retornar status ok e versão."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert data["version"] == "1.0.0"
