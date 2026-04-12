# Coding agent (веб)

Загрузка CSV с открытыми ответами + codebook (JSON/CSV) → кодирование через OpenAI API → таблица кодов, частоты, список на ручную проверку.

## Структура репозитория

```
coding-agent-web/
  app/                 # FastAPI: API и логика
  static/              # index.html (встроенные стили и скрипт)
  examples/            # примеры файлов для проверки
  run.py               # точка входа для Render (PORT + uvicorn)
  requirements.txt
  Procfile
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
python run.py
# или: uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Открой `http://127.0.0.1:8000`. Документация API: `http://127.0.0.1:8000/docs`.

## Деплой на Render

1. Залей **содержимое** папки `coding-agent-web` в корень GitHub-репозитория (или укажи в Render **Root Directory** = `coding-agent-web`, если репозиторий содержит только эту папку как подкаталог).
2. **New** → **Web Service** → подключи репозиторий.
3. Настройки:
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python run.py` (в `run.py` подставляется переменная `PORT` от Render)
4. **Environment** → добавь секрет **`OPENAI_API_KEY`** (ключ OpenAI).
5. Опционально: **`OPENAI_MODEL`** (по умолчанию `gpt-4o-mini`), **`CORS_ORIGINS`** (через запятую, если фронт на другом домене).

Если используешь `render.yaml` из репозитория, при создании сервиса выбери подключение Blueprint — переменные подтянутся из файла, ключ `OPENAI_API_KEY` нужно задать вручную в панели.

### Ошибка деплоя «Exited with status 1»

1. **Root Directory** в настройках сервиса должен указывать на папку, где лежат `requirements.txt` и каталог `app/` (если репозиторий не только этот проект — укажи подпапку, например `coding-agent-web`).
2. Во вкладке **Logs** открой **полный лог**: чаще всего там `ModuleNotFoundError: No module named 'app'` (неверный root) или ошибка `pip install` / версии Python.
3. **Start Command:** `python run.py` (как в `render.yaml` и `Procfile`).
4. Версия Python задаётся `runtime.txt` (сейчас `3.11.9` — стабильно на Render).

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
