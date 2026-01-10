"""add_news_topic_statistics_table

Revision ID: d376777ac017
Revises: 4287da6108de
Create Date: 2026-01-10 13:55:39.299437

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd376777ac017'
down_revision: Union[str, Sequence[str], None] = '4287da6108de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 創建新聞主題統計表
    op.create_table('news_topic_statistics',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('analysis_date', sa.Date(), nullable=False, comment='分析日期'),
    sa.Column('total_articles', sa.Integer(), nullable=False, comment='總文章數'),
    sa.Column('topics_data', sa.JSON(), nullable=False, comment='主題分析數據'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True, comment='建立時間'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True, comment='更新時間'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('analysis_date', name='uq_analysis_date')
    )
    # 為分析日期創建索引
    op.create_index('idx_analysis_date', 'news_topic_statistics', ['analysis_date'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # 刪除索引
    op.drop_index('idx_analysis_date', table_name='news_topic_statistics')
    # 刪除表
    op.drop_table('news_topic_statistics')
