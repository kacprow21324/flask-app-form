"""Add server-side grade calculation history

Revision ID: d6f84a9013bc
Revises: b17f0a62c94e
Create Date: 2026-06-07 14:05:00
"""
from alembic import op
import sqlalchemy as sa


revision = "d6f84a9013bc"
down_revision = "b17f0a62c94e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "grade_calculations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("internship_id", sa.Integer(), nullable=False),
        sa.Column("grade_e", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column("grade_s", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column("grade_u", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column("grade_z", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column("weighted_result", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column("final_grade", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column("formula_version", sa.String(length=30), nullable=False),
        sa.Column("calculated_by", sa.Integer(), nullable=True),
        sa.Column("calculated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["calculated_by"], ["users.id"], ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["internship_id"], ["internships.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("grade_calculations", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_grade_calculations_calculated_by"),
            ["calculated_by"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_grade_calculations_internship_id"),
            ["internship_id"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("grade_calculations", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_grade_calculations_internship_id"))
        batch_op.drop_index(batch_op.f("ix_grade_calculations_calculated_by"))
    op.drop_table("grade_calculations")
