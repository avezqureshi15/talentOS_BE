"""Initial schema + band designation seed data

Revision ID: 001
Revises:
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

BAND_DATA = [
    ("Developer", "B5", "Principal Engineer"),
    ("Quality Assurance", "B5", "QA Lead"),
    ("UI/UX", "B5", "UI/UX Lead"),
    ("Delivery Manager", "B5", "Delivery Manager"),
    ("AI/ML", "B5", "AM Lead"),
    ("Human Resources", "B5", "Senior HR Manager"),
    ("Finance", "B5", "Senior Finance Manager"),
    ("QA", "B6", "Senior QA"),
    ("UI/UX", "B6", "Senior Designer"),
    ("Project Manager", "B6", "Senior PM"),
    ("Business Analyst", "B6", "Business Analyst"),
    ("Account Manager", "B6", "Senior AM"),
    ("Human Resources", "B6", "HR Manager"),
    ("Finance", "B6", "Finance Manager"),
    ("Developer", "B6H", "Sr. Team Lead – Developer Captain"),
    ("Business Analyst", "B6H", "Product Owner – Management Captain"),
    ("Project Manager", "B6H", "Project Manager"),
    ("Developer", "B6L", "Team Lead"),
    ("AI/ML", "B6L", "AI Team Lead"),
    ("DevOps", "B6L", "DevOps Team Lead"),
    ("Developer", "B7H", "Senior Software Engineer"),
    ("AI/ML", "B7H", "Senior AI/ML Engineer"),
    ("DevOps", "B7H", "Senior DevOps Engineer"),
    ("Quality Assurance", "B7H", "Associate QA"),
    ("UI/UX", "B7H", "Associate Designer"),
    ("Project Manager", "B7H", "Project Manager"),
    ("Business Analyst", "B7H", "Associate BA"),
    ("Account Manager", "B7H", "Account Manager"),
    ("Human Resources", "B7H", "HR Generalist II"),
    ("Finance", "B7H", "Finance Associate"),
    ("Developer", "B7L", "Software Engineer"),
    ("AI/ML", "B7L", "AI/ML Engineer"),
    ("DevOps", "B7L", "DevOps Engineer"),
    ("Quality Assurance", "B7L", "Assistant QA"),
    ("UI/UX", "B7L", "Assistant Designer"),
    ("Project Manager", "B7L", "Assistant Project Manager"),
    ("Account Manager", "B7L", "AM Assistant"),
    ("Human Resources", "B7L", "HR Generalist I"),
    ("Developer", "B8 – Intern", "Software Development Intern"),
    ("AI/ML", "B8 – Intern", "AI/ML Engineer Intern"),
    ("DevOps", "B8 – Intern", "DevOps Engineer Intern"),
    ("Quality Assurance", "B8 – Intern", "QA Intern"),
    ("UI/UX", "B8 – Intern", "Designer Intern"),
    ("Project Manager", "B8 – Intern", "Project Management Intern"),
    ("Business Analyst", "B8 – Intern", "BA Intern"),
    ("Account Manager", "B8 – Intern", "AM Intern"),
    ("Human Resources", "B8 – Intern", "HR Intern"),
    ("Finance", "B8 – Intern", "Finance Intern"),
    ("Executive", "B4", "Senior Technical Architect"),
    ("Executive", "B4", "Senior Delivery Manager"),
    ("Executive", "B3", "Directors"),
    ("Executive", "B2", "Vice Presidents"),
    ("Executive", "B1", "CEO"),
    ("Executive", "B1", "CTO"),
    ("Executive", "B1", "COO"),
    ("Executive", "B1", "CBO"),
    ("Executive", "B1", "Managing Director"),
]


def upgrade():
    op.create_table(
        "allowed_users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="hr_user"),
        sa.Column("added_by", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_allowed_users_email", "allowed_users", ["email"])

    op.create_table(
        "band_designations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("stream", sa.String(100), nullable=False),
        sa.Column("band", sa.String(50), nullable=False),
        sa.Column("designation", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stream", "band", "designation", name="uq_stream_band_designation"),
    )

    op.create_table(
        "job_postings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("stream", sa.String(100), nullable=False),
        sa.Column("band", sa.String(50), nullable=False),
        sa.Column("designation", sa.String(200), nullable=False),
        sa.Column("employment_type", sa.String(50), nullable=False, server_default="full_time"),
        sa.Column("experience_min", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skills_required", JSON, nullable=False),
        sa.Column("urgency", sa.String(50), nullable=False, server_default="standard"),
        sa.Column("jd_text", sa.Text(), nullable=True),
        sa.Column("jd_raw", JSON, nullable=True),
        sa.Column("ats_threshold", sa.Integer(), nullable=False, server_default="70"),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("bench_check_done", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("bench_result", JSON, nullable=True),
        sa.Column("careers_page_id", sa.String(255), nullable=True),
        sa.Column("total_applications", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_shortlisted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "candidates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_posting_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=False),
        sa.Column("resume_url", sa.String(1000), nullable=False),
        sa.Column("fit_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("score_breakdown", JSON, nullable=True),
        sa.Column("score_explanation", sa.Text(), nullable=True),
        sa.Column("source", sa.String(50), nullable=False, server_default="organic"),
        sa.Column("referral_by", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="evaluating"),
        sa.Column("is_shortlisted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("shortlisted_by", sa.String(255), nullable=True),
        sa.Column("shortlisted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hr_override", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("hr_override_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("hr_override_reason", sa.Text(), nullable=True),
        sa.Column("hr_override_by", sa.String(255), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_posting_id"], ["job_postings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_candidates_job_posting_id", "candidates", ["job_posting_id"])
    op.create_index("ix_candidates_email", "candidates", ["email"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("actor_email", sa.String(255), nullable=False),
        sa.Column("payload", JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_entity", "audit_events", ["entity_type", "entity_id"])
    op.create_index("ix_audit_actor", "audit_events", ["actor_email"])
    op.create_index("ix_audit_created", "audit_events", ["created_at"])

    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("hr_email", sa.String(255), nullable=False),
        sa.Column("job_posting_id", sa.UUID(), nullable=True),
        sa.Column("messages", JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_posting_id"], ["job_postings.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_recipient", "notifications", ["recipient_email"])

    # Seed band designations from PRD Appendix B
    band_table = sa.table(
        "band_designations",
        sa.column("id", sa.UUID()),
        sa.column("stream", sa.String()),
        sa.column("band", sa.String()),
        sa.column("designation", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    import uuid
    from datetime import datetime, timezone
    op.bulk_insert(
        band_table,
        [
            {
                "id": str(uuid.uuid4()),
                "stream": stream,
                "band": band,
                "designation": designation,
                "created_at": datetime.now(timezone.utc),
            }
            for stream, band, designation in BAND_DATA
        ],
    )


def downgrade():
    op.drop_table("notifications")
    op.drop_table("chat_sessions")
    op.drop_table("audit_events")
    op.drop_table("candidates")
    op.drop_table("job_postings")
    op.drop_table("band_designations")
    op.drop_table("allowed_users")
