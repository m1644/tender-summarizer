import io

from pypdf import PdfReader

from app.exceptions import PDFProcessingError


def extract_text_from_pdf(content: bytes) -> str:
    """Extract text from a text-based PDF."""
    if not content:
        raise PDFProcessingError("PDF-файл пуст.")

    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as exc:
        raise PDFProcessingError(f"Не удалось открыть PDF: {exc}") from exc

    if not reader.pages:
        raise PDFProcessingError("PDF не содержит страниц.")

    pages: list[str] = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text = text.strip()
        if text:
            pages.append(f"\n--- Страница {page_number} ---\n{text}")

    return "\n".join(pages).strip()


def has_extractable_text(text: str, minimum_chars: int = 100) -> bool:
    """Check whether extracted text is usable."""
    normalized = " ".join(text.split())
    return len(normalized) >= minimum_chars
