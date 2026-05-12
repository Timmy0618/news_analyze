import os
from typing import Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# 加載 .env 文件
load_dotenv()


def create_llm(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
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
        api_key = os.getenv("OPENAPI_KEY", "EMPTY")
    if model is None:
        model = os.getenv("LLM_MODEL", "Qwen/Qwen3-4B-Instruct-2507")
    return ChatOpenAI(
        base_url=base_url,
        api_key=api_key,
        model=model,
        temperature=temperature,
        timeout=timeout,
    )


if __name__ == "__main__":
    # 測試 LLM 連接
    print("正在測試 LLM 連接...")
    llm = create_llm()
    print(f"使用模型: {llm.model_name}")
    print(f"Base URL: {llm.openai_api_base}")
    
    # 發送測試請求
    try:
        response = llm.invoke("你好，請用一句話介紹你自己")
        print(f"\n測試成功！回應: {response.content}")
    except Exception as e:
        print(f"\n測試失敗: {e}")