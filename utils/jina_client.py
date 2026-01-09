"""
Jina AI API 客戶端工具
提供統一的 Jina Embeddings API 介面
"""

import os
from typing import List, Optional, Dict, Any
import httpx
import requests
from dotenv import load_dotenv

from .logger import get_logger

# 載入環境變數
load_dotenv()

# 建立 logger
logger = get_logger("jina_client")


class JinaClient:
    """Jina AI API 客戶端"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 Jina AI 客戶端
        
        Args:
            api_key: Jina AI API 金鑰（可選，從環境變數 JINA_API_KEY 讀取）
        """
        self.api_key = api_key or os.getenv("JINA_API_KEY")
        if not self.api_key:
            error_msg = "JINA_API_KEY 未設定，請在 .env 檔案中設定或提供 API 金鑰"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        self.api_url = "https://api.jina.ai/v1/embeddings"
        self.model = "jina-embeddings-v3"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        logger.info(f"Jina 客戶端初始化完成，使用模型: {self.model}")
    
    def generate_embeddings(
        self,
        texts: List[str],
        task: str = "text-matching",
        dimensions: int = 1024,
        encoding_type: str = "float"
    ) -> List[List[float]]:
        """
        生成多個文本的向量嵌入（同步版本）
        
        Args:
            texts: 要生成嵌入的文本列表
            task: 任務類型（text-matching, retrieval.passage, retrieval.query 等）
            dimensions: 向量維度（預設 1024）
            encoding_type: 編碼類型（float 或 int8）
        
        Returns:
            向量嵌入列表
        """
        if not texts:
            logger.warning("輸入文本列表為空")
            return []
        
        payload = {
            "model": self.model,
            "input": texts,
            "task": task,
            "dimensions": dimensions,
            "encoding_type": encoding_type,
            "late_chunking": False
        }
        
        try:
            logger.debug(f"發送 Jina API 請求，文本數量: {len(texts)}")
            
            response = requests.post(
                self.api_url,
                json=payload,
                headers=self.headers,
                timeout=60
            )
            
            if not response.ok:
                error_msg = f"Jina API 請求失敗 - 狀態碼: {response.status_code}, 內容: {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            response.raise_for_status()
            
            data = response.json()
            embeddings = [item["embedding"] for item in data["data"]]
            
            logger.info(f"成功生成 {len(embeddings)} 個向量嵌入")
            return embeddings
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Jina API 請求異常: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise Exception(error_msg) from e
            
        except (KeyError, ValueError, IndexError) as e:
            error_msg = f"解析 Jina API 回應失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if 'response' in locals():
                logger.error(f"回應內容: {response.text}")
            raise Exception(error_msg) from e
    
    async def generate_embeddings_async(
        self,
        texts: List[str],
        task: str = "text-matching",
        dimensions: int = 1024,
        encoding_type: str = "float"
    ) -> List[List[float]]:
        """
        生成多個文本的向量嵌入（異步版本）
        
        Args:
            texts: 要生成嵌入的文本列表
            task: 任務類型（text-matching, retrieval.passage, retrieval.query 等）
            dimensions: 向量維度（預設 1024）
            encoding_type: 編碼類型（float 或 int8）
        
        Returns:
            向量嵌入列表
        """
        if not texts:
            logger.warning("輸入文本列表為空")
            return []
        
        payload = {
            "model": self.model,
            "input": texts,
            "task": task,
            "dimensions": dimensions,
            "encoding_type": encoding_type,
            "late_chunking": False
        }
        
        try:
            logger.debug(f"發送 Jina API 異步請求，文本數量: {len(texts)}")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=60.0
                )
                
                if not response.is_success:
                    error_msg = f"Jina API 請求失敗 - 狀態碼: {response.status_code}, 內容: {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                
                response.raise_for_status()
            
            data = response.json()
            embeddings = [item["embedding"] for item in data["data"]]
            
            logger.info(f"成功生成 {len(embeddings)} 個向量嵌入")
            return embeddings
            
        except httpx.HTTPError as e:
            error_msg = f"Jina API HTTP 錯誤: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise Exception(error_msg) from e
            
        except (KeyError, ValueError, IndexError) as e:
            error_msg = f"解析 Jina API 回應失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if 'response' in locals():
                logger.error(f"回應內容: {response.text}")
            raise Exception(error_msg) from e
    
    def generate_single_embedding(
        self,
        text: str,
        task: str = "text-matching",
        dimensions: int = 1024
    ) -> List[float]:
        """
        生成單個文本的向量嵌入（同步版本）
        
        Args:
            text: 要生成嵌入的文本
            task: 任務類型
            dimensions: 向量維度
        
        Returns:
            向量嵌入
        """
        embeddings = self.generate_embeddings([text], task, dimensions)
        return embeddings[0] if embeddings else []
    
    async def generate_single_embedding_async(
        self,
        text: str,
        task: str = "text-matching",
        dimensions: int = 1024
    ) -> List[float]:
        """
        生成單個文本的向量嵌入（異步版本）
        
        Args:
            text: 要生成嵌入的文本
            task: 任務類型
            dimensions: 向量維度
        
        Returns:
            向量嵌入
        """
        embeddings = await self.generate_embeddings_async([text], task, dimensions)
        return embeddings[0] if embeddings else []


# 全域單例
_jina_client: Optional[JinaClient] = None


def get_jina_client(api_key: Optional[str] = None) -> JinaClient:
    """
    取得 Jina 客戶端單例
    
    Args:
        api_key: API 金鑰（可選）
    
    Returns:
        JinaClient 實例
    """
    global _jina_client
    
    if _jina_client is None:
        _jina_client = JinaClient(api_key)
    
    return _jina_client


async def generate_embedding(text: str, task: str = "text-matching") -> List[float]:
    """
    便捷函數：生成單個文本的向量嵌入（異步）
    
    Args:
        text: 要轉換的文本
        task: 任務類型
    
    Returns:
        向量嵌入
    """
    try:
        client = get_jina_client()
        embedding = await client.generate_single_embedding_async(text, task)
        return embedding
    except Exception as e:
        logger.error(f"生成向量嵌入失敗: {str(e)}", exc_info=True)
        raise
