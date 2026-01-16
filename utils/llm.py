import os
from langchain_huggingface import HuggingFaceEndpoint
from transformers import AutoTokenizer


def create_llm(
    base_url: str = None,
    api_key: str = None,
    model: str = None,
    temperature: float = 0.7,
    timeout: int = 120,
) -> HuggingFaceEndpoint:
    """
    創建統一的 LLM 實例

    Args:
        base_url: LLM API 的 base URL（Hugging Face 不使用，保留兼容性）
        api_key: API key，如果為 None 則從環境變量 HF_TOKEN 讀取
        model: 模型名稱，如果為 None 則從環境變量 LLM_MODEL 讀取
        temperature: 溫度參數
        timeout: 超時時間

    Returns:
        HuggingFaceEndpoint 實例
    """
    if api_key is None:
        api_key = os.getenv("HF_TOKEN", "EMPTY")
    if model is None:
        model = os.getenv("LLM_MODEL", "Qwen/Qwen3-4B-Instruct-2507")

    return HuggingFaceEndpoint(
        repo_id=model,
        huggingfacehub_api_token=api_key,
        temperature=temperature,
        timeout=timeout,
    )


def create_tokenizer(model_name: str = None) -> AutoTokenizer:
    """
    創建統一的 tokenizer 實例

    Args:
        model_name: 模型名稱，如果為 None 則從環境變量 LLM_MODEL 讀取

    Returns:
        AutoTokenizer 實例，如果載入失敗則返回 None
    """
    if model_name is None:
        model_name = os.getenv("LLM_MODEL", "Qwen/Qwen3-4B-Instruct-2507")

    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        return tokenizer
    except Exception as e:
        print(f"⚠ tokenizer 載入失敗: {e}，將無法做 token-based 截斷")
        return None