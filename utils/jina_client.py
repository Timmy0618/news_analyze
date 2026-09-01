"""
Embedding 客戶端：呼叫本機 OpenAI 相容的 embedding server
（預設 vLLM + Qwen/Qwen3-Embedding-0.6B，1024 維）
"""

import os
from typing import List, Optional
import httpx
import requests
from dotenv import load_dotenv

from .logger import get_logger

load_dotenv()

logger = get_logger("embed_client")


class JinaClient:
    """Embedding 客戶端（沿用舊名稱，避免動到其他呼叫端）"""

    def __init__(self, api_key: Optional[str] = None):
        base_url = os.getenv("EMBED_URL", "http://localhost:8003/v1").rstrip("/")
        self.api_url = f"{base_url}/embeddings"
        self.model = os.getenv("EMBED_MODEL", "qwen3-embed")
        # ponytail: 本機 server 不驗 key，帶著只是為了相容遠端 endpoint
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key or os.getenv('EMBED_API_KEY', 'EMPTY')}",
        }
        logger.info(f"Embedding 客戶端初始化完成: {self.api_url}, 模型: {self.model}")

    def _payload(self, texts: List[str]) -> dict:
        return {"model": self.model, "input": texts}

    @staticmethod
    def _parse(data: dict) -> List[List[float]]:
        return [item["embedding"] for item in data["data"]]

    def generate_embeddings(
        self,
        texts: List[str],
        task: str = "text-matching",  # 保留簽名相容，本機模型不吃這參數
        dimensions: int = 1024,
        encoding_type: str = "float",
    ) -> List[List[float]]:
        """生成多個文本的向量嵌入（同步版本）"""
        if not texts:
            logger.warning("輸入文本列表為空")
            return []

        try:
            response = requests.post(
                self.api_url, json=self._payload(texts), headers=self.headers, timeout=120
            )
            if not response.ok:
                raise Exception(
                    f"Embedding API 請求失敗 - 狀態碼: {response.status_code}, 內容: {response.text}"
                )

            embeddings = self._parse(response.json())
            logger.info(f"成功生成 {len(embeddings)} 個向量嵌入")
            return embeddings

        except requests.exceptions.RequestException as e:
            logger.error(f"Embedding API 請求異常: {e}", exc_info=True)
            raise Exception(f"Embedding API 請求異常: {e}") from e
        except (KeyError, ValueError, IndexError) as e:
            logger.error(f"解析 Embedding API 回應失敗: {e}", exc_info=True)
            raise Exception(f"解析 Embedding API 回應失敗: {e}") from e

    async def generate_embeddings_async(
        self,
        texts: List[str],
        task: str = "text-matching",
        dimensions: int = 1024,
        encoding_type: str = "float",
    ) -> List[List[float]]:
        """生成多個文本的向量嵌入（異步版本）"""
        if not texts:
            logger.warning("輸入文本列表為空")
            return []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url, headers=self.headers, json=self._payload(texts), timeout=120.0
                )
                if not response.is_success:
                    raise Exception(
                        f"Embedding API 請求失敗 - 狀態碼: {response.status_code}, 內容: {response.text}"
                    )

            embeddings = self._parse(response.json())
            logger.info(f"成功生成 {len(embeddings)} 個向量嵌入")
            return embeddings

        except httpx.HTTPError as e:
            logger.error(f"Embedding API HTTP 錯誤: {e}", exc_info=True)
            raise Exception(f"Embedding API HTTP 錯誤: {e}") from e
        except (KeyError, ValueError, IndexError) as e:
            logger.error(f"解析 Embedding API 回應失敗: {e}", exc_info=True)
            raise Exception(f"解析 Embedding API 回應失敗: {e}") from e

    def generate_single_embedding(
        self, text: str, task: str = "text-matching", dimensions: int = 1024
    ) -> List[float]:
        """生成單個文本的向量嵌入（同步版本）"""
        embeddings = self.generate_embeddings([text])
        return embeddings[0] if embeddings else []

    async def generate_single_embedding_async(
        self, text: str, task: str = "text-matching", dimensions: int = 1024
    ) -> List[float]:
        """生成單個文本的向量嵌入（異步版本）"""
        embeddings = await self.generate_embeddings_async([text])
        return embeddings[0] if embeddings else []


# 全域單例
_jina_client: Optional[JinaClient] = None


def get_jina_client(api_key: Optional[str] = None) -> JinaClient:
    """取得 Embedding 客戶端單例"""
    global _jina_client
    if _jina_client is None:
        _jina_client = JinaClient(api_key)
    return _jina_client


async def generate_embedding(text: str, task: str = "text-matching") -> List[float]:
    """便捷函數：生成單個文本的向量嵌入（異步）"""
    try:
        return await get_jina_client().generate_single_embedding_async(text)
    except Exception as e:
        logger.error(f"生成向量嵌入失敗: {e}", exc_info=True)
        raise


def generate_embedding_sync(text: str, task: str = "text-matching") -> List[float]:
    """同步生成單個文字的向量嵌入"""
    try:
        return get_jina_client().generate_single_embedding(text)
    except Exception as e:
        logger.error(f"同步生成向量嵌入失敗: {e}", exc_info=True)
        raise
