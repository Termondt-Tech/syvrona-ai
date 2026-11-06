"""Create the tables that existed before the first recorded migration

The original chain starts at 6e6b4a63de26 (2025-05-20), which adds ``conversation``
with a foreign key to ``user``; ``user``, ``post`` and ``comment`` had been created by
``db.create_all()`` and never recorded. Without this baseline, ``flask db upgrade`` on
an empty database fails at the first revision. The shapes below are the models as
they stood at a5fc22d^ (later revisions add every other ``user`` column, and
6a9d18428602 drops ``post`` and ``comment``).

Databases that were bootstrapped by ``create_all()`` already sit above this revision,
so ``upgrade`` never runs it for them.

Revision ID: baseline_2025_05
Revises:
Create Date: 2026-11-06

"""

import sqlalchemy as sa
from alembic import op

revision = "baseline_2025_05"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=100), nullable=True),
        sa.Column("password", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=1000), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "post",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=True),
        sa.Column("content", sa.String(length=1000), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "comment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content", sa.String(length=1000), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["post.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("comment")
    op.drop_table("post")
    op.drop_table("user")
