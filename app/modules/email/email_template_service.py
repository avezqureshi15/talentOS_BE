"""Service for listing, editing, rendering, previewing and testing email templates."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.common.services.email_service import EmailService
from app.core.config import settings
from app.core.logger import get_logger
from app.modules.email.email_template_model import EmailTemplate
from app.modules.email.email_template_registry import (
    all_template_specs,
    build_email_html,
    format_template,
    get_template_spec,
)
from app.modules.email.email_template_schema import (
    EmailTemplateDetail,
    EmailTemplateSummary,
)

logger = get_logger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def _build_email_service() -> EmailService:
    return EmailService(
        smtp_host=settings.SMTP_HOST,
        smtp_port=settings.SMTP_PORT,
        username=settings.SMTP_USERNAME,
        password=settings.SMTP_PASSWORD,
        use_tls=settings.SMTP_USE_TLS,
    )


def html_to_text(html: str) -> str:
    """Best-effort plain-text extraction from an HTML email body."""
    text = html.replace("</p>", "\n\n").replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = re.sub(r"<a [^>]*href=\"([^\"]+)\"[^>]*>.*?</a>", r"\1", text, flags=re.DOTALL | re.IGNORECASE)
    text = _TAG_RE.sub("", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return _WS_RE.sub(" ", text).strip()


def ensure_seeded(db: Session) -> None:
    """Insert the default templates and refresh stale or legacy-format rows."""
    rows = db.query(EmailTemplate).all()
    if not rows:
        for spec in all_template_specs():
            db.add(
                EmailTemplate(
                    id=spec.key,
                    name=spec.name,
                    description=spec.description,
                    subject_template=spec.default_subject,
                    body_html_template=spec.default_html,
                    is_editable=spec.is_editable,
                    template_version=spec.default_version,
                )
            )
        db.commit()
        logger.info("Seeded %d email templates", len(all_template_specs()))
        return

    changed = 0
    by_key = {r.id: r for r in rows}
    for spec in all_template_specs():
        row = by_key.get(spec.key)
        if row is None:
            db.add(
                EmailTemplate(
                    id=spec.key,
                    name=spec.name,
                    description=spec.description,
                    subject_template=spec.default_subject,
                    body_html_template=spec.default_html,
                    is_editable=spec.is_editable,
                    template_version=spec.default_version,
                )
            )
            changed += 1
        elif (row.template_version or 0) < spec.default_version or _is_full_document(row.body_html_template):
            row.subject_template = spec.default_subject
            row.body_html_template = spec.default_html
            row.template_version = spec.default_version
            changed += 1
    if changed:
        db.commit()
        logger.info("Refreshed %d email templates to newer defaults", changed)


def _is_full_document(html: str) -> bool:
    return html.lstrip().startswith("<!DOCTYPE html>") or "<!doctype html" in html.lower()


def _to_summary(row: EmailTemplate) -> EmailTemplateSummary:
    return EmailTemplateSummary(
        key=row.id,
        name=row.name,
        description=row.description,
        is_editable=row.is_editable,
        updated_at=row.updated_at,
        updated_by=row.updated_by,
    )


def _to_detail(row: EmailTemplate) -> EmailTemplateDetail:
    spec = get_template_spec(row.id)
    return EmailTemplateDetail(
        key=row.id,
        name=row.name,
        description=row.description,
        is_editable=row.is_editable,
        updated_at=row.updated_at,
        updated_by=row.updated_by,
        subject_template=row.subject_template,
        body_html_template=row.body_html_template,
        placeholders=list(spec.placeholders) if spec else [],
        sample_context=dict(spec.sample_context) if spec else {},
    )


def list_templates(db: Session) -> list[EmailTemplateSummary]:
    ensure_seeded(db)
    rows = db.query(EmailTemplate).order_by(EmailTemplate.name.asc()).all()
    return [_to_summary(r) for r in rows]


def get_template(db: Session, key: str) -> EmailTemplateDetail:
    ensure_seeded(db)
    row = db.query(EmailTemplate).filter(EmailTemplate.id == key).first()
    if row is None:
        raise KeyError(f"Email template '{key}' not found")
    return _to_detail(row)


def update_template(db: Session, key: str, subject_template: str, body_html_template: str, updated_by: str) -> EmailTemplateDetail:
    ensure_seeded(db)
    row = db.query(EmailTemplate).filter(EmailTemplate.id == key).first()
    if row is None:
        raise KeyError(f"Email template '{key}' not found")
    if not row.is_editable:
        raise ValueError(f"Email template '{key}' is not editable")
    spec = get_template_spec(key)
    row.subject_template = subject_template
    row.body_html_template = body_html_template
    row.updated_by = updated_by
    row.template_version = max(row.template_version or 0, spec.default_version if spec else 1) + 1
    db.commit()
    db.refresh(row)
    return _to_detail(row)


def render(db: Session, key: str, context: dict[str, str]) -> tuple[str, str, str]:
    """Render ``(subject, plain, html)`` for a template key.

    The stored template holds only the message body; the branded shell is
    applied here so the email always renders with the full TalentOS design.
    """
    spec = get_template_spec(key)
    if spec is None:
        raise KeyError(f"Email template '{key}' not found")

    row = db.query(EmailTemplate).filter(EmailTemplate.id == key).first()
    subject_src = row.subject_template if row else spec.default_subject
    content_src = row.body_html_template if row else spec.default_html

    subject = format_template(subject_src, context)
    content = format_template(content_src, context)
    html = build_email_html(spec, context, subject, content)
    plain = html_to_text(html)
    return subject, plain, html


def render_preview(
    db: Session,
    key: str,
    subject_template: str | None = None,
    body_html_template: str | None = None,
) -> tuple[str, str]:
    """Render a preview using the template's sample context.

    When ``subject_template`` / ``body_html_template`` are provided they are
    treated as unsaved edits (used by the Email Manager live preview).
    """
    ensure_seeded(db)
    spec = get_template_spec(key)
    if spec is None:
        raise KeyError(f"Email template '{key}' not found")

    row = db.query(EmailTemplate).filter(EmailTemplate.id == key).first()
    subject_src = subject_template if subject_template is not None else (row.subject_template if row else spec.default_subject)
    content_src = body_html_template if body_html_template is not None else (row.body_html_template if row else spec.default_html)

    subject = format_template(subject_src, spec.sample_context)
    content = format_template(content_src, spec.sample_context)
    html = build_email_html(spec, spec.sample_context, subject, content)
    return subject, html


def send_test(db: Session, key: str, to_email: str) -> None:
    """Send a test copy of a template to ``to_email`` using sample context."""
    spec = get_template_spec(key)
    if spec is None:
        raise KeyError(f"Email template '{key}' not found")
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        raise RuntimeError("SMTP not configured")

    subject, html = render_preview(db, key)
    plain = html_to_text(html)
    service = _build_email_service()
    service.send(to_email=to_email, subject=subject, body=plain, html=html)
    logger.info("Email template test sent: key=%s | to=%s", key, to_email)


def placeholder_keys(html: str) -> list[str]:
    """Return any ``{{...}}`` placeholder keys found in a template body."""
    return _PLACEHOLDER_RE.findall(html)
