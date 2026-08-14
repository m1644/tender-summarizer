from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.config import get_settings
from app.utils.logging import configure_logging, get_logger

configure_logging()
settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle."""
    logger.info(
        "Starting %s v%s",
        settings.app_name,
        settings.app_version,
    )
    logger.info("LLM provider: %s", settings.llm_provider)
    logger.info("OCR enabled: %s", settings.enable_ocr)
    yield
    logger.info("Application shutdown")


app = FastAPI(
    title=settings.app_name,
    description="API для анализа тендерной документации в PDF.",
    version=settings.app_version,
    lifespan=lifespan,
)
app.include_router(router)
