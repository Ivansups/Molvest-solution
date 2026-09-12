"""Интэйк-роутер запроса: малая LLM отсекает нерелевантный трафик.

Что делает нода: классифицирует текст гостя и перенаправляет граф.
- SUPPORT → идём дальше (кэш → retrieve → generate на GigaChat).
- HANDOFF → эскалация (как раньше детект «позовите оператора»).
- GREETING / AWAY_CHECK / OFFTOPIC → короткий шаблонный ответ малой модели,
  без RAG и GigaChat: граф заканчивается.
Фолбэк без OpenRouter (пустой ключ или сбой) — правила и GigaChat Lite для
хэндоффа: деградация до прежнего поведения, но без потери отсечения приветствий.
"""

import logging
import re

from app.agent.prompts import (
    DEFAULT_AWAY_REPLY,
    DEFAULT_GREETING_REPLY,
    DEFAULT_OFFTOPIC_REPLY,
    HANDOFF_SYSTEM_PROMPT,
)
from app.agent.state import AgentState
from app.core.gigachat_client import GigaChatError, GigaChatService
from app.core.logging import preview
from app.core.openrouter_client import (
    OpenRouterClassifier,
    OpenRouterError,
    RouterDecision,
)

logger = logging.getLogger(__name__)

# Причина эскалации по явной просьбе гостя — видна оператору в тикете.
HANDOFF_ESCALATION_REASON = "Явный запрос передачи оператору"
# Классификатор недоступен: безопаснее тикет, чем автоответ из базы.
DETECTOR_FAILURE_REASON = "Сбой детекта передачи оператору"

# Правила фолбэка: только короткие «чистые» реплики, чтобы не отсечь вопрос 1С
# с приветствием в начале. Всё длиннее одного шаблона уходит в SUPPORT.
_GREETING_ONLY = re.compile(
    r"^\s*(привет|здравств\w+|добрый\s+(день|вечер|утро)|доброе\s+утро|"
    r"спасибо|благодар\w+|hi|hello)[\s!.,?]*$",
    re.IGNORECASE,
)
_AWAY_CHECK = re.compile(
    r"^\s*(ты\s+тут|на\s+связи|есть\s+кто|алло|ау|ты\s+работаешь|"
    r"are\s+you\s+there)[\s!.,?]*$",
    re.IGNORECASE,
)
_HANDOFF_RULES = (
    r"(позови|вызови|соедини|подключи)\s+\S*\s*(инженера|оператора|"
    r"специалиста|человека|менеджера)",
    r"(хочу|нужен|нужна|дайте|дай)\s+.*(оператор|человек|специалист)",
    r"поговорить\s+с\s+(человеком|оператором|специалистом)",
)


async def route_intent(
    state: AgentState,
    *,
    classifier: OpenRouterClassifier,
    llm: GigaChatService,
) -> dict[str, object]:
    """Маршрутизирует запрос: handoff/оффтоп/приветствие или поддержка.

    OpenRouter — основной intake-фильтр. Пустой ключ или сбой — правила, затем
    GigaChat Lite для хэндоффа. Сбой всех путей — эскалация, не RAG.
    """
    if state.get("force_handoff"):
        logger.info("route_intent force_handoff без классификатора")
        return {
            "intent": "handoff",
            "escalated": True,
            "escalation_reason": HANDOFF_ESCALATION_REASON,
        }

    query = (state.get("query") or "").strip()
    if not query:
        return {}

    # Текст гостя, не дамп Vision: иначе описание скрина путает маршрутизацию.
    guest_text = (state.get("text") or "").strip() or query
    try:
        decision = await _route(guest_text, classifier=classifier, llm=llm)
    except _RouterFailure:
        logger.warning("route_intent оба классификатора упали, эскалация")
        return {
            "intent": "handoff",
            "escalated": True,
            "escalation_reason": DETECTOR_FAILURE_REASON,
        }

    intent = decision["intent"]
    if intent == "handoff":
        logger.info("route_intent запрос хэндоффа query=%s", preview(guest_text))
        return {
            "intent": "handoff",
            "escalated": True,
            "escalation_reason": HANDOFF_ESCALATION_REASON,
        }
    if intent in ("greeting", "away", "offtopic"):
        answer = decision["reply"] or _default_reply(intent)
        logger.info("route_intent intent=%s answer_chars=%s", intent, len(answer))
        return {
            "intent": intent,
            "answer": answer,
            "confidence": 1.0,
            "escalated": False,
        }
    logger.info("route_intent intent=support query=%s", preview(guest_text))
    return {}


async def _route(
    guest_text: str,
    *,
    classifier: OpenRouterClassifier,
    llm: GigaChatService,
) -> RouterDecision:
    """OpenRouter, при сбое/пустом ключе — правила, затем GigaChat Lite."""
    if classifier.is_configured():
        try:
            return await classifier.route(guest_text)
        except OpenRouterError as exc:
            logger.warning(
                "OpenRouter сбой, фолбэк на правила query=%s (%s)",
                preview(guest_text),
                exc,
            )
    else:
        logger.info("OpenRouter не задан, фолбэк на правила")
    decision = _rules_decision(guest_text)
    if decision is not None:
        return decision
    return await _gigachat_fallback(guest_text, llm)


def _rules_decision(query: str) -> RouterDecision | None:
    """Правила для явных коротких реплик. None — нельзя решить по правилам."""
    if any(re.search(pattern, query, re.IGNORECASE) for pattern in _HANDOFF_RULES):
        return {"intent": "handoff", "reply": ""}
    if _AWAY_CHECK.match(query):
        return {"intent": "away", "reply": DEFAULT_AWAY_REPLY}
    if _GREETING_ONLY.match(query):
        return {"intent": "greeting", "reply": DEFAULT_GREETING_REPLY}
    return None


async def _gigachat_fallback(query: str, llm: GigaChatService) -> RouterDecision:
    """Правила не решили: хэндофф через GigaChat Lite. Сбой — _RouterFailure."""
    try:
        handoff = await llm.classify_handoff(query, system_prompt=HANDOFF_SYSTEM_PROMPT)
    except GigaChatError as exc:
        logger.warning(
            "GigaChat хэндофф-детект сбой, эскалация query=%s (%s)",
            preview(query),
            exc,
        )
        raise _RouterFailure() from exc
    if handoff:
        return {"intent": "handoff", "reply": ""}
    return {"intent": "support", "reply": ""}


class _RouterFailure(Exception):
    """Оба пути классификации недоступны — нода эскалирует без RAG."""


def _default_reply(intent: str) -> str:
    """Запасной шаблон, если малая модель не дала свой."""
    if intent == "greeting":
        return DEFAULT_GREETING_REPLY
    if intent == "away":
        return DEFAULT_AWAY_REPLY
    return DEFAULT_OFFTOPIC_REPLY
