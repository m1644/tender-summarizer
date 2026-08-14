from pydantic import BaseModel, Field


class TenderSummary(BaseModel):
    """Structured tender summary."""

    contract_amount: str = Field(default="Не указана", description="Сумма контракта.")
    currency: str = Field(default="Не указана", description="Валюта контракта.")
    execution_period: str = Field(default="Не указан", description="Срок выполнения контракта.")
    key_requirements: list[str] = Field(default_factory=list, description="Ключевые требования к исполнителю.")
    penalties: list[str] = Field(default_factory=list, description="Штрафы, пени и иные меры ответственности.")
    summary: str = Field(default="", description="Краткое резюме документа.")


class HealthResponse(BaseModel):
    """Health-check response."""

    status: str
    llm_provider: str
    llm_configured: bool
    ocr_enabled: bool


class ErrorResponse(BaseModel):
    """API error response."""

    detail: str
