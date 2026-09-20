"""Add unique advertiser alias constraint.

Revision ID: 0002_advertiser_alias_unique
Revises: 0001_initial
Create Date: 2026-09-20
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002_advertiser_alias_unique"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_advertiser_aliases_advertiser_alias",
        "advertiser_aliases",
        ["advertiser_id", "alias"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_advertiser_aliases_advertiser_alias", "advertiser_aliases", type_="unique")
