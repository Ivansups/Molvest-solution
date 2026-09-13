"""Казуарный инжест успешно решённых диалогов в базу знаний.

Сценарий 4: после закрытия диалога фоново, вне запроса, по правилам отбираем
пары «вопрос гость — автоответ ассистента», малая LLM (OpenRouter) выносит
GOOD/BAD, и только GOOD индексируется как документ FileType.KB_CASE. Кейс
формируется без файла на диске — чанки передаются в index_document напрямую.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.agent.prompts import (
    DEFAULT_AWAY_REPLY,
    DEFAULT_GREETING_REPLY,
    DEFAULT_OFFTOPIC_REPLY,
)
from app.core.config import Settings, settings
from app.core.gigachat_client import get_gigachat_service
from app.core.openrouter_client import (
    OpenRouterClassifier,
    OpenRouterError,
    get_openrouter_classifier,
)
from app.db.session import SessionLocal
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.enums import ConversationStatus, FileType, MessageRole
from app.models.message import Message
from app.models.time import utc_now
from app.rag.chunking import extract_chunks
from app.rag.ingestion import IngestionError, index_document
from app.rag.protocols import EmbeddingsProvider
from app.services.conversations import GUEST_ESCALATION_TEXT

logger = logging.getLogger(__name__)

# Короткий вопрос или дежурный ответ в базу знаний не тянет.
_CASE_QUESTION_MIN_CHARS = 10
_CASE_ANSWER_MIN_CHARS = 30
# Ответы малой модели вне вопроса 1С: так мы отсекаем маршруты из роутера
# даже без сохранённого интента в строке диалога.
_NOT_CASE_REPLIES: frozenset[str] = frozenset(
    {
        DEFAULT_AWAY_REPLY,
        DEFAULT_GREETING_REPLY,
        DEFAULT_OFFTOPIC_REPLY,
        GUEST_ESCALATION_TEXT,
    }
)


async def evaluate_and_ingest(
    conversation_id: UUID,
    *,
    classifier: OpenRouterClassifier | None = None,
    llm: EmbeddingsProvider | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    app_settings: Settings | None = None,
) -> None:
    """Разбирает resolved-диалог на кейс: правила → малая LLM → индексация.

    Вызывается из BackgroundTasks уже после закрытия сессии запроса, поэтому
    открывает собственную. Fail-closed: документ в БЗ появляется только при
    GOOD и успешной индексации; BAD или правила не прошли — кейс
    пропускается и диалог помечается разобранным. Сбой внешнего вызова
    (OpenRouter) или ошибка индексации метку не ставят, чтобы следующий
    resolve перепробовал инжест.
    """
    cfg = app_settings or settings
    if not cfg.case_learning_enabled:
        return
    effective_classifier = classifier or get_openrouter_classifier()
    if not effective_classifier.is_configured():
        logger.info(
            "case learning: OpenRouter не настроен, кейс пропущен conversation_id=%s",
            conversation_id,
        )
        return
    effective_llm = llm or get_gigachat_service()
    factory = session_factory or SessionLocal

    async with factory() as session:
        conversation = await _load_conversation(session, conversation_id)
        if conversation is None:
            logger.info(
                "case learning: диалог не найден conversation_id=%s", conversation_id
            )
            return
        if conversation.status != ConversationStatus.RESOLVED:
            logger.info(
                "case learning: диалог ещё не решён conversation_id=%s", conversation_id
            )
            return
        if conversation.case_ingested_at is not None:
            logger.info("case learning: повтор conversation_id=%s", conversation_id)
            return

        pair = extract_case(conversation, confidence_threshold=cfg.confidence_threshold)
        if pair is None:
            logger.info(
                "case learning: правила не прошли conversation_id=%s", conversation_id
            )
            await _mark_ingested(session, conversation)
            return

        question, answer = pair
        try:
            verdict = await effective_classifier.evaluate_case(question, answer)
        except OpenRouterError as exc:
            logger.warning(
                "case learning: оценка недоступна conversation_id=%s (%s)",
                conversation_id,
                exc,
            )
            return
        logger.info(
            "case learning: verdict=%s conversation_id=%s", verdict, conversation_id
        )
        if verdict == "bad":
            await _mark_ingested(session, conversation)
            return

        indexed = await _ingest_case(
            session,
            conversation,
            question=question,
            answer=answer,
            llm=effective_llm,
            cfg=cfg,
        )
        if indexed:
            await _mark_ingested(session, conversation)


def extract_case(
    conversation: Conversation,
    *,
    confidence_threshold: float,
) -> tuple[str, str] | None:
    """Правила-предфильтр: содержительный вопрос и автоответ без эскалации.

    Ответ — последнее сообщение ассистента, которое не эскалировало, прошло
    по RAG-источникам и порогу уверенности; вопрос — последняя реплика гостя
    до него. None — подходящей пары нет.
    """
    if conversation.status != ConversationStatus.RESOLVED:
        return None
    ordered = sorted(conversation.messages, key=lambda message: message.created_at)
    answer = _last_auto_answer(ordered, confidence_threshold=confidence_threshold)
    if answer is None:
        return None
    question = _last_question_before(ordered, answer)
    if question is None:
        return None
    return question.content.strip(), answer.content.strip()


def _last_auto_answer(
    messages: list[Message],
    *,
    confidence_threshold: float,
) -> Message | None:
    """Последний автоответ диалога: ASSISTANT, без эскалации, с источниками."""
    candidate: Message | None = None
    for message in messages:
        if (
            message.role == MessageRole.ASSISTANT
            and not message.escalated
            and message.confidence is not None
            and message.confidence >= confidence_threshold
            and bool(message.sources)
            and message.content not in _NOT_CASE_REPLIES
            and len(message.content.strip()) >= _CASE_ANSWER_MIN_CHARS
        ):
            candidate = message
    return candidate


def _last_question_before(messages: list[Message], answer: Message) -> Message | None:
    """Последний достаточно содержательный вопрос гостя не позже ответа."""
    candidate: Message | None = None
    for message in messages:
        if message.created_at > answer.created_at:
            break
        if (
            message.role == MessageRole.USER
            and len(message.content.strip()) >= _CASE_QUESTION_MIN_CHARS
        ):
            candidate = message
    return candidate


def _case_title(question: str) -> str:
    """Заголовок документа-кейса: первая строка вопроса, не длиннее 512 символов."""
    first_line = question.splitlines()[0].strip()
    return first_line[:512] or "Кейс из диалога"


async def _ingest_case(
    session: AsyncSession,
    conversation: Conversation,
    *,
    question: str,
    answer: str,
    llm: EmbeddingsProvider,
    cfg: Settings,
) -> bool:
    """Создаёт документ-кейс и индексирует его.

    Возвращает True при успешной индексации — только тогда вызывающий код
    вправе пометить диалог разобранным. При сбое индексации возвращает False
    и откатывает созданный документ, чтобы следующий resolve повторил
    попытку (fail-closed).
    """
    case_text = f"Вопрос: {question}\n\nОтвет: {answer}"
    data = case_text.encode("utf-8")
    chunks = extract_chunks(
        data,
        FileType.KB_CASE,
        max_chunk_size=cfg.max_chunk_size,
        chunk_overlap=cfg.chunk_overlap,
    )
    if not chunks:
        logger.warning("case learning: пустой кейс conversation_id=%s", conversation.id)
        return False
    document = Document(
        installation_id=conversation.installation_id,
        title=_case_title(question),
        file_name=f"case-{conversation.id}.md",
        file_type=FileType.KB_CASE,
        extra_metadata={
            "conversation_id": str(conversation.id),
            "source": "case_learning",
        },
    )
    session.add(document)
    try:
        await session.flush()
    except IntegrityError:
        # Повторный вызов или гонка двух фоновых задач — документ уже есть.
        await session.rollback()
        logger.info("case learning: дубль conversation_id=%s", conversation.id)
        return False
    try:
        await index_document(session, document, llm, chunks=chunks, app_settings=cfg)
    except IngestionError as exc:
        logger.warning(
            "case learning: индексация не удалась conversation_id=%s (%s)",
            conversation.id,
            exc,
        )
        await session.delete(document)
        await session.commit()
        return False
    return True


async def _load_conversation(
    session: AsyncSession,
    conversation_id: UUID,
) -> Conversation | None:
    """Диалог с сообщениями для разбора кейса."""
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id)
    )
    return (await session.scalars(stmt)).first()


async def _mark_ingested(session: AsyncSession, conversation: Conversation) -> None:
    conversation.case_ingested_at = utc_now()
    await session.commit()
