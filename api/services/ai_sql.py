"""OpenRouter-backed SQL generation and chat session persistence."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterator
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

_DOMAIN_CONTEXT = """
Sen OtomHR puantaj / bordro asistanisin. Kullanici Meyer PDKS dosyasindan uretilmis AYLIK RAPOR CIKTISI uzerinden soru sorar.
Veri kaynagi ham Meyer satirlari degil; sistemin hesapladigi ozet/haftalik/gunluk rapor tablolaridir.

## Surec
1. Kullanici Meyer Excel/CSV yukler.
2. Sistem secilen donem icin aylik puantaj raporu uretir.
3. Rapor: Personel Ozeti (summary), Haftalik Kontrol (weekly), Gunluk Detay (daily), Aylik Matris (monthly).
4. Sen yalnizca bu rapor ciktilarina bakarak cevap verirsin.

## Temel kavramlar
- NM = Normal Mesai (normal_calisma / nm_guncel)
- FM = Fazla Mesai (fazla_mesai / fm_guncel)
- FM->NM Aktarim = Haftalik 45 saat kurali nedeniyle hafta sonu FM'den NM'ye aktarilan saat (fm_nm_aktarim)
- MS = Mesai suresi / beklenen gunluk sure (genelde 9 saat)
- Sicil = personel kimligi (sicil_no)

## Is kurallari (rapor zaten bunlari uygulamistir)
1. 45 saat kurali: Hafta ici NM 45'in altindaysa, ayni haftanin hafta sonu FM'sinden eksik kisim NM'ye aktarilir.
2. Bu yuzden "ham FM" ile "rapordaki Fazla Mesai" farkli olabilir. Toplam FM sorularinda summary.fazla_mesai kullan.
3. Izin ayrimi: Yillik / Ucretli / SGK Rapor / Ucretsiz izin ayri tutulur.
4. Devamsizlik: Hafta ici beklenen sure karsilanmazsa ve izin yoksa M (mazeretsiz).
5. Pazar kesintisi: Yalnizca mazeretsiz tam gun (~9 saat) devamsizlikta o haftanin pazari kesilir (Z / Kesildi).
6. Rapor, yillik/ucretli mazeret izni, isveren izni ve resmi tatiller calisilmis sayilir; hafta tatili hakki dusmez (T / Hak Edildi).
7. Cumartesi mesai yoksa A3 (serbest zaman); mesai varsa saat yazilir.
8. Gunluk matriste calisma gunlerinde kod yerine NM+FM saati (sayisal) gorunebilir.

## Matris / gun kodlari (daily.kod)
- Sayisal deger (ornegin 9.0, 9.7): Fiili calisma saati (NM+FM)
- N: Normal calisma (9,00)
- U: Uzaktan calisma
- R: Raporlu
- W: Tatilde raporlu
- Y: Yillik izin
- U/Ü: Ucretli izin (kod: Ü)
- Z: Ucretsiz izin VEYA mazeretsiz nedeniyle kesilen hafta tatili
- Z*: Onceki ay baglamindan gelen pazar kesintisi isareti olabilir
- M: Mazeretsiz / devamsizlik
- T: Hafta tatili / resmi tatil (hak edilmis)
- C: Ucretsiz hafta tatili
- B: Resmi tatil hafta ici
- D: Dini bayram
- K: Yarim gun resmi tatil
- V: Yarim gun
- X: Sayilmayan gun
- A1: Serbest zaman maktu tam gun
- A2: Serbest zaman maktu yarim gun
- A3: Serbest zaman saatlik / cumartesi mesaisiz
- A4: Serbest zaman saatlik yarim gun

## Haftalik pazar durumu
- Hak Edildi: Pazar kesilmedi
- Kesildi / Yanar: Pazar kesildi (pazar_kesintisi / pazar_durumu)

## Hangi view ne icin
- payroll_report_summary_view: personel ozeti, toplam NM/FM, izin gunleri, pazar kesintisi, ranking
- payroll_report_weekly_view: hafta bazli NM/FM, FM->NM aktarim, pazar durumu
- payroll_report_daily_view: gun bazli kod, tarih, nm_guncel, fm_guncel, durum aciklamasi

