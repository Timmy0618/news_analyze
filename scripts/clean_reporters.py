"""
用本地 LLM 清理 news_articles.reporter 裡抓錯的舊值。

byline.py 修好之前留下的髒值有兩類：字串裡根本沒人名（「會」「會說明\\」），
和名字被雜訊包住（「王藝菘攝）」「張聰秋、張瑞楨」）。前者只能歸零成
未提及、交給 scripts/fix_missing_reporters.py 重抓；後者 LLM 能救回來，
而且能處理 byline.py 的正則做不到的事——雙掛名。

只對「不同的字串」跑 LLM（348 篇髒資料只有 167 個相異值），不是逐篇跑。

用法:
    uv run python scripts/clean_reporters.py             # dry-run，只印對照表
    uv run python scripts/clean_reporters.py --apply     # 真的寫入
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.config import Session
from database.models import NewsArticle
from news_scraper.byline import NO_BYLINE, looks_like_name
from utils.llm import create_llm

# LLM 可能用任何一種分隔符回多人掛名，統一收斂成「、」
_SEPARATORS = re.compile(r'[、,，/／;；&]|\s+和\s+')
# qwen3 是 reasoning model，正文前會有一段 <think>，裡面也有大括號會騙過 JSON 擷取
_THINK = re.compile(r'<think>.*?</think>', re.DOTALL)

PROMPT = """你要清理台灣新聞資料庫裡抓壞的「記者署名」欄位。

規則：
1. 字串裡若有真實記者姓名，回傳姓名。多位記者用「、」分隔，例如「張三、李四」。
2. 攝影師不算記者。「王藝菘攝）」這種只有攝影掛名的，回傳「未提及」。
3. 桌別、地名、媒體名不是人名（政治中心、新聞中心、台北、中央社、CTWANT），回傳「未提及」。
4. 從新聞內文誤抓的句子片段（會說明、別整天跟著她、聲量看政治），回傳「未提及」。
5. 不確定就回傳「未提及」。不要猜，不要編造姓名。

只輸出 JSON 物件，key 是原字串，value 是清理後的結果，不要有其他文字。

要清理的字串：
{items}"""


def normalize(value: str) -> str:
    """把 LLM 回的一格收斂成『、』分隔的人名，或 NO_BYLINE。

    每個名字都要過 looks_like_name——LLM 也會幻覺，這道關卡確保寫回 DB 的
    一定是 2-4 字中文人名，壞不過原本的資料。
    """
    parts = [p.strip() for p in _SEPARATORS.split(value or '')]
    names = [p for p in parts if looks_like_name(p)]
    # 去重但保順序：同一個名字被 LLM 重複列出時不要變成「張三、張三」
    seen: dict[str, None] = {}
    for n in names:
        seen[n] = None
    return '、'.join(seen) if seen else NO_BYLINE


def parse_llm_map(raw: str, originals: list[str]) -> dict[str, str]:
    """從 LLM 回應抽出 {原字串: 清理後}，只保留這批問過的 key。

    回不出合法 JSON 就回空 dict——這批跳過，不要讓一批壞掉的輸出污染整場。
    """
    match = re.search(r'\{.*\}', _THINK.sub('', raw or ''), re.DOTALL)
    if not match:
        return {}
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    allowed = set(originals)
    return {k: normalize(v) for k, v in data.items() if k in allowed and isinstance(v, str)}


def clean_reporters(apply: bool = False, batch: int = 20) -> dict[str, str]:
    """清一輪髒 reporter，回傳 {原字串: 清理後}。apply=False 時只算不寫。

    排程每天跑一次，所以「這批 LLM 掛了」不需要在這輪硬處理——沒回的值原封
    不動留著，明天那輪會再看到它。絕不因為 LLM 失敗就把資料覆寫成未提及。
    """
    session = Session()
    # 只讀 reporter 這一欄的相異值，不撈整列（見 ARCHITECTURE.md §3 egress 守則）
    rows = session.query(NewsArticle.reporter).distinct().all()
    dirty = sorted(
        {r[0] for r in rows if r[0] and r[0] != NO_BYLINE and not looks_like_name(r[0])}
    )
    print(f"相異髒值 {len(dirty)} 個")
    if not dirty:
        return {}

    llm = create_llm(temperature=0, timeout=600)
    mapping: dict[str, str] = {}
    for i in range(0, len(dirty), batch):
        chunk = dirty[i:i + batch]
        print(f"批次 {i // batch + 1}：{len(chunk)} 個字串 → LLM")
        try:
            raw = llm.invoke(PROMPT.format(items=json.dumps(chunk, ensure_ascii=False, indent=2)))
        except Exception as exc:
            print(f"  ⚠ LLM 呼叫失敗，這批留到下次：{exc}")
            continue
        parsed = parse_llm_map(str(raw.content), chunk)
        skipped = len(chunk) - len(parsed)
        if skipped:
            print(f"  ⚠ {skipped} 個沒回或解析不出，原值保留，下次再試")
        mapping.update(parsed)

    recovered = {k: v for k, v in mapping.items() if v != NO_BYLINE}
    print(f"\n救回人名 {len(recovered)} 個，另 {len(mapping) - len(recovered)} 個歸為 {NO_BYLINE}")
    for old_value, new_value in sorted(recovered.items()):
        print(f"  {old_value!r} → {new_value}")

    if not apply:
        print(f"\n(dry-run；加 --apply 才寫入。寫入後跑 fix_missing_reporters.py 重抓 {NO_BYLINE} 的)")
        return mapping

    changed = 0
    for old_value, new_value in mapping.items():
        changed += (
            session.query(NewsArticle)
            .filter(NewsArticle.reporter == old_value)
            .update({NewsArticle.reporter: new_value}, synchronize_session=False)
        )
    session.commit()
    print(f"\n已更新 {changed} 篇（{len(mapping)} 個相異值）")
    return mapping


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="真的寫入 DB（預設只印不寫）")
    # 27B reasoning model 一批 50 個要吐 50 筆 JSON，實測會超過 120s 預設 timeout
    parser.add_argument("--batch", type=int, default=20, help="每批丟給 LLM 幾個字串")
    args = parser.parse_args()
    clean_reporters(apply=args.apply, batch=args.batch)


if __name__ == "__main__":
    main()
