"""OpenRouter-backed SQL generation and chat session persistence."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any
from urllib import error, request

from api.services.report_snapshots import get_report_run
from api.services.supabase import SupabaseClient, SupabaseError
from api.services.uploads import get_upload

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_DEFAULT_MODEL = "google/gemma-4-31b-it"
_DEFAULT_ROW_LIMIT = 100
_MAX_ROW_LIMIT = 200
_ALLOWED_VIEWS = (
    "payroll_report_summary_view",
    "payroll_report_weekly_view",
    "payroll_report_daily_view",
)


class OpenRouterError(RuntimeError):
    """Raised when OpenRouter cannot complete the request."""


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise OpenRouterError(f"Eksik ortam değişkeni: {name}")
    return value


def _post_openrouter(messages: list[dict[str, str]], *, temperature: float = 0.1) -> str:
    api_key = _require_env("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL
    payload = {
        "model": model,
        "temperature": temperature,
        "messages": messages,
    }
    req = request.Request(
        _OPENROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://otomhr.vercel.app",
            "X-Title": "Otom Bordro AI",
        },
    )
    try:
        with request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
    except error.HTTPError as exc:  # pragma: no cover - network surface
        raw = exc.read().decode("utf-8", errors="replace")
        raise OpenRouterError(f"OpenRouter HTTP {exc.code}: {raw}") from exc
    except error.URLError as exc:  # pragma: no cover - network surface
        raise OpenRouterError(f"OpenRouter erişim hatası: {exc.reason}") from exc

    try:
        body = json.loads(raw)
        return str(body["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise OpenRouterError(f"OpenRouter cevabı çözümlenemedi: {raw}") from exc


def _extract_json_object(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise OpenRouterError(f"Model geçerli JSON döndürmedi: {text}")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise OpenRouterError(f"Model JSON cevabı ayrıştırılamadı: {text}") from exc


def _validate_sql(sql: str, row_limit: int) -> str:
    normalized = re.sub(r"\s+", " ", sql or "").strip()
    if not normalized:
        raise OpenRouterError("Model boş SQL üretti.")
    if ";" in normalized:
        raise OpenRouterError("SQL tek statement olmalıdır.")
    if not re.match(r"^(select|with)\s", normalized, flags=re.IGNORECASE):
        raise OpenRouterError("Sadece SELECT sorguları desteklenir.")
    if re.search(
        r"\b(insert|update|delete|drop|alter|create|grant|revoke|truncate|call|copy|comment|vacuum|analyze|refresh|merge)\b",
        normalized,
        flags=re.IGNORECASE,
    ):
        raise OpenRouterError("Sorguda yasaklı anahtar kelime tespit edildi.")
    if not re.search(
        r"\b(from|join)\s+(public\.)?payroll_report_(summary|weekly|daily)_view\b",
        normalized,
        flags=re.IGNORECASE,
    ):
        raise OpenRouterError(
            "SQL yalnızca payroll_report_summary_view, payroll_report_weekly_view "
            "veya payroll_report_daily_view üzerinden sorgu yapmalıdır."
        )
    if not re.search(r"\blimit\s+\d+\b", normalized, flags=re.IGNORECASE):
        normalized = f"{normalized} LIMIT {row_limit}"
    return normalized


def _build_sql_prompt(question: str, run: dict[str, Any], row_limit: int) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You generate safe PostgreSQL SELECT statements for monthly payroll report analytics. "
                "Only query these views: payroll_report_summary_view, payroll_report_weekly_view, "
                "payroll_report_daily_view. Never use semicolons. "
                f"Always keep LIMIT <= {row_limit}. Return JSON only with keys sql and title."
            ),
        },
        {
            "role": "user",
            "content": (
                "Kullanici sorusu:\n"
                f"{question}\n\n"
                f"Aktif rapor donemi: {run.get('label')} (year={run.get('year')}, month={run.get('month')})\n"
                f"Personel sayisi: {run.get('employee_count')}, gunluk kayit: {run.get('record_count')}\n"
                f"Toplam NM: {run.get('total_nm')}, Toplam FM: {run.get('total_fm')}\n\n"
                "Kullanabilecegin view'lar:\n"
                "1) public.payroll_report_summary_view\n"
                "   Kolonlar: run_id, upload_id, year, month, period_label, sicil_no, personel, firma, bolum, "
                "pozisyon, calisma_gunu, normal_calisma, fazla_mesai, fm_nm_aktarim, yillik_izin_gun, "
                "ucretli_izin_gun, rapor_gun, ucretsiz_izin_gun, devamsizlik_gun, hafta_tatili_gun, "
                "pazar_kesintisi, row_data\n"
                "2) public.payroll_report_weekly_view\n"
                "   Kolonlar: run_id, upload_id, year, month, period_label, sicil_no, personel, hafta, "
                "normal_calisma, fazla_mesai, fm_nm_aktarim, pazar_durumu, row_data\n"
                "3) public.payroll_report_daily_view\n"
                "   Kolonlar: run_id, upload_id, year, month, period_label, sicil_no, personel, firma, bolum, "
                "pozisyon, tarih, kod, durum_aciklamasi, pazar_durumu, nm_guncel, fm_guncel, row_data\n\n"
                "Kurallar:\n"
                "- Sadece SELECT veya WITH kullan.\n"
                "- Personel ozeti / toplam / ranking sorulari icin summary_view kullan.\n"
                "- Haftalik kontrol icin weekly_view, gun bazli detay icin daily_view kullan.\n"
                "- Saat alanlari numeric'tir (ornegin normal_calisma, fazla_mesai).\n"
                f"- LIMIT en fazla {row_limit} olsun.\n"
                'JSON disinda hicbir sey donme. Ornek: {"sql":"SELECT ...","title":"Kisa baslik"}'
            ),
        },
    ]


def _summarize_answer(question: str, sql: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "Bu soru icin eslesen kayit bulunamadi."
    preview = json.dumps(rows[:15], ensure_ascii=False)
    return _post_openrouter(
        [
            {
                "role": "system",
                "content": (
                    "Sen Turkce yanit veren bordro rapor asistansin. "
                    "Kisa, net ve dogrudan cevap ver. Sonucu uydurma. "
                    "Sayisal degerlerden bahsederken tablo sonucuna dayan. "
                    "Saat degerlerini saat cinsinden net soyle."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Soru: {question}\n"
                    f"Calistirilan SQL: {sql}\n"
                    f"Ilk sonuc kayitlari: {preview}\n"
                    "Buna gore Turkce cevap ver."
                ),
            },
        ],
        temperature=0.2,
    )


def _create_session(upload_id: str, title: str | None) -> dict[str, Any]:
    client = SupabaseClient.from_env()
    return client.insert_row(
        "payroll_chat_sessions",
        {
            "upload_id": upload_id,
            "title": title or "Yeni sohbet",
        },
    )


def list_sessions(upload_id: str) -> list[dict[str, Any]]:
    get_upload(upload_id, touch=False)
    client = SupabaseClient.from_env()
    return client.select_rows(
        "payroll_chat_sessions",
        filters={"upload_id": ("eq", upload_id)},
        order="updated_at.desc",
    )


def get_session(session_id: str) -> dict[str, Any]:
    client = SupabaseClient.from_env()
    session = client.select_single(
        "payroll_chat_sessions",
        filters={"id": ("eq", session_id)},
    )
    if not session:
        raise SupabaseError(f"Sohbet oturumu bulunamadı: {session_id}")
    messages = client.select_rows(
        "payroll_chat_messages",
        filters={"session_id": ("eq", session_id)},
        order="created_at.asc",
    )
    session["messages"] = messages
    return session


def ask_question(
    upload_id: str,
    question: str,
    *,
    year: int,
    month: int,
    session_id: str | None = None,
    row_limit: int = _DEFAULT_ROW_LIMIT,
) -> dict[str, Any]:
    get_upload(upload_id, touch=True)
    run = get_report_run(upload_id, year, month)
    row_limit = max(1, min(row_limit, _MAX_ROW_LIMIT))
    client = SupabaseClient.from_env()
    session = get_session(session_id) if session_id else None
    if session and session.get("upload_id") != upload_id:
        raise SupabaseError("Sohbet oturumu farkli bir upload kaydina ait.")
    if not session:
        session = _create_session(upload_id, question[:80].strip())

    sql_payload = _extract_json_object(_post_openrouter(_build_sql_prompt(question, run, row_limit)))
    sql = _validate_sql(str(sql_payload.get("sql") or ""), row_limit)
    rows = client.rpc(
        "execute_payroll_query",
        {
            "p_upload_id": upload_id,
            "p_sql": sql,
            "p_limit": row_limit,
            "p_year": year,
            "p_month": month,
        },
    )
    if not isinstance(rows, list):
        raise SupabaseError("SQL sonucu beklenen liste formatinda donmedi.")

    answer = _summarize_answer(question, sql, rows)
    now = datetime.utcnow().isoformat()
    client.insert_rows(
        "payroll_chat_messages",
        [
            {
                "session_id": session["id"],
                "role": "user",
                "content": question,
                "created_at": now,
            },
            {
                "session_id": session["id"],
                "role": "assistant",
                "content": answer,
                "sql_text": sql,
                "result_rows": rows,
                "created_at": now,
            },
        ],
    )
    updated_session = client.update_rows(
        "payroll_chat_sessions",
        {
            "title": str(sql_payload.get("title") or question[:80].strip() or "Yeni sohbet"),
            "updated_at": now,
        },
        filters={"id": ("eq", session["id"])},
    )
    session = updated_session[0] if updated_session else session
    session["messages"] = client.select_rows(
        "payroll_chat_messages",
        filters={"session_id": ("eq", session["id"])},
        order="created_at.asc",
    )
    return {
        "session": session,
        "answer": answer,
        "sql": sql,
        "rows": rows,
    }
