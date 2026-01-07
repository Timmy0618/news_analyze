"""
通用新聞爬蟲類別
支援多種新聞網站的爬取和分析
"""

import requests
import re
import os
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from langchain_openai import ChatOpenAI


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
        html_example: Optional[str] = None,
        html_example_description: Optional[str] = None,
        page_url_format: Optional[str] = None,
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
            html_example: HTML 結構範例（用於 LLM 提示）
            html_example_description: HTML 範例的說明（如何解讀各欄位）
            page_url_format: 換頁 URL 格式（使用 {page} 作為佔位符），None 表示使用預設格式 "&p={page}"
        """
        self.base_url = base_url
        self.list_tags = list_tags
        self.article_tags = article_tags
        self.date_pattern = date_pattern
        self.category_pattern = category_pattern
        self.link_pattern = link_pattern
        self.target_category = target_category
        self.html_example = html_example
        self.html_example_description = html_example_description
        self.page_url_format = page_url_format


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
        load_dotenv()
        self.config = config
        self.firecrawl_url = firecrawl_url
        self.llm = ChatOpenAI(
            base_url=llm_url,
            api_key=os.getenv("token", "EMPTY"),
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
    
    def get_page_url(self, page: int) -> str:
        """
        生成分頁 URL（可被子類覆寫以實現自訂換頁邏輯）
        
        Args:
            page: 頁碼
            
        Returns:
            該頁的完整 URL
        """
        if self.config.page_url_format:
            return self.config.page_url_format.format(page=page)
        else:
            # 預設格式（如三立新聞）
            return f"{self.config.base_url}&p={page}"
    
    def scrape_list_page(self, url: str) -> str:
        """
        直接用 requests 抓取列表頁面（不使用 Firecrawl）
        
        Args:
            url: 要抓取的 URL
            
        Returns:
            頁面的 HTML 內容
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"  抓取錯誤: {e}")
            return ""
    
    def extract_news_block(self, content: str) -> Optional[str]:
        """
        從完整頁面 HTML 中提取新聞列表區塊（建議子類覆寫此方法）
        
        Args:
            content: 完整頁面 HTML
            
        Returns:
            新聞列表區塊的 HTML，如果找不到則返回 None
        """
        # 預設實現：返回頁面中間部分作為備用
        # 建議：每個網站都應該創建子類並覆寫此方法
        print(f"  ⚠ 使用預設 extract_news_block 方法，建議為該網站創建專用子類")
        return content[len(content)//4:len(content)*3//4]
    
    def build_full_link(self, link: str) -> str:
        """
        將相對路徑轉換為完整 URL（建議子類覆寫此方法）
        
        Args:
            link: 相對或絕對路徑
            
        Returns:
            完整的 URL
        """
        if link.startswith('http'):
            return link
        
        # 預設實現：使用 base_url 的 domain
        # 建議：每個網站都應該創建子類並覆寫此方法
        from urllib.parse import urlparse
        parsed = urlparse(self.config.base_url)
        return f"{parsed.scheme}://{parsed.netloc}{link}"
    
    def extract_news_links(
        self, 
        content: str, 
        date_str: str,
        save_dir: Optional[str] = None,
        page_num: Optional[int] = None
    ) -> List[Tuple[str, str]]:
        """
        使用 LLM 從 HTML 內容中提取新聞連結
        
        Args:
            content: 頁面 HTML 內容
            date_str: 目標日期字串（如 "2026/01/04"）
            save_dir: 儲存 debug 資料的資料夾（可選）
            page_num: 頁碼（可選，用於檔名）
            
        Returns:
            [(標題, 連結), ...] 的列表
        """
        # 使用可覆寫的方法提取新聞區塊
        content_to_parse = self.extract_news_block(content)
        
        if not content_to_parse:
            print(f"  ✗ 無法提取新聞區塊")
            return []
        
        # 進一步清理 HTML，只保留關鍵資訊
        # 移除 script, style, img, input, noscript 標籤
        content_to_parse = re.sub(r'<script[^>]*>.*?</script>', '', content_to_parse, flags=re.DOTALL | re.IGNORECASE)
        content_to_parse = re.sub(r'<style[^>]*>.*?</style>', '', content_to_parse, flags=re.DOTALL | re.IGNORECASE)
        content_to_parse = re.sub(r'<noscript[^>]*>.*?</noscript>', '', content_to_parse, flags=re.DOTALL | re.IGNORECASE)
        content_to_parse = re.sub(r'<img[^>]*/?>', '', content_to_parse, flags=re.IGNORECASE)
        content_to_parse = re.sub(r'<input[^>]*/?>', '', content_to_parse, flags=re.IGNORECASE)
        # 移除 HTML 註解
        content_to_parse = re.sub(r'<!--.*?-->', '', content_to_parse, flags=re.DOTALL)
        # 移除空的 div 和 span
        content_to_parse = re.sub(r'<(div|span)[^>]*>\s*</(div|span)>', '', content_to_parse, flags=re.IGNORECASE)
        # 移除多餘空白和換行
        content_to_parse = re.sub(r'\s+', ' ', content_to_parse)
        # 移除不需要的屬性（只保留 href 和 class）
        content_to_parse = re.sub(r'\s+(style|onclick|onmouseover|data-[a-z-]+|pl|target|onerror|width|height|alt)="[^"]*"', '', content_to_parse, flags=re.IGNORECASE)
        
        print(f"  清理後內容長度: {len(content_to_parse)} 字元")
        
        # 儲存傳給 LLM 的清理後內容（用於 debug）
        if save_dir and page_num is not None:
            llm_input_filename = f"{save_dir}/page_{page_num}_llm_input.html"
            with open(llm_input_filename, "w", encoding="utf-8") as f:
                f.write(f"<!-- 第 {page_num} 頁 - 傳給 LLM 的清理後內容 -->\n")
                f.write(f"<!-- 目標日期: {date_str} -->\n")
                f.write(f"<!-- 內容長度: {len(content_to_parse)} 字元 -->\n\n")
                f.write(content_to_parse)
            print(f"  ✓ LLM 輸入內容已儲存: {llm_input_filename}")
        
        # 檢查內容是否太短
        if len(content_to_parse.strip()) < 100:
            print(f"  ✗ 清理後內容太短 ({len(content_to_parse)} 字元)，跳過 LLM 處理")
            print(f"  內容預覽: {content_to_parse[:200]}")
            return []
        
        # 限制內容長度避免 token 過多
        max_content_len = 8000  # 恢復較大的限制
        if len(content_to_parse) > max_content_len:
            content_to_parse = content_to_parse[:max_content_len]
        
        # 構建類別過濾提示
        category_hint = ""
        if self.config.target_category:
            category_hint = f"優先提取類別為「{self.config.target_category}」的新聞，但如果找不到也可以提取其他類別。"
        
        # 構建 HTML 範例提示
        html_example_section = ""
        if self.config.html_example:
            html_example_section = f"""HTML 中一則新聞的結構範例：
```html
{self.config.html_example}
```
{self.config.html_example_description or ''}
"""
        
        extract_query = f"""從以下 HTML 內容中提取新聞列表。

重要篩選條件：
1. 只提取日期為「{date_str}」的新聞（日期格式如 01/05、2026/01/05 等）
2. {category_hint if category_hint else "不限類別"}

{html_example_section}
請提取每則符合日期條件的新聞：
1. 標題（在 <h3 class="title"> 或類似標籤中）
2. 連結（在 href 屬性中，格式如 /News.aspx?NewsID=xxx 或 /realtimenews/xxx）

HTML 內容：
{content_to_parse}

請用以下 JSON 格式回答（只回答 JSON，不要其他文字）：
[
  {{"title": "新聞標題1", "link": "/News.aspx?NewsID=123456"}},
  {{"title": "新聞標題2", "link": "/realtimenews/20260107001962-260407"}}
]

注意：
1. 只回傳日期為「{date_str}」的新聞（比對 <time> 或 <span class="date"> 標籤中的日期）
2. 連結保持相對路徑格式（不要加上 https://...）
3. 其他日期的新聞請忽略
4. 如果沒有找到符合條件的新聞，回答空陣列 []"""

        try:
            print(f"  正在呼叫 LLM 提取新聞連結...")
            print(f"  傳送內容長度: {len(content_to_parse)} 字元")
            response = self.llm.invoke(extract_query)
            result_text = response.content.strip()
            print(f"  LLM 回應長度: {len(result_text)} 字元")
            print(f"  LLM 回應內容: {result_text[:300]}...")
            
            # 儲存 LLM 回應以便 debug
            if save_dir and page_num is not None:
                llm_response_filename = f"{save_dir}/page_{page_num}_llm_response.txt"
                with open(llm_response_filename, "w", encoding="utf-8") as f:
                    f.write(f"# LLM 回應 - 第 {page_num} 頁\n")
                    f.write(f"目標日期: {date_str}\n")
                    f.write(f"回應長度: {len(result_text)} 字元\n\n")
                    f.write("---\n\n")
                    f.write(result_text)
                print(f"  ✓ LLM 回應已儲存: {llm_response_filename}")
            
            # 嘗試解析 JSON
            # 移除可能的 markdown 代碼塊標記
            result_text = re.sub(r'^```json\s*', '', result_text)
            result_text = re.sub(r'^```\s*', '', result_text)
            result_text = re.sub(r'\s*```$', '', result_text)
            
            # 移除 Qwen 模型的思考過程（<think>...</think>）
            result_text = re.sub(r'<think>.*?</think>', '', result_text, flags=re.DOTALL)
            result_text = result_text.strip()
            
            # 嘗試解析 JSON
            try:
                news_list = json.loads(result_text)
            except json.JSONDecodeError:
                # 嘗試修復截斷的 JSON
                print(f"  嘗試修復截斷的 JSON...")
                # 找到最後一個完整的物件
                last_complete = result_text.rfind('},')
                if last_complete > 0:
                    result_text = result_text[:last_complete+1] + ']'
                    news_list = json.loads(result_text)
                else:
                    # 嘗試只取第一個物件
                    first_obj_end = result_text.find('}')
                    if first_obj_end > 0:
                        result_text = '[' + result_text[result_text.find('{'):first_obj_end+1] + ']'
                        news_list = json.loads(result_text)
                    else:
                        raise
            
            links = []
            for item in news_list:
                title = item.get('title', '').strip()
                link = item.get('link', '').strip()
                
                if title and link:
                    # 使用可覆寫的方法組合完整連結
                    full_link = self.build_full_link(link)
                    links.append((title, full_link))
            
            return links
            
        except json.JSONDecodeError as e:
            print(f"  LLM 回應解析失敗: {e}")
            print(f"  回應內容前 500 字: {result_text[:500]}")
            print(f"  回應內容後 200 字: {result_text[-200:] if len(result_text) > 200 else result_text}")
            return []
        except Exception as e:
            print(f"  LLM 提取錯誤: {e}")
            import traceback
            traceback.print_exc()
            return []
    
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
        
        # 建立儲存原始資料的資料夾
        raw_data_dir = f"raw_data_{target_date.strftime('%Y%m%d')}"
        os.makedirs(raw_data_dir, exist_ok=True)
        print(f"✓ 原始資料將儲存至資料夾: {raw_data_dir}")
        
        print("="*80)
        print(f"步驟 1: 抓取新聞列表 (日期: {date_str_full})")
        print("="*80)
        
        all_links = []
        
        # 抓取多個分頁
        for page in range(1, num_pages + 1):
            # 使用 get_page_url 方法生成換頁 URL（可被子類覆寫）
            page_url = self.get_page_url(page)
            print(f"\n正在抓取第 {page} 頁: {page_url}")
            
            # 直接用 requests 抓取列表頁（不用 Firecrawl）
            raw_content = self.scrape_list_page(page_url)
            print(f"  抓取到內容長度: {len(raw_content)} 字元")
            
            # 儲存每頁的原始內容
            if raw_content:
                page_filename = f"{raw_data_dir}/page_{page}.md"
                with open(page_filename, "w", encoding="utf-8") as f:
                    f.write(f"# 第 {page} 頁 - {page_url}\n\n")
                    f.write(f"抓取時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write("---\n\n")
                    f.write(raw_content)
                print(f"  ✓ 原始內容已儲存: {page_filename}")
            
            page_links = self.extract_news_links(raw_content, date_str_full, save_dir=raw_data_dir, page_num=page)
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
            
            # 儲存每篇文章的原始內容
            if article_content:
                # 從連結提取新聞 ID 作為檔案名稱
                news_id = link.split('newsid=')[-1].split('&')[0] if 'newsid=' in link else str(i)
                article_filename = f"{raw_data_dir}/article_{news_id}.md"
                with open(article_filename, "w", encoding="utf-8") as f:
                    f.write(f"# {title}\n\n")
                    f.write(f"連結: {link}\n")
                    f.write(f"抓取時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write("---\n\n")
                    f.write(article_content)
                print(f"  ✓ 原始文章已儲存: {article_filename}")
            
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
        print(f"✓ 原始資料已儲存至 {raw_data_dir} 資料夾")
        print("  包含：每頁的原始內容、各篇文章的原始內容")
        
        return result
