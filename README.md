# Coding agent (веб)

Загрузка CSV с открытыми ответами + codebook (JSON/CSV) → кодирование через OpenAI API → таблица кодов, частоты, список на ручную проверку.

## Структура репозитория

```
coding-agent-web/
  app/                 # FastAPI: API и логика
  static/              # index.html (встроенные стили и скрипт)
  examples/            # примеры файлов для проверки
  requirements.txt
  render.yaml          # опционально: Blueprint для Render
  runtime.txt          # версия Python на Render
  README.md
```

## Локальный запуск

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."   # Windows PowerShell: $env:OPENAI_API_KEY="sk-..."
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Открой `http://127.0.0.1:8000`. Документация API: `http://127.0.0.1:8000/docs`.

## Деплой на Render

1. Залей **содержимое** папки `coding-agent-web` в корень GitHub-репозитория (или укажи в Render **Root Directory** = `coding-agent-web`, если репозиторий содержит только эту папку как подкаталог).
2. **New** → **Web Service** → подключи репозиторий.
3. Настройки:
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. **Environment** → добавь секрет **`OPENAI_API_KEY`** (ключ OpenAI).
5. Опционально: **`OPENAI_MODEL`** (по умолчанию `gpt-4o-mini`), **`CORS_ORIGINS`** (через запятую, если фронт на другом домене).

Если используешь `render.yaml` из репозитория, при создании сервиса выбери подключение Blueprint — переменные подтянутся из файла, ключ `OPENAI_API_KEY` нужно задать вручную в панели.

## Форматы файлов

**Ответы (CSV):** колонки с id и текстом, например `respondent_id` + `answer` (другие имена см. в `app/parsers.py`).

**Codebook (JSON):** массив `codes` с полями `code`, `label`, опционально `definition`.

**Codebook (CSV):** колонки кода и названия (`code`, `label` и аналоги).

## Переменные окружения

| Переменная | Обязательно | Описание |
|------------|-------------|----------|
| `OPENAI_API_KEY` | да | Ключ API OpenAI |
| `OPENAI_MODEL` | нет | Модель чата (по умолчанию `gpt-4o-mini`) |
| `OPENAI_API_URL` | нет | URL `.../v1/chat/completions` при совместимом прокси |
| `CORS_ORIGINS` | нет | Список origin через запятую или `*` |
