"""Add practice document metadata

Revision ID: c27d1148a72f
Revises: a84c9d127e31
Create Date: 2026-06-07 17:30:00
"""
from alembic import op
import sqlalchemy as sa


revision = "c27d1148a72f"
down_revision = "a84c9d127e31"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "practice_documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("internship_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("document_type", sa.String(length=100), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.Column(
            "verification_status", sa.String(length=20), nullable=False,
        ),
        sa.Column("supervisor_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["internship_id"], ["internships.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("practice_documents", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_practice_documents_internship_id"),
            ["internship_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_practice_documents_verification_status"),
            ["verification_status"],
            unique=False,
        )


def downgrade():
    op.drop_table("practice_documents")
