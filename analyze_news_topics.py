import json
import sys
import os
from datetime import datetime, date
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
from langchain_openai import ChatOpenAI

from database.config import get_db
from database.models import NewsArticle
from database.operations import save_topic_statistics
from utils.jina_client import JinaClient


def _extract_json_object(text: str) -> str:
    """
    從一段文字中，擷取第一個 '{' 到最後一個 '}' 之間的內容。
    若找不到，直接回傳原字串。
    """
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1].strip()
    return text.strip()


def _validate_keywords_schema(obj: Any) -> Tuple[bool, str]:
    """
    驗證回傳 JSON 是否符合預期 schema
    """
    if not isinstance(obj, dict):
        return False, "root is not a JSON object"
    if "keywords" not in obj or not isinstance(obj["keywords"], list):
        return False, "`keywords` missing or not a list"
    for i, kw in enumerate(obj["keywords"]):
        if not isinstance(kw, dict):
            return False, f"keywords[{i}] is not an object"
        if "name" not in kw or "description" not in kw:
            return False, f"keywords[{i}] missing name/description"
        if not isinstance(kw["name"], str) or not isinstance(kw["description"], str):
            return False, f"keywords[{i}] name/description must be string"
    return True, ""


def get_news_titles_by_date(target_date: date) -> List[str]:
    """
    從資料庫獲取指定日期的所有新聞標題

    Args:
        target_date: 目標日期

    Returns:
        新聞標題列表
    """
    db: Session = next(get_db())

    try:
        # 查詢指定日期的新聞
        articles = db.query(NewsArticle).filter(
            NewsArticle.publish_date == target_date
        ).all()

        titles = [article.title for article in articles]

        print(f"找到 {len(titles)} 篇新聞於 {target_date}")
        return titles

    except Exception as e:
        print(f"查詢資料庫失敗: {str(e)}")
        return []
    finally:
        db.close()


def analyze_topics_with_llm(titles: List[str]) -> dict:
    """
    直接讓 LLM 分析所有新聞標題，找出熱門關鍵字（只輸出關鍵字和描述）
    """
    if not titles:
        return {"error": "沒有新聞標題可以分析"}

    titles_text = "\n".join(f"- {title}" for title in titles)

    prompt = f"""你是新聞分析專家。以下是今天的 {len(titles)} 則新聞標題：

{titles_text}

請分析這些標題，找出最常被討論的熱門關鍵字或主題（約10-15個）。
關鍵字可以是人名、事件名稱、政策、議題等。

嚴格要求：
1) 只能輸出「一個」JSON物件（不要Markdown，不要多餘文字）
2) 字串只能使用雙引號
3) keywords 必須是陣列，元素必須包含 name 與 description

請輸出：
{{
  "keywords": [
    {{"name": "關鍵字1", "description": "簡短說明"}},
    {{"name": "關鍵字2", "description": "簡短說明"}}
  ]
}}
"""

    llm_url = os.getenv("LLM_URL", "http://localhost:8000/v1")
    model_name = os.getenv("LLM_MODEL", "Qwen/Qwen3-4B-Instruct-2507")

    llm = ChatOpenAI(
        base_url=llm_url,
        api_key=os.getenv("token", "EMPTY"),
        model=model_name,
        temperature=0,
        timeout=120,
    )

    def _clean_content(raw: str) -> str:
        content = raw.strip()

        # 移除 markdown code fence
        if "```" in content:
            # 優先找 ```json
            if "```json" in content:
                content = content.split("```json", 1)[1]
                content = content.split("```", 1)[0]
            else:
                # 一般 fence
                parts = content.split("```")
                if len(parts) >= 3:
                    content = parts[1]
        content = content.strip()

        # 移除 </think>（Qwen 常見）
        if "</think>" in content:
            content = content.split("</think>", 1)[1].strip()

        # 擷取 JSON 主體
        content = _extract_json_object(content)
        return content

    def _fix_json_with_llm(broken_json: str) -> str:
        """用 LLM 修復錯誤的 JSON"""
        fix_prompt = f"""以下是一個錯誤的 JSON 字串，請修復它，讓它成為正確的 JSON 格式：

{broken_json}

請只輸出修復後的 JSON，不要任何其他文字。"""

        try:
            fix_response = llm.invoke(fix_prompt)
            fixed_content = _clean_content(fix_response.content)
            return fixed_content
        except Exception:
            return broken_json  # 如果修復失敗，返回原內容

    # 嘗試一次，如果失敗就用 LLM 修復
    try:
        print("正在讓 LLM 分析熱門關鍵字...")
        response = llm.invoke(prompt)
        content = _clean_content(response.content)

        result = json.loads(content)
        ok, reason = _validate_keywords_schema(result)
        if not ok:
            raise ValueError(f"schema invalid: {reason}")

        return result

    except json.JSONDecodeError as json_err:
        print(f"JSON 解析失敗: {json_err}")
        # 嘗試用 LLM 修復 JSON
        print("嘗試用 LLM 修復 JSON...")
        try:
            fixed_content = _fix_json_with_llm(content)
            result = json.loads(fixed_content)
            ok, reason = _validate_keywords_schema(result)
            if ok:
                print("JSON 修復成功！")
                return result
            else:
                print(f"修復後 schema 仍無效: {reason}")
        except Exception as fix_err:
            print(f"JSON 修復失敗: {fix_err}")
        
        # 最終失敗：保留 content 方便你 log
        try:
            print(f"原始回應（清理後）: {content}")
        except Exception:
            pass
        return {"error": "LLM 回應格式錯誤"}
    except Exception as e:
        print(f"LLM 回應解析失敗: {e}")
        # 最終失敗：保留 content 方便你 log
        try:
            print(f"原始回應（清理後）: {content}")
        except Exception:
            pass
        return {"error": "LLM 回應格式錯誤"}


