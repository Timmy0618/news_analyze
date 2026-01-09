"""
生成新聞文章的向量嵌入（Embedding）
使用 Jina AI API 為標題和摘要生成向量，並存儲到資料庫
"""

import os
import sys
from pathlib import Path
from typing import List, Optional
import requests
from dotenv import load_dotenv

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent))

from database.models import NewsArticle
from database.config import Session

load_dotenv()


class JinaEmbeddingGenerator:
    """Jina AI Embedding 生成器"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 Jina Embedding 生成器
        
        Args:
            api_key: Jina AI API 金鑰（可選，從環境變數 JINA_API_KEY 讀取）
        """
        self.api_key = api_key or os.getenv("JINA_API_KEY")
        if not self.api_key:
            raise ValueError("請設定 JINA_API_KEY 環境變數或提供 API 金鑰")
        
        self.api_url = "https://api.jina.ai/v1/embeddings"
        self.model = "jina-embeddings-v3"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    def generate_embeddings(self, texts: List[str], task: str = "retrieval.passage") -> List[List[float]]:
        """
        生成文本的向量嵌入
        
        Args:
            texts: 要生成嵌入的文本列表
            task: 任務類型（retrieval.passage, retrieval.query, text-matching, classification 等）
        
        Returns:
            向量嵌入列表
        """
        if not texts:
            return []
        
        # Jina AI API v1 參數格式
        payload = {
            "model": self.model,
            "input": texts,
            "encoding_type": "float"  # 使用 float 編碼
        }
        
        # jina-embeddings-v3 最大支援 1024 維度
        if "v3" in self.model:
            payload["dimensions"] = 1024
        elif "v2" in self.model:
            payload["dimensions"] = 1024
        
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers=self.headers,
                timeout=60  # 增加超時時間
            )
            
            # 如果請求失敗，打印詳細錯誤信息
            if not response.ok:
                print(f"  ✗ API 錯誤狀態碼: {response.status_code}")
                print(f"  ✗ 錯誤內容: {response.text}")
                print(f"  ✗ 請求參數: {payload}")
            
            response.raise_for_status()
            
            data = response.json()
            embeddings = [item["embedding"] for item in data["data"]]
            
            return embeddings
            
        except requests.exceptions.RequestException as e:
            print(f"  ✗ Jina API 請求失敗: {e}")
            raise
        except (KeyError, ValueError) as e:
            print(f"  ✗ 解析 Jina API 回應失敗: {e}")
            print(f"  ✗ 回應內容: {response.text if 'response' in locals() else 'N/A'}")
            raise
    
    def generate_single_embedding(self, text: str, task: str = "retrieval.passage") -> List[float]:
        """
        生成單一文本的向量嵌入
        
        Args:
            text: 要生成嵌入的文本
            task: 任務類型
        
        Returns:
            向量嵌入
        """
        embeddings = self.generate_embeddings([text], task)
        return embeddings[0] if embeddings else []


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
    
    # 初始化 Jina Embedding 生成器
    try:
        generator = JinaEmbeddingGenerator()
        print(f"✓ Jina AI API 初始化成功")
    except ValueError as e:
        print(f"✗ 錯誤: {e}")
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
            print("\n✓ 所有文章都已有嵌入，無需處理")
            return
        
        print(f"找到 {total_articles} 篇需要處理的文章")
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
                    title_embeddings = generator.generate_embeddings(titles)
                    print(f"  ✓ 標題嵌入生成成功")
                except Exception as e:
                    print(f"  ✗ 標題嵌入生成失敗: {e}")
            
            # 生成摘要嵌入
            summary_embeddings = []
            if summaries:
                try:
                    print(f"  生成 {len(summaries)} 個摘要嵌入...")
                    summary_embeddings = generator.generate_embeddings(summaries)
                    print(f"  ✓ 摘要嵌入生成成功")
                except Exception as e:
                    print(f"  ✗ 摘要嵌入生成失敗: {e}")
            
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
                    
                except Exception as e:
                    db.rollback()
                    stats["failed"] += 1
                    print(f"  ✗ 更新失敗: {article.title[:50]}... - {e}")
        
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
