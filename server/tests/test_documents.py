"""Загрузка, список, удаление и реиндексация документов."""

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk
from app.models.enums import DocumentStatus

INSTALL_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
INSTALL_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


async def _upload(
    client: AsyncClient,
    file_name: str,
    *,
    installation_id: UUID = INSTALL_A,
    title: str = "Инструкция",
    body: bytes = b"%PDF-1.4 test",
) -> tuple[int, dict[str, object]]:
    response = await client.post(
        "/api/documents",
        files={"file": (file_name, body, "application/octet-stream")},
        data={"title": title, "installation_id": str(installation_id)},
    )
    payload: dict[str, object] = response.json() if response.content else {}
    return response.status_code, payload


async def test_upload_pdf_and_docx_are_pending(api_client: AsyncClient) -> None:
    pdf_status, pdf = await _upload(api_client, "guide.pdf")
    docx_status, docx = await _upload(
        api_client,
        "manual.docx",
        body=b"PK\x03\x04docx",
    )
    assert pdf_status == 201
    assert docx_status == 201
    assert pdf["status"] == DocumentStatus.PENDING
    assert docx["status"] == DocumentStatus.PENDING
    pdf_path = Path(str(pdf["metadata"]["storage_path"]))  # type: ignore[index]
    docx_path = Path(str(docx["metadata"]["storage_path"]))  # type: ignore[index]
    assert pdf_path.is_file()
    assert docx_path.is_file()


async def test_unsupported_type_is_rejected(api_client: AsyncClient) -> None:
    code, _ = await _upload(api_client, "note.txt", body=b"hello")
    assert code == 422
    listed = await api_client.get(
        "/api/documents",
        params={"installation_id": str(INSTALL_A)},
    )
    assert listed.json()["total"] == 0


async def test_duplicate_name_conflicts_per_installation(
    api_client: AsyncClient,
) -> None:
    first, _ = await _upload(api_client, "same.pdf")
    second, _ = await _upload(api_client, "same.pdf")
    other, payload = await _upload(api_client, "same.pdf", installation_id=INSTALL_B)
    assert first == 201
    assert second == 409
    assert other == 201
    assert payload["installation_id"] == str(INSTALL_B)


async def test_list_filter_and_get_has_empty_chunks(api_client: AsyncClient) -> None:
    await _upload(api_client, "one.pdf")
    listed = await api_client.get(
        "/api/documents",
        params={"installation_id": str(INSTALL_A), "status": "PENDING"},
    )
    body = listed.json()
    assert listed.status_code == 200
    assert body["total"] == 1
    assert body["items"][0]["file_name"] == "one.pdf"

    document_id = body["items"][0]["id"]
    detail = await api_client.get(f"/api/documents/{document_id}")
    assert detail.status_code == 200
    assert detail.json()["chunks"] == []

    missing = await api_client.get(f"/api/documents/{uuid4()}")
    assert missing.status_code == 404


async def test_delete_removes_chunks_and_file(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    code, created = await _upload(api_client, "drop.pdf")
    assert code == 201
    document_id = UUID(str(created["id"]))
    storage = Path(str(created["metadata"]["storage_path"]))  # type: ignore[index]
    db_session.add(Chunk(document_id=document_id, content="фрагмент", chunk_index=0))
    await db_session.commit()

    deleted = await api_client.delete(f"/api/documents/{document_id}")
    assert deleted.status_code == 204
    assert not storage.exists()

    again = await api_client.delete(f"/api/documents/{document_id}")
    assert again.status_code == 404


class _FakeEmbedder:
    """Эмбеддинги без сети — для reindex через API."""

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        vector = [0.1] * 1024
        return [vector for _ in texts]


async def test_reindex_indexes_document_idempotently(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.documents as documents_api

    monkeypatch.setattr(
        documents_api,
        "get_gigachat_service",
        lambda: _FakeEmbedder(),
    )
    code, created = await _upload(
        api_client,
        "reindex.md",
        body=("Как провести документ в 1С. ".encode()),
    )
    assert code == 201
    document_id = created["id"]
    first = await api_client.post(f"/api/documents/{document_id}/reindex")
    second = await api_client.post(f"/api/documents/{document_id}/reindex")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == DocumentStatus.INDEXED
    assert second.json()["status"] == DocumentStatus.INDEXED
    assert len(first.json()["chunks"]) == 1
    assert len(second.json()["chunks"]) == 1


async def test_reindex_unparseable_document_fails(api_client: AsyncClient) -> None:
    code, created = await _upload(api_client, "broken.pdf")
    assert code == 201
    document_id = created["id"]
    response = await api_client.post(f"/api/documents/{document_id}/reindex")
    assert response.status_code == 422
