from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.main import app
from app.schemas import TenderSummary

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


def test_empty_pdf_reaches_processing():
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
    assert response.status_code in {422, 500}
