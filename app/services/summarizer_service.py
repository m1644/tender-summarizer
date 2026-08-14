from app.config import get_settings
from app.services.chunking_service import split_text
from app.services.llm_service import aggregate_summaries, analyze_text
from app.services.ocr_service import extract_text_with_ocr
from app.services.pdf_service import extract_text_from_pdf, has_extractable_text
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def summarize_tender(content: bytes):
    """Run PDF extraction, OCR fallback, chunking, LLM analysis and final aggregation."""
    settings = get_settings()
    text = extract_text_from_pdf(content)

    if not has_extractable_text(text):
        if not settings.enable_ocr:
            raise ValueError("Не удалось получить текст из документа, а OCR отключен.")
        logger.info("Insufficient PDF text. Starting OCR fallback.")
        text = extract_text_with_ocr(content)

    if not text.strip():
        raise ValueError("Не удалось получить текст из документа.")

    if len(text) > settings.max_text_chars:
        raise ValueError(
            "Документ содержит слишком много текста для безопасной обработки. "
            f"Максимум: {settings.max_text_chars:,} символов. "
            "Увеличьте MAX_TEXT_CHARS или разделите документ."
        )

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

    logger.info("Running final LLM aggregation for %d chunk summaries", len(summaries))
    return aggregate_summaries(summaries)
