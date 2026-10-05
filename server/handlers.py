"""
Web 请求处理与 API 路由分发模块
支持静态资源托管 (CSS/JS/图片/字体)、HTML 模板直出、REST API 路由处理
"""

import json
import mimetypes
import os
import re
import time
import urllib.parse
import zlib
from contextlib import closing
from http.server import BaseHTTPRequestHandler
from typing import Optional, Dict, Any

from searcher.engine import HanziEngine
from searcher.font_parser import parse_font_file
from server.font_manager import (
    CUSTOM_FONT_PATH,
    CUSTOM_FONT_META_PATH,
    MAX_FONT_BYTES,
    load_font_meta,
    save_font_meta,
    remove_custom_font,
)

DB_PATH = "data/hanzi.db"
TEMPLATES_DIR = "templates"
STATIC_DIR = "static"

engine = HanziEngine()

# 初始化 MIME 类型映射
mimetypes.init()
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("font/ttf", ".ttf")
mimetypes.add_type("font/woff", ".woff")
mimetypes.add_type("font/woff2", ".woff2")


def _int_arg(qs: Dict[str, list], key: str, default: int, lo: Optional[int] = None, hi: Optional[int] = None) -> int:
    """
    从 parse_qs 结果中安全解析整数参数：
    - 非法输入回退默认值，绝不抛异常
    - 可选范围钳制（lo/hi）
    """
    raw = qs.get(key, [str(default)])[0].strip()
    try:
        val = int(raw)
    except (ValueError, TypeError):
        val = default
    if lo is not None and val < lo:
        val = lo
    if hi is not None and val > hi:
        val = hi
    return val


def _parse_code_param(code_param: str) -> Optional[int]:
    """
    严格解析码位参数：单字符 / U+XXXX / U XXXX / 0xXXXX / 1~6 位纯十六进制。
    """
    s = (code_param or "").strip()
    if not s:
        return None
    if len(s) == 1:
        return ord(s)
    m = re.fullmatch(r"(?:[Uu][\+\s]?|0[xX])([0-9A-Fa-f]{1,6})", s)
    if m:
        return int(m.group(1), 16)
    if re.fullmatch(r"[0-9A-Fa-f]{1,6}", s):
        return int(s, 16)
    return None


