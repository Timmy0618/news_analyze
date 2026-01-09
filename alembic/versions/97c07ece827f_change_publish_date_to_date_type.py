"""change_publish_date_to_date_type

Revision ID: 97c07ece827f
Revises: ff6502bff2e5
Create Date: 2026-01-09 11:33:04.151795

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '97c07ece827f'
down_revision: Union[str, Sequence[str], None] = 'ff6502bff2e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 使用 USING 子句明確指定如何轉換數據
    # 先檢查欄位類型是否已經是 DATE，如果不是才轉換
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'news_articles' 
                AND column_name = 'publish_date' 
                AND data_type = 'character varying'
            ) THEN
                ALTER TABLE news_articles 
                ALTER COLUMN publish_date TYPE DATE 
                USING to_date(publish_date, 'YYYY/MM/DD');
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # 降級時將 DATE 轉回 VARCHAR，格式化為 YYYY/MM/DD
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'news_articles' 
                AND column_name = 'publish_date' 
                AND data_type = 'date'
            ) THEN
                ALTER TABLE news_articles 
                ALTER COLUMN publish_date TYPE VARCHAR(20) 
                USING to_char(publish_date, 'YYYY/MM/DD');
            END IF;
        END $$;
    """)
    # ### end Alembic commands ###
