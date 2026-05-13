"""
新聞向量搜尋 Streamlit 應用程式
提供直觀的網頁介面來搜尋新聞文章
"""

import streamlit as st
from datetime import date, datetime
from typing import List, Dict, Optional
import sys
import os
import pandas as pd
import plotly.express as px

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.operations import search_articles_vector, search_articles_keyword, get_articles_by_date, get_articles_by_source, get_topic_statistics
from database.config import get_db
from database.models import NewsArticle
from sqlalchemy import func

def render_article_graph(nodes: list, edges: list, color_map: dict) -> str:
    """Generate pyvis network HTML for embedding in Streamlit."""
    from pyvis.network import Network

    net = Network(height="600px", width="100%", bgcolor="#1a1a2e", font_color="#eeeeee")
    net.set_options("""
    {
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -80,
          "springLength": 150,
          "springConstant": 0.05,
          "damping": 0.4
        },
        "minVelocity": 0.75,
        "solver": "forceAtlas2Based"
      },
      "interaction": {"tooltipDelay": 100, "hideEdgesOnDrag": true}
    }
    """)

    for node in nodes:
        color = color_map.get(node["source_site"], "#95a5a6")
        label = node["title"][:18] + ("…" if len(node["title"]) > 18 else "")
        tooltip = (
            f"<b>{node['title']}</b><br>"
            f"日期：{node['publish_date']}<br>"
            f"來源：{node['source_site']}<br>"
            f"記者：{node['reporter'] or '—'}"
        )
        net.add_node(node["id"], label=label, title=tooltip, color=color, size=12)

    for edge in edges:
        net.add_edge(edge["source"], edge["target"], value=round(edge["weight"], 3), color="#44475a")

    return net.generate_html()


class NewsSearchApp:
    """新聞搜尋應用程式"""

    def __init__(self):
        pass

    def format_articles_for_table(self, articles: List[Dict], show_similarity: bool = False) -> pd.DataFrame:
        """將文章列表格式化為表格顯示"""
        data = []
        for article in articles:
            row = {
                "標題": article["title"],
                "來源": article["source"],
                "發布日期": str(article["publish_date"]),
                "記者": article.get("reporter", ""),
                "摘要": article.get("summary", ""),
                "連結": article["url"]
            }
            if show_similarity:
                row["相關度"] = f"{article['similarity']*100:.1f}%" if article.get("similarity") else "N/A"
            data.append(row)
        
        return pd.DataFrame(data)

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

    def get_articles_browse(self, source: Optional[str] = None,
                           date_from: Optional[date] = None,
                           date_to: Optional[date] = None,
                           limit: int = 50,
                           sort_by: str = "date_desc",
                           offset: int = 0) -> List[Dict]:
        """獲取文章列表用於瀏覽"""
        try:
            db = next(get_db())
            
            query = db.query(NewsArticle)
            
            # 添加過濾條件
            if source:
                query = query.filter(NewsArticle.source_site == source)
            
            if date_from:
                query = query.filter(NewsArticle.publish_date >= date_from)
            
            if date_to:
                query = query.filter(NewsArticle.publish_date <= date_to)
            
            # 排序
            if sort_by == "date_desc":
                query = query.order_by(NewsArticle.publish_date.desc())
            elif sort_by == "date_asc":
                query = query.order_by(NewsArticle.publish_date.asc())
            elif sort_by == "title":
                query = query.order_by(NewsArticle.title)
            
            # 分頁
            articles = query.offset(offset).limit(limit).all()
            db.close()
            
            # 轉換為字典格式
            results = []
            for article in articles:
                results.append({
                    "id": article.id,
                    "title": article.title,
                    "reporter": article.reporter,
                    "summary": article.summary,
                    "url": article.source_url,
                    "source": article.source_site,
                    "publish_date": article.publish_date,
                    "similarity": 1.0  # 瀏覽模式給予滿分相似度
                })
            
            return results
            
        except Exception as e:
            st.error(f"獲取文章列表失敗: {str(e)}")
            return []

    def get_articles_count(self, source: Optional[str] = None,
                          date_from: Optional[date] = None,
                          date_to: Optional[date] = None) -> int:
        """獲取符合條件的文章總數"""
        try:
            db = next(get_db())
            
            query = db.query(func.count(NewsArticle.id))
            
            # 添加過濾條件
            if source:
                query = query.filter(NewsArticle.source_site == source)
            
            if date_from:
                query = query.filter(NewsArticle.publish_date >= date_from)
            
            if date_to:
                query = query.filter(NewsArticle.publish_date <= date_to)
            
            count = query.scalar()
            db.close()
            
            return count or 0
            
        except Exception as e:
            st.error(f"獲取文章數量失敗: {str(e)}")
            return 0

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

    def get_sources(self) -> List[str]:
        """獲取所有新聞來源"""
        try:
            db = next(get_db())
            sources = db.query(NewsArticle.source_site).distinct().all()
            db.close()
            return [s[0] for s in sources if s[0]]
        except Exception:
            return []

    def get_topic_statistics(self, analysis_date: Optional[date] = None, limit: int = 10) -> List[Dict]:
        """獲取主題統計資料"""
        try:
            from database.operations import get_topic_statistics
            statistics = get_topic_statistics(analysis_date=analysis_date, limit=limit)
            
            # 轉換為字典格式
            results = []
            for stat in statistics:
                results.append(stat.to_dict())
            
            return results
        except Exception as e:
            st.error(f"獲取主題統計失敗: {str(e)}")
            return []

