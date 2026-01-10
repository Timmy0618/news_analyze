"""
啟動 Streamlit 應用程式
"""

import subprocess
import sys
import os

def main():
    """啟動 Streamlit 應用程式"""
    # 確保在專案根目錄
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

    # 啟動 Streamlit
    cmd = [sys.executable, "-m", "streamlit", "run", "streamlit_app.py",
           "--server.port", "8501", "--server.address", "0.0.0.0"]

    print("啟動新聞搜尋 Streamlit 應用程式...")
    print(f"應用程式將在 http://localhost:8501 上運行")
    print("按 Ctrl+C 停止應用程式")

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n應用程式已停止")
    except Exception as e:
        print(f"啟動失敗: {e}")

if __name__ == "__main__":
    main()