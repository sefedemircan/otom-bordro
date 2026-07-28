"""Pydantic request / response models for the public API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"


class CodeLegendItem(BaseModel):
    kod: str
    aciklama: str


class MetaResponse(BaseModel):
    weekly_max_hours: float
    daily_work_hours: float
    sunday_cut_absence_hours: float
    unpaid_leave_column: str
    gun_durumlari: list[str]
    day_names: list[str]
    code_legend: list[CodeLegendItem]
    status_labels: dict[str, str]
    calc_required_columns: list[str]
    report_required_columns: list[str]
    meyer_hour_columns: list[str]


class EmployeeItem(BaseModel):
    sicilno: str
    Ad: str
    Soyad: str
    Kayıt: int = Field(alias="Kayıt")
    Firma: str | None = None
    Bölüm: str | None = Field(default=None, alias="Bölüm")
    Pozisyon: str | None = None

    model_config = {"populate_by_name": True, "extra": "allow"}


class InspectResponse(BaseModel):
    is_bulk: bool
    record_count: int
    employees: list[dict[str, Any]]


class CalcSummary(BaseModel):
    toplam_nm: float
    toplam_fm: float
    toplam_nm_fmt: str
    toplam_fm_fmt: str
    ucretli_izin_gun: int
    ucretli_izin_saat: float
    ucretli_izin_saat_fmt: str
    ucretsiz_izin_gun: int
    ucretsiz_izin_saat: float
    ucretsiz_izin_saat_fmt: str
    devamsizlik_gun: int
    devamsizlik_saat: float
    devamsizlik_saat_fmt: str
    calisma_gun: int
    pazar_yanan_hafta: int
    donem: str
    toplam_gun: int
    iso_hafta_sayisi: int
    kisami_hafta_sayisi: int
    tam_hafta_sayisi: int
    period_year: int | None = None
    period_month: int | None = None
    baglam_gun: int = 0
    employee_label: str | None = None
    sicilno: str | None = None


class ComputeResponse(BaseModel):
    summary: dict[str, Any]
    leave_breakdown: list[dict[str, Any]]
    daily: list[dict[str, Any]]
    weekly: list[dict[str, Any]]
    processed: list[dict[str, Any]]


class ComputeJsonRequest(BaseModel):
    rows: list[dict[str, Any]] = Field(..., min_length=1)
    employee_label: str | None = None
    year: int | None = None
    month: int | None = None


class PeriodItem(BaseModel):
    year: int
    month: int
    label: str


class PeriodsResponse(BaseModel):
    periods: list[PeriodItem]


class ReportMeta(BaseModel):
    year: int
    month: int
    label: str
    period_start: str
    period_end: str
    employee_count: int
    record_count: int
    total_nm: float
    total_fm: float
    total_nm_fmt: str
    total_fm_fmt: str


class ReportBuildResponse(BaseModel):
    meta: ReportMeta
    quality: list[dict[str, Any]]
    monthly: list[dict[str, Any]]
    summary: list[dict[str, Any]]
    weekly: list[dict[str, Any]]
    daily: list[dict[str, Any]]


class ErrorDetail(BaseModel):
    code: str
    message: str


class UploadDatasetInfo(BaseModel):
    id: str
    source_type: Literal["report", "calc"]
    filename: str
    file_size: int
    row_count: int
    metadata: dict[str, Any]
    created_at: str
    expires_at: str


class UploadCreateResponse(BaseModel):
    upload: UploadDatasetInfo


class GeneratedSqlPreview(BaseModel):
    sql: str
    row_limit: int


class ChatSessionSummary(BaseModel):
    id: str
    upload_id: str
    title: str | None = None
    updated_at: str


class ChatMessageItem(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    sql_text: str | None = None
    result_rows: list[dict[str, Any]] | None = None
    created_at: str


class ChatSessionDetail(BaseModel):
    id: str
    upload_id: str
    title: str | None = None
    created_at: str
    updated_at: str
    messages: list[ChatMessageItem]


class ChatMessageRequest(BaseModel):
    upload_id: str
    question: str = Field(..., min_length=1)
    session_id: str | None = None
    row_limit: int = Field(default=100, ge=1, le=200)


class ChatMessageResponse(BaseModel):
    session: ChatSessionDetail
    answer: str
    generated_sql: GeneratedSqlPreview
    rows: list[dict[str, Any]]
