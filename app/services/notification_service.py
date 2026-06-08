from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.notification import Notification


class NotificationService:
    @staticmethod
    async def create(
        db: AsyncSession,
        recipient_email: str,
        type: str,
        title: str,
        body: str,
        entity_type: str,
        entity_id: UUID,
    ) -> Notification:
        notif = Notification(
            recipient_email=recipient_email,
            type=type,
            title=title,
            body=body,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        db.add(notif)
        await db.flush()
        return notif

    @staticmethod
    async def new_shortlisted(db: AsyncSession, hr_email: str, job_title: str, job_id: UUID):
        await NotificationService.create(
            db=db,
            recipient_email=hr_email,
            type="NEW_SHORTLISTED",
            title=f"New candidate shortlisted",
            body=f"A candidate has been shortlisted for {job_title}",
            entity_type="job_posting",
            entity_id=job_id,
        )

    @staticmethod
    async def job_published(db: AsyncSession, hr_email: str, job_title: str, job_id: UUID):
        await NotificationService.create(
            db=db,
            recipient_email=hr_email,
            type="JOB_PUBLISHED",
            title=f"Job posted successfully",
            body=f"{job_title} is now live on the careers page",
            entity_type="job_posting",
            entity_id=job_id,
        )
