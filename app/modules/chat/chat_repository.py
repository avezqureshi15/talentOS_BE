import uuid

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.chat.chat_model import Chat, Message

logger = get_logger(__name__)


class ChatRepository:
    def __init__(self, db: Session):
        self.db = db

    # ── Chat ──────────────────────────────────────────────────────

    def get_chat_by_id_and_user(self, chat_id: uuid.UUID, user_id: int) -> Chat | None:
        return self.db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()

    def get_chat_by_id(self, chat_id: uuid.UUID) -> Chat | None:
        return self.db.query(Chat).filter(Chat.id == chat_id).first()

    def create_chat(self, chat_id: uuid.UUID | None, user_id: int, title: str) -> Chat:
        chat = Chat(
            id=chat_id or uuid.uuid4(),
            user_id=user_id,
            title=title,
        )
        self.db.add(chat)
        self.db.commit()
        self.db.refresh(chat)
        logger.info("Created chat id=%s user=%d", chat.id, user_id)
        return chat

    def list_chats_by_user(
        self, user_id: int, limit: int = 5, offset: int = 0,
    ) -> tuple[list[Chat], bool]:
        base = self.db.query(Chat).filter(Chat.user_id == user_id)
        total = base.count()
        chats = (
            base
            .order_by(desc(Chat.updated_at))
            .offset(offset)
            .limit(limit + 1)
            .all()
        )
        has_more = len(chats) > limit
        if has_more:
            chats = chats[:limit]
        logger.debug("Listed %d chats for user=%d (total=%d)", len(chats), user_id, total)
        return chats, has_more

    def update_chat_title(self, chat_id: uuid.UUID, title: str) -> Chat | None:
        chat = self.get_chat_by_id(chat_id)
        if not chat:
            return None
        chat.title = title[:500]
        self.db.commit()
        self.db.refresh(chat)
        logger.info("Updated chat title id=%s", chat_id)
        return chat

    def delete_chat(self, chat_id: uuid.UUID) -> bool:
        chat = self.get_chat_by_id(chat_id)
        if not chat:
            return False
        self.db.query(Message).filter(Message.chat_id == chat_id).delete()
        self.db.delete(chat)
        self.db.commit()
        logger.info("Deleted chat id=%s", chat_id)
        return True

    # ── Message ────────────────────────────────────────────────────

    def save_message(self, chat_id: uuid.UUID, role: str, content: str) -> Message:
        msg = Message(chat_id=chat_id, role=role, content=content)
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        logger.debug("Saved message id=%d chat=%s role=%s", msg.id, chat_id, role)
        return msg

    def get_messages_by_chat(
        self, chat_id: uuid.UUID, limit: int = 20, before: int | None = None,
    ) -> tuple[list[Message], bool]:
        query = self.db.query(Message).filter(Message.chat_id == chat_id)

        if before is not None:
            query = query.filter(Message.id < before)

        query = query.order_by(Message.id.desc()).limit(limit + 1)
        results = query.all()

        has_more = len(results) > limit
        if has_more:
            results = results[:limit]

        results.reverse()
        return results, has_more
