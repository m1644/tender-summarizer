from app.schemas import TenderSummary
from app.services import llm_service


def test_aggregate_summaries_uses_final_llm_pass(monkeypatch):
    chunk_summaries = [
        TenderSummary(
            contract_amount="2 000 000",
            currency="рублей",
            execution_period="30 дней",
            key_requirements=["Опыт аналогичных работ"],
            penalties=[],
            summary="Стоимость отдельного этапа.",
        ),
        TenderSummary(
            contract_amount="15 000 000",
            currency="рублей",
            execution_period="90 дней",
            key_requirements=[],
            penalties=["Пеня 0,1 процента за каждый день"],
            summary="НМЦК и общий срок контракта.",
        ),
    ]
    captured: dict[str, str] = {}
    expected = TenderSummary(
        contract_amount="15 000 000",
        currency="рублей",
        execution_period="90 дней",
        key_requirements=["Опыт аналогичных работ"],
        penalties=["Пеня 0,1 процента за каждый день"],
        summary="Финальное консолидированное резюме.",
    )

    def fake_call_llm(text: str, system_prompt: str) -> TenderSummary:
        captured["text"] = text
        captured["system_prompt"] = system_prompt
        return expected

    monkeypatch.setattr(llm_service, "_call_llm", fake_call_llm)

    result = llm_service.aggregate_summaries(chunk_summaries)

    assert result == expected
    assert "15 000 000" in captured["text"]
    assert "2 000 000" in captured["text"]
    assert "НМЦК" in captured["system_prompt"]
    assert "Не придумывай" in captured["system_prompt"]
