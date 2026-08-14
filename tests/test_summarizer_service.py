import pytest

from app.schemas import TenderSummary
from app.services import summarizer_service


def make_summary(amount: str = "Не указана") -> TenderSummary:
    return TenderSummary(
        contract_amount=amount,
        currency="рублей" if amount != "Не указана" else "Не указана",
        execution_period="30 дней" if amount != "Не указана" else "Не указан",
        key_requirements=["Опыт работы"],
        penalties=["Пеня за просрочку"],
        summary="Фрагмент тендера.",
    )


@pytest.mark.asyncio
async def test_full_pipeline_uses_all_chunks_and_final_aggregator(monkeypatch):
    text = " ".join(f"текст {index}" for index in range(4000))
    chunks_seen: list[str] = []

    monkeypatch.setattr(summarizer_service, "extract_text_from_pdf", lambda _: text)
    monkeypatch.setattr(summarizer_service, "has_extractable_text", lambda _: True)

    def fake_analyze(chunk: str) -> TenderSummary:
        chunks_seen.append(chunk)
        if "текст 3999" in chunk:
            return make_summary("15 000 000")
        return make_summary()

    monkeypatch.setattr(summarizer_service, "analyze_text", fake_analyze)

    def fake_aggregate(summaries: list[TenderSummary]) -> TenderSummary:
        assert len(summaries) == len(chunks_seen)
        assert any(item.contract_amount == "15 000 000" for item in summaries)
        return TenderSummary(
            contract_amount="15 000 000",
            currency="рублей",
            execution_period="30 дней",
            key_requirements=["Опыт работы"],
            penalties=["Пеня за просрочку"],
            summary="Финальный результат.",
        )

    monkeypatch.setattr(summarizer_service, "aggregate_summaries", fake_aggregate)

    result = await summarizer_service.summarize_tender(b"%PDF-test")

    assert result.contract_amount == "15 000 000"
    assert result.summary == "Финальный результат."
    assert len(chunks_seen) > 1


@pytest.mark.asyncio
async def test_large_document_is_processed_without_truncation(monkeypatch):
    """Large PDFs must reach the chunker/LLM instead of being silently truncated."""
    text = "x" * 500_001
    chunks_seen: list[str] = []

    monkeypatch.setattr(summarizer_service, "extract_text_from_pdf", lambda _: text)
    monkeypatch.setattr(summarizer_service, "has_extractable_text", lambda _: True)

    def fake_analyze(chunk: str) -> TenderSummary:
        chunks_seen.append(chunk)
        return make_summary()

    monkeypatch.setattr(summarizer_service, "analyze_text", fake_analyze)
    monkeypatch.setattr(
        summarizer_service,
        "aggregate_summaries",
        lambda summaries: make_summary(),
    )

    result = await summarizer_service.summarize_tender(b"%PDF-test")

    assert result.contract_amount == "Не указана"
    assert len(chunks_seen) > 1
    assert sum(len(chunk) for chunk in chunks_seen) >= len(text)
