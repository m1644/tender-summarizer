# Tender Documentation Summarizer

FastAPI-сервис для автоматического анализа тендерной документации в PDF.

Сервис принимает PDF-файл, извлекает текст, при необходимости запускает OCR для сканированных документов, обрабатывает **весь документ без искусственного обрезания по числу символов**, разбивает его на части и выполняет двухэтапный анализ через LLM. Финальный LLM-pass консолидирует результаты chunks и консервативно разрешает конфликты.

## Задача

Получить из тендерной документации:

- сумму контракта;
- валюту;
- сроки выполнения;
- ключевые требования к исполнителю;
- штрафы и пени;
- краткое резюме.

## Логика решения

```text
PDF
 ↓
Проверка файла
 ↓
pypdf extraction
 ↓
Текста достаточно?
 ├─ Да → chunking
 └─ Нет → OCR (Poppler + Tesseract) → chunking
                         ↓
              анализ каждого chunk
                         ↓
                Pydantic validation
                         ↓
             FINAL LLM reconciliation
                         ↓
           deduplication + conflict rules
                         ↓
                     JSON API
```

### Алгоритм

1. FastAPI принимает `multipart/form-data` с PDF.
2. Проверяется расширение, PDF signature и максимальный размер файла.
3. `pypdf` извлекает текст из обычного PDF.
4. Если текста недостаточно, включается OCR fallback.
5. **Весь полученный текст сохраняется.** Он не обрезается по `MAX_TEXT_CHARS`, поэтому штрафы и требования в конце большого документа не теряются.
6. Документ разбивается на перекрывающиеся chunks.
7. Каждый chunk передается выбранному LLM-провайдеру.
8. Ответ каждого вызова приводится к схеме `TenderSummary` через Pydantic.
9. Все chunk summaries передаются во второй LLM-pass для финальной консолидации.
10. Финальный агрегатор при конфликте сумм приоритетно выбирает НМЦК/цену всего контракта, а не стоимость этапа или отдельной позиции.
11. При неразрешимом конфликте финальный агрегатор возвращает безопасное значение `Не указана` / `Не указан`, вместо угадывания.
12. Списки требований и штрафов дедуплицируются.
13. API возвращает единый JSON-ответ.

## Архитектура

```text
app/
├── main.py
├── config.py
├── schemas.py
├── exceptions.py
├── api/routes.py
├── services/
│   ├── pdf_service.py
│   ├── ocr_service.py
│   ├── chunking_service.py
│   ├── llm_service.py
│   └── summarizer_service.py
└── utils/logging.py
```

Ответственность разделена по слоям: HTTP API, PDF/OCR, chunking, LLM и orchestration.

## LLM-провайдеры

### OpenAI

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_api_key
OPENAI_MODEL=gpt-4.1-mini
```

Используется structured output с Pydantic-схемой.

### Ollama

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
```

Ollama позволяет запускать модель локально без передачи документа внешнему LLM API.

## API

### `GET /`

Информация о сервисе.

### `GET /health`

Проверка состояния приложения, LLM configuration и OCR.

### `POST /summarize`

Основной endpoint. Принимает поле `file` типа `multipart/form-data`.

Пример:

```bash
curl -X POST \
  http://127.0.0.1:8000/summarize \
  -H "accept: application/json" \
  -F "file=@tender.pdf"
```

Ответ:

```json
{
  "contract_amount": "2 450 000",
  "currency": "рублей",
  "execution_period": "до 31 декабря 2026 года",
  "key_requirements": [
    "Наличие опыта выполнения аналогичных работ",
    "Предоставление обеспечения исполнения контракта"
  ],
  "penalties": [
    "Пеня за нарушение сроков исполнения обязательств"
  ],
  "summary": "Краткое резюме тендерной документации."
}
```

## Установка локально

Требуется Python 3.12+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

### macOS

```bash
brew install tesseract
brew install tesseract-lang
brew install poppler
```

### Ubuntu/Debian

```bash
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng poppler-utils
```

## Запуск

```bash
uvicorn app.main:app --reload
```

Swagger: `http://127.0.0.1:8000/docs`

ReDoc: `http://127.0.0.1:8000/redoc`

## Docker

Сборка:

```bash
docker build -t tender-summarizer .
```

Запуск:

```bash
docker run --env-file .env -p 8000:8000 tender-summarizer
```

Docker Compose:

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f api
```

Остановка:

```bash
docker compose down
```

Docker image уже содержит Poppler и Tesseract с русским и английским языками.

## Тестирование и QA

Тесты не требуют API key:

```bash
pytest -v
```

В тестах LLM вызывается через mock, поэтому CI не делает реальные платные запросы. Основной integration test проверяет полный pipeline: extraction → chunking → анализ chunks → финальная агрегация.

Проверка качества:

```bash
ruff check .
python -m compileall app tests
pytest -v
```

Перед сдачей рекомендуется также выполнить:

```bash
docker build -t tender-summarizer .
docker compose up --build -d
curl http://127.0.0.1:8000/health
```

После этого проверить `/docs` и обработать реальный текстовый и сканированный PDF.

## Конфигурация

Основные параметры находятся в `.env`:

```env
MAX_FILE_SIZE_MB=20
CHUNK_SIZE=12000
CHUNK_OVERLAP=1000
LLM_TEMPERATURE=0.1
LLM_TIMEOUT_SECONDS=120
ENABLE_OCR=true
OCR_LANGUAGE=rus+eng
OCR_DPI=200
```

Ограничение размера файла остается на уровне HTTP API. Ограничения на суммарное число символов документа нет: документ обрабатывается полностью через chunking.

`.env` не коммитится в Git. В репозитории хранится только `.env.example`.

## Обработка ошибок

- `400` — некорректный upload или не-PDF.
- `413` — превышен лимит размера.
- `422` — ошибка PDF/OCR/обработки документа.
- `500` — ошибка конфигурации сервера.
- `502` — ошибка LLM-провайдера.

## Git workflow

Разработка ведется в feature-ветке:

```bash
git checkout -b feature/tender-summarizer
git add .
git commit -m "feat: ..."
git push -u origin feature/tender-summarizer
```

Затем создается Pull Request:

```text
feature/tender-summarizer → main
```

История коммитов разбита по этапам: зависимости, конфигурация, PDF/OCR, chunking, LLM, API, тесты, Docker, документация и LICENSE.

## Ограничения текущей версии

Проект намеренно не включает авторизацию, БД, Redis/Celery, историю документов и frontend: исходная задача требует API для обработки PDF и структурированного извлечения информации.

Для очень больших production-документов количество LLM-вызовов растет пропорционально числу chunks. Следующий шаг масштабирования — очередь фоновых задач с ограничением параллелизма и кэшированием промежуточных результатов.

## Возможное развитие

- фоновые задачи и очередь для больших документов;
- PostgreSQL и история обработки;
- авторизация пользователей;
- Telegram Bot;
- Web UI с drag-and-drop;
- экспорт результатов в DOCX/PDF;
- дополнительные LLM-провайдеры;
- page-aware extraction и приоритизация юридически значимых разделов.

## License

MIT License. См. `LICENSE`.