def get_svg_from_db(code_param: str) -> str:
    """
    从 SQLite 本地库获取字形 SVG 矢量数据（100% 离线，无网络请求）
    兼容 Unicode 码位字符串 (如 'U+4E00', '4E00', 0x4E00) 与原始单字符 (如 '一')
    """
    cp = _parse_code_param(code_param)
    if cp is None:
        return ""
    full_hex = f"U+{cp:04X}"

    with closing(sqlite3_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT svg_data FROM character_svgs WHERE hex_code = ? OR code_point = ?", (full_hex, cp))
        row = cursor.fetchone()

    if row and row[0]:
        val = row[0]
        if isinstance(val, bytes):
            try:
                return zlib.decompress(val).decode("utf-8")
            except Exception:
                return ""
        return val
    return ""


def sqlite3_connect():
    """获取 SQLite 数据库连接"""
    import sqlite3
    return sqlite3.connect(DB_PATH, timeout=5)





class HanziSearchHandler(BaseHTTPRequestHandler):
    """汉字检索与全功能 Web 服务处理器"""

    def _send_json(self, status: int, payload: Any, extra_headers: Optional[Dict[str, str]] = None):
        """统一 JSON 响应：带 Content-Length，并开启跨域"""
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, file_path: str, content_type: Optional[str] = None, cache_seconds: int = 86400):
        """分发静态本地文件，支持 MIME 判定与缓存头"""
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            self.send_response(404)
            self.end_headers()
            return

        if not content_type:
            content_type, _ = mimetypes.guess_type(file_path)
            if not content_type:
                content_type = "application/octet-stream"

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8" if "text" in content_type else content_type)
            self.send_header("Content-Length", str(len(content)))
            if cache_seconds > 0:
                self.send_header("Cache-Control", f"public, max-age={cache_seconds}")
            else:
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)
        except Exception:
            self.send_response(500)
            self.end_headers()

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        try:
            self._handle_get()
        except BrokenPipeError:
            pass
        except Exception as e:
            try:
                self._send_json(500, {"error": f"服务内部错误: {e}"})
            except Exception:
                pass

    def _handle_get(self):
        parsed = urllib.parse.urlparse(self.path)

        # 1. 静态资源托管路由 (/static/css/..., /static/js/...)
        if parsed.path.startswith("/static/"):
            rel_path = parsed.path[len("/static/"):].lstrip("/")
            file_path = os.path.join(STATIC_DIR, rel_path)
            # 安全防路径穿越检查
            real_base = os.path.realpath(STATIC_DIR)
            real_target = os.path.realpath(file_path)
            if real_target.startswith(real_base) and os.path.exists(real_target):
                self._serve_file(real_target, cache_seconds=0)
            else:
                self.send_response(404)
                self.end_headers()
            return

        # 2. 字符检索 API (每页 50 条，内联 SVG 直出)
        if parsed.path == "/api/search":
            qs = urllib.parse.parse_qs(parsed.query)
            q = qs.get("q", [""])[0]
            strokes = _int_arg(qs, "strokes", 0, lo=0, hi=99)
            strokes = strokes if strokes > 0 else None
            page = _int_arg(qs, "page", 1, lo=1)
            page_size = _int_arg(qs, "page_size", 50, lo=1, hi=200)

            result = engine.smart_search(q, strokes=strokes, page=page, page_size=page_size)
            self._send_json(200, result)

        # 3. 汉字血缘探针与谱系 API
        elif parsed.path == "/api/family":
            qs = urllib.parse.parse_qs(parsed.query)
            code = qs.get("code", [""])[0] or qs.get("char", [""])[0]

            family_data = engine.get_character_family(code)
            if family_data is None:
                self._send_json(404, {"error": "未找到该字的谱系数据"})
            else:
                self._send_json(200, family_data)

        # 4. 本地 SQLite 矢量 SVG 资源分发接口
        elif parsed.path == "/api/svg":
            qs = urllib.parse.parse_qs(parsed.query)
            code = qs.get("code", [""])[0]
            svg_content = get_svg_from_db(code)

            if svg_content:
                body = svg_content.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "public, max-age=31536000")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        # 5. 汉字乐高：拆字提取机 API
        elif parsed.path == "/api/lego/disassemble":
            qs = urllib.parse.parse_qs(parsed.query)
            char = qs.get("char", [""])[0] or qs.get("q", [""])[0]
            if not char:
                self._send_json(400, {"error": "缺少参数 char"})
            else:
                res = engine.disassemble_char(char)
                self._send_json(200, res)

        # 6. 汉字乐高：分类部首积木库 API
        elif parsed.path == "/api/lego/radicals":
            presets = engine.get_preset_radicals()
            self._send_json(200, presets)

        # 7. 汉字乐高：单部件矢量查询 API
        elif parsed.path == "/api/lego/svg":
            qs = urllib.parse.parse_qs(parsed.query)
            comp = qs.get("char", [""])[0] or qs.get("code", [""])[0]
            svg_data = engine.get_component_svg(comp)
            if svg_data:
                body = svg_data.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            else:
                self._send_json(404, {"error": f"未找到部件 {comp} 的 SVG 矢量"})

        # 8. 当前自定义字体信息获取
        elif parsed.path == "/api/current_font":
            meta = load_font_meta()
            resp_data = meta if meta else {"has_font": False}
            self._send_json(200, resp_data)

        # 9. 当前自定义字体二进制下载接口 (供浏览器 @font-face 加载)
        elif parsed.path == "/api/font_file":
            if os.path.exists(CUSTOM_FONT_PATH):
                self._serve_file(CUSTOM_FONT_PATH, content_type="font/ttf", cache_seconds=0)
            else:
                self.send_response(404)
                self.end_headers()



        # 11. 汉字乐高独立页面
        elif parsed.path in ("/lego", "/lego.html"):
            lego_path = os.path.join(TEMPLATES_DIR, "lego.html")
            self._serve_file(lego_path, content_type="text/html", cache_seconds=0)

        # 12. 根页面与默认检索模板页面
        else:
            index_path = os.path.join(TEMPLATES_DIR, "index.html")
            self._serve_file(index_path, content_type="text/html", cache_seconds=0)

    def do_POST(self):
        try:
            self._handle_post()
        except BrokenPipeError:
            pass
        except Exception as e:
            try:
                self._send_json(500, {"error": f"服务内部错误: {e}"})
            except Exception:
                pass

    def _handle_post(self):
        parsed = urllib.parse.urlparse(self.path)

        # 1. 用户上传自定义字体接口
        if parsed.path == "/api/upload_font":
            qs = urllib.parse.parse_qs(parsed.query)
            filename = qs.get("filename", ["uploaded_font.ttf"])[0]

            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > MAX_FONT_BYTES:
                self._send_json(413, {"success": False, "error": f"字体文件过大（上限 {MAX_FONT_BYTES // (1024 * 1024)}MB）"})
                return
            if content_length <= 0:
                self._send_json(400, {"success": False, "error": "文件内容为空"})
                return

            font_data = self.rfile.read(content_length)

            os.makedirs(os.path.dirname(CUSTOM_FONT_PATH), exist_ok=True)
            with open(CUSTOM_FONT_PATH, "wb") as f:
                f.write(font_data)

            font_name, codepoints = parse_font_file(CUSTOM_FONT_PATH)
            if not codepoints:
                font_name = filename

            meta = {
                "has_font": True,
                "font_name": font_name or filename,
                "glyph_count": len(codepoints),
                "codepoints": sorted(list(codepoints))
            }
            save_font_meta(meta)
            self._send_json(200, {"success": True, **meta})

        # 2. 恢复默认 SVG 渲染 (删除已上传自定义字体)
        elif parsed.path == "/api/reset_font":
            remove_custom_font()
            self._send_json(200, {"success": True, "has_font": False})

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass
