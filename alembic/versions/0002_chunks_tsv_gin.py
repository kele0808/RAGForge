"""
gin index on chunks.tsv
Revision ID: 0002
Revises: 0001
"""
from alembic import op
from alembic.command import revision

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None
def upgrade() -> None:
    op.execute(
        "UPDATE chunks SET tsv = to_tsvector('simple', content) WHERE tsv IS NULL"
    )
    op.execute("CREATE INDEX ix_chunks_tsv ON chunks USING gin(tsv)")
def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_tsv")
