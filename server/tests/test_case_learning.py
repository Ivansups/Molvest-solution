"""Case learning: разбор resolved-диалогов на кейсы базы знаний."""

from datetime import datetime, timedelta
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.openrouter_client import (
    CaseEvaluation,
    OpenRouterClassifier,
    OpenRouterError,
    parse_case_evaluation,
)
from app.models.chunk import Chunk
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.enums import (
    ConversationStatus,
    DocumentStatus,
    FileType,
    MessageRole,
)
from app.models.message import Message
from app.services.case_learning import evaluate_and_ingest, extract_case

NOW = datetime(2026, 1, 1, tzinfo=None)


def _message(
    role: MessageRole,
    content: str,
    *,
    created_at: datetime,
    confidence: float | None = None,
    escalated: bool = False,
    sources: list[object] | None = None,
) -> Message:
    return Message(
        role=role,
        content=content,
        created_at=created_at,
        confidence=confidence,
        escalated=escalated,
        sources=sources,
    )


def _resolved_conversation(
    *messages: tuple[MessageRole, str, dict[str, Any]],
) -> Conversation:
    """Диалог в статусе resolved с заданными сообщениями, без БД."""
    conversation = Conversation(
        id=uuid4(),
        installation_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        user_id="guest",
        status=ConversationStatus.RESOLVED,
    )
    conversation.messages = [
        _message(role, content, **kwargs) for role, content, kwargs in messages
    ]
    return conversation


def _grounded_answer() -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    question = (
        MessageRole.USER,
        "Как провести документ реализации в 1С после обновления?",
        dict(created_at=NOW, confidence=None),
    )
    answer = (
        MessageRole.ASSISTANT,
        "Откройте журнал документов, найдите не проведённый документ, "
        "нажмите кнопку Провести и подтвердите. Проверьте, что документ "
        "имеет номер и дату.",
        dict(
            created_at=NOW + timedelta(minutes=1),
            confidence=0.95,
            sources=[{"document_id": str(uuid4()), "title": "Инструкция"}],
        ),
    )
    return question, answer


# --- Разбор вердикта малой LLM (fail-closed) ---


def test_parse_case_evaluation_good() -> None:
    assert parse_case_evaluation("GOOD") == "good"


def test_parse_case_evaluation_bad_case_insensitive() -> None:
    assert parse_case_evaluation("bad") == "bad"


@pytest.mark.parametrize("content", ["", "MAYBE", "GOOD\nпояснения", "да"])
def test_parse_case_evaluation_unexpected_raises(content: str) -> None:
    with pytest.raises(OpenRouterError):
        parse_case_evaluation(content)


# --- Правила-предфильтр extract_case (без БД) ---


def test_extract_case_picks_last_grounded_answer() -> None:
    question, answer = _grounded_answer()
    stale = (
        MessageRole.ASSISTANT,
        "Старый ответ про проведение, тоже содержательный и с источниками.",
        dict(
            created_at=NOW - timedelta(hours=1),
            confidence=0.9,
            sources=[{"document_id": str(uuid4())}],
        ),
    )
    conversation = _resolved_conversation(question, stale, answer)
    result = extract_case(conversation, confidence_threshold=0.8)
    assert result == (
        "Как провести документ реализации в 1С после обновления?",
        answer[1],
    )


def test_extract_case_skips_greeting_wo_sources() -> None:
    greeting = (
        MessageRole.ASSISTANT,
        "Здравствуйте! Опишите проблему или приложите скриншот ошибки.",
        dict(created_at=NOW, confidence=1.0),
    )
    conversation = _resolved_conversation(
        (
            MessageRole.USER,
            "Привет!",
            dict(created_at=NOW - timedelta(minutes=1)),
        ),
        greeting,
    )
    assert extract_case(conversation, confidence_threshold=0.8) is None


def test_extract_case_skips_escalated_message() -> None:
    _, answer = _grounded_answer()
    escalated = (
        MessageRole.SYSTEM,
        "Вопрос передан оператору техподдержки.",
        dict(
            created_at=NOW,
            confidence=0.9,
            escalated=True,
            sources=[{"document_id": str(uuid4())}],
        ),
    )
    conversation = _resolved_conversation(escalated, answer)
    assert extract_case(conversation, confidence_threshold=0.8) is None


