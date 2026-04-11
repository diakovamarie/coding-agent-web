from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass


@dataclass
class ResponseRow:
    respondent_id: str
    answer: str


@dataclass
class CodebookEntry:
    code: str
    label: str
    definition: str = ""


ID_CANDIDATES = ("respondent_id", "id", "resp_id", "case_id", "rid", "номер", "id_респондента")
ANSWER_CANDIDATES = (
    "answer",
    "text",
    "open_answer",
    "response",
    "высказывание",
    "ответ",
    "текст",
    "open",
)


def _norm_col(c: str) -> str:
    return str(c).strip().lower().replace(" ", "_")


def _read_csv_rows(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    lines = list(reader)
    if not lines:
        raise ValueError("Пустой CSV.")
    headers = [_norm_col(c) for c in lines[0]]
    rows: list[dict[str, str]] = []
    for parts in lines[1:]:
        row: dict[str, str] = {}
        for i, h in enumerate(headers):
            v = parts[i].strip() if i < len(parts) and parts[i] is not None else ""
            row[h] = v
        rows.append(row)
    return headers, rows


def parse_responses_csv(content: bytes) -> tuple[list[ResponseRow], str, str]:
    headers, dict_rows = _read_csv_rows(content)
    header_set = set(headers)

    id_col = next((c for c in ID_CANDIDATES if c in header_set), None)
    if id_col is None:
        id_col = headers[0]

    ans_col = next((c for c in ANSWER_CANDIDATES if c in header_set), None)
    if ans_col is None:
        if len(headers) < 2:
            raise ValueError("В файле ответов нужны минимум 2 колонки (id и текст).")
        ans_col = headers[1]

    out: list[ResponseRow] = []
    for row in dict_rows:
        rid = row.get(id_col, "").strip()
        ans = row.get(ans_col, "").strip()
        if ans:
            out.append(ResponseRow(respondent_id=rid, answer=ans))

    if not out:
        raise ValueError("Нет непустых ответов в файле.")

    return out, id_col, ans_col


def parse_codebook_json(content: bytes) -> list[CodebookEntry]:
    data = json.loads(content.decode("utf-8-sig"))
    if isinstance(data, dict) and "codes" in data:
        items = data["codes"]
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError("JSON codebook: ожидается объект с ключом 'codes' или массив кодов.")

    out: list[CodebookEntry] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        code = str(it.get("code") or it.get("id") or it.get("код") or "").strip()
        label = str(it.get("label") or it.get("name") or it.get("наименование") or "").strip()
        definition = str(
            it.get("definition") or it.get("description") or it.get("описание") or ""
        ).strip()
        if code and label:
            out.append(CodebookEntry(code=code, label=label, definition=definition))
    if not out:
        raise ValueError("В codebook нет валидных записей (code + label).")
    return out


def parse_codebook_csv(content: bytes) -> list[CodebookEntry]:
    headers, dict_rows = _read_csv_rows(content)
    hs = set(headers)

    code_col = next((c for c in ("code", "код", "id", "variable") if c in hs), None)
    if code_col is None:
        code_col = headers[0]

    label_col = next((c for c in ("label", "name", "наименование", "категория", "title") if c in hs), None)
    if label_col is None:
        label_col = headers[1] if len(headers) > 1 else code_col

    def_col = next(
        (c for c in ("definition", "description", "описание", "правило", "rules") if c in hs), None
    )

    out: list[CodebookEntry] = []
    for row in dict_rows:
        code = row.get(code_col, "").strip()
        label = row.get(label_col, "").strip()
        definition = row.get(def_col, "").strip() if def_col else ""
        if code and label:
            out.append(CodebookEntry(code=code, label=label, definition=definition))
    if not out:
        raise ValueError("В CSV codebook нет валидных строк.")
    return out
