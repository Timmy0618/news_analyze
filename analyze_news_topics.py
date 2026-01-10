"""
新聞主題分析腳本
從指定日期的新聞標題中提取前10個討論主題
"""

import json
import sys
from datetime import datetime, date
from typing import List
import requests
from sqlalchemy.orm import Session

from database.config import get_db
from database.models import NewsArticle
from database.operations import save_topic_statistics


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
    使用LLM分析新聞標題中的主題

    Args:
        titles: 新聞標題列表

    Returns:
        包含主題分析的字典
    """
    if not titles:
        return {"error": "沒有新聞標題可以分析"}

    # 構建提示詞
    titles_text = "\n".join(f"- {title}" for title in titles)

    prompt = f"""
請分析以下新聞標題，找出前10個最熱門的討論主題。
請按照重要性和出現頻率排序。

新聞標題列表：
{titles_text}

請以JSON格式輸出，格式如下：
{{
  "topics": [
    {{
      "rank": 1,
      "name": "主題名稱",
      "description": "簡短描述",
      "article_count": 5
    }},
    {{
      "rank": 2,
      "name": "主題名稱", 
      "description": "簡短描述",
      "article_count": 3
    }}
  ]
}}

只輸出JSON，不要其他文字。
"""

    # 調用vLLM API
    api_url = "http://localhost:8000/v1/chat/completions"

    payload = {
        "model": "Qwen/Qwen3-4B-Instruct-2507",  # 根據實際模型調整
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,  # 較低的temperature以獲得更一致的結果
    }

    try:
        print("正在調用LLM分析主題...")
        response = requests.post(
            api_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=120
        )

        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            # 嘗試解析JSON
            try:
                parsed_result = json.loads(content.strip())
                return parsed_result
            except json.JSONDecodeError as e:
                return {
                    "error": f"LLM返回的內容不是有效的JSON: {str(e)}",
                    "raw_content": content
                }
        else:
            return {
                "error": f"API調用失敗: {response.status_code}",
                "response_text": response.text
            }

    except requests.exceptions.RequestException as e:
        return {"error": f"網路請求失敗: {str(e)}"}
    except Exception as e:
        return {"error": f"分析失敗: {str(e)}"}


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

    # 分析主題
    analysis_result = analyze_topics_with_llm(titles)

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
                topics_data=analysis_result
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