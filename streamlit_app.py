"""
新聞向量搜尋 Streamlit 應用程式
提供直觀的網頁介面來搜尋新聞文章
"""

import streamlit as st
from datetime import date, datetime
from typing import List, Dict, Optional
import sys
import os

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.operations import search_articles_vector, search_articles_keyword
from database.config import get_db
from database.models import NewsArticle
from sqlalchemy import func

class NewsSearchApp:
    """新聞搜尋應用程式"""

    def __init__(self):
        pass

    def search_articles(self, query: str, search_field: str = "both",
                       top_k: int = 10, source: Optional[str] = None,
                       date_from: Optional[date] = None,
                       date_to: Optional[date] = None) -> Dict:
        """直接呼叫資料庫搜尋函數"""
        try:
            # 優先使用向量搜尋
            results = search_articles_vector(
                query=query,
                search_field=search_field,
                top_k=top_k,
                source=source,
                date_from=date_from,
                date_to=date_to
            )
            
            return {
                "query": query,
                "search_field": search_field,
                "total": len(results),
                "results": results
            }
        except Exception as e:
            # 如果向量搜尋失敗，使用關鍵字搜尋作為後備
            st.warning(f"向量搜尋失敗，使用關鍵字搜尋: {str(e)}")
            try:
                results = search_articles_keyword(
                    query=query,
                    search_field=search_field,
                    top_k=top_k,
                    source=source,
                    date_from=date_from,
                    date_to=date_to
                )
                
                return {
                    "query": query,
                    "search_field": search_field,
                    "total": len(results),
                    "results": results
                }
            except Exception as e2:
                return {
                    "query": query,
                    "search_field": search_field,
                    "total": 0,
                    "results": [],
                    "error": f"搜尋失敗: {str(e2)}"
                }

    def get_sources(self) -> List[str]:
        """獲取所有新聞來源"""
        try:
            db = next(get_db())
            sources = db.query(NewsArticle.source_site).distinct().all()
            db.close()
            return [s[0] for s in sources if s[0]]
        except Exception:
            return []

    def get_stats(self) -> Dict:
        """獲取資料庫統計"""
        try:
            db = next(get_db())
            total_articles = db.query(func.count(NewsArticle.id)).scalar()
            
            embedded_articles = db.query(func.count(NewsArticle.id)).filter(
                NewsArticle.title_embedding.isnot(None),
                NewsArticle.summary_embedding.isnot(None)
            ).scalar()
            
            sources_count = db.query(func.count(func.distinct(NewsArticle.source_site))).scalar()
            
            date_range = db.query(
                func.min(NewsArticle.publish_date),
                func.max(NewsArticle.publish_date)
            ).first()
            
            db.close()
            
            return {
                "total_articles": total_articles or 0,
                "embedded_articles": embedded_articles or 0,
                "embedding_coverage": (embedded_articles / total_articles * 100) if total_articles > 0 else 0,
                "sources_count": sources_count or 0,
                "date_range": {
                    "min": date_range[0].isoformat() if date_range[0] else None,
                    "max": date_range[1].isoformat() if date_range[1] else None
                }
            }
        except Exception:
            return {
                "total_articles": 0,
                "embedded_articles": 0,
                "embedding_coverage": 0,
                "sources_count": 0,
                "date_range": {"min": None, "max": None}
            }

