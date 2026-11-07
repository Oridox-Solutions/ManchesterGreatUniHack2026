import asyncio

import httpx

from app.main import create_app


async def request(method: str, path: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.request(method, path, **kwargs)


def test_health_endpoint():
    response = asyncio.run(request("GET", "/health"))
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_invalid_pull_request_url_is_rejected_before_network_call():
    response = asyncio.run(
        request(
            "POST",
            "/api/analyse",
            json={"pull_request_url": "https://example.com/not-github/pull/1"},
        )
    )
    assert response.status_code == 422
