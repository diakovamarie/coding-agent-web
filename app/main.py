from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.coding_service import code_responses
from app.parsers import parse_codebook_csv, parse_codebook_json, parse_responses_csv

app = FastAPI(title="Coding Agent", version="1.0.0")

_cors = os.environ.get("CORS_ORIGINS", "*")
_origins = [o.strip() for o in _cors.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins if _origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/code")
async def run_coding(
    responses: UploadFile = File(..., description="CSV: id + текст ответа"),
    codebook: UploadFile = File(..., description="JSON или CSV codebook"),
):
    if not responses.filename:
        raise HTTPException(400, "Файл ответов обязателен.")
    if not codebook.filename:
        raise HTTPException(400, "Файл codebook обязателен.")

    try:
        resp_bytes = await responses.read()
        rows, id_col, ans_col = parse_responses_csv(resp_bytes)
    except Exception as e:
        raise HTTPException(400, f"Ответы: {e}") from e

    try:
        cb_bytes = await codebook.read()
        name = (codebook.filename or "").lower()
        if name.endswith(".json"):
            codes = parse_codebook_json(cb_bytes)
        else:
            codes = parse_codebook_csv(cb_bytes)
    except Exception as e:
        raise HTTPException(400, f"Codebook: {e}") from e

    try:
        table, frequencies, manual = await code_responses(rows, codes)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"Ошибка кодирования: {e}") from e

    return JSONResponse(
        {
            "meta": {
                "respondents": len(table),
                "id_column_hint": id_col,
                "answer_column_hint": ans_col,
            },
            "coding_table": table,
            "frequencies": frequencies,
            "manual_review": manual,
        }
    )


@app.get("/api/health")
async def health():
    return {"ok": True}


_static = Path(__file__).resolve().parent.parent / "static"
_index = _static / "index.html"


@app.get("/")
async def root():
    """Без mount('/') — иначе на части окружений ломается порядок маршрутов."""
    if _index.is_file():
        return FileResponse(_index, media_type="text/html; charset=utf-8")
    return JSONResponse({"error": "static/index.html не найден"}, status_code=404)
