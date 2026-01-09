"""
生成新聞文章的向量嵌入（Embedding）
使用 Jina AI API 為標題和摘要生成向量，並存儲到資料庫
"""

import os
import sys
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.models import NewsArticle
from database.config import Session
from utils.logger import get_logger
from utils.jina_client import JinaClient

load_dotenv()

# 建立 logger
logger = get_logger("generate_embeddings")



def generate_embeddings_for_articles(
    batch_size: int = 10,
    limit: Optional[int] = None,
    force_update: bool = False
):
    """
    為資料庫中的文章生成向量嵌入
    
    Args:
        batch_size: 每批次處理的文章數量
        limit: 最多處理的文章數量（None 表示處理所有）
        force_update: 是否強制更新已有嵌入的文章
    """
    print("="*80)
    print("開始生成文章向量嵌入")
    print("="*80)
    logger.info("開始生成文章向量嵌入")
    
    # 初始化 Jina Embedding 生成器
    try:
        generator = JinaClient()
        print(f"✓ Jina AI API 初始化成功")
        logger.info("Jina AI 客戶端初始化成功")
    except ValueError as e:
        error_msg = f"錯誤: {e}"
        print(f"✗ {error_msg}")
        logger.error(error_msg)
        return
    
    # 建立資料庫連線
    db = Session()
    
    try:
        # 查詢需要生成嵌入的文章
        if force_update:
            query = db.query(NewsArticle)
            print(f"模式: 強制更新所有文章")
        else:
            query = db.query(NewsArticle).filter(
                (NewsArticle.title_embedding.is_(None)) | 
                (NewsArticle.summary_embedding.is_(None))
            )
            print(f"模式: 只處理缺少嵌入的文章")
        
        if limit:
            query = query.limit(limit)
        
        articles = query.all()
        total_articles = len(articles)
        
        if total_articles == 0:
            msg = "所有文章都已有嵌入，無需處理"
            print(f"\n✓ {msg}")
            logger.info(msg)
            return
        
        print(f"找到 {total_articles} 篇需要處理的文章")
        logger.info(f"找到 {total_articles} 篇需要處理的文章")
        print(f"批次大小: {batch_size}")
        print("="*80)
        
        # 統計資訊
        stats = {
            "total": total_articles,
            "success": 0,
            "failed": 0,
            "title_generated": 0,
            "summary_generated": 0
        }
        
        # 分批處理
        for i in range(0, total_articles, batch_size):
            batch_articles = articles[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_articles + batch_size - 1) // batch_size
            
            print(f"\n處理批次 {batch_num}/{total_batches} ({len(batch_articles)} 篇文章)")
            
            # 準備標題和摘要文本
            titles = []
            summaries = []
            title_indices = []
            summary_indices = []
            
            for idx, article in enumerate(batch_articles):
                # 檢查是否需要生成標題嵌入
                if force_update or article.title_embedding is None:
                    if article.title:
                        titles.append(article.title)
                        title_indices.append(idx)
                
                # 檢查是否需要生成摘要嵌入
                if force_update or article.summary_embedding is None:
                    if article.summary:
                        summaries.append(article.summary)
                        summary_indices.append(idx)
            
            # 生成標題嵌入
            title_embeddings = []
            if titles:
                try:
                    print(f"  生成 {len(titles)} 個標題嵌入...")
                    logger.debug(f"生成 {len(titles)} 個標題嵌入")
                    title_embeddings = generator.generate_embeddings(titles, task="text-matching")
                    print(f"  ✓ 標題嵌入生成成功")
                    logger.info(f"標題嵌入生成成功: {len(title_embeddings)} 個")
                except Exception as e:
                    error_msg = f"標題嵌入生成失敗: {e}"
                    print(f"  ✗ {error_msg}")
                    logger.error(error_msg, exc_info=True)
            
            # 生成摘要嵌入
            summary_embeddings = []
            if summaries:
                try:
                    print(f"  生成 {len(summaries)} 個摘要嵌入...")
                    logger.debug(f"生成 {len(summaries)} 個摘要嵌入")
                    summary_embeddings = generator.generate_embeddings(summaries, task="text-matching")
                    print(f"  ✓ 摘要嵌入生成成功")
                    logger.info(f"摘要嵌入生成成功: {len(summary_embeddings)} 個")
                except Exception as e:
                    error_msg = f"摘要嵌入生成失敗: {e}"
                    print(f"  ✗ {error_msg}")
                    logger.error(error_msg, exc_info=True)
            
            # 更新資料庫
            for idx, article in enumerate(batch_articles):
                try:
                    updated = False
                    
                    # 更新標題嵌入
                    if idx in title_indices:
                        embedding_idx = title_indices.index(idx)
                        if embedding_idx < len(title_embeddings):
                            article.title_embedding = title_embeddings[embedding_idx]
                            stats["title_generated"] += 1
                            updated = True
                    
                    # 更新摘要嵌入
                    if idx in summary_indices:
                        embedding_idx = summary_indices.index(idx)
                        if embedding_idx < len(summary_embeddings):
                            article.summary_embedding = summary_embeddings[embedding_idx]
                            stats["summary_generated"] += 1
                            updated = True
                    
                    if updated:
                        db.commit()
                        stats["success"] += 1
                        print(f"  ✓ 已更新: {article.title[:50]}...")
                        logger.debug(f"已更新文章 {article.id}: {article.title[:50]}")
                    
                except Exception as e:
                    db.rollback()
                    stats["failed"] += 1
                    error_msg = f"更新失敗: {article.title[:50]}... - {e}"
                    print(f"  ✗ {error_msg}")
                    logger.error(error_msg, exc_info=True)
        
        # 顯示統計資訊
        print("\n" + "="*80)
        print("嵌入生成完成 - 統計資訊")
        print("="*80)
        print(f"總文章數: {stats['total']}")
        print(f"  ✓ 成功: {stats['success']}")
        print(f"  ✗ 失敗: {stats['failed']}")
        print(f"\n生成的嵌入:")
        print(f"  標題嵌入: {stats['title_generated']}")
        print(f"  摘要嵌入: {stats['summary_generated']}")
        print("="*80)
        
        logger.info(f"嵌入生成完成 - 成功: {stats['success']}, 失敗: {stats['failed']}, 標題: {stats['title_generated']}, 摘要: {stats['summary_generated']}")
        
    finally:
        db.close()


def main():
    """主程式"""
    import argparse
    
    parser = argparse.ArgumentParser(description='為新聞文章生成向量嵌入')
    parser.add_argument('--batch-size', type=int, default=10, help='每批次處理的文章數量（預設: 10）')
    parser.add_argument('--limit', type=int, help='最多處理的文章數量（預設: 處理所有）')
    parser.add_argument('--force', action='store_true', help='強制更新已有嵌入的文章')
    
    args = parser.parse_args()
    
    # 執行嵌入生成
    generate_embeddings_for_articles(
        batch_size=args.batch_size,
        limit=args.limit,
        force_update=args.force
    )


if __name__ == "__main__":
    main()
