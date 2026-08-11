"""create users table

Revision ID: 19a80d91046e
Revises: 19fc0e5404d9
Create Date: 2026-08-06 19:09:54.102501

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '19a80d91046e'
down_revision: Union[str, Sequence[str], None] = '19fc0e5404d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "users",
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username")
    )

    with op.batch_alter_table("projects") as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DATETIME(),
            nullable=False
        )

        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DATETIME(),
            nullable=False
        )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""

    with op.batch_alter_table("projects") as batch_op:
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DATETIME(),
            nullable=True
        )

        batch_op.alter_column(
            "created_at",
            existing_type=sa.DATETIME(),
            nullable=True
        )

    op.drop_table("users")
    # ### end Alembic commands ###
