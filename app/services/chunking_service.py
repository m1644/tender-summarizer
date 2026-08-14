from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    """A document text chunk."""

    index: int
    text: str


def split_text(text: str, chunk_size: int, overlap: int) -> list[TextChunk]:
    """Split text into overlapping chunks, preferring paragraph boundaries."""
    if not text.strip():
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size должен быть больше 0.")
    if overlap < 0:
        raise ValueError("overlap не может быть отрицательным.")
    if overlap >= chunk_size:
        raise ValueError("overlap должен быть меньше chunk_size.")

    normalized = text.replace("\r\n", "\n").strip()
    if len(normalized) <= chunk_size:
        return [TextChunk(index=1, text=normalized)]

    chunks: list[TextChunk] = []
    start = 0
    chunk_index = 1

    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        if end < len(normalized):
            boundary = normalized.rfind("\n\n", start, end)
            if boundary > start + chunk_size // 2:
                end = boundary

        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(TextChunk(index=chunk_index, text=chunk))
            chunk_index += 1

        if end >= len(normalized):
            break

        start = max(end - overlap, start + 1)

    return chunks
