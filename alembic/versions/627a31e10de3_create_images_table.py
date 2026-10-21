"""create images table

Revision ID: 627a31e10de3
Revises: 9d5c0637f98d
Create Date: 2026-10-19 14:15:49.374635
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "627a31e10de3"

down_revision: Union[str, Sequence[str], None] = "9d5c0637f98d"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "images",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            nullable=False,
        ),

        sa.Column(
            "url",
            sa.String(),
            nullable=False,
        ),

        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("images")