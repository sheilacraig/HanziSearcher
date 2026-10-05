#!/usr/bin/env python3
"""
🏮 HanziSearcher Web 服务启动入口 (模块化架构重构版)
前后端彻底解耦：
- 静态资源层: static/css, static/js
- 页面模板层: templates/index.html
- 后端业务层: server/handlers.py, server/font_manager.py
- 核心引擎层: searcher/engine.py
"""

import os
import sys
from http.server import ThreadingHTTPServer

# 项目根目录：DB / 模板 / 静态资源全部以它为基准做相对定位
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 确保项目根目录在 Python 模块搜索路径中
sys.path.insert(0, BASE_DIR)

# 锚定工作目录到项目根。
# DB_PATH("data/hanzi.db")、STATIC_DIR、TEMPLATES_DIR 均为相对路径，
# 若从其它目录启动，sqlite 会抛 "unable to open database file"，整个服务不可用。
os.chdir(BASE_DIR)

# Windows 控制台下避免 GBK 编码引发 emoji 输出崩溃
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from server.handlers import HanziSearchHandler


def run_server(port: int = 8088):
    """
    启动多线程 HTTP 服务
    每连接分配独立线程，避免阻塞浏览器多路并发请求
    """
    server = ThreadingHTTPServer(("127.0.0.1", port), HanziSearchHandler)
    server.daemon_threads = True

    print("============================================================")
    print("🏮 HanziSearcher Web 服务 (模块化高性能版) 已启动！")
    print(f"👉 访问地址: http://127.0.0.1:{port}")
    print("📁 前端静态托管: static/ | 页面模板: templates/ | 引擎: searcher/")
    print("按 Ctrl+C 可停止服务")
    print("============================================================")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已平稳停止。")
    finally:
        # 显式关闭套接字，确保快速重启时端口可立即重新绑定
        server.server_close()


if __name__ == "__main__":
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8088
    run_server(port_arg)
