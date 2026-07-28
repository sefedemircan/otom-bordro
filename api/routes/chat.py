"""Natural-language SQL chat endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from api.deps import api_error
from api.schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionDetail,
    ChatSessionSummary,
    GeneratedSqlPreview,
)
from api.services.ai_sql import ask_question, get_session, list_sessions
from api.services.supabase import SupabaseError

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.get("/sessions", response_model=list[ChatSessionSummary])
def get_chat_sessions(upload_id: str = Query(...)) -> list[ChatSessionSummary]:
    try:
        sessions = list_sessions(upload_id)
    except SupabaseError as exc:
        raise api_error(404, "UPLOAD_NOT_FOUND", str(exc)) from exc
    return [ChatSessionSummary.model_validate(session) for session in sessions]


@router.get("/sessions/{session_id}", response_model=ChatSessionDetail)
def get_chat_session(session_id: str) -> ChatSessionDetail:
    try:
        session = get_session(session_id)
    except SupabaseError as exc:
        raise api_error(404, "CHAT_SESSION_NOT_FOUND", str(exc)) from exc
    return ChatSessionDetail.model_validate(session)


@router.post("/query", response_model=ChatMessageResponse)
def query_chat(request: ChatMessageRequest) -> ChatMessageResponse:
    try:
        result = ask_question(
            request.upload_id,
            request.question,
            year=request.year,
            month=request.month,
            session_id=request.session_id,
            row_limit=request.row_limit,
        )
    except (SupabaseError, RuntimeError) as exc:
        raise api_error(400, "CHAT_QUERY_FAILED", str(exc)) from exc
    return ChatMessageResponse(
        session=ChatSessionDetail.model_validate(result["session"]),
        answer=str(result["answer"]),
        generated_sql=GeneratedSqlPreview(sql=str(result["sql"]), row_limit=request.row_limit),
        rows=result["rows"],
    )

