from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.config import get_settings
from app.exceptions import (
    LLMConfigurationError,
    LLMProcessingError,
    OCRProcessingError,
    PDFProcessingError,
)
from app.schemas import HealthResponse, TenderSummary
from app.services.summarizer_service import summarize_tender
from app.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/", tags=["system"])
async def root() -> dict[str, str]:
    settings = get_settings()
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "ok",
        "docs": "/docs",
    }


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    settings = get_settings()
    llm_configured = (
        settings.llm_provider.lower() == "ollama"
        or bool(settings.openai_api_key)
    )
    return HealthResponse(
        status="healthy",
        llm_provider=settings.llm_provider,
        llm_configured=llm_configured,
        ocr_enabled=settings.enable_ocr,
    )


@router.post(
    "/summarize",
    response_model=TenderSummary,
    responses={
        400: {"description": "Invalid file"},
        413: {"description": "File too large"},
        422: {"description": "Document processing error"},
        500: {"description": "Server configuration error"},
        502: {"description": "LLM processing error"},
    },
    status_code=status.HTTP_200_OK,
    tags=["tenders"],
)
async def summarize(file: UploadFile = File(...)) -> TenderSummary:
    settings = get_settings()

    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не выбран.")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Поддерживаются только PDF-файлы.",
        )

    content = await file.read()
    max_size = settings.max_file_size_mb * 1024 * 1024

    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=(
                "Файл слишком большой. "
                f"Максимальный размер: {settings.max_file_size_mb} MB."
            ),
        )

    if not content.startswith(b"%PDF"):
        raise HTTPException(
            status_code=400,
            detail="Файл не является корректным PDF.",
        )

    logger.info("Processing file=%s size=%d", file.filename, len(content))

    try:
        return await summarize_tender(content)
    except PDFProcessingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OCRProcessingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except LLMProcessingError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected tender processing error")
        raise HTTPException(
            status_code=500,
            detail="Внутренняя ошибка сервера.",
        ) from exc
