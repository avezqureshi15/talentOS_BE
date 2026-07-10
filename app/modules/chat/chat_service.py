import uuid

from sqlalchemy.orm import Session

from app.common.clients import AIClient
from app.core.logger import get_logger
from app.modules.chat.chat_repository import ChatRepository
from app.modules.chat.chat_model import Chat, Message

logger = get_logger(__name__)


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


def get_or_create_chat(db: Session, chat_id: str | None, user_id: int, message: str) -> Chat:
    repo = ChatRepository(db)
    if chat_id:
        chat = repo.get_chat_by_id_and_user(uuid.UUID(chat_id), user_id)
        if chat:
            return chat
    title = message[:500] if message else "New chat"
    chat_id_uuid = uuid.UUID(chat_id) if chat_id else None
    return repo.create_chat(chat_id_uuid, user_id, title)


def save_message(db: Session, chat_id: uuid.UUID, role: str, content: str) -> Message:
    return ChatRepository(db).save_message(chat_id, role, content)


async def stream_chat_to_ai(message: str, thread_id: str):
    client = AIClient()
    async for chunk in client.stream_chat(message, thread_id):
        yield chunk


def list_chats_by_user(
    db: Session,
    user_id: int,
    limit: int = 5,
    offset: int = 0,
) -> tuple[list[Chat], bool]:
    return ChatRepository(db).list_chats_by_user(user_id, limit, offset)


def get_chat_owned_by_user(db: Session, chat_id: uuid.UUID, user_id: int) -> Chat | None:
    return ChatRepository(db).get_chat_by_id_and_user(chat_id, user_id)


def update_chat_title(db: Session, chat_id: uuid.UUID, title: str) -> Chat | None:
    return ChatRepository(db).update_chat_title(chat_id, title)


def delete_chat(db: Session, chat_id: uuid.UUID) -> bool:
    return ChatRepository(db).delete_chat(chat_id)


def get_messages_by_chat(
    db: Session,
    chat_id: uuid.UUID,
    limit: int = 20,
    before: int | None = None,
) -> tuple[list[Message], bool]:
    return ChatRepository(db).get_messages_by_chat(chat_id, limit, before)
