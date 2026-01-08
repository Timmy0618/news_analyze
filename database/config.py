"""
資料庫連線設定
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from dotenv import load_dotenv

load_dotenv()

# 資料庫連線 URL
# 格式: postgresql://username:password@host:port/database
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://postgres:postgres@localhost:5432/news_db'
)

# 建立資料庫引擎
engine = create_engine(
    DATABASE_URL,
    echo=True,  # 開發時顯示 SQL，生產環境建議設為 False
    pool_size=10,  # 連線池大小
    max_overflow=20,  # 最大溢出連線數
    pool_pre_ping=True,  # 連線前先檢查是否有效
)

# 建立 Session 工廠
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 建立 thread-safe 的 Session
Session = scoped_session(SessionLocal)


def get_db():
    """
    獲取資料庫 session（用於依賴注入）
    
    使用方式:
    ```python
    db = next(get_db())
    try:
        # 執行資料庫操作
        pass
    finally:
        db.close()
    ```
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    初始化資料庫
    - 啟用 pgvector 擴展
    - 創建所有資料表
    """
    from database.models import Base
    from sqlalchemy import text
    
    # 啟用 pgvector 擴展
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    
    # 創建所有資料表
    Base.metadata.create_all(bind=engine)
    print("✓ 資料庫初始化完成")


if __name__ == "__main__":
    # 測試資料庫連線
    from sqlalchemy import text
    print(f"正在連接資料庫: {DATABASE_URL}")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✓ 資料庫連線成功")
            print(f"PostgreSQL 版本: {version}")
    except Exception as e:
        print(f"✗ 資料庫連線失敗: {e}")
