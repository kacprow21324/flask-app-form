"""Version approved PDF documents

Revision ID: e42c3a70f15d
Revises: d6f84a9013bc
Create Date: 2026-06-07 14:20:00
"""
from collections import defaultdict
import hashlib

from alembic import op
import sqlalchemy as sa


revision = "e42c3a70f15d"
down_revision = "d6f84a9013bc"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("document_workflow", schema=None) as batch_op:
        batch_op.add_column(sa.Column("approved_revision", sa.Integer(), nullable=True))

    with op.batch_alter_table("generated_documents", schema=None) as batch_op:
        batch_op.add_column(sa.Column("internship_part_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("document_version", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("source_revision", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("source_checksum", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("source_fingerprint", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("source_approved_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("is_current", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_generated_documents_internship_part_id",
            "internship_parts",
            ["internship_part_id"],
            ["id"],
            ondelete="SET NULL",
        )

    bind = op.get_bind()
    rows = list(bind.execute(sa.text(
        """
        SELECT id, album_number, form_key, checksum_sha256, generated_at,
               template_version
        FROM generated_documents
        ORDER BY album_number, form_key, generated_at, id
        """
    )).mappings())
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["album_number"], row["form_key"])].append(row)

    update = sa.text(
        """
        UPDATE generated_documents
        SET document_version = :document_version,
            source_revision = 0,
            source_checksum = :source_checksum,
            source_fingerprint = :source_fingerprint,
            source_approved_at = :source_approved_at,
            template_version = :template_version,
            is_current = :is_current
        WHERE id = :id
        """
    )
    for group_rows in grouped.values():
        latest_id = group_rows[-1]["id"]
        for version, row in enumerate(group_rows, start=1):
            fingerprint = hashlib.sha256(
                f"legacy:{row['id']}:{row['checksum_sha256']}".encode("utf-8")
            ).hexdigest()
            bind.execute(update, {
                "id": row["id"],
                "document_version": version,
                "source_checksum": row["checksum_sha256"],
                "source_fingerprint": fingerprint,
                "source_approved_at": row["generated_at"],
                "template_version": row["template_version"] or "legacy",
                "is_current": 1 if row["id"] == latest_id else 0,
            })

    with op.batch_alter_table("generated_documents", schema=None) as batch_op:
        batch_op.alter_column(
            "document_version", existing_type=sa.Integer(), nullable=False,
        )
        batch_op.alter_column(
            "source_revision", existing_type=sa.Integer(), nullable=False,
        )
        batch_op.alter_column(
            "source_checksum", existing_type=sa.String(length=64), nullable=False,
        )
        batch_op.alter_column(
            "source_fingerprint", existing_type=sa.String(length=64), nullable=False,
        )
        batch_op.alter_column(
            "template_version", existing_type=sa.String(length=50),
            type_=sa.String(length=80), nullable=False,
        )
        batch_op.alter_column(
            "is_current", existing_type=sa.Integer(), nullable=False,
        )
        batch_op.create_index(
            batch_op.f("ix_generated_documents_internship_part_id"),
            ["internship_part_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_generated_documents_is_current"),
            ["is_current"],
            unique=False,
        )
        batch_op.create_unique_constraint(
            "uq_generated_document_source", ["source_fingerprint"],
        )


def downgrade():
    with op.batch_alter_table("generated_documents", schema=None) as batch_op:
        batch_op.drop_constraint("uq_generated_document_source", type_="unique")
        batch_op.drop_index(batch_op.f("ix_generated_documents_is_current"))
        batch_op.drop_index(
            batch_op.f("ix_generated_documents_internship_part_id"),
        )
        batch_op.drop_constraint(
            "fk_generated_documents_internship_part_id", type_="foreignkey",
        )
        batch_op.alter_column(
            "template_version", existing_type=sa.String(length=80),
            type_=sa.String(length=50), nullable=True,
        )
        batch_op.drop_column("is_current")
        batch_op.drop_column("source_approved_at")
        batch_op.drop_column("source_fingerprint")
        batch_op.drop_column("source_checksum")
        batch_op.drop_column("source_revision")
        batch_op.drop_column("document_version")
        batch_op.drop_column("internship_part_id")

    with op.batch_alter_table("document_workflow", schema=None) as batch_op:
        batch_op.drop_column("approved_revision")
