from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core import indexing
from app.core.rag import answer_question, answer_question_stream
from app.models import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _check_ready(repo_id: str):
    status = indexing.get_status(repo_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Unknown repo_id — index a repository first.")
    if status.status != "ready":
        raise HTTPException(status_code=409, detail=f"Repository is not ready yet (status: {status.status}).")


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    _check_ready(req.repo_id)
    return answer_question(req.repo_id, req.message, req.history, req.model_override, req.template_id)


@router.post("/stream")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    """
    Server-Sent Events: emits one `event: step` per reasoning step as it
    happens, then a single `event: final` with the completed answer —
    this is what drives the *live* agent reasoning canvas on the
    frontend, rather than a trace rendered only after the full answer
    is already back.
    """
    _check_ready(req.repo_id)

    def gen():
        for event in answer_question_stream(req.repo_id, req.message, req.history, req.model_override, req.template_id):
            if event["type"] == "step":
                payload = event["step"].model_dump()
                yield f"event: step\ndata: {json.dumps(payload)}\n\n"
            else:
                payload = event["response"].model_dump()
                yield f"event: final\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
