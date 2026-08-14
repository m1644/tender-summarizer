import json

import httpx
from openai import OpenAI

from app.config import get_settings
from app.exceptions import LLMConfigurationError, LLMProcessingError
from app.schemas import TenderSummary
from app.utils.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """
Ты эксперт по анализу государственных закупок и тендерной документации.

Тебе передается фрагмент тендерной документации.
Извлеки только информацию, которая подтверждается предоставленным текстом.

Нужно определить:
1. Сумму контракта.
2. Валюту.
3. Срок выполнения контракта.
4. Ключевые требования к исполнителю.
5. Штрафы, пени и другие меры ответственности.
6. Краткое резюме.

Правила:
- Не придумывай информацию.
- Если сумма отсутствует: "Не указана".
- Если валюта отсутствует: "Не указана".
- Если срок отсутствует: "Не указан".
- Требования возвращай отдельными пунктами.
- Штрафы и пени возвращай отдельными пунктами.
- Не смешивай требования и штрафы.
- Сохраняй денежные суммы, проценты и условия начисления пеней.
- Если штрафы не обнаружены, верни пустой список.
- Если информация неоднозначна, не делай предположение.
"""

AGGREGATION_PROMPT = """
Ты — финальный эксперт по проверке тендерной документации.
Тебе переданы структурированные результаты анализа нескольких фрагментов одного PDF.
Сформируй ЕДИНЫЙ итоговый объект TenderSummary.

Правила при конфликте данных:
- Для суммы контракта выбирай именно НМЦК/цену контракта, а не цену отдельного этапа,
  позиции, единицы товара, обеспечения или штрафа.
- Для срока выбирай срок исполнения самого контракта/обязательства, а не срок действия
  заявки, банковской гарантии или отдельного этапа, если это не единственный срок.
- Не объединяй противоречащие значения в одно поле. Выбирай значение, которое явно
  относится к контракту. Если определить нельзя — верни значение "Не указана" или
  "Не указан".
- Удали дубли требований и штрафов, сохрани юридически важные условия, проценты,
  суммы и основания начисления.
- Не придумывай отсутствующие сведения.
- Итоговое summary должно быть кратким и полезным для заказчика/исполнителя.
"""


def _summary_json_schema() -> dict:
    """Return JSON schema for Ollama structured output."""
    return {
        "type": "object",
        "properties": {
            "contract_amount": {"type": "string"},
            "currency": {"type": "string"},
            "execution_period": {"type": "string"},
            "key_requirements": {"type": "array", "items": {"type": "string"}},
            "penalties": {"type": "array", "items": {"type": "string"}},
            "summary": {"type": "string"},
        },
        "required": [
            "contract_amount",
            "currency",
            "execution_period",
            "key_requirements",
            "penalties",
            "summary",
        ],
        "additionalProperties": False,
    }


def _call_openai(text: str, system_prompt: str = SYSTEM_PROMPT) -> TenderSummary:
    """Analyze text using OpenAI structured output."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise LLMConfigurationError("OPENAI_API_KEY не настроен.")

    try:
        client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.llm_timeout_seconds,
        )
        response = client.chat.completions.parse(
            model=settings.openai_model,
            temperature=settings.llm_temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            response_format=TenderSummary,
        )
        message = response.choices[0].message
        if message.parsed is None:
            raise LLMProcessingError(
                "OpenAI не вернул структурированный ответ."
            )
        return message.parsed
    except LLMProcessingError:
        raise
    except Exception as exc:
        logger.exception("OpenAI request failed")
        raise LLMProcessingError(f"Ошибка OpenAI API: {exc}") from exc


def _call_ollama(text: str, system_prompt: str = SYSTEM_PROMPT) -> TenderSummary:
    """Analyze text using Ollama structured output."""
    settings = get_settings()
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "format": _summary_json_schema(),
        "options": {"temperature": settings.llm_temperature},
    }

    try:
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
    except Exception as exc:
        logger.exception("Ollama request failed")
        raise LLMProcessingError(f"Ошибка Ollama: {exc}") from exc

    try:
        data = response.json()
        content = data["message"]["content"]
        parsed = json.loads(content)
        return TenderSummary.model_validate(parsed)
    except Exception as exc:
        raise LLMProcessingError(
            f"Ollama вернула некорректный JSON: {exc}"
        ) from exc


def _call_provider(text: str, system_prompt: str) -> TenderSummary:
    """Call the configured LLM provider with a custom system prompt."""
    settings = get_settings()
    provider = settings.llm_provider.lower().strip()
    if provider == "openai":
        return _call_openai(text, system_prompt)
    if provider == "ollama":
        return _call_ollama(text, system_prompt)
    raise LLMConfigurationError(
        f"Неизвестный LLM_PROVIDER: {settings.llm_provider}"
    )


def analyze_text(text: str) -> TenderSummary:
    """Analyze one document chunk using the configured LLM provider."""
    return _call_provider(text, SYSTEM_PROMPT)


def aggregate_summaries(summaries: list[TenderSummary]) -> TenderSummary:
    """Use a second LLM pass to reconcile facts extracted from all chunks."""
    if not summaries:
        raise LLMProcessingError("Нет результатов для финальной агрегации.")

    payload = json.dumps(
        [item.model_dump(mode="json") for item in summaries],
        ensure_ascii=False,
        indent=2,
    )
    prompt = (
        "Ниже приведены результаты анализа фрагментов одного тендерного документа.\n"
        "Сведи их в один проверенный итоговый результат.\n\n"
        f"{payload}"
    )
    return _call_provider(prompt, AGGREGATION_PROMPT)


def merge_summaries(summaries: list[TenderSummary]) -> TenderSummary:
    """Backward-compatible deterministic merge for callers/tests."""
    if not summaries:
        raise LLMProcessingError("LLM не вернула результатов.")

    def unique(values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = " ".join(value.split()).strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key not in seen:
                seen.add(key)
                result.append(normalized)
        return result

    amounts = [
        item.contract_amount
        for item in summaries
        if item.contract_amount != "Не указана"
    ]
    currencies = [
        item.currency for item in summaries if item.currency != "Не указана"
    ]
    periods = [
        item.execution_period
        for item in summaries
        if item.execution_period != "Не указан"
    ]
    requirements = [value for item in summaries for value in item.key_requirements]
    penalties = [value for item in summaries for value in item.penalties]
    summaries_text = [item.summary.strip() for item in summaries if item.summary.strip()]

    return TenderSummary(
        contract_amount=amounts[0] if amounts else "Не указана",
        currency=currencies[0] if currencies else "Не указана",
        execution_period=periods[0] if periods else "Не указан",
        key_requirements=unique(requirements),
        penalties=unique(penalties),
        summary=" ".join(summaries_text[:5]),
    )
