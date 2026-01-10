"""
新聞資料庫模型
支援 pgvector 向量搜尋
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Date, Index, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class NewsArticle(Base):
    """新聞文章模型"""
    
    __tablename__ = 'news_articles'
    
    # 主鍵
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 新聞基本資訊
    title = Column(String(500), nullable=False, comment='新聞標題')
    reporter = Column(String(100), comment='記者')
    summary = Column(Text, comment='新聞大綱')
    
    # 日期和來源
    publish_date = Column(Date, nullable=False, comment='發布日期')
    source_url = Column(String(1000), nullable=False, unique=True, comment='新聞連結')
    source_site = Column(String(50), comment='來源網站（如：TVBS、三立、中時）')
    
    # 向量欄位（用於語義搜索）
    # 1024 維度適用於 Jina AI jina-embeddings-v3
    # 可根據使用的模型調整維度
    title_embedding = Column(Vector(1024), comment='標題向量')
    summary_embedding = Column(Vector(1024), comment='大綱向量')
    
    # 系統欄位
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment='建立時間')
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment='更新時間')
    
    # 索引
    __table_args__ = (
        # 標題全文檢索索引
        Index('idx_title', 'title'),
        # 日期索引
        Index('idx_publish_date', 'publish_date'),
        # 來源網站索引
        Index('idx_source_site', 'source_site'),
        # 向量相似度索引（HNSW 索引，適合大規模向量搜索）
        Index('idx_title_embedding_hnsw', 'title_embedding', postgresql_using='hnsw', 
              postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'title_embedding': 'vector_cosine_ops'}),
        Index('idx_summary_embedding_hnsw', 'summary_embedding', postgresql_using='hnsw',
              postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'summary_embedding': 'vector_cosine_ops'}),
    )
    
    def __repr__(self):
        return f"<NewsArticle(id={self.id}, title='{self.title[:30]}...', date={self.publish_date})>"
    
    def to_dict(self):
        """轉換為字典格式"""
        return {
            'id': self.id,
            'title': self.title,
            'reporter': self.reporter,
            'summary': self.summary,
            'publish_date': self.publish_date.isoformat() if self.publish_date else None,
            'source_url': self.source_url,
            'source_site': self.source_site,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class NewsTopicStatistics(Base):
    """新聞主題統計模型"""
    
    __tablename__ = 'news_topic_statistics'
    
    # 主鍵
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 分析日期（每天一筆統計）
    analysis_date = Column(Date, nullable=False, unique=True, comment='分析日期')
    
    # 統計數據
    total_articles = Column(Integer, nullable=False, comment='總文章數')
    topics_data = Column(JSON, nullable=False, comment='主題分析數據')
    
    # 系統欄位
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment='建立時間')
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment='更新時間')
    
    # 索引
    __table_args__ = (
        Index('idx_analysis_date', 'analysis_date'),
    )
    
    def __repr__(self):
        return f"<NewsTopicStatistics(id={self.id}, date={self.analysis_date}, total_articles={self.total_articles})>"
    
    def to_dict(self):
        """轉換為字典格式"""
        return {
            'id': self.id,
            'analysis_date': self.analysis_date.isoformat() if self.analysis_date else None,
            'total_articles': self.total_articles,
            'topics_data': self.topics_data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
