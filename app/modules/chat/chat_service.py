import uuid
from collections.abc import AsyncGenerator

import httpx
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.chat.chat_model import Chat, Message

logger = get_logger(__name__)

AI_STREAM_URL = "http://localhost:8003/api/v1/chat/stream"


def _parse_ndjson_line(line: str) -> str:
    trimmed = line.strip()
    if not trimmed:
        return ""
    try:
        import json
        obj = json.loads(trimmed)
        if isinstance(obj, dict):
            final = obj.get("final", [])
            parts = [b.get("content", "") for b in final if isinstance(b, dict)]
            return "".join(parts)
    except (json.JSONDecodeError, TypeError):
        pass
    return ""


def get_or_create_chat(db: Session, chat_id: str | None, visitor_id: str | None, message: str) -> Chat:
    if chat_id:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if chat:
            return chat

    title = message[:500] if message else "New chat"
    chat = Chat(
        id=uuid.uuid4() if not chat_id else uuid.UUID(chat_id),
        visitor_id=visitor_id or "unknown",
        title=title,
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)
    logger.info("Created chat id=%s visitor=%s title=%s", chat.id, chat.visitor_id, chat.title[:50])
    return chat


def save_message(db: Session, chat_id: uuid.UUID, role: str, content: str) -> Message:
    msg = Message(chat_id=chat_id, role=role, content=content)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


async def stream_chat_to_ai(message: str, thread_id: str) -> AsyncGenerator[bytes, None]:
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
        async with client.stream(
            "POST",
            AI_STREAM_URL,
            json={"message": message, "thread_id": thread_id},
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                yield chunk


def list_chats_by_visitor(db: Session, visitor_id: str) -> list[Chat]:
    return (
        db.query(Chat)
        .filter(Chat.visitor_id == visitor_id)
        .order_by(desc(Chat.updated_at))
        .all()
    )


def get_messages_by_chat(
    db: Session,
    chat_id: uuid.UUID,
    limit: int = 20,
    before: int | None = None,
) -> tuple[list[Message], bool]:
    query = db.query(Message).filter(Message.chat_id == chat_id)

    if before is not None:
        query = query.filter(Message.id < before)

    query = query.order_by(Message.id.desc()).limit(limit + 1)
    results = query.all()

    has_more = len(results) > limit
    if has_more:
        results = results[:limit]

    results.reverse()
    return results, has_more
