"""Add retention archives and anonymization metadata

Revision ID: f93b6d1a820e
Revises: e42c3a70f15d
Create Date: 2026-06-07 14:45:00
"""
from alembic import op
import sqlalchemy as sa


revision = "f93b6d1a820e"
down_revision = "e42c3a70f15d"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("anonymized_at", sa.DateTime(), nullable=True))

    op.create_table(
        "archive_packages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=True),
        sa.Column("original_album_number", sa.String(length=20), nullable=True),
        sa.Column("album_hash", sa.String(length=64), nullable=False),
        sa.Column("package_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("file_path", sa.String(length=700), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("manifest_checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("retention_until", sa.DateTime(), nullable=False),
        sa.Column("anonymized_at", sa.DateTime(), nullable=True),
        sa.Column("purged_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "student_id", "package_version", name="uq_archive_student_version",
        ),
    )
    with op.batch_alter_table("archive_packages", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_archive_packages_album_hash"),
            ["album_hash"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_archive_packages_created_by"),
            ["created_by"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_archive_packages_original_album_number"),
            ["original_album_number"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_archive_packages_retention_until"),
            ["retention_until"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_archive_packages_status"),
            ["status"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_archive_packages_student_id"),
            ["student_id"],
            unique=False,
        )
    op.execute(sa.text(
        """
        INSERT INTO app_config (`key`, value, label)
        SELECT 'data_retention_years', '10',
               'Okres retencji archiwum studenta w latach'
        WHERE NOT EXISTS (
            SELECT 1 FROM app_config WHERE `key` = 'data_retention_years'
        )
        """
    ))


def downgrade():
    op.execute(sa.text(
        "DELETE FROM app_config WHERE `key` = 'data_retention_years'"
    ))
    with op.batch_alter_table("archive_packages", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_archive_packages_student_id"))
        batch_op.drop_index(batch_op.f("ix_archive_packages_status"))
        batch_op.drop_index(batch_op.f("ix_archive_packages_retention_until"))
        batch_op.drop_index(
            batch_op.f("ix_archive_packages_original_album_number"),
        )
        batch_op.drop_index(batch_op.f("ix_archive_packages_created_by"))
        batch_op.drop_index(batch_op.f("ix_archive_packages_album_hash"))
    op.drop_table("archive_packages")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("anonymized_at")
