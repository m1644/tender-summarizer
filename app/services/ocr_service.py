import pytesseract
from pdf2image import convert_from_bytes

from app.config import get_settings
from app.exceptions import OCRProcessingError
from app.utils.logging import get_logger

logger = get_logger(__name__)


def extract_text_with_ocr(content: bytes) -> str:
    """Extract text from scanned PDF using Tesseract OCR."""
    settings = get_settings()

    if not settings.enable_ocr:
        raise OCRProcessingError("OCR отключен в настройках.")

    try:
        images = convert_from_bytes(
            content,
            dpi=settings.ocr_dpi,
            fmt="jpeg",
        )
    except Exception as exc:
        raise OCRProcessingError(
            "Не удалось преобразовать PDF в изображения. "
            "Убедитесь, что установлен Poppler."
        ) from exc

    if not images:
        raise OCRProcessingError("OCR не получил изображения из PDF.")

    pages: list[str] = []
    for page_number, image in enumerate(images, start=1):
        try:
            text = pytesseract.image_to_string(
                image,
                lang=settings.ocr_language,
            )
        except Exception as exc:
            logger.warning("OCR failed page=%d error=%s", page_number, exc)
            continue

        text = text.strip()
        if text:
            pages.append(f"\n--- OCR Страница {page_number} ---\n{text}")

    result = "\n".join(pages).strip()
    if not result:
        raise OCRProcessingError("OCR не смог распознать текст документа.")

    return result
