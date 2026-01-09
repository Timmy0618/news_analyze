"""
日誌記錄工具
提供統一的日誌記錄功能，並自動清理超過7天的日誌檔案
"""

import logging
import os
from pathlib import Path
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
import glob


# 設定日誌目錄
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


def cleanup_old_logs(days: int = 7):
    """
    清理超過指定天數的日誌檔案
    
    Args:
        days: 保留的天數，預設為7天
    """
    try:
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(days=days)
        
        # 查找所有日誌檔案
        log_files = glob.glob(str(LOG_DIR / "*.log"))
        log_files.extend(glob.glob(str(LOG_DIR / "*.log.*")))  # 包含輪轉的日誌
        
        deleted_count = 0
        for log_file in log_files:
            try:
                # 取得檔案修改時間
                file_mtime = datetime.fromtimestamp(os.path.getmtime(log_file))
                
                # 如果檔案超過保留期限，則刪除
                if file_mtime < cutoff_time:
                    os.remove(log_file)
                    deleted_count += 1
                    print(f"已刪除舊日誌: {log_file}")
            except Exception as e:
                print(f"刪除日誌檔案失敗 {log_file}: {e}")
        
        if deleted_count > 0:
            print(f"共刪除 {deleted_count} 個超過 {days} 天的日誌檔案")
        
    except Exception as e:
        print(f"清理日誌時發生錯誤: {e}")


def setup_logger(
    name: str,
    log_file: str = None,
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    console_output: bool = True
) -> logging.Logger:
    """
    設定並返回 logger 實例
    
    Args:
        name: Logger 名稱
        log_file: 日誌檔案名稱（不含路徑），預設為 {name}.log
        level: 日誌級別
        max_bytes: 單個日誌檔案最大大小（bytes）
        backup_count: 保留的日誌檔案數量
        console_output: 是否同時輸出到控制台
    
    Returns:
        配置好的 Logger 實例
    """
    # 建立 logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重複添加 handler
    if logger.handlers:
        return logger
    
    # 設定日誌格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 檔案處理器（使用輪轉日誌）
    if log_file is None:
        log_file = f"{name}.log"
    
    file_path = LOG_DIR / log_file
    file_handler = RotatingFileHandler(
        file_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 控制台處理器
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    取得或建立 logger
    
    Args:
        name: Logger 名稱
    
    Returns:
        Logger 實例
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger


# 在模組載入時清理舊日誌
cleanup_old_logs()
