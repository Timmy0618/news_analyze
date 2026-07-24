"""
從文章內容擷取記者署名。

純函式模組：只吃 markdown 內容，不需網路或爬蟲實例，因此可直接匯入測試。
擷取失敗時回傳 '未提及'。
"""

import re

_BYLINE_PATTERNS = [
    r'(?:政治|國際|生活|社會|財經|娛樂|體育|綜合|新聞|即時)中心[／/][^\n]{0,30}',
    r'記者\s*[^\s／/，,\n]{1,10}(?:[／/][^\n]{0,20})?',
    r'[^\s，,\n]{2,8}[／/]特派員[^\n]{0,10}',
    r'文[／/]\s*[^\s，,\n]{2,10}',
    r'撰文[：:]\s*[^\s，,\n]{2,10}',
    r'記者[：:]\s*([^\s，,\n]{2,15})',
    r'編輯\s+([^\s\n|｜，,]{1,10})',
]

# Words that appear in "XX中心／○○報導" bylines but are NOT personal names
# (e.g. 即時新聞／綜合報導, 政治中心／外電報導) — these mean the piece is unsigned.
_GENERIC_DESK_WORDS = {
    '綜合', '即時', '外電', '編譯', '本報', '中央社', '地方', '國際',
    '財經', '生活', '社會', '政治', '娛樂', '體育', '大陸', '中心', '新聞',
}

_NO_BYLINE = "未提及"


def extract_byline(content: str) -> str:
    """
    從文章內容中提取記者署名（使用 regex，不需 LLM）。

    Args:
        content: 文章內容（markdown 格式）

    Returns:
        記者姓名；若無法辨識則回傳 '未提及'。
    """
    # Check reporter/author links across full content
    link_m = re.search(r'\[([^\]]{1,15})\]\(https?://[^)]+/(?:reporter|author)/[^)]+\)', content)
    if link_m:
        return link_m.group(1).strip()

    # TVBS uses 記者/編輯 [name](url) format; scope to tvbs.com.tw to avoid cross-site false positives
    tvbs_reporter_m = re.search(r'記者\s+\[([^\]]{1,15})\]\(https?://[^.]+\.tvbs\.com\.tw[^)]*\)', content)
    if tvbs_reporter_m:
        return tvbs_reporter_m.group(1).strip()

    tvbs_editor_m = re.search(r'編輯\s+\[([^\]]{1,15})\]\(https?://[^.]+\.tvbs\.com\.tw[^)]*\)', content)
    if tvbs_editor_m:
        return tvbs_editor_m.group(1).strip()

    # Firecrawl renders reporter names as markdown links [name](url); strip to plain text
    snippet = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', content)

    # Desk byline "XX中心／姓名報導" or "XX新聞／姓名報導": the real reporter is the
    # name *after* the slash, not the desk. Works for any desk prefix (e.g. 大陸中心)
    # and skips unsigned pieces where the token is generic (綜合/即時/外電…).
    desk_m = re.search(
        r'(?:中心|新聞)[／/]([一-鿿]{2,4})(?:[／/][一-鿿]{0,8})?報導',
        snippet,
    )
    if desk_m:
        name = desk_m.group(1).strip()
        if name and name not in _GENERIC_DESK_WORDS:
            return name

    for pattern in _BYLINE_PATTERNS:
        m = re.search(pattern, snippet)
        if m:
            # Prefer named capture group when available (patterns 6, 7)
            reporter = m.group(1).strip() if m.lastindex else m.group(0).strip()
            # Strip 記者/編輯/撰文/文 prefixes and /地點報導 suffixes
            reporter = re.sub(r'^(?:記者|編輯|撰文[：:]|文[／/])\s*', '', reporter)
            reporter = re.sub(r'[／/].*$', '', reporter)
            reporter = reporter.strip()
            if reporter and len(reporter) <= 20:
                return reporter

    return _NO_BYLINE