def count_related_articles_by_vector(
    keyword: str,
    target_date: date,
    similarity_threshold: float = 0.3
) -> int:
    """
    使用向量搜尋計算與關鍵字相關的文章數量（相似度 > threshold）
    同時比較標題和摘要的相似度，取平均值

    Args:
        keyword: 關鍵字
        target_date: 目標日期
        similarity_threshold: 相似度閾值（預設 0.3）

    Returns:
        相關文章數量
    """
    db: Session = next(get_db())
    
    try:
        # 生成關鍵字的向量
        jina_client = JinaClient()
        embeddings = jina_client.generate_embeddings([keyword], task="text-matching")
        
        if not embeddings:
            return 0
        
        query_embedding = embeddings[0]
        # 統一使用和 search_articles_vector 相同的方式
        query_embedding_str = str(query_embedding)
        
        # 固定使用標題和摘要的平均相似度
        similarity_condition = """
            (
                (1 - (title_embedding <=> CAST(:query_embedding AS vector))) +
                (1 - (summary_embedding <=> CAST(:query_embedding AS vector)))
            ) / 2 > :threshold
        """
        
        # 查詢相似度 > threshold 的文章數量
        query_sql = f"""
            SELECT COUNT(*) as count
            FROM news_articles
            WHERE title_embedding IS NOT NULL
              AND summary_embedding IS NOT NULL
              AND publish_date = :target_date
              AND {similarity_condition}
        """
        
        result = db.execute(text(query_sql), {
            "query_embedding": query_embedding_str,
            "target_date": target_date,
            "threshold": similarity_threshold
        })
        
        row = result.fetchone()
        count = row.count if row else 0
        
        # 添加調試信息
        print(f"  關鍵字 '{keyword}' (both, threshold={similarity_threshold}): {count} 篇相關文章")
        
        return count
        
    except Exception as e:
        print(f"向量搜尋失敗 ({keyword}): {str(e)}")
        return 0
    finally:
        db.close()


def analyze_and_rank_keywords(
    keywords_data: Dict,
    target_date: date,
    similarity_threshold: float = 0.5
) -> Dict:
    """
    對 LLM 輸出的關鍵字進行向量搜尋，計算文章數量並排序

    Args:
        keywords_data: LLM 輸出的關鍵字資料
        target_date: 目標日期
        similarity_threshold: 相似度閾值

    Returns:
        排序後的主題統計資料
    """
    if "error" in keywords_data or "keywords" not in keywords_data:
        return keywords_data
    
    keywords = keywords_data["keywords"]
    print(f"\n正在用向量搜尋計算 {len(keywords)} 個關鍵字的相關文章數量...")
    
    # 計算每個關鍵字的相關文章數量
    results = []
    for kw in keywords:
        name = kw.get("name", "")
        description = kw.get("description", "")
        
        count = count_related_articles_by_vector(name, target_date, similarity_threshold)
        print(f"  - {name}: {count} 篇相關文章")
        
        results.append({
            "name": name,
            "description": description,
            "article_count": count
        })
    
    # 按 article_count 排序（降序）
    results.sort(key=lambda x: x["article_count"], reverse=True)
    
    # 只取前10名並加上排名
    top_10 = results[:10]
    for idx, item in enumerate(top_10, 1):
        item["rank"] = idx
    
    return {"topics": top_10}


def main():
    """主函數"""
    if len(sys.argv) != 2:
        print("使用方法: python analyze_news_topics.py YYYY-MM-DD")
        print("例如: python analyze_news_topics.py 2024-01-10")
        sys.exit(1)

    # 解析日期參數
    date_str = sys.argv[1]
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        print(f"日期格式錯誤: {date_str}，請使用 YYYY-MM-DD 格式")
        sys.exit(1)

    print(f"分析日期: {target_date}")
    print("=" * 50)

    # 獲取新聞標題
    titles = get_news_titles_by_date(target_date)

    if not titles:
        print("沒有找到新聞，程式結束")
        sys.exit(0)

    # 第一步：讓 LLM 分析關鍵字
    keywords_result = analyze_topics_with_llm(titles)

    if "error" in keywords_result:
        print(f"\n⚠ 分析失敗: {keywords_result['error']}")
        sys.exit(1)

    # 第二步：用向量搜尋計算文章數量並排序
    analysis_result = analyze_and_rank_keywords(keywords_result, target_date)

    print("\n分析結果:")
    print("=" * 50)
    
    # 漂亮打印JSON
    print(json.dumps(analysis_result, ensure_ascii=False, indent=2))

    # 如果分析成功，將結果儲存到資料庫
    if "error" not in analysis_result and "topics" in analysis_result:
        try:
            success = save_topic_statistics(
                analysis_date=target_date,
                total_articles=len(titles),
                topics_data=analysis_result["topics"]  # 建議直接存 list
            )
            if success:
                print(f"\n✓ 分析結果已儲存到資料庫")
            else:
                print(f"\n✗ 儲存分析結果到資料庫失敗")
        except Exception as e:
            print(f"\n✗ 儲存分析結果時發生錯誤: {str(e)}")
    else:
        print(f"\n⚠ 分析失敗，跳過資料庫儲存")


if __name__ == "__main__":
    main()