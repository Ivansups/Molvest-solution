"""Маршруты документов, чата, диалогов и метрик есть в OpenAPI."""

from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_openapi_has_documents_chat_conversations_metrics() -> None:
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
    assert "/api/conversations" in paths
    assert "get" in paths["/api/conversations"]
    assert "/api/conversations/{conversation_id}" in paths
    assert "post" in paths["/api/conversations/{conversation_id}/messages"]
    assert "post" in paths["/api/conversations/{conversation_id}/resolve"]
    assert "post" in paths["/api/conversations/{conversation_id}/suggest"]
    assert "/api/metrics" in paths
    assert "get" in paths["/api/metrics"]
    assert "/api/settings" in paths
    assert "get" in paths["/api/settings"]
    assert "put" in paths["/api/settings"]
    assert "/webhook/bitrix" in paths
    assert "/webhook/bitrix/openlines" in paths
    assert "post" in paths["/webhook/bitrix/openlines"]
