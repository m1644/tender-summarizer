from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.main import app
from app.schemas import TenderSummary
from app.services import summarizer_service

client = TestClient(app)


def create_pdf() -> bytes:
    """Create a minimal valid PDF."""
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.write(output)
    return output.getvalue()


def test_non_pdf_is_rejected():
    response = client.post(
        "/summarize",
        files={"file": ("document.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400


def test_invalid_pdf_signature():
    response = client.post(
        "/summarize",
        files={"file": ("document.pdf", b"not a pdf", "application/pdf")},
    )
    assert response.status_code == 400


def test_summary_schema():
    result = TenderSummary(
        contract_amount="1 000 000",
        currency="рублей",
        execution_period="30 дней",
        key_requirements=["Опыт выполнения работ"],
        penalties=["Пеня за просрочку"],
        summary="Тестовое резюме.",
    )
    assert result.contract_amount == "1 000 000"
    assert result.currency == "рублей"
    assert len(result.key_requirements) == 1
    assert len(result.penalties) == 1


@pytest.mark.asyncio
async def test_full_pipeline_uses_all_chunks_and_final_aggregation(monkeypatch):
    source_text = (
        "НМЦК 15 000 000 рублей. Срок исполнения 90 дней. "
        "Исполнитель должен иметь опыт аналогичных работ. "
        "За просрочку начисляется пеня 0,1 процента за каждый день. "
    ) * 120
    chunk_results = [
        TenderSummary(
            contract_amount="Не указана",
            currency="Не указана",
            execution_period="Не указан",
            key_requirements=["Опыт аналогичных работ"],
            penalties=["Пеня 0,1 процента за каждый день"],
            summary="Фрагмент документа.",
        ),
        TenderSummary(
            contract_amount="15 000 000",
            currency="рублей",
            execution_period="90 дней",
            key_requirements=[],
            penalties=[],
            summary="НМЦК и срок исполнения.",
        ),
    ]
    analyzed_chunks: list[str] = []

    monkeypatch.setattr(summarizer_service, "extract_text_from_pdf", lambda _: source_text)
    monkeypatch.setattr(summarizer_service, "has_extractable_text", lambda _: True)
    monkeypatch.setattr(
        summarizer_service,
        "analyze_text",
        lambda text: analyzed_chunks.append(text)
        or chunk_results[(len(analyzed_chunks) - 1) % len(chunk_results)],
    )

    final_result = TenderSummary(
        contract_amount="15 000 000",
        currency="рублей",
        execution_period="90 дней",
        key_requirements=["Опыт аналогичных работ"],
        penalties=["Пеня 0,1 процента за каждый день"],
        summary="Консолидированное резюме тендера.",
    )
    aggregation_input: list[TenderSummary] = []

    def fake_aggregate(items: list[TenderSummary]) -> TenderSummary:
        aggregation_input.extend(items)
        return final_result

    monkeypatch.setattr(summarizer_service, "aggregate_summaries", fake_aggregate)

    result = await summarizer_service.summarize_tender(create_pdf())

    assert len(analyzed_chunks) >= 2
    assert len(aggregation_input) == len(analyzed_chunks)
    assert result == final_result
    assert len("".join(analyzed_chunks)) >= len(source_text) * 0.9


def test_empty_pdf_reaches_processing(monkeypatch):
    monkeypatch.setattr(summarizer_service, "extract_text_from_pdf", lambda _: "")
    monkeypatch.setattr(summarizer_service, "has_extractable_text", lambda _: False)
    monkeypatch.setattr(summarizer_service, "extract_text_with_ocr", lambda _: "")

    response = client.post(
        "/summarize",
        files={
            "file": (
                "document.pdf",
                create_pdf(),
                "application/pdf",
            )
        },
    )
    assert response.status_code == 422
