"""create refresh tokens table

Revision ID: 9d5c0637f98d
Revises: 40b016ca58ef
Create Date: 2026-09-02 19:31:54.748213

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9d5c0637f98d"
down_revision: Union[str, Sequence[str], None] = "40b016ca58ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",

        sa.Column(
            "jti",
            sa.String(),
            nullable=False,
        ),

        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "family_id",
            sa.String(),
            nullable=False,
        ),

        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.Column(
            "status",
            sa.Enum(
                "active",
                "used",
                "revoked",
                name="refresh_token_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),

        sa.Column(
            "used_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),

        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_refresh_tokens_family_id"),
        "refresh_tokens",
        ["family_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_refresh_tokens_jti"),
        "refresh_tokens",
        ["jti"],
        unique=True,
    )

    op.create_index(
        op.f("ix_refresh_tokens_user_id"),
        "refresh_tokens",
        ["user_id"],
        unique=False,
    )

    op.drop_column(
        "projects",
        "deleted_at",
    )

    op.drop_column(
        "users",
        "deleted_at",
    )


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "deleted_at",
            sa.DateTime(),
            nullable=True,
        ),
    )

    op.add_column(
        "projects",
        sa.Column(
            "deleted_at",
            sa.DateTime(),
            nullable=True,
        ),
    )

    op.drop_index(
        op.f("ix_refresh_tokens_user_id"),
        table_name="refresh_tokens",
    )

    op.drop_index(
        op.f("ix_refresh_tokens_jti"),
        table_name="refresh_tokens",
    )

    op.drop_index(
        op.f("ix_refresh_tokens_family_id"),
        table_name="refresh_tokens",
    )

    op.drop_table(
        "refresh_tokens",
    )