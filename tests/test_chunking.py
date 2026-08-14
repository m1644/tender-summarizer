import pytest

from app.services.chunking_service import split_text


def test_small_text_returns_one_chunk():
    chunks = split_text("Тестовый текст", chunk_size=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0].index == 1
    assert chunks[0].text == "Тестовый текст"


def test_large_text_is_split():
    text = "A" * 500
    chunks = split_text(text, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    assert all(chunk.text for chunk in chunks)


def test_invalid_overlap():
    with pytest.raises(ValueError):
        split_text("test", chunk_size=100, overlap=100)


def test_empty_text():
    chunks = split_text("", chunk_size=100, overlap=10)
    assert chunks == []
