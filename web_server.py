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


class HanziHTTPServer(ThreadingHTTPServer):
    """
    ThreadingHTTPServer 的 listen backlog 默认仅 5，
    公网 / nginx 突发并发下会直接丢弃入站连接，提到 64。
    """
    daemon_threads = True
    request_queue_size = 64


def run_server(port: int = 8088, host: str = "127.0.0.1"):
    """
    启动多线程 HTTP 服务
    每连接分配独立线程，避免阻塞浏览器多路并发请求

    host 默认仅本机可访问；部署到公网时传 "0.0.0.0" 监听全部网卡。
    """
    server = HanziHTTPServer((host, port), HanziSearchHandler)

    print("============================================================")
    print("🏮 HanziSearcher Web 服务 (模块化高性能版) 已启动！")
    if host == "127.0.0.1":
        print(f"👉 访问地址: http://127.0.0.1:{port}")
        print("   (仅本机可访问；如需公网访问请用 --host 0.0.0.0 启动)")
    else:
        print(f"👉 监听地址: http://{host}:{port}  (所有网卡，请自行确认防火墙与公网暴露风险)")
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
    # 用 argparse 而非手工解析 argv：支持 --port / --host，
    # 且 --help 自带说明，避免部署时靠猜参数。
    import argparse

    parser = argparse.ArgumentParser(
        description="HanziSearcher 汉字拆字与部件检索服务",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python web_server.py                # 默认 127.0.0.1:8088（仅本机）
  python web_server.py 9000           # 指定端口
  python web_server.py 9000 --host 0.0.0.0    # 监听所有网卡（公网部署用）
        """,
    )
    parser.add_argument("port", nargs="?", type=int, default=8088,
                        help="监听端口，默认 8088")
    parser.add_argument("--host", default="127.0.0.1",
                        help="监听地址，默认 127.0.0.1（仅本机）；公网部署用 0.0.0.0")
    args = parser.parse_args()

    if not (1 <= args.port <= 65535):
        print(f"端口必须在 1~65535 之间，收到: {args.port}", file=sys.stderr)
        sys.exit(1)

    run_server(args.port, args.host)
