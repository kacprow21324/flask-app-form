"""Add multiple parts to an internship

Revision ID: b17f0a62c94e
Revises: 721cdc45917b
Create Date: 2026-06-07 13:45:00
"""
from alembic import op
import sqlalchemy as sa


revision = "b17f0a62c94e"
down_revision = "721cdc45917b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "internship_parts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("internship_id", sa.Integer(), nullable=False),
        sa.Column("part_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("uopz_id", sa.Integer(), nullable=True),
        sa.Column("zopz_id", sa.Integer(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("planned_hours", sa.Integer(), nullable=False),
        sa.Column("total_hours", sa.Integer(), nullable=False),
        sa.Column("total_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "part_number > 0", name="ck_internship_part_number_positive",
        ),
        sa.CheckConstraint(
            "planned_hours >= 0", name="ck_internship_part_planned_hours",
        ),
        sa.CheckConstraint(
            "total_hours >= 0", name="ck_internship_part_total_hours",
        ),
        sa.CheckConstraint(
            "total_days >= 0", name="ck_internship_part_total_days",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["internship_id"], ["internships.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["uopz_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["zopz_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "internship_id", "part_number", name="uq_internship_part_number",
        ),
    )
    with op.batch_alter_table("internship_parts", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_internship_parts_company_id"),
            ["company_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_internship_parts_internship_id"),
            ["internship_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_internship_parts_status"),
            ["status"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_internship_parts_uopz_id"),
            ["uopz_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_internship_parts_zopz_id"),
            ["zopz_id"],
            unique=False,
        )

    bind = op.get_bind()
    internships = bind.execute(sa.text(
        """
        SELECT id, company_id, uopz_id, zopz_id, start_date, end_date,
               total_hours, total_days, status, created_at, updated_at
        FROM internships
        """
    )).mappings()
    insert_part = sa.text(
        """
        INSERT INTO internship_parts (
            internship_id, part_number, name, company_id, uopz_id, zopz_id,
            start_date, end_date, planned_hours, total_hours, total_days,
            status, created_at, updated_at
        ) VALUES (
            :internship_id, 1, :name, :company_id, :uopz_id, :zopz_id,
            :start_date, :end_date, :planned_hours, :total_hours, :total_days,
            :status, :created_at, :updated_at
        )
        """
    )
    for row in internships:
        total_hours = row["total_hours"] or 0
        part_status = (
            row["status"]
            if row["status"] in {"active", "completed"}
            else "planned"
        )
        bind.execute(insert_part, {
            "internship_id": row["id"],
            "name": "Część 1",
            "company_id": row["company_id"],
            "uopz_id": row["uopz_id"],
            "zopz_id": row["zopz_id"],
            "start_date": row["start_date"],
            "end_date": row["end_date"],
            "planned_hours": total_hours,
            "total_hours": total_hours,
            "total_days": row["total_days"] or 0,
            "status": part_status,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        })


def downgrade():
    with op.batch_alter_table("internship_parts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_internship_parts_zopz_id"))
        batch_op.drop_index(batch_op.f("ix_internship_parts_uopz_id"))
        batch_op.drop_index(batch_op.f("ix_internship_parts_status"))
        batch_op.drop_index(batch_op.f("ix_internship_parts_internship_id"))
        batch_op.drop_index(batch_op.f("ix_internship_parts_company_id"))
    op.drop_table("internship_parts")
