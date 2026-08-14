from app.config import get_settings
from app.services.chunking_service import split_text
from app.services.llm_service import analyze_text, merge_summaries
from app.services.ocr_service import extract_text_with_ocr
from app.services.pdf_service import extract_text_from_pdf, has_extractable_text
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def summarize_tender(content: bytes):
    """Run PDF extraction, OCR fallback, chunking, LLM analysis and merge."""
    settings = get_settings()
    text = extract_text_from_pdf(content)

    if not has_extractable_text(text):
        logger.info("Insufficient PDF text. Starting OCR fallback.")
        text = extract_text_with_ocr(content)

    if len(text) > settings.max_text_chars:
        logger.warning(
            "Text truncated: %d -> %d chars",
            len(text),
            settings.max_text_chars,
        )
        text = text[: settings.max_text_chars]

    chunks = split_text(
        text=text,
        chunk_size=settings.chunk_size,
        overlap=settings.chunk_overlap,
    )
    if not chunks:
        raise ValueError("Не удалось получить текст из документа.")

    logger.info("Document split into %d chunks", len(chunks))
    summaries = []
    for chunk in chunks:
        logger.info("Analyzing chunk %d/%d", chunk.index, len(chunks))
        summaries.append(analyze_text(chunk.text))

    return merge_summaries(summaries)
