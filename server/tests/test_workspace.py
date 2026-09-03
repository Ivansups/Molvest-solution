"""Маппинг workspace_id → installation_id."""

from uuid import UUID

from app.rag.retrieval import workspace_to_installation_id

ADMIN = UUID("7c77cfdc-2806-4e0f-a95f-c98d7a5b2f11")


def test_uuid_workspace_is_not_hashed() -> None:
    assert workspace_to_installation_id(str(ADMIN)) == ADMIN


def test_plain_workspace_is_stable_uuid5() -> None:
    first = workspace_to_installation_id("demo")
    second = workspace_to_installation_id("demo")
    assert first == second
    assert first != ADMIN
