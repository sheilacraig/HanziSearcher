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

# 确保项目根目录在 Python 模块搜索路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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


if __name__ == "__main__":
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8088
    run_server(port_arg)
