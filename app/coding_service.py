from __future__ import annotations

import json
import os
import re
from collections import Counter

import httpx

from app.parsers import CodebookEntry, ResponseRow

OPENAI_URL = os.environ.get("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

RESERVED_OTHER = "ДРУГОЕ"
RESERVED_UNCLEAR = "ЗАТРУДНЯЮСЬ ОТВЕТИТЬ"

SYSTEM_PROMPT = """Coding agent для открытых ответов. Есть фиксированный codebook.

Правила: только коды из codebook; без новых категорий; не summary; мультикод разрешён.
Если не подходит ни один код — код ДРУГОЕ (если есть в списке). Если неясно — ЗАТРУДНЯЮСЬ ОТВЕТИТЬ (если есть).
Ответ строго JSON по схеме пользователя; в codes только значения поля code из codebook."""


def _ensure_reserved_codes(entries: list[CodebookEntry]) -> list[CodebookEntry]:
    codes = {e.code.strip().upper() for e in entries}
    labels_upper = {e.label.strip().upper() for e in entries}
    out = list(entries)
    if RESERVED_OTHER.upper() not in codes and RESERVED_OTHER not in labels_upper:
        out.append(CodebookEntry(code="OTHER", label=RESERVED_OTHER, definition="Ни один код не подходит."))
    if RESERVED_UNCLEAR.upper() not in codes and RESERVED_UNCLEAR not in labels_upper:
        out.append(
            CodebookEntry(
                code="UNCLEAR",
                label=RESERVED_UNCLEAR,
                definition="Недостаточно информации для кодирования.",
            )
        )
    return out


def _codebook_block(entries: list[CodebookEntry]) -> str:
    lines = []
    for e in entries:
        d = f" — {e.definition}" if e.definition else ""
        lines.append(f'- code: "{e.code}" | label: "{e.label}"{d}')
    return "\n".join(lines)


def _needs_manual(codes: list[str], entries: list[CodebookEntry]) -> bool:
    label_by_code = {e.code.strip().upper(): e.label.strip().upper() for e in entries}
    for c in codes:
        cu = c.strip().upper()
        lab = label_by_code.get(cu, "")
        if RESERVED_OTHER in cu or RESERVED_OTHER in lab:
            return True
        if RESERVED_UNCLEAR in cu or RESERVED_UNCLEAR in lab:
            return True
        if cu in ("OTHER", "UNCLEAR"):
            return True
    return False


async def _call_openai(user_content: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Не задана переменная окружения OPENAI_API_KEY.")

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(OPENAI_URL, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Неожиданный ответ API: {data!r}") from exc


def _parse_llm_json(raw: str) -> list[dict]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    data = json.loads(raw)
    items = data.get("items") or data.get("rows") or data.get("coding")
    if not isinstance(items, list):
        raise ValueError("JSON должен содержать массив items с полями respondent_id, answer, codes.")
    return items


async def code_responses(
    rows: list[ResponseRow],
    codebook: list[CodebookEntry],
    batch_size: int = 15,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Returns: coding_table, frequencies, manual_review_rows
    """
    entries = _ensure_reserved_codes(codebook)
    allowed_codes = {e.code.strip() for e in entries}

    coding_table: list[dict] = []
    all_code_counts: Counter[str] = Counter()

    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        ids_answers = [
            {"respondent_id": r.respondent_id, "answer": r.answer} for r in batch
        ]

        user_msg = f"""Codebook:
{_codebook_block(entries)}

Закодируй каждый ответ. Разрешённые значения в codes — только поля code из codebook.

Верни JSON объект:
{{
  "items": [
    {{
      "respondent_id": "<как во входе>",
      "answer": "<копия текста ответа>",
      "codes": ["<code1>", "<code2>"]
    }}
  ]
}}

Данные для кодирования (JSON):
{json.dumps(ids_answers, ensure_ascii=False)}"""

        content = await _call_openai(user_msg)
        items = _parse_llm_json(content)

        by_id = {str(it.get("respondent_id")): it for it in items if isinstance(it, dict)}

        for r in batch:
            it = by_id.get(r.respondent_id)
            if not it:
                codes = ["UNCLEAR"] if "UNCLEAR" in allowed_codes else list(allowed_codes)[:1]
                answer_out = r.answer
            else:
                codes = it.get("codes") or []
                if not isinstance(codes, list):
                    codes = []
                codes = [str(c).strip() for c in codes if str(c).strip()]
                codes = [c for c in codes if c in allowed_codes]
                answer_out = str(it.get("answer") or r.answer)

            if not codes:
                fallback = "OTHER" if "OTHER" in allowed_codes else next(iter(allowed_codes))
                codes = [fallback]

            manual = _needs_manual(codes, entries)
            coding_table.append(
                {
                    "respondent_id": r.respondent_id,
                    "answer": answer_out,
                    "codes": codes,
                    "needs_manual_review": manual,
                }
            )
            all_code_counts.update(codes)

    n_respondents = len(coding_table)
    frequencies: list[dict] = []
    total_assignments = sum(all_code_counts.values()) or 1
    for code, n in sorted(all_code_counts.items(), key=lambda x: (-x[1], x[0])):
        label = next((e.label for e in entries if e.code == code), code)
        frequencies.append(
            {
                "code": code,
                "label": label,
                "n": n,
                "pct_of_assignments": round(100.0 * n / total_assignments, 2),
                "pct_of_respondents": round(100.0 * n / max(n_respondents, 1), 2),
            }
        )

    manual_review = [row for row in coding_table if row["needs_manual_review"]]

    return coding_table, frequencies, manual_review
