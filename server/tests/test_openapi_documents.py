"""Маршруты документов есть в OpenAPI; чат и диалоги не сломаны."""

from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_openapi_documents_and_unchanged_chat() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        spec = (await client.get("/openapi.json")).json()
    paths = spec["paths"]
    assert "/api/documents" in paths
    assert "get" in paths["/api/documents"]
    assert "post" in paths["/api/documents"]
    assert "/api/documents/{document_id}" in paths
    assert "/api/documents/{document_id}/reindex" in paths
    assert "/chat" in paths
    assert "post" in paths["/chat"]
    assert not any(path.startswith("/api/conversations") for path in paths)
