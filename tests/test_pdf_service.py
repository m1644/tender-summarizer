from io import BytesIO

from pypdf import PdfWriter

from app.services.pdf_service import extract_text_from_pdf, has_extractable_text


def create_pdf() -> bytes:
    """Create a minimal valid PDF."""
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.write(output)
    return output.getvalue()


def test_extract_valid_pdf():
    content = create_pdf()
    text = extract_text_from_pdf(content)
    assert isinstance(text, str)


def test_has_extractable_text():
    text = "Тестовая тендерная документация. " * 30
    assert has_extractable_text(text)


def test_short_text():
    assert not has_extractable_text("Короткий текст")
