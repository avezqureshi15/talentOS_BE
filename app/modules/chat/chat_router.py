from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.auth.auth_dependencies import get_current_user, require_human_user
from app.modules.auth.auth_schema import UserInfo
from app.modules.chat.chat_schema import ChatResponse, ChatStreamRequest, MessageResponse
from app.modules.chat.chat_service import (
    _parse_ndjson_line,
    delete_chat,
    get_chat_owned_by_user,
    get_messages_by_chat,
    get_or_create_chat,
    list_chats_by_user,
    save_message,
    stream_chat_to_ai,
    update_chat_title,
)

class UpdateTitleRequest(BaseModel):
    title: str


router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/chat", tags=["chat"])


@router.post("/stream")
async def chat_stream(
    body: ChatStreamRequest,
    authorization: str = Header(alias="Authorization"),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_human_user),
):
    chat = get_or_create_chat(db, body.chat_id, current_user.id, body.message)
    save_message(db, chat.id, "user", body.message)

    async def generate():
        accumulated = ""

        async for chunk in stream_chat_to_ai(body.message, str(chat.id), authorization):
            yield chunk
            decoded = chunk.decode("utf-8", errors="replace")
            accumulated += _parse_ndjson_line(decoded)

        if accumulated:
            save_message(db, chat.id, "assistant", accumulated)

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"X-Chat-Id": str(chat.id)},
    )


@router.get("/chats")
def get_chats(
    limit: int = Query(5, ge=1, le=50, description="Items per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_human_user),
):
    chats, has_more = list_chats_by_user(db, current_user.id, limit, offset)
    items = [ChatResponse.model_validate(c).model_dump() for c in chats]
    return {"data": items, "count": len(items), "has_more": has_more}


@router.get("/messages")
def get_messages(
    chat_id: UUID = Query(..., description="Chat session ID"),
    limit: int = Query(20, ge=1, le=100, description="Max messages per page"),
    before: int | None = Query(None, ge=0, description="Cursor: last message ID from previous page"),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_human_user),
):
    chat = get_chat_owned_by_user(db, chat_id, current_user.id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    msgs, has_more = get_messages_by_chat(db, chat_id, limit, before)
    if not msgs and before is None:
        raise HTTPException(status_code=404, detail="Chat not found or has no messages")
    items = [MessageResponse.model_validate(m).model_dump() for m in msgs]
    return {"data": items, "has_more": has_more}


@router.patch("/chats/{chat_id}")
def patch_chat_endpoint(
    chat_id: UUID,
    body: UpdateTitleRequest,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_human_user),
):
    chat = get_chat_owned_by_user(db, chat_id, current_user.id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    chat = update_chat_title(db, chat_id, body.title)
    return ChatResponse.model_validate(chat).model_dump()


@router.delete("/chats/{chat_id}")
def delete_chat_endpoint(
    chat_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_human_user),
):
    chat = get_chat_owned_by_user(db, chat_id, current_user.id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    deleted = delete_chat(db, chat_id)
    return {"deleted": True}
