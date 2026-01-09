"""change_embedding_dimensions_to_1024

Revision ID: 4287da6108de
Revises: 97c07ece827f
Create Date: 2026-01-09 14:05:18.162087

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4287da6108de'
down_revision: Union[str, Sequence[str], None] = '97c07ece827f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 使用原生 SQL 改變 vector 維度
    op.execute("""
        ALTER TABLE news_articles 
        ALTER COLUMN title_embedding TYPE vector(1024);
    """)
    
    op.execute("""
        ALTER TABLE news_articles 
        ALTER COLUMN summary_embedding TYPE vector(1024);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # 恢復原本的 1536 維度
    op.execute("""
        ALTER TABLE news_articles 
        ALTER COLUMN title_embedding TYPE vector(1536);
    """)
    
    op.execute("""
        ALTER TABLE news_articles 
        ALTER COLUMN summary_embedding TYPE vector(1536);
    """)