def test_extract_case_skips_low_confidence() -> None:
    question, _ = _grounded_answer()
    weak = (
        MessageRole.ASSISTANT,
        "Ответ с низкой уверенностью ретривала, но текст длинный и с источниками.",
        dict(created_at=NOW, confidence=0.5, sources=[{"document_id": str(uuid4())}]),
    )
    conversation = _resolved_conversation(question, weak)
    assert extract_case(conversation, confidence_threshold=0.8) is None


def test_extract_case_skips_short_question() -> None:
    _, answer = _grounded_answer()
    conversation = _resolved_conversation(
        (
            MessageRole.USER,
            "Как?",
            dict(created_at=NOW),
        ),
        answer,
    )
    assert extract_case(conversation, confidence_threshold=0.8) is None


def test_extract_case_not_resolved_returns_none() -> None:
    question, answer = _grounded_answer()
    conversation = _resolved_conversation(question, answer)
    conversation.status = ConversationStatus.ESCALATED
    assert extract_case(conversation, confidence_threshold=0.8) is None


# --- evaluate_and_ingest (интеграция с Postgres) ---


class FakeEmbedder:
    """Заменяет GigaChatService: эмбеддинги без сети."""

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        vector = [0.1, 0.2, 0.3]
        return [vector for _ in texts]


class FakeClassifier:
    """Мок intake и оценки кейсов: вердикт задаётся в конструкторе."""

    def __init__(
        self,
        *,
        verdict: str | None = None,
        error: Exception | None = None,
        configured: bool = True,
    ) -> None:
        self._verdict = verdict
        self._error = error
        self._configured = configured

    def is_configured(self) -> bool:
        return self._configured

    async def evaluate_case(self, question: str, answer: str) -> CaseEvaluation:
        if self._error is not None:
            raise self._error
        assert self._verdict is not None
        return cast(CaseEvaluation, self._verdict)


def _column_verdict_factory(
    verdict: str | None = None,
    *,
    error: Exception | None = None,
) -> MagicMock:
    classifier = MagicMock(spec=OpenRouterClassifier)
    classifier.is_configured = MagicMock(return_value=True)
    if error is not None:
        classifier.evaluate_case = AsyncMock(side_effect=error)
    else:
        classifier.evaluate_case = AsyncMock(return_value=verdict)
    return classifier


def _case_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


async def _seed_resolved_chat(
    db_session: AsyncSession,
) -> Conversation:
    """Диалог с успешным автоответом (кейс проходит правила)."""
    conversation = Conversation(
        installation_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        user_id="guest",
        status=ConversationStatus.RESOLVED,
    )
    db_session.add(conversation)
    await db_session.flush()
    db_session.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="Как провести документ реализации в 1С после обновления?",
        )
    )
    db_session.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=(
                "Откройте журнал документов, найдите не проведённый документ, "
                "нажмите Провести и подтвердите. Проверьте номер и дату."
            ),
            confidence=0.95,
            sources=[
                {
                    "document_id": str(uuid4()),
                    "title": "Инструкция",
                    "chunk_text": "проведение",
                }
            ],
        )
    )
    await db_session.commit()
    return conversation


async def _count_case_documents(
    db_session: AsyncSession,
    conversation_id: UUID,
) -> int:
    stmt = (
        select(func.count())
        .select_from(Document)
        .where(
            Document.extra_metadata["conversation_id"].astext == str(conversation_id)
        )
    )
    return int(await db_session.scalar(stmt) or 0)


async def _ingested_documents(
    db_session: AsyncSession,
) -> list[Document]:
    stmt = select(Document).where(Document.file_type == FileType.KB_CASE)
    return list((await db_session.scalars(stmt)).all())


