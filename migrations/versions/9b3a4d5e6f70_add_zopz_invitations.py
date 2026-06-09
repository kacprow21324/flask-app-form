"""Add invitations for workplace internship supervisors

Revision ID: 9b3a4d5e6f70
Revises: c27d1148a72f
Create Date: 2026-06-08 12:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "9b3a4d5e6f70"
down_revision = "c27d1148a72f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "zopz_invitations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("internship_id", sa.Integer(), nullable=False),
        sa.Column("internship_part_id", sa.Integer(), nullable=True),
        sa.Column("invited_by_id", sa.Integer(), nullable=True),
        sa.Column("accepted_user_id", sa.Integer(), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["accepted_user_id"], ["users.id"], ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["internship_id"], ["internships.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["internship_part_id"], ["internship_parts.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_id"], ["users.id"], ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    with op.batch_alter_table("zopz_invitations", schema=None) as batch_op:
        for column in (
            "accepted_user_id",
            "email",
            "expires_at",
            "internship_id",
            "internship_part_id",
            "invited_by_id",
        ):
            batch_op.create_index(
                batch_op.f(f"ix_zopz_invitations_{column}"),
                [column],
                unique=False,
            )


def downgrade():
    with op.batch_alter_table("zopz_invitations", schema=None) as batch_op:
        for column in (
            "invited_by_id",
            "internship_part_id",
            "internship_id",
            "expires_at",
            "email",
            "accepted_user_id",
        ):
            batch_op.drop_index(
                batch_op.f(f"ix_zopz_invitations_{column}"),
            )
    op.drop_table("zopz_invitations")