def main():
    """主應用程式"""
    st.set_page_config(
        page_title="新聞搜尋與瀏覽系統",
        page_icon="📰",
        layout="wide"
    )

    st.title("📰 新聞搜尋與瀏覽系統")
    
    # 應用說明
    st.info("""
    📋 **應用說明**: 此系統專門收集台灣主要新聞媒體的政治新聞，包括TVBS、三立新聞、中時電子報等來源。
    提供向量語義搜尋、關鍵字搜尋、文章瀏覽以及每日主題統計分析功能。
    
    ⚠️ **重要提醒**: 文章內容和主題統計分析功能均為手動更新，非即時資料。
    """)

    st.markdown("提供向量搜尋、關鍵字搜尋和文章瀏覽功能")

    # 初始化應用程式
    app = NewsSearchApp()

    # 模式選擇
    mode = st.sidebar.radio(
        "選擇模式",
        ["📈 主題統計", "🔍 搜尋模式", "📚 瀏覽模式", "🕸️ 關聯圖譜"],
        help="搜尋模式：使用向量或關鍵字搜尋；瀏覽模式：查看所有文章；主題統計：查看新聞主題分析結果；關聯圖譜：視覺化文章關聯"
    )

    # 側邊欄 - 設定
    with st.sidebar:
        if mode == "🔍 搜尋模式":
            st.header("🔍 搜尋設定")

            # 搜尋類型
            search_type = st.selectbox(
                "搜尋類型",
                options=["vector", "keyword"],
                format_func=lambda x: {
                    "vector": "向量語義搜尋",
                    "keyword": "關鍵字搜尋"
                }[x],
                help="向量搜尋理解語意，關鍵字搜尋精確匹配"
            )

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
            search_button = st.button("🔍 開始搜尋", type="primary", width='stretch')

            # 初始化其他模式變數
            load_stats_button = False
            browse_button = False

        elif mode == "📈 主題統計":
            st.header("📈 主題統計設定")

            # 日期選擇
            selected_date = st.date_input(
                "選擇分析日期",
                value=date.today(),
                help="選擇要查看主題統計的日期"
            )

            # 初始化其他變數以避免UnboundLocalError
            selected_source = None
            date_from = None
            date_to = None
            sort_by = "date_desc"
            page_size = 50
            browse_button = False
            search_button = False

            # 載入按鈕
            load_stats_button = st.button("📊 載入統計", type="primary", width='stretch')

        elif mode == "🕸️ 關聯圖譜":
            st.header("🕸️ 圖譜設定")

            col1, col2 = st.columns(2)
            with col1:
                graph_date_from = st.date_input("開始日期", value=None, key="graph_date_from")
            with col2:
                graph_date_to = st.date_input("結束日期", value=None, key="graph_date_to")

            sources = app.get_sources()
            source_options = ["全部"] + sources
            _graph_source_display = st.selectbox("新聞來源", source_options, key="graph_source")
            graph_source = None if _graph_source_display == "全部" else _graph_source_display

            graph_max_nodes = st.slider("最多節點數", min_value=20, max_value=200, value=100, step=10)

            graph_button = st.button("🕸️ 建立圖譜", type="primary", width="stretch")

            # Initialize vars used by other mode main-content blocks
            search_button = False
            browse_button = False
            load_stats_button = False
            sort_by = "date_desc"
            page_size = 50

        else:  # 瀏覽模式
            st.header("📚 瀏覽設定")

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
                    help="限制瀏覽的開始日期"
                )

            with col2:
                date_to = st.date_input(
                    "結束日期",
                    value=None,
                    help="限制瀏覽的結束日期"
                )

            # 排序方式
            sort_by = st.selectbox(
                "排序方式",
                options=["date_desc", "date_asc", "title"],
                format_func=lambda x: {
                    "date_desc": "日期降序（最新優先）",
                    "date_asc": "日期升序（最舊優先）",
                    "title": "標題字母順序"
                }[x],
                help="選擇文章的排序方式"
            )

            # 每頁顯示數量
            page_size = st.selectbox(
                "每頁顯示數量",
                options=[10, 20, 50, 100],
                index=2,  # 預設 50
                help="選擇每頁顯示的文章數量"
            )

            # 瀏覽按鈕
            browse_button = st.button("📚 開始瀏覽", type="primary", width='stretch')

            # 初始化其他模式變數
            search_button = False
            load_stats_button = False

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
    if mode == "🔍 搜尋模式":
        if search_button and query.strip():
            with st.spinner("🔍 正在搜尋相關新聞..."):
                if search_type == "vector":
                    results = app.search_articles(
                        query=query.strip(),
                        search_field=search_field,
                        top_k=top_k,
                        source=selected_source,
                        date_from=date_from if date_from else None,
                        date_to=date_to if date_to else None
                    )
                else:  # keyword search
                    try:
                        results = {
                            "query": query.strip(),
                            "search_field": search_field,
                            "total": 0,
                            "results": search_articles_keyword(
                                query=query.strip(),
                                search_field=search_field,
                                top_k=top_k,
                                source=selected_source,
                                date_from=date_from if date_from else None,
                                date_to=date_to if date_to else None
                            )
                        }
                        results["total"] = len(results["results"])
                    except Exception as e:
                        results = {
                            "query": query.strip(),
                            "search_field": search_field,
                            "total": 0,
                            "results": [],
                            "error": f"關鍵字搜尋失敗: {str(e)}"
                        }

            if results and results.get("results"):
                # 顯示搜尋摘要
                search_type_name = "向量語義搜尋" if search_type == "vector" else "關鍵字搜尋"
                st.success(f"使用{search_type_name}找到 {results['total']} 筆相關新聞")

                # 轉換為表格格式
                df = app.format_articles_for_table(results["results"], show_similarity=(search_type == "vector"))
                
                # 顯示表格
                st.dataframe(
                    df,
                    column_config={
                        "標題": st.column_config.TextColumn("標題", width="large"),
                        "來源": st.column_config.TextColumn("來源", width="small"),
                        "發布日期": st.column_config.TextColumn("發布日期", width="medium"),
                        "記者": st.column_config.TextColumn("記者", width="medium"),
                        "摘要": st.column_config.TextColumn("摘要", width="large", max_chars=None),
                        "連結": st.column_config.LinkColumn("連結", display_text="閱讀全文"),
                        "相關度": st.column_config.TextColumn("相關度", width="small") if search_type == "vector" else None
                    },
                    hide_index=True,
                    width='stretch'
                )

                # 顯示詳細資訊（可選）
                with st.expander("📋 查看詳細資訊", expanded=False):
                    st.write("點擊表格中的連結可直接閱讀全文文章")
                    if search_type == "vector":
                        st.write("相關度表示文章與搜尋查詢的語意相似度")

            elif results:
                st.warning("沒有找到相關的新聞文章，請嘗試調整搜尋條件")

            else:
                st.error("搜尋失敗，請檢查 API 服務是否正常運行")

        elif search_button and not query.strip():
            st.warning("請輸入搜尋關鍵字")

        else:
            # 搜尋模式歡迎頁面
            st.info("👋 請在左側輸入搜尋條件，開始探索新聞資料庫")

    elif mode == "🕸️ 關聯圖譜":
        if "graph_data" not in st.session_state:
            st.session_state.graph_data = None

        if graph_button:
            with st.spinner("🕸️ 正在計算文章關聯圖譜..."):
                from utils.graph_builder import get_article_graph
                st.session_state.graph_data = get_article_graph(
                    date_from=graph_date_from if graph_date_from else None,
                    date_to=graph_date_to if graph_date_to else None,
                    source_site=graph_source,
                    max_nodes=graph_max_nodes,
                )

        if st.session_state.graph_data:
            nodes = st.session_state.graph_data["nodes"]
            edges = st.session_state.graph_data["edges"]

            if nodes:
                st.success(f"圖譜包含 {len(nodes)} 個節點、{len(edges)} 條連結")

                _palette = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c", "#e67e22", "#34495e"]
                _sources = sorted({n["source_site"] for n in nodes if n["source_site"]})
                _color_map = {s: _palette[i % len(_palette)] for i, s in enumerate(_sources)}

                legend_cols = st.columns(min(len(_sources), 6) or 1)
                for i, src in enumerate(_sources):
                    legend_cols[i % len(legend_cols)].markdown(
                        f"<span style='color:{_color_map[src]};font-size:18px'>■</span> {src}",
                        unsafe_allow_html=True,
                    )

                import streamlit.components.v1 as components
                components.html(render_article_graph(nodes, edges, _color_map), height=650, scrolling=False)

                st.markdown("---")
                st.subheader("📄 文章詳情")
                title_to_node = {n["title"]: n for n in nodes}
                selected = st.selectbox("選擇文章查看詳情", ["（請選擇）"] + list(title_to_node.keys()))
                if selected != "（請選擇）":
                    n = title_to_node[selected]
                    st.markdown(f"**標題** {n['title']}")
                    st.markdown(f"**日期** {n['publish_date']}")
                    st.markdown(f"**來源** {n['source_site']}")
                    st.markdown(f"**記者** {n['reporter'] or '—'}")
                    st.markdown(f"**連結** [{n['url']}]({n['url']})")
            else:
                st.warning("所選條件下沒有包含向量的文章，無法建立圖譜")
        else:
            st.info("👋 請設定條件並點擊「建立圖譜」開始探索文章關聯")

    else:  # 瀏覽模式
        # 初始化 session state 用於分頁
        if 'browse_page' not in st.session_state:
            st.session_state.browse_page = 1
        if 'browse_filters' not in st.session_state:
            st.session_state.browse_filters = {}
        if 'show_browse_results' not in st.session_state:
            st.session_state.show_browse_results = False

        # 檢查篩選條件是否改變
        current_filters = {
            'source': selected_source,
            'date_from': date_from,
            'date_to': date_to,
            'sort_by': sort_by,
            'page_size': page_size
        }
        
        if current_filters != st.session_state.browse_filters:
            st.session_state.browse_page = 1
            st.session_state.browse_filters = current_filters

        # 當點擊瀏覽按鈕時，啟用顯示
        if browse_button:
            st.session_state.show_browse_results = True

        if st.session_state.show_browse_results:
            # 獲取總數量
            total_count = app.get_articles_count(
                source=selected_source,
                date_from=date_from if date_from else None,
                date_to=date_to if date_to else None
            )
            
            # 計算分頁資訊
            total_pages = (total_count + page_size - 1) // page_size
            current_page = st.session_state.browse_page
            
            # 確保當前頁數有效
            if current_page > total_pages and total_pages > 0:
                current_page = total_pages
                st.session_state.browse_page = current_page
            
            # 載入當前頁的文章
            offset = (current_page - 1) * page_size
            articles = app.get_articles_browse(
                source=selected_source,
                date_from=date_from if date_from else None,
                date_to=date_to if date_to else None,
                limit=page_size,
                sort_by=sort_by,
                offset=offset
            )

            if articles:
                st.success(f"載入 {len(articles)} 篇文章 (第 {current_page} 頁，共 {total_pages} 頁，總共 {total_count} 篇)")

                # 轉換為表格格式
                df = app.format_articles_for_table(articles, show_similarity=False)
                
                # 顯示表格
                st.dataframe(
                    df,
                    column_config={
                        "標題": st.column_config.TextColumn("標題", width="large"),
                        "來源": st.column_config.TextColumn("來源", width="small"),
                        "發布日期": st.column_config.TextColumn("發布日期", width="medium"),
                        "記者": st.column_config.TextColumn("記者", width="medium"),
                        "摘要": st.column_config.TextColumn("摘要", width="large", max_chars=None),
                        "連結": st.column_config.LinkColumn("連結", display_text="閱讀全文")
                    },
                    hide_index=True,
                    width='stretch'
                )

                # 分頁控制（底部）
                st.markdown("---")
                col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
                
                with col1:
                    if st.button("⏮️ 第一頁", disabled=(current_page == 1), width='stretch'):
                        st.session_state.browse_page = 1
                        st.rerun()
                
                with col2:
                    if st.button("⬅️ 上一頁", disabled=(current_page == 1), width='stretch'):
                        st.session_state.browse_page -= 1
                        st.rerun()
                
                with col3:
                    st.markdown(f"<center><strong>第 {current_page} 頁 / 共 {total_pages} 頁</strong></center>", unsafe_allow_html=True)
                
                with col4:
                    if st.button("下一頁 ➡️", disabled=(current_page == total_pages), width='stretch'):
                        st.session_state.browse_page += 1
                        st.rerun()
                
                with col5:
                    if st.button("最後頁 ⏭️", disabled=(current_page == total_pages), width='stretch'):
                        st.session_state.browse_page = total_pages
                        st.rerun()

            else:
                st.warning("沒有找到符合條件的文章")

        elif mode == "📈 主題統計":
            if load_stats_button:
                with st.spinner("📊 正在載入主題統計..."):
                    statistics = app.get_topic_statistics(analysis_date=selected_date)
                    
                    if statistics:
                        stat = statistics[0]  # 應該只有一筆該日期的統計
                        
                        # 顯示統計摘要
                        st.success(f"找到 {selected_date} 的主題統計資料")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("總文章數", stat["total_articles"])
                        with col2:
                            st.metric("主題數量", len(stat["topics_data"]))
                        
                        # 顯示主題列表
                        topics = stat["topics_data"]
                        if topics:
                            st.subheader("🏷️ 熱門主題排行")
                            
                            # 轉換為表格格式
                            topics_data = []
                            for topic in topics:
                                topics_data.append({
                                    "排名": f"#{topic['rank']}",
                                    "主題名稱": topic['name'],
                                    "描述": topic['description'],
                                    "相關文章數": f"{topic['article_count']}篇"
                                })
                            
                            topics_df = pd.DataFrame(topics_data)
                            
                            # 顯示表格
                            st.dataframe(
                                topics_df,
                                column_config={
                                    "排名": st.column_config.TextColumn("排名", width="small"),
                                    "主題名稱": st.column_config.TextColumn("主題名稱", width="large"),
                                    "描述": st.column_config.TextColumn("描述", width="large"),
                                    "相關文章數": st.column_config.TextColumn("相關文章數", width="medium")
                                },
                                hide_index=True,
                                width='stretch'
                            )
                            
                            # 創建氣泡圖顯示主題重要度
                            st.subheader("📊 主題重要度視覺化")
                            
                            # 準備氣泡圖數據
                            bubble_data = []
                            for i, topic in enumerate(topics):
                                bubble_data.append({
                                    '主題': topic['name'],
                                    '排名': topic['rank'],
                                    '文章數量': topic['article_count'],
                                    '描述': topic['description'][:50] + '...' if len(topic['description']) > 50 else topic['description']
                                })
                            
                            bubble_df = pd.DataFrame(bubble_data)
                            
                            # 創建氣泡圖
                            fig = px.scatter(
                                bubble_df, 
                                x='排名', 
                                y='主題',
                                size='文章數量',
                                color='文章數量',
                                hover_name='主題',
                                hover_data=['描述', '文章數量'],
                                title='主題重要度氣泡圖 (氣泡大小表示相關文章數量)',
                                size_max=50,
                                color_continuous_scale='Blues'
                            )
                            
                            # 調整圖表佈局
                            fig.update_layout(
                                xaxis=dict(tickmode='linear', tick0=1, dtick=1),
                                yaxis=dict(autorange="reversed"),  # 排名1在上面
                                height=400
                            )
                            
                            # 顯示圖表
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.warning("該日期沒有主題分析資料")
                    else:
                        st.warning(f"沒有找到 {selected_date} 的主題統計資料")
                        
                        # 提供執行分析的建議
                        st.info("💡 提示：您可以使用命令列工具執行分析：")
                        st.code(f"python analyze_news_topics.py {selected_date}")
            else:
                st.info("👋 請選擇日期並點擊「載入統計」來查看主題分析結果")

        else:
            # 搜尋模式歡迎頁面
            st.info("👋 請在左側輸入搜尋條件，開始尋找相關新聞")

        # 功能介紹
        st.header("✨ 功能特色")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.subheader("🔍 向量語義搜尋")
            st.write("使用向量相似度進行智慧搜尋，理解語意而非僅匹配關鍵字")

        with col2:
            st.subheader("🔎 關鍵字搜尋")
            st.write("傳統的精確關鍵字匹配搜尋，適合查找特定詞彙")

        with col3:
            st.subheader("📚 文章瀏覽")
            st.write("瀏覽所有文章，按日期或標題排序，方便隨機瀏覽")

        with col4:
            st.subheader("📈 主題統計")
            st.write("查看每日新聞主題分析，了解熱門討論話題")

        # 使用說明
        st.header("📖 使用說明")
        st.markdown("""
        ### 搜尋模式
        1. **選擇搜尋類型**: 向量搜尋（理解語意）或關鍵字搜尋（精確匹配）
        2. **輸入關鍵字**: 在搜尋框中輸入您想找的新聞主題
        3. **選擇範圍**: 決定要在標題、摘要還是兩者中搜尋
        4. **設定條件**: 可選的來源和日期篩選
        5. **查看結果**: 系統會顯示最相關的新聞，按相似度排序

        ### 瀏覽模式
        1. **設定篩選**: 選擇新聞來源和日期範圍
        2. **選擇排序**: 按日期或標題排序
        3. **設定數量**: 決定要顯示多少篇文章
        4. **瀏覽文章**: 查看文章列表，展開摘要，點擊連結閱讀全文

        ### 主題統計模式
        1. **選擇日期**: 選擇要查看主題統計的日期
        2. **載入統計**: 點擊按鈕載入該日期的主題分析結果
        3. **查看主題**: 瀏覽熱門主題排行和相關描述
        4. **執行分析**: 如果沒有資料，可以使用命令列工具生成分析
        """)

if __name__ == "__main__":
    main()