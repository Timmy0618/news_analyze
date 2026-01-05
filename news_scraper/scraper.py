"""
通用新聞爬蟲類別
支援多種新聞網站的爬取和分析
"""

import requests
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from langchain_openai import ChatOpenAI
import json


class NewsScraperConfig:
    """新聞爬蟲配置類"""
    
    def __init__(
        self,
        base_url: str,
        list_tags: List[str],
        article_tags: List[str],
        date_pattern: str,
        category_pattern: str,
        link_pattern: str,
        target_category: Optional[str] = None,
    ):
        """
        初始化爬蟲配置
        
        Args:
            base_url: 新聞列表頁的基礎 URL
            list_tags: 新聞列表頁要抓取的 HTML 標籤
            article_tags: 文章頁要抓取的 HTML 標籤
            date_pattern: 日期的正則表達式（使用 {date} 作為佔位符）
            category_pattern: 類別的正則表達式
            link_pattern: 連結的正則表達式（需包含兩個群組：標題和連結）
            target_category: 目標類別（如 "政治"），None 表示不過濾
        """
        self.base_url = base_url
        self.list_tags = list_tags
        self.article_tags = article_tags
        self.date_pattern = date_pattern
        self.category_pattern = category_pattern
        self.link_pattern = link_pattern
        self.target_category = target_category


