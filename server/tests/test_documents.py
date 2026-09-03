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


async def test_upload_ignores_swagger_metadata_placeholder(
    api_client: AsyncClient,
) -> None:
    response = await api_client.post(
        "/api/documents",
        files={"file": ("guide.md", b"# 1C", "text/markdown")},
        data={
            "title": "Гайд",
            "installation_id": str(INSTALL_A),
            "metadata": "string",
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == DocumentStatus.PENDING


async def test_upload_rejects_non_object_metadata(api_client: AsyncClient) -> None:
    response = await api_client.post(
        "/api/documents",
        files={"file": ("guide.md", b"# 1C", "text/markdown")},
        data={
            "title": "Гайд",
            "installation_id": str(INSTALL_A),
            "metadata": "[1]",
        },
    )
    assert response.status_code == 422


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
    scope = {"installation_id": str(INSTALL_A)}
    detail = await api_client.get(f"/api/documents/{document_id}", params=scope)
    assert detail.status_code == 200
    assert detail.json()["chunks"] == []

    missing = await api_client.get(f"/api/documents/{uuid4()}", params=scope)
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

    scope = {"installation_id": str(INSTALL_A)}
    deleted = await api_client.delete(f"/api/documents/{document_id}", params=scope)
    assert deleted.status_code == 204
    assert not storage.exists()

    again = await api_client.delete(f"/api/documents/{document_id}", params=scope)
    assert again.status_code == 404


async def test_reindex_schedules_background_task(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.documents as documents_api

    ran: list[UUID] = []

    async def fake_background(
        document_id: UUID,
        installation_id: UUID,
        request_id: str,
    ) -> None:
        assert request_id
        assert installation_id == INSTALL_A
        ran.append(document_id)

    monkeypatch.setattr(documents_api, "_reindex_in_background", fake_background)
    code, created = await _upload(
        api_client,
        "reindex.md",
        body=("Как провести документ в 1С. ".encode()),
    )
    assert code == 201
    document_id = UUID(str(created["id"]))
    assert ran == [document_id]

    accepted = await api_client.post(
        f"/api/documents/{document_id}/reindex",
        params={"installation_id": str(INSTALL_A)},
    )
    assert accepted.status_code == 202
    assert accepted.json()["status"] == DocumentStatus.PENDING
    assert accepted.json()["id"] == str(document_id)
    assert ran == [document_id, document_id]


async def test_upload_starts_background_index(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.documents as documents_api

    ran: list[UUID] = []

    async def fake_background(
        document_id: UUID,
        installation_id: UUID,
        request_id: str,
    ) -> None:
        assert request_id
        assert installation_id == INSTALL_A
        ran.append(document_id)

    monkeypatch.setattr(documents_api, "_reindex_in_background", fake_background)
    code, created = await _upload(api_client, "queued.md", body=b"# 1C")
    assert code == 201
    assert created["status"] == DocumentStatus.PENDING
    assert ran == [UUID(str(created["id"]))]


async def test_reindex_unknown_document_is_404(
    api_client: AsyncClient,
) -> None:
    response = await api_client.post(
        f"/api/documents/{uuid4()}/reindex",
        params={"installation_id": str(INSTALL_A)},
    )
    assert response.status_code == 404


async def test_installation_scope_hides_foreign_document(
    api_client: AsyncClient,
) -> None:
    code, created = await _upload(api_client, "foreign.pdf", installation_id=INSTALL_A)
    assert code == 201
    document_id = str(created["id"])
    foreign = {"installation_id": str(INSTALL_B)}

    detail = await api_client.get(f"/api/documents/{document_id}", params=foreign)
    assert detail.status_code == 404

    reindex = await api_client.post(
        f"/api/documents/{document_id}/reindex",
        params=foreign,
    )
    assert reindex.status_code == 404

    deleted = await api_client.delete(f"/api/documents/{document_id}", params=foreign)
    assert deleted.status_code == 404

    own = await api_client.get(
        f"/api/documents/{document_id}",
        params={"installation_id": str(INSTALL_A)},
    )
    assert own.status_code == 200

    unscoped = await api_client.get(f"/api/documents/{document_id}")
    assert unscoped.status_code == 422
