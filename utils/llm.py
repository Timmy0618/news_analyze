import os
from langchain_openai import ChatOpenAI


def create_llm(
    base_url: str = None,
    api_key: str = None,
    model: str = None,
    temperature: float = 0.7,
    timeout: int = 120,
) -> ChatOpenAI:
    """
    創建統一的 LLM 實例

    Args:
        base_url: LLM API 的 base URL，如果為 None 則從環境變量 LLM_URL 讀取
        api_key: API key，如果為 None 則從環境變量 token 讀取
        model: 模型名稱，如果為 None 則從環境變量 LLM_MODEL 讀取
        temperature: 溫度參數
        timeout: 超時時間

    Returns:
        ChatOpenAI 實例
    """
    if base_url is None:
        base_url = os.getenv("LLM_URL", "http://localhost:8000/v1")
    if api_key is None:
        api_key = os.getenv("token", "EMPTY")
    if model is None:
        model = os.getenv("LLM_MODEL", "Qwen/Qwen3-4B-Instruct-2507")

    return ChatOpenAI(
        base_url=base_url,
        api_key=api_key,
        model=model,
        temperature=temperature,
        timeout=timeout,
    )