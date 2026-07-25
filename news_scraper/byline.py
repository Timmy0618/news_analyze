"""
從文章內容擷取記者署名。

純函式模組：只吃 markdown / HTML 字串，不需網路或爬蟲實例，因此可直接匯入測試。
擷取失敗時回傳 NO_BYLINE（'未提及'）。
"""

import json
import re

NO_BYLINE = "未提及"

# 人名：2-4 個中文字
_NAME = r'[一-鿿]{2,4}'
# 署名前綴；「記者會」「記者們」「編輯部」等非署名用法用 negative lookahead 排除
_PREFIX_RE = re.compile(
    r'記者[：:]?\s*(?!會|們|問|群|席)'
    r'|特派員[：:]?\s*'
    r'|編輯[：:]?\s*(?!部|台|室)'
    r'|(?:撰文|文)[：:／/]\s*'
)
# 人名的結尾界線：標點/空白，或緊接的動作詞（讓「記者盧素梅攝影」只取到「盧素梅」）
_END_WORDS = ('攝', '報導', '採訪', '整理', '編譯', '翻攝')
# 句末逗號/句號刻意不算界線：「記者求證後，」這種句中用法才不會被當成人名
_END_CHARS = '／/、（）()[]【】「」〔〕〈〉|｜'

# 出現在署名位置但不是人名的詞（桌別、地名、通稱）。
_NOT_A_NAME = {
    NO_BYLINE,
    '綜合', '即時', '外電', '編譯', '本報', '中央社', '地方', '國際',
    '財經', '生活', '社會', '政治', '娛樂', '體育', '大陸', '中心', '新聞',
    '台北', '新北', '桃園', '台中', '台南', '高雄', '基隆', '新竹', '苗栗',
    '彰化', '南投', '雲林', '嘉義', '屏東', '宜蘭', '花蓮', '台東', '澎湖',
    '金門', '連江', '馬祖', '北京', '上海', '東京', '首爾', '華府', '華盛頓',
    # 「中央社記者指出」這類句中用法，記者後面接的是動詞不是人名
    '指出', '表示', '說明', '提問', '追問', '詢問', '問及', '提及', '透露',
    '求證', '採訪', '訪問', '直擊', '實測', '爆料', '獲悉', '致電', '查詢',
    '報導', '整理', '編輯', '記者', '攝影', '會上', '稍早', '目前',
}

# JSON-LD 的 author 常是媒體本身（自由時報電子報、中時新聞網）而非記者，用這些字排除
_ORG_WORDS = ('報', '社', '網', '台', '電視', '通訊', '中心', '新聞', '記者', '週刊', '雜誌')


def looks_like_name(name: str) -> bool:
    return (
        bool(re.fullmatch(_NAME, name))
        and name not in _NOT_A_NAME
        and not name.endswith(('中心', '新聞'))
    )


def _name_after_prefix(text: str, start: int) -> str:
    """署名前綴後面的 2-4 字人名；每個長度都要驗，不能讓 regex 自己挑（會挑到「求證後」）。"""
    for length in (2, 3, 4):
        name, rest = text[start:start + length], text[start + length:]
        if not looks_like_name(name):
            continue
        if not rest or rest[0].isspace() or rest[0] in _END_CHARS or rest.startswith(_END_WORDS):
            return name
    return ''


def extract_byline(content: str) -> str:
    """
    從文章內容中提取記者署名（使用 regex，不需 LLM）。

    Args:
        content: 文章內容（markdown 格式）

    Returns:
        記者姓名；若無法辨識則回傳 '未提及'。
    """
    # Check reporter/author links across full content
    link_m = re.search(r'\[([^\]]{1,15})\]\(\S*/(?:reporter|author)/[^)]+\)', content)
    if link_m:
        return link_m.group(1).strip()

    # TVBS uses 記者/編輯 [name](url) format; scope to tvbs.com.tw to avoid cross-site false positives
    tvbs_m = re.search(
        r'(?:記者|編輯)\s+\[([^\]]{1,15})\]\(https?://[^.]+\.tvbs\.com\.tw[^)]*\)', content
    )
    if tvbs_m:
        return tvbs_m.group(1).strip()

    # Firecrawl renders reporter names as markdown links [name](url); strip to plain text
    snippet = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', content)

    # Desk byline "XX中心／姓名報導" or "XX新聞／姓名報導": the real reporter is the
    # name *after* the slash, not the desk. Works for any desk prefix (e.g. 大陸中心)
    # and skips unsigned pieces where the token is generic (綜合/即時/外電/台北…).
    desk_m = re.search(
        rf'(?:中心|新聞)[／/]({_NAME})(?:[／/][一-鿿]{{0,8}})?報導',
        snippet,
    )
    if desk_m and looks_like_name(desk_m.group(1)):
        return desk_m.group(1)

    for m in _PREFIX_RE.finditer(snippet):
        name = _name_after_prefix(snippet, m.end())
        if name:
            return name

    return NO_BYLINE


def _walk_authors(node):
    """遞迴走訪 JSON-LD，吐出所有 @type=Person 的 name。"""
    if isinstance(node, list):
        for item in node:
            yield from _walk_authors(item)
    elif isinstance(node, dict):
        if node.get('@type') == 'Person' and isinstance(node.get('name'), str):
            yield node['name']
        for value in node.values():
            yield from _walk_authors(value)


def extract_byline_from_html(html: str) -> str:
    """
    從原始 HTML 補抓署名，用於 markdown 裡沒有署名的站（三立、中時快評的記者名
    只出現在 JSON-LD 的 author 欄位）。JSON-LD 找不到時退回純文字比對。

    Args:
        html: 文章頁的原始 HTML

    Returns:
        記者姓名；若無法辨識則回傳 '未提及'。
    """
    for block in re.findall(
        r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I
    ):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        for name in _walk_authors(data):
            name = name.strip()
            if looks_like_name(name) and not any(w in name for w in _ORG_WORDS):
                return name

    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html, flags=re.S | re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    return extract_byline(text)
