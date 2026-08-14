import asyncio

from app.config import get_settings
from app.services.chunking_service import split_text
from app.services.llm_service import aggregate_summaries, analyze_text
from app.services.ocr_service import extract_text_with_ocr
from app.services.pdf_service import extract_text_from_pdf, has_extractable_text
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def summarize_tender(content: bytes):
    """Extract, chunk and analyze the complete document with final reconciliation."""
    settings = get_settings()
    text = await asyncio.to_thread(extract_text_from_pdf, content)

    if not has_extractable_text(text):
        logger.info("Insufficient PDF text. Starting OCR fallback.")
        if not settings.enable_ocr:
            raise ValueError("В PDF не найден текст, а OCR отключен.")
        text = await asyncio.to_thread(extract_text_with_ocr, content)

    if not text.strip():
        raise ValueError("Не удалось получить текст из документа.")

    chunks = split_text(
        text=text,
        chunk_size=settings.chunk_size,
        overlap=settings.chunk_overlap,
    )
    if not chunks:
        raise ValueError("Не удалось получить текст из документа.")

    logger.info(
        "Document contains %d characters and was split into %d chunks",
        len(text),
        len(chunks),
    )

    summaries = []
    for chunk in chunks:
        logger.info("Analyzing chunk %d/%d", chunk.index, len(chunks))
        summaries.append(await asyncio.to_thread(analyze_text, chunk.text))

    logger.info("Running final LLM reconciliation over %d chunk summaries", len(summaries))
    return await asyncio.to_thread(aggregate_summaries, summaries)
