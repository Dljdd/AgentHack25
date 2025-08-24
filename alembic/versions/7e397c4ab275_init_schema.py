"""init schema

Revision ID: 7e397c4ab275
Revises: 
Create Date: 2025-08-23 17:53:55.711718

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = '7e397c4ab275'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op baseline: the database is already in sync with models."""
    pass


def downgrade() -> None:
    """No-op baseline revert."""
    pass
