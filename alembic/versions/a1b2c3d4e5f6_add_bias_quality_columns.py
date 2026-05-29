"""add cluster_type, attempted_count, confidence for bias quality

Revision ID: a1b2c3d4e5f6
Revises: 7cf38f6a33f3
Create Date: 2026-05-29 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '7cf38f6a33f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'topic_clusters',
        sa.Column('cluster_type', sa.String(length=20), nullable=True,
                  server_default='controversial', comment='controversial | informational'),
    )
    op.add_column(
        'topic_clusters',
        sa.Column('attempted_count', sa.Integer(), nullable=True,
                  server_default='0', comment='嘗試分析的文章數（含抓取失敗）'),
    )
    op.add_column(
        'article_bias',
        sa.Column('confidence', sa.Float(), nullable=True, comment='LLM 判斷信心 0-1'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('article_bias', 'confidence')
    op.drop_column('topic_clusters', 'attempted_count')
    op.drop_column('topic_clusters', 'cluster_type')
