"""Загрузка, список, PATCH метаданных, удаление и реиндексация документов."""

from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk
from app.models.document import Document
from app.models.enums import DocumentStatus, FileType
from app.services.documents import file_type_from_name

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
    doc_status, doc = await _upload(
        api_client,
        "legacy.doc",
        body=b"not ole",
    )
    assert pdf_status == 201
    assert docx_status == 201
    assert doc_status == 201
    assert pdf["status"] == DocumentStatus.PENDING
    assert docx["status"] == DocumentStatus.PENDING
    assert doc["status"] == DocumentStatus.PENDING
    assert doc["file_type"] == FileType.DOC
    pdf_path = Path(str(pdf["metadata"]["storage_path"]))  # type: ignore[index]
    docx_path = Path(str(docx["metadata"]["storage_path"]))  # type: ignore[index]
    assert pdf_path.is_file()
    assert docx_path.is_file()


def test_file_type_from_name_accepts_doc() -> None:
    assert file_type_from_name("legacy.doc") == FileType.DOC
    assert file_type_from_name("manual.docx") == FileType.DOCX


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

    patched = await api_client.patch(
        f"/api/documents/{document_id}",
        params=foreign,
        json={"title": "Чужой"},
    )
    assert patched.status_code == 404

    own = await api_client.get(
        f"/api/documents/{document_id}",
        params={"installation_id": str(INSTALL_A)},
    )
    assert own.status_code == 200
    assert own.json()["title"] == "Инструкция"

    unscoped = await api_client.get(f"/api/documents/{document_id}")
    assert unscoped.status_code == 422


async def _mark_indexed(
    session: AsyncSession,
    document_id: UUID,
    *,
    chunk_text: str = "фрагмент",
) -> None:
    document = await session.get(Document, document_id)
    assert document is not None
    document.status = DocumentStatus.INDEXED
    session.add(Chunk(document_id=document_id, content=chunk_text, chunk_index=0))
    await session.commit()


async def test_patch_title_does_not_reindex(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.documents as documents_api
    import app.services.documents as documents_service

    reindex_calls: list[UUID] = []

    async def fake_background(
        document_id: UUID,
        installation_id: UUID,
        request_id: str,
    ) -> None:
        assert request_id
        assert installation_id == INSTALL_A
        reindex_calls.append(document_id)

    monkeypatch.setattr(documents_api, "_reindex_in_background", fake_background)
    incr = AsyncMock(return_value=1)
    monkeypatch.setattr(documents_service, "increment_kb_version", incr)

    code, created = await _upload(api_client, "indexed.pdf")
    assert code == 201
    document_id = UUID(str(created["id"]))
    await _mark_indexed(db_session, document_id)

    scope = {"installation_id": str(INSTALL_A)}
    before = await api_client.get(f"/api/documents/{document_id}", params=scope)
    assert before.status_code == 200
    assert before.json()["status"] == DocumentStatus.INDEXED
    chunks_before = before.json()["chunks"]
    storage = Path(str(created["metadata"]["storage_path"]))  # type: ignore[index]
    size_before = storage.stat().st_size

    patched = await api_client.patch(
        f"/api/documents/{document_id}",
        params=scope,
        json={"title": "Новое имя"},
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Новое имя"
    assert patched.json()["status"] == DocumentStatus.INDEXED

    again = await api_client.patch(
        f"/api/documents/{document_id}",
        params=scope,
        json={"title": "Новое имя"},
    )
    assert again.status_code == 200
    assert again.json()["title"] == "Новое имя"
    assert again.json()["status"] == DocumentStatus.INDEXED

    after = await api_client.get(f"/api/documents/{document_id}", params=scope)
    assert after.status_code == 200
    assert after.json()["title"] == "Новое имя"
    assert after.json()["status"] == DocumentStatus.INDEXED
    assert after.json()["chunks"] == chunks_before
    assert storage.is_file()
    assert storage.stat().st_size == size_before
    incr.assert_not_called()
    assert reindex_calls == [document_id]


async def test_patch_metadata_round_trip(api_client: AsyncClient) -> None:
    code, created = await _upload(api_client, "meta.pdf")
    assert code == 201
    document_id = str(created["id"])
    scope = {"installation_id": str(INSTALL_A)}

    patched = await api_client.patch(
        f"/api/documents/{document_id}",
        params=scope,
        json={
            "metadata": {
                "category": "1С",
                "description": "Как провести документ",
            }
        },
    )
    assert patched.status_code == 200
    assert patched.json()["metadata"]["category"] == "1С"
    assert patched.json()["metadata"]["description"] == "Как провести документ"
    stored_path = created["metadata"]["storage_path"]  # type: ignore[index]
    assert patched.json()["metadata"]["storage_path"] == stored_path

    detail = await api_client.get(f"/api/documents/{document_id}", params=scope)
    assert detail.status_code == 200
    assert detail.json()["metadata"]["category"] == "1С"
    assert detail.json()["metadata"]["description"] == "Как провести документ"


async def test_patch_reserved_metadata_keys_rejected(
    api_client: AsyncClient,
) -> None:
    code, created = await _upload(api_client, "reserved.pdf")
    assert code == 201
    document_id = str(created["id"])
    scope = {"installation_id": str(INSTALL_A)}
    stored_path = created["metadata"]["storage_path"]  # type: ignore[index]

    patched = await api_client.patch(
        f"/api/documents/{document_id}",
        params=scope,
        json={"metadata": {"storage_path": "/tmp/evil", "category": "1С"}},
    )
    assert patched.status_code == 422

    indexing = await api_client.patch(
        f"/api/documents/{document_id}",
        params=scope,
        json={"metadata": {"indexing_error": "подмена"}},
    )
    assert indexing.status_code == 422

    detail = await api_client.get(f"/api/documents/{document_id}", params=scope)
    assert detail.status_code == 200
    metadata = detail.json()["metadata"]
    assert metadata["storage_path"] == stored_path
    assert "category" not in metadata
    assert metadata.get("indexing_error") != "подмена"


async def test_patch_empty_body_is_422(api_client: AsyncClient) -> None:
    code, created = await _upload(api_client, "empty-patch.pdf")
    assert code == 201
    document_id = str(created["id"])
    scope = {"installation_id": str(INSTALL_A)}
    original_title = created["title"]

    empty = await api_client.patch(
        f"/api/documents/{document_id}",
        params=scope,
        json={},
    )
    assert empty.status_code == 422

    blank_title = await api_client.patch(
        f"/api/documents/{document_id}",
        params=scope,
        json={"title": "   "},
    )
    assert blank_title.status_code == 422

    missing_body = await api_client.patch(
        f"/api/documents/{document_id}",
        params=scope,
    )
    assert missing_body.status_code == 422

    unscoped = await api_client.patch(
        f"/api/documents/{document_id}",
        json={"title": "Без установки"},
    )
    assert unscoped.status_code == 422

    detail = await api_client.get(f"/api/documents/{document_id}", params=scope)
    assert detail.status_code == 200
    assert detail.json()["title"] == original_title


async def test_patch_unknown_document_is_404(api_client: AsyncClient) -> None:
    response = await api_client.patch(
        f"/api/documents/{uuid4()}",
        params={"installation_id": str(INSTALL_A)},
        json={"title": "Нет такого"},
    )
    assert response.status_code == 404