async def test_evaluate_and_ingest_good_creates_indexed_document(
    db_session: AsyncSession,
    db_engine: AsyncEngine,
) -> None:
    conversation = await _seed_resolved_chat(db_session)
    classifier = _column_verdict_factory("good")

    await evaluate_and_ingest(
        conversation.id,
        classifier=classifier,
        llm=FakeEmbedder(),
        session_factory=_case_factory(db_engine),
    )

    documents = await _ingested_documents(db_session)
    assert len(documents) == 1
    document = documents[0]
    assert document.file_type == FileType.KB_CASE
    assert document.status == DocumentStatus.INDEXED
    assert document.installation_id == conversation.installation_id

    chunks = list(
        (
            await db_session.scalars(
                select(Chunk).where(Chunk.document_id == document.id)
            )
        ).all()
    )
    assert len(chunks) > 0

    await db_session.refresh(conversation)
    assert conversation.case_ingested_at is not None


async def test_evaluate_and_ingest_bad_marks_ingested_without_document(
    db_session: AsyncSession,
    db_engine: AsyncEngine,
) -> None:
    conversation = await _seed_resolved_chat(db_session)
    classifier = _column_verdict_factory("bad")

    await evaluate_and_ingest(
        conversation.id,
        classifier=classifier,
        llm=FakeEmbedder(),
        session_factory=_case_factory(db_engine),
    )

    assert await _ingested_documents(db_session) == []
    await db_session.refresh(conversation)
    assert conversation.case_ingested_at is not None


async def test_evaluate_and_ingest_failure_leaves_unmarked(
    db_session: AsyncSession,
    db_engine: AsyncEngine,
) -> None:
    conversation = await _seed_resolved_chat(db_session)
    classifier = _column_verdict_factory(error=OpenRouterError("сеть недоступна"))

    await evaluate_and_ingest(
        conversation.id,
        classifier=classifier,
        llm=FakeEmbedder(),
        session_factory=_case_factory(db_engine),
    )

    assert await _ingested_documents(db_session) == []
    await db_session.refresh(conversation)
    assert conversation.case_ingested_at is None


async def test_evaluate_and_ingest_rules_skip_marks_ingested(
    db_session: AsyncSession,
    db_engine: AsyncEngine,
) -> None:
    conversation = Conversation(
        installation_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        user_id="guest",
        status=ConversationStatus.RESOLVED,
    )
    db_session.add(conversation)
    await db_session.flush()
    db_session.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="Привет!",
        )
    )
    db_session.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content="Здравствуйте! Опишите проблему или приложите скриншот.",
            confidence=1.0,
        )
    )
    await db_session.commit()
    classifier = _column_verdict_factory("bad")

    await evaluate_and_ingest(
        conversation.id,
        classifier=classifier,
        llm=FakeEmbedder(),
        session_factory=_case_factory(db_engine),
    )

    assert await _ingested_documents(db_session) == []
    classifier.evaluate_case.assert_not_awaited()
    await db_session.refresh(conversation)
    assert conversation.case_ingested_at is not None


async def test_evaluate_and_ingest_idempotent(
    db_session: AsyncSession,
    db_engine: AsyncEngine,
) -> None:
    conversation = await _seed_resolved_chat(db_session)
    classifier = _column_verdict_factory("good")

    await evaluate_and_ingest(
        conversation.id,
        classifier=classifier,
        llm=FakeEmbedder(),
        session_factory=_case_factory(db_engine),
    )
    await evaluate_and_ingest(
        conversation.id,
        classifier=classifier,
        llm=FakeEmbedder(),
        session_factory=_case_factory(db_engine),
    )

    assert await _count_case_documents(db_session, conversation.id) == 1
    classifier.evaluate_case.assert_awaited_once()


async def test_evaluate_and_ingest_disabled_setting_skips(
    db_session: AsyncSession,
    db_engine: AsyncEngine,
) -> None:
    from app.core.config import Settings

    conversation = await _seed_resolved_chat(db_session)
    classifier = _column_verdict_factory("good")

    await evaluate_and_ingest(
        conversation.id,
        classifier=classifier,
        llm=FakeEmbedder(),
        session_factory=_case_factory(db_engine),
        app_settings=Settings(
            confidence_threshold=0.8,
            case_learning_enabled=False,
        ),
    )

    assert await _ingested_documents(db_session) == []
    classifier.evaluate_case.assert_not_awaited()
