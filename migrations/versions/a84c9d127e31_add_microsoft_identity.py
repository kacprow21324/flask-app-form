"""Add immutable Microsoft Entra identity to users

Revision ID: a84c9d127e31
Revises: f93b6d1a820e
Create Date: 2026-06-07 15:05:00
"""
from alembic import op
import sqlalchemy as sa


revision = "a84c9d127e31"
down_revision = "f93b6d1a820e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("microsoft_tenant_id", sa.String(length=36), nullable=True)
        )
        batch_op.add_column(
            sa.Column("microsoft_object_id", sa.String(length=36), nullable=True)
        )
        batch_op.create_unique_constraint(
            "uq_users_microsoft_identity",
            ["microsoft_tenant_id", "microsoft_object_id"],
        )


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint(
            "uq_users_microsoft_identity", type_="unique",
        )
        batch_op.drop_column("microsoft_object_id")
        batch_op.drop_column("microsoft_tenant_id")
