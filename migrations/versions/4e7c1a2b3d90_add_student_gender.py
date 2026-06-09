"""Add explicit student gender

Revision ID: 4e7c1a2b3d90
Revises: 9b3a4d5e6f70
Create Date: 2026-06-08 19:30:00
"""
from alembic import op
import sqlalchemy as sa


revision = "4e7c1a2b3d90"
down_revision = "9b3a4d5e6f70"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("gender", sa.String(length=1)))


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("gender")