class NewsScraper:
    """通用新聞爬蟲類"""
    
    def __init__(
        self,
        config: NewsScraperConfig,
        firecrawl_url: str = "http://localhost:3002",
        llm_url: str = "http://localhost:8000/v1",
        model_name: str = "Qwen/Qwen3-4B-Instruct-2507",
    ):
        """
        初始化爬蟲
        
        Args:
            config: 網站配置
            firecrawl_url: Firecrawl API 的 URL
            llm_url: LLM API 的 URL
            model_name: 使用的模型名稱
        """
        self.config = config
        self.firecrawl_url = firecrawl_url
        self.llm = ChatOpenAI(
            base_url=llm_url,
            api_key="EMPTY",
            model=model_name,
            temperature=0.7,
        )
    
    def scrape_page(self, url: str, tags: List[str]) -> str:
        """
        抓取單一頁面
        
        Args:
            url: 要抓取的 URL
            tags: 要抓取的 HTML 標籤列表
            
        Returns:
            頁面的 Markdown 內容
        """
        try:
            scrape_config = {
                "url": url,
                "formats": ["markdown"],
                "includeTags": tags,
                "onlyMainContent": False
            }
            
            response = requests.post(
                f"{self.firecrawl_url}/v2/scrape",
                json=scrape_config,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            data = response.json()
            
            if "data" in data and "markdown" in data["data"]:
                return data["data"]["markdown"]
            return ""
        except Exception as e:
            print(f"  抓取錯誤: {e}")
            return ""
    
    def extract_news_links(
        self, 
        content: str, 
        date_str: str
    ) -> List[Tuple[str, str]]:
        """
        從內容中提取新聞連結
        
        Args:
            content: 頁面內容
            date_str: 目標日期字串（如 "2026/01/04"）
            
        Returns:
            [(標題, 連結), ...] 的列表
        """
        links = []
        date_pattern = self.config.date_pattern.format(date=date_str)
        date_positions = [(m.start(), m.group()) for m in re.finditer(date_pattern, content)]
        
        for pos, date_text in date_positions:
            before_context = content[max(0, pos-500):pos]
            
            # 檢查類別（如果有指定）
            if self.config.target_category:
                category_match = re.search(self.config.category_pattern, before_context)
                if not category_match or category_match.group(1) != self.config.target_category:
                    continue
                
                category_pos = before_context.rfind(f'[{self.config.target_category}]')
                if category_pos == -1:
                    continue
                title_context = before_context[:category_pos]
            else:
                title_context = before_context
            
            # 提取連結
            found_links = re.findall(self.config.link_pattern, title_context, re.IGNORECASE)
            if found_links:
                title, link = found_links[-1]
                links.append((title.strip(), link))
        
        return links
    
    def extract_article_info(self, content: str) -> Tuple[str, str]:
        """
        使用 LLM 提取記者和大綱
        
        Args:
            content: 文章內容
            
        Returns:
            (記者, 大綱) 的元組
        """
        extract_query = f"""從以下新聞內容提取兩項資訊：

內容：
{content[:1500]}

任務：
1. 找出記者署名（格式：政治中心／綜合報導、記者XXX／台北報導、XXX／報導等）
2. 整理新聞內容大綱（3-5個重點，每個重點一句話）

請用以下格式回答：
記者：XXX
大綱：
- 重點1
- 重點2
- 重點3"""

        try:
            response = self.llm.invoke(extract_query)
            result_text = response.content.strip()
            
            # 解析記者
            reporter = "未提及"
            reporter_match = re.search(r'記者[：:]\s*(.+?)(?:\n|$)', result_text)
            if reporter_match:
                reporter = reporter_match.group(1).strip()
                if len(reporter) > 20:
                    match = re.search(r'(政治中心|國際中心|生活中心|社會中心|記者\s*[：:]?\s*)?([^\s\/]{2,5})', reporter)
                    if match:
                        reporter = match.group(2) if match.group(2) else match.group(1)
                    else:
                        reporter = "未提及"
            
            # 解析大綱
            summary = ""
            summary_match = re.search(r'大綱[：:]\s*(.+)', result_text, re.DOTALL)
            if summary_match:
                summary = summary_match.group(1).strip()
            
            return reporter, summary
        except Exception as e:
            print(f"  LLM 提取錯誤: {e}")
            return "未提及", ""
    
    def scrape_news(
        self,
        target_date: Optional[datetime] = None,
        num_pages: int = 10,
        max_articles: int = 15,
        output_file: str = "news_result.json"
    ) -> Dict:
        """
        執行完整的新聞爬蟲流程
        
        Args:
            target_date: 目標日期（None 表示昨天）
            num_pages: 要抓取的分頁數量
            max_articles: 最多處理的文章數量
            output_file: 輸出檔案名稱
            
        Returns:
            包含所有文章資料的字典
        """
        if target_date is None:
            target_date = datetime.now() - timedelta(days=1)
        
        date_str = target_date.strftime("%m/%d")
        date_str_full = target_date.strftime("%Y/%m/%d")
        
        print("="*80)
        print(f"步驟 1: 抓取新聞列表 (日期: {date_str_full})")
        print("="*80)
        
        all_links = []
        
        # 抓取多個分頁
        for page in range(1, num_pages + 1):
            page_url = f"{self.config.base_url}&p={page}"
            print(f"\n正在抓取第 {page} 頁: {page_url}")
            
            raw_content = self.scrape_page(page_url, self.config.list_tags)
            print(f"  抓取到內容長度: {len(raw_content)} 字元")
            
            page_links = self.extract_news_links(raw_content, date_str_full)
            all_links.extend(page_links)
            
            print(f"  本頁找到 {len(page_links)} 個新聞")
        
        # 去重
        seen_links = set()
        unique_links = []
        for title, link in all_links:
            if link not in seen_links:
                seen_links.add(link)
                unique_links.append((title, link))
        
        print(f"\n總共找到 {len(unique_links)} 個新聞連結")
        
        # 抓取文章內容
        print("\n" + "="*80)
        print("步驟 2: 抓取文章並提取資訊")
        print("="*80)
        
        articles_data = []
        for i, (title, link) in enumerate(unique_links[:max_articles], 1):
            print(f"\n處理 {i}/{min(len(unique_links), max_articles)}: {link}")
            print(f"  標題: {title}")
            
            article_content = self.scrape_page(link, self.config.article_tags)
            reporter, summary = self.extract_article_info(article_content[:2000])
            
            articles_data.append({
                "標題": title,
                "記者": reporter,
                "大綱": summary,
                "日期": date_str_full,
                "連結": link
            })
            
            print(f"  記者: {reporter}")
            if summary:
                summary_preview = summary[:100] + "..." if len(summary) > 100 else summary
                print(f"  大綱: {summary_preview}")
        
        # 儲存結果
        print("\n" + "="*80)
        print("步驟 3: 儲存結果")
        print("="*80)
        
        result = {"articles": articles_data}
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ 結果已儲存至 {output_file}")
        print(f"✓ 共處理 {len(articles_data)} 篇新聞")
        
        return result
