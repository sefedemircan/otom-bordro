"""Temporary upload persistence endpoints."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from api.deps import api_error, read_upload_bytes
from api.schemas import UploadCreateResponse, UploadDatasetInfo
from api.services.supabase import SupabaseError
from api.services.uploads import UploadSource, create_upload, get_upload

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])


def _serialize_upload(upload: dict) -> UploadDatasetInfo:
    return UploadDatasetInfo.model_validate(upload)


@router.post("", response_model=UploadCreateResponse)
async def create_temp_upload(
    file: UploadFile = File(...),
    source_type: UploadSource = Form(...),
) -> UploadCreateResponse:
    data, filename = await read_upload_bytes(file)
    try:
        upload = create_upload(data, filename, source_type, content_type=file.content_type)
    except SupabaseError as exc:
        raise api_error(500, "UPLOAD_STORE_ERROR", str(exc)) from exc
    return UploadCreateResponse(upload=_serialize_upload(upload))


@router.get("/{upload_id}", response_model=UploadDatasetInfo)
def get_temp_upload(upload_id: str) -> UploadDatasetInfo:
    try:
        upload = get_upload(upload_id, touch=True)
    except SupabaseError as exc:
        raise api_error(404, "UPLOAD_NOT_FOUND", str(exc)) from exc
    return _serialize_upload(upload)