## Cevap ilkeleri
- Turkce, kisa ve net cevap ver.
- Sonucu uydurma; sadece sorgu sonucuna dayan.
- Saatleri mumkunse HH:MM ile de belirt (0.7 saat = 0:42).
- Kullaniciya SQL, tablo adi veya teknik jargonu gosterme.
- "Toplam fazla mesai" = summary.fazla_mesai toplami (aktarim sonrasi kalan FM).
- Ham cumartesi FM'sini toplam FM sanma; once FM->NM aktarimini dikkate al.
""".strip()


class OpenRouterError(RuntimeError):
    """Raised when OpenRouter cannot complete the request."""


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise OpenRouterError(f"Eksik ortam değişkeni: {name}")
    return value


def _openrouter_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://otomhr.vercel.app",
        "X-Title": "Otom Bordro AI",
    }


def _openrouter_model() -> str:
    return os.getenv("OPENROUTER_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL


def _post_openrouter(messages: list[dict[str, str]], *, temperature: float = 0.1) -> str:
    api_key = _require_env("OPENROUTER_API_KEY")
    payload = {
        "model": _openrouter_model(),
        "temperature": temperature,
        "messages": messages,
    }
    req = request.Request(
        _OPENROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers=_openrouter_headers(api_key),
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


def _iter_openrouter_stream(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
) -> Iterator[str]:
    api_key = _require_env("OPENROUTER_API_KEY")
    payload = {
        "model": _openrouter_model(),
        "temperature": temperature,
        "messages": messages,
        "stream": True,
    }
    req = request.Request(
        _OPENROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers=_openrouter_headers(api_key),
    )
    try:
        resp = request.urlopen(req, timeout=120)
    except error.HTTPError as exc:  # pragma: no cover - network surface
        raw = exc.read().decode("utf-8", errors="replace")
        raise OpenRouterError(f"OpenRouter HTTP {exc.code}: {raw}") from exc
    except error.URLError as exc:  # pragma: no cover - network surface
        raise OpenRouterError(f"OpenRouter erişim hatası: {exc.reason}") from exc

    try:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            try:
                body = json.loads(data)
            except json.JSONDecodeError:
                continue
            choices = body.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            content = delta.get("content")
            if content:
                yield str(content)
    finally:
        resp.close()


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
                f"{_DOMAIN_CONTEXT}\n\n"
                "Gorevin: guvenli PostgreSQL SELECT uretmek.\n"
                "Yalnizca su view'lari kullan: payroll_report_summary_view, "
                "payroll_report_weekly_view, payroll_report_daily_view.\n"
                "Noktali virgul kullanma. "
                f"LIMIT <= {row_limit} olsun. Sadece JSON don: {{\"sql\":\"...\",\"title\":\"...\"}}"
            ),
        },
        {
            "role": "user",
            "content": (
                "Kullanici sorusu:\n"
                f"{question}\n\n"
                f"Aktif rapor donemi: {run.get('label')} (year={run.get('year')}, month={run.get('month')})\n"
                f"Personel sayisi: {run.get('employee_count')}, gunluk kayit: {run.get('record_count')}\n"
                f"Donem toplam NM: {run.get('total_nm')}, Donem toplam FM (aktarim sonrasi): {run.get('total_fm')}\n\n"
                "View kolonlari:\n"
                "1) payroll_report_summary_view: run_id, upload_id, year, month, period_label, sicil_no, personel, "
                "firma, bolum, pozisyon, calisma_gunu, normal_calisma, fazla_mesai, fm_nm_aktarim, "
                "yillik_izin_gun, ucretli_izin_gun, rapor_gun, ucretsiz_izin_gun, devamsizlik_gun, "
                "hafta_tatili_gun, pazar_kesintisi, row_data\n"
                "2) payroll_report_weekly_view: run_id, upload_id, year, month, period_label, sicil_no, personel, "
                "hafta, normal_calisma, fazla_mesai, fm_nm_aktarim, pazar_durumu, row_data\n"
                "3) payroll_report_daily_view: run_id, upload_id, year, month, period_label, sicil_no, personel, "
                "firma, bolum, pozisyon, tarih, kod, durum_aciklamasi, pazar_durumu, nm_guncel, fm_guncel, row_data\n\n"
                "Kurallar:\n"
                "- Sadece SELECT/WITH.\n"
                "- Toplam / ranking / personel ozeti icin summary_view.\n"
                "- Haftalik kontrol icin weekly_view.\n"
                "- Gun/kod/tarih detayi icin daily_view.\n"
                "- 'Toplam fazla mesai' icin SUM(fazla_mesai) FROM payroll_report_summary_view.\n"
                f"- LIMIT en fazla {row_limit}.\n"
                'JSON disinda hicbir sey yazma.'
            ),
        },
    ]


def _build_answer_messages(question: str, rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    preview = json.dumps(rows[:15], ensure_ascii=False)
    return [
        {
            "role": "system",
            "content": (
                f"{_DOMAIN_CONTEXT}\n\n"
                "Gorevin: sorgu sonucunu kullaniciya Turkce aciklamak.\n"
                "SQL gosterme. Teknik tablo/view adi yazma.\n"
                "Gerekirse kod harflerinin anlamini kisaca acikla."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Soru: {question}\n"
                f"Sorgu sonucu kayitlari: {preview}\n"
                "Sadece kullaniciya donuk, anlasilir Turkce cevap ver."
            ),
        },
    ]


def _summarize_answer(question: str, sql: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "Bu soru için eşleşen kayıt bulunamadı."
    return _post_openrouter(_build_answer_messages(question, rows), temperature=0.2)


@dataclass
class _PreparedQuestion:
    session: dict[str, Any]
    question: str
    sql: str
    rows: list[dict[str, Any]]
    title: str
    answer_messages: list[dict[str, str]] | None


def _prepare_question(
    upload_id: str,
    question: str,
    *,
    year: int,
    month: int,
    session_id: str | None = None,
    row_limit: int = _DEFAULT_ROW_LIMIT,
) -> _PreparedQuestion:
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

    title = str(sql_payload.get("title") or question[:80].strip() or "Yeni sohbet")
    answer_messages = _build_answer_messages(question, rows) if rows else None
    return _PreparedQuestion(
        session=session,
        question=question,
        sql=sql,
        rows=rows,
        title=title,
        answer_messages=answer_messages,
    )


def _persist_question(prepared: _PreparedQuestion, answer: str) -> dict[str, Any]:
    client = SupabaseClient.from_env()
    now = datetime.utcnow().isoformat()
    client.insert_rows(
        "payroll_chat_messages",
        [
            {
                "session_id": prepared.session["id"],
                "role": "user",
                "content": prepared.question,
                "sql_text": None,
                "result_rows": None,
                "created_at": now,
            },
            {
                "session_id": prepared.session["id"],
                "role": "assistant",
                "content": answer,
                "sql_text": prepared.sql,
                "result_rows": prepared.rows,
                "created_at": now,
            },
        ],
    )
    updated_session = client.update_rows(
        "payroll_chat_sessions",
        {
            "title": prepared.title,
            "updated_at": now,
        },
        filters={"id": ("eq", prepared.session["id"])},
    )
    session = updated_session[0] if updated_session else prepared.session
    session["messages"] = client.select_rows(
        "payroll_chat_messages",
        filters={"session_id": ("eq", session["id"])},
        order="created_at.asc",
    )
    return {
        "session": session,
        "answer": answer,
        "sql": prepared.sql,
        "rows": prepared.rows,
    }


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
    prepared = _prepare_question(
        upload_id,
        question,
        year=year,
        month=month,
        session_id=session_id,
        row_limit=row_limit,
    )
    answer = (
        "Bu soru için eşleşen kayıt bulunamadı."
        if not prepared.rows
        else _post_openrouter(prepared.answer_messages or [], temperature=0.2)
    )
    return _persist_question(prepared, answer)


def stream_question(
    upload_id: str,
    question: str,
    *,
    year: int,
    month: int,
    session_id: str | None = None,
    row_limit: int = _DEFAULT_ROW_LIMIT,
) -> Iterator[dict[str, Any]]:
    yield {"type": "status", "message": "Sorgu hazırlanıyor…"}
    prepared = _prepare_question(
        upload_id,
        question,
        year=year,
        month=month,
        session_id=session_id,
        row_limit=row_limit,
    )
    yield {
        "type": "session",
        "session_id": prepared.session["id"],
        "title": prepared.title,
    }
    if not prepared.rows:
        answer = "Bu soru için eşleşen kayıt bulunamadı."
        yield {"type": "token", "content": answer}
    else:
        answer_parts: list[str] = []
        for token in _iter_openrouter_stream(prepared.answer_messages or [], temperature=0.2):
            answer_parts.append(token)
            yield {"type": "token", "content": token}
        answer = "".join(answer_parts).strip() or "Bu soru için eşleşen kayıt bulunamadı."

    result = _persist_question(prepared, answer)
    yield {
        "type": "done",
        "session": result["session"],
        "answer": result["answer"],
        "sql": result["sql"],
        "rows": result["rows"],
    }
