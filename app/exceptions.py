class TenderSummarizerError(Exception):
    """Base application exception."""


class PDFProcessingError(TenderSummarizerError):
    """PDF processing error."""


class OCRProcessingError(TenderSummarizerError):
    """OCR processing error."""


class LLMProcessingError(TenderSummarizerError):
    """LLM processing error."""


class LLMConfigurationError(TenderSummarizerError):
    """LLM configuration error."""
