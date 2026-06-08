from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import AllowedUser
from app.models.chat import ChatSession
from app.schemas.chat import ChatMessageIn
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
async def chat(
    body: ChatMessageIn,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    """
    Main HR chat endpoint. Streams Claude responses via SSE.
    """
    return StreamingResponse(
        ChatService.stream(
            db=db,
            hr_email=current_user.email,
            message=body.message,
            session_id=body.session_id,
            job_posting_id=body.job_posting_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history/{job_id}")
async def get_chat_history(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.hr_email == current_user.email,
            ChatSession.job_posting_id == job_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return {"messages": []}
    return {"session_id": str(session.id), "messages": session.messages}


@router.delete("/history/{job_id}")
async def clear_chat_history(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.hr_email == current_user.email,
            ChatSession.job_posting_id == job_id,
        )
    )
    session = result.scalar_one_or_none()
    if session:
        session.messages = []
    return {"message": "Chat history cleared"}