def main():
    """主應用程式"""
    st.set_page_config(
        page_title="新聞向量搜尋",
        page_icon="📰",
        layout="wide"
    )

    st.title("📰 新聞向量搜尋系統")
    st.markdown("使用語義搜尋快速找到相關的新聞文章")

    # 初始化應用程式
    app = NewsSearchApp()

    # 側邊欄 - 搜尋設定
    with st.sidebar:
        st.header("🔍 搜尋設定")

        # 搜尋查詢
        query = st.text_input(
            "搜尋關鍵字",
            placeholder="輸入要搜尋的新聞內容...",
            help="支援自然語言搜尋，如：'台灣政治'、'中美關係'等"
        )

        # 搜尋欄位
        search_field = st.selectbox(
            "搜尋範圍",
            options=["both", "title", "summary"],
            format_func=lambda x: {
                "both": "標題+摘要",
                "title": "僅標題",
                "summary": "僅摘要"
            }[x],
            help="選擇要在哪些欄位中進行搜尋"
        )

        # 結果數量
        top_k = st.slider(
            "顯示結果數量",
            min_value=1,
            max_value=50,
            value=10,
            help="最多顯示多少筆搜尋結果"
        )

        # 來源過濾
        sources = app.get_sources()
        source_options = ["全部"] + sources
        selected_source_display = st.selectbox(
            "新聞來源",
            options=source_options,
            help="選擇特定的新聞來源"
        )
        selected_source = None if selected_source_display == "全部" else selected_source_display

        # 日期範圍
        st.subheader("📅 日期範圍")
        col1, col2 = st.columns(2)

        with col1:
            date_from = st.date_input(
                "開始日期",
                value=None,
                help="限制搜尋的開始日期"
            )

        with col2:
            date_to = st.date_input(
                "結束日期",
                value=None,
                help="限制搜尋的結束日期"
            )

        # 搜尋按鈕
        search_button = st.button("🔍 開始搜尋", type="primary", use_container_width=True)

        # 統計資訊
        st.header("📊 資料庫統計")
        stats = app.get_stats()
        if stats:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("總文章數", stats.get("total_articles", 0))
                st.metric("嵌入文章數", stats.get("embedded_articles", 0))
            with col2:
                coverage = f"{stats.get('embedding_coverage', 0):.1f}%"
                st.metric("嵌入覆蓋率", coverage)
                st.metric("來源數量", stats.get("sources_count", 0))

            date_range = stats.get("date_range", {})
            if date_range.get("min") and date_range.get("max"):
                st.caption(f"日期範圍: {date_range['min']} ~ {date_range['max']}")

    # 主內容區域
    if search_button and query.strip():
        with st.spinner("🔍 正在搜尋相關新聞..."):
            results = app.search_articles(
                query=query.strip(),
                search_field=search_field,
                top_k=top_k,
                source=selected_source,
                date_from=date_from if date_from else None,
                date_to=date_to if date_to else None
            )

        if results and results.get("results"):
            # 顯示搜尋摘要
            st.success(f"找到 {results['total']} 筆相關新聞")

            # 顯示搜尋結果
            for i, article in enumerate(results["results"], 1):
                with st.container():
                    # 文章標題和來源
                    col1, col2, col3 = st.columns([3, 1, 1])

                    with col1:
                        st.subheader(f"{i}. {article['title']}")

                    with col2:
                        st.caption(f"來源: {article['source']}")

                    with col3:
                        similarity_pct = f"{article['similarity']*100:.1f}%"
                        st.caption(f"相關度: {similarity_pct}")

                    # 發布日期
                    st.caption(f"📅 發布日期: {article['publish_date']}")

                    # 記者資訊
                    if article.get('reporter'):
                        st.caption(f"👤 記者: {article['reporter']}")

                    # 摘要
                    if article.get('summary'):
                        with st.expander("📝 查看摘要", expanded=False):
                            st.write(article['summary'])

                    # 文章連結
                    st.markdown(f"[🔗 閱讀全文]({article['url']})")

                    # 分隔線
                    st.divider()

        elif results:
            st.warning("沒有找到相關的新聞文章，請嘗試調整搜尋條件")

        else:
            st.error("搜尋失敗，請檢查 API 服務是否正常運行")

    elif search_button and not query.strip():
        st.warning("請輸入搜尋關鍵字")

    else:
        # 歡迎頁面
        st.info("👋 請在左側輸入搜尋條件，開始探索新聞資料庫")

        # 功能介紹
        st.header("✨ 功能特色")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("🔍 語義搜尋")
            st.write("使用向量相似度進行智慧搜尋，不僅匹配關鍵字，還理解語意")

        with col2:
            st.subheader("📊 多元篩選")
            st.write("支援來源、日期範圍等多重篩選條件")

        with col3:
            st.subheader("📈 相關度排序")
            st.write("結果按相關度排序，幫助您快速找到最相關的內容")

        # 使用說明
        st.header("📖 使用說明")
        st.markdown("""
        1. **輸入關鍵字**: 在搜尋框中輸入您想找的新聞主題
        2. **選擇範圍**: 決定要在標題、摘要還是兩者中搜尋
        3. **設定條件**: 可選的來源和日期篩選
        4. **查看結果**: 系統會顯示最相關的新聞，按相似度排序
        """)

if __name__ == "__main__":
    main()