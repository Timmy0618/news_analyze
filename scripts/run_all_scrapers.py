"""
執行所有新聞爬蟲
依序爬取各個新聞網站的政治新聞並儲存到資料庫
"""

import sys
from datetime import datetime
from pathlib import Path

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.tvbs_scraper import TvbsScraper
from scrapers.setn_scraper import SetnScraper
from scrapers.chinatimes_scraper import ChinaTimesScraper
from database.operations import save_scraper_results_to_db


def run_all_scrapers(
    target_date=None,
    num_pages=1,
    max_articles=1,
    save_to_db=True,
    debug=False
):
    """
    執行所有爬蟲
    
    Args:
        target_date: 目標日期（None 表示今天）
        num_pages: 每個網站要抓取的分頁數量
        max_articles: 每個網站最多處理的文章數量
        save_to_db: 是否儲存到資料庫
        debug: 是否啟用調試模式 (儲存中間檔案)
    """
    if target_date is None:
        target_date = datetime.now()
    
    date_str = target_date.strftime("%Y%m%d")
    
    # 定義所有爬蟲類別（配置從各自的類別中獲取）
    scraper_classes = [
        TvbsScraper,
        SetnScraper,
        ChinaTimesScraper,
    ]
    
    # 創建結果資料夾
    Path("results").mkdir(exist_ok=True)
    
    print("="*80)
    print(f"開始執行所有爬蟲")
    print(f"目標日期: {target_date.strftime('%Y/%m/%d')}")
    print(f"每個網站: {num_pages} 頁, 最多 {max_articles} 篇文章")
    print(f"是否儲存到資料庫: {'是' if save_to_db else '否'}")
    print("="*80)
    
    # 統計資訊
    total_stats = {
        "total_sites": len(scraper_classes),
        "success_sites": 0,
        "failed_sites": 0,
        "total_articles": 0,
        "db_inserted": 0,
        "db_updated": 0,
        "db_skipped": 0,
        "db_failed": 0
    }
    
    # 執行各個爬蟲
    for idx, scraper_class in enumerate(scraper_classes, 1):
        # 從類別方法獲取網站名稱和配置
        site_name = scraper_class.get_site_name()
        config = scraper_class.get_config()
        output_file = f"results/{site_name.lower().replace(' ', '_')}_{date_str}.json"
        
        print(f"\n{'='*80}")
        print(f"[{idx}/{len(scraper_classes)}] 開始爬取: {site_name}")
        print(f"{'='*80}")
        
        try:
            # 初始化爬蟲（使用類別自己的配置）
            scraper = scraper_class(config, debug=debug)
            
            # 執行爬蟲
            result = scraper.scrape_news(
                target_date=target_date,
                num_pages=num_pages,
                max_articles=max_articles,
                output_file=output_file
            )
            
            if result and result.get("articles"):
                article_count = len(result["articles"])
                total_stats["total_articles"] += article_count
                total_stats["success_sites"] += 1
                
                print(f"\n✓ {site_name} 爬取完成")
                print(f"  找到 {article_count} 篇文章")
                print(f"  結果已儲存至: {output_file}")
                
                # 儲存到資料庫
                if save_to_db:
                    print(f"\n  正在儲存到資料庫...")
                    db_stats = save_scraper_results_to_db(
                        result=result,
                        source_site=site_name
                    )
                    
                    total_stats["db_inserted"] += db_stats.get("inserted", 0)
                    total_stats["db_updated"] += db_stats.get("updated", 0)
                    total_stats["db_skipped"] += db_stats.get("skipped", 0)
                    total_stats["db_failed"] += db_stats.get("failed", 0)
                    
                    print(f"  資料庫儲存完成: 新增 {db_stats['inserted']} 篇, "
                          f"更新 {db_stats['updated']} 篇, "
                          f"跳過 {db_stats['skipped']} 篇")
            else:
                print(f"\n✗ {site_name} 爬取失敗或沒有找到文章")
                total_stats["failed_sites"] += 1
                
        except Exception as e:
            print(f"\n✗ {site_name} 發生錯誤: {e}")
            total_stats["failed_sites"] += 1
            import traceback
            traceback.print_exc()
    
    # 顯示總體統計
    print("\n" + "="*80)
    print("所有爬蟲執行完成 - 總體統計")
    print("="*80)
    print(f"總網站數: {total_stats['total_sites']}")
    print(f"  ✓ 成功: {total_stats['success_sites']}")
    print(f"  ✗ 失敗: {total_stats['failed_sites']}")
    print(f"\n總文章數: {total_stats['total_articles']}")
    
    if save_to_db:
        print(f"\n資料庫統計:")
        print(f"  ✓ 新增: {total_stats['db_inserted']}")
        print(f"  ↻ 更新: {total_stats['db_updated']}")
        print(f"  ⊘ 跳過: {total_stats['db_skipped']}")
        print(f"  ✗ 失敗: {total_stats['db_failed']}")
    
    print("="*80)
    
    return total_stats


def main():
    """主程式"""
    import argparse
    
    parser = argparse.ArgumentParser(description='執行所有新聞爬蟲')
    parser.add_argument('--pages', type=int, default=1, help='每個網站要爬取的頁數（預設: 1）')
    parser.add_argument('--max-articles', type=int, default=15, help='每個網站最多處理的文章數（預設: 15）')
    parser.add_argument('--no-db', action='store_true', help='不儲存到資料庫（只儲存 JSON）')
    parser.add_argument('--date', type=str, help='目標日期 (格式: YYYY-MM-DD)，預設為今天')
    parser.add_argument('--debug', action='store_true', help='啟用調試模式，儲存中間檔案')
    
    args = parser.parse_args()
    
    # 解析日期
    target_date = None
    if args.date:
        try:
            target_date = datetime.strptime(args.date, '%Y-%m-%d')
        except ValueError:
            print(f"錯誤：日期格式不正確，請使用 YYYY-MM-DD 格式")
            return
    else:
        target_date = datetime.now()
    
    # 執行爬蟲
    run_all_scrapers(
        target_date=target_date,
        num_pages=args.pages,
        max_articles=args.max_articles,
        save_to_db=not args.no_db,
        debug=args.debug
    )


if __name__ == "__main__":
    main()
