"""
Web 请求处理与 API 路由分发模块
支持静态资源托管 (CSS/JS/图片/字体)、HTML 模板直出、REST API 路由处理
"""

import json
import mimetypes
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler
from typing import Optional, Dict, Any, Tuple

from searcher.engine import HanziEngine
from searcher.font_parser import parse_font_file
from server import seo
from server import seo_pages
from server.seo import build_robots
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

# 站长平台验证文件白名单（站点根路径 -> 实际存放于 static/）。
#
# 这些文件本体是平台下发的固定内容，无敏感信息，可公开访问；
# 但路由必须精确匹配文件名，不允许通配 —— 见 _handle_get 中的说明。
GSC_VERIFY_FILES = frozenset({
    "/google7edc209a0eca8c73.html",
})

# 允许的跨域来源白名单。
# 历史问题：无条件下发 Access-Control-Allow-Origin: * 且 do_OPTIONS 主动放行预检，
# 任意第三方网页可对本机端口发起跨域 fetch，从而静默覆盖 / 删除用户字体文件。
#
# 必须包含站点自身域名（主域名 + 备用域名）：页面内的 fetch / XHR 会携带 Origin 头，
# 若白名单只列127.0.0.1 与 localhost，部署上线后自身请求会被 403 拦死，
# 表现为「首页能打开但检索全无结果」。此处从 seo 的域名配置自动派生，避免再次漏配；
# 备用域名同样提供完整站点，漏配会导致经备用域名访问时检索失效。
def _build_allowed_origins() -> tuple:
    """构造来源白名单：本机回环地址 + 站点主域名与备用域名（含 http/https 两种 scheme）"""
    origins = ["http://127.0.0.1", "http://localhost", "https://127.0.0.1", "https://localhost"]
    for base in [seo.get_base_url()] + seo.get_alt_base_urls():
        base = (base or "").strip().rstrip("/")
        if not base:
            continue
        origins.append(base)
        # 同时放行 http 版本，nginx 未强制跳转 https 时仍可用
        if base.startswith("https://"):
            origins.append("http://" + base[len("https://"):])
    return tuple(origins)


ALLOWED_ORIGIN_PREFIXES = _build_allowed_origins()


def _origin_in_allowlist(origin: str) -> bool:
    """
    精确判断 Origin 是否在白名单内。

    不能用 startswith 做前缀匹配：那样 https://站点域名.evil.com
    会因前缀匹配而被误判为合法，等于给跨域绕过留了口子。

    解析为 (scheme, host, port) 三元组后比对，并按同 scheme 默认端口归一化：
    浏览器发送的 Origin 常带显式端口（如本地开发 http://127.0.0.1:8080），
    不做归一化会把最常见的本地开发场景误判为跨域。
    """
    if not origin:
        return True  # 无 Origin（curl、同源直连、导航请求）视为可信

    origin = origin.strip().rstrip("/")
    if origin in ALLOWED_ORIGIN_PREFIXES:
        return True

    parsed = _parse_origin(origin)
    if parsed is None:
        return False
    o_scheme, o_host, o_port = parsed

    # 回环地址放行任意端口：本地开发时服务端口由 --port 指定（8080/9000 等皆可），
    # 不按固定端口比对会把正常的本地调试请求误判为跨域。
    if o_host in ("127.0.0.1", "localhost", "::1"):
        return True

    for allowed in ALLOWED_ORIGIN_PREFIXES:
        a = _parse_origin(allowed)
        if a is None:
            continue
        a_scheme, a_host, a_port = a
        if o_host != a_host:
            continue
        # 端口归一：未显式给出时按 scheme 默认端口处理
        port = o_port if o_port is not None else (443 if o_scheme == "https" else 80)
        allow_port = a_port if a_port is not None else (443 if a_scheme == "https" else 80)
        if port == allow_port:
            return True
    return False


def _parse_origin(origin: str) -> Optional[Tuple[str, str, Optional[int]]]:
    """把 Origin 拆成 (scheme, host, port)；格式非法返回 None"""
    if "://" not in origin:
        return None
    scheme, rest = origin.split("://", 1)
    scheme = scheme.lower()
    if not rest or "/" in rest or "@" in rest or " " in rest:
        return None
    if ":" in rest:
        host, _, port_str = rest.rpartition(":")
        try:
            port = int(port_str)
        except ValueError:
            return None
        if not (0 < port < 65536):
            return None
    else:
        host, port = rest, None
    if not host:
        return None
    return scheme, host.lower(), port

# 分页页码上限：page 无界时 OFFSET 可达 5e10，触发大偏移全表扫描（实测 608ms）
MAX_PAGE = 10_000

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


def get_svg_from_db(code_param: str) -> str:
    """
    从 SQLite 本地库获取字形 SVG 矢量数据（100% 离线，无网络请求）
    兼容 Unicode 码位字符串 (如 'U+4E00', '4E00', 0x4E00) 与原始单字符 (如 '一')

    码位解析统一委托 searcher.engine._normalize_code_point，
    避免与 /api/search 出现两套解析规则导致同一输入返回不同字符。
    """
    return engine.get_svg_by_code_param(code_param)





def _is_client_disconnect(exc: BaseException) -> bool:
    """
    判断异常是否为「客户端提前断开连接」。

    浏览器刷新 / 关标签 / 脚本被中断时，Windows 抛的是 ConnectionAbortedError /
    ConnectionResetError，而不只是 POSIX 的 BrokenPipeError。原先只捕 BrokenPipeError，
    导致这类正常断连被当成服务内部错误处理。
    """
    if isinstance(exc, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
        return True
    inner = getattr(exc, "errno", None)
    return inner in (10053, 10054, 104)


class _HeadOnlySink:
    """
    HEAD 请求的响应体抑制器。

    注意不能简单把 self.wfile 换成空 sink —— BaseHTTPRequestHandler 的
    end_headers()/send_response() 会通过 wfile 写响应头，换掉后头部也丢了。
    因此这里只拦截「响应体」写入：先让响应头正常落盘，再把 body 丢弃。

    实现方式：作为 wfile 的前置过滤器，仅在第一次写入后放行（响应头），
    之后的所有写入（响应体）静默丢弃。
    """

    def __init__(self, real_wfile):
        self._real = real_wfile
        self._headers_done = False

    def write(self, data):
        if not self._headers_done:
            # 首个写入通常是 b"" 或状态行，视为响应头阶段，正常透传
            self._headers_done = True
            return self._real.write(data)
        return len(data)

    def flush(self):
        try:
            self._real.flush()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._real, name)


class HanziSearchHandler(BaseHTTPRequestHandler):
    """汉字检索与全功能 Web 服务处理器"""

    def _cors_origin(self) -> Optional[str]:
        """
        校验并返回回显用的 Origin。

        无 Origin 头（curl、同源直连、导航请求）视为可信，返回 None 表示不下发 CORS 头。
        有 Origin 头时必须在白名单内，否则跨域请求被拒。
        """
        origin = self.headers.get("Origin")
        if not origin:
            return None
        if _origin_in_allowlist(origin):
            return origin
        return None

    def _origin_allowed(self) -> bool:
        """判断当前请求来源是否可接受（拒绝时由调用方返回 403）"""
        origin = self.headers.get("Origin")
        if not origin:
            return True
        return _origin_in_allowlist(origin)

    def _send_cors_headers(self) -> None:
        """按校验结果下发 CORS 头；不可信来源不下发任何 CORS 头"""
        origin = self._cors_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _send_json(self, status: int, payload: Any, extra_headers: Optional[Dict[str, str]] = None):
        """统一 JSON 响应：带 Content-Length，并按白名单开启跨域"""
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, file_path: str, content_type: Optional[str] = None, cache_seconds: int = 86400):
        """分发静态本地文件，支持 MIME 判定、分块流式传输与缓存头"""
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            self.send_response(404)
            self.end_headers()
            return

        if not content_type:
            content_type, _ = mimetypes.guess_type(file_path)
            if not content_type:
                content_type = "application/octet-stream"

        body_started = False
        try:
            file_size = os.path.getsize(file_path)
            self.send_response(200)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8" if "text" in content_type else content_type)
            self.send_header("Content-Length", str(file_size))
            if cache_seconds > 0:
                self.send_header("Cache-Control", f"public, max-age={cache_seconds}")
            else:
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
            self._send_cors_headers()
            self.end_headers()
            body_started = True

            # 64KB 分块流式写出，避免大文件 (如 100MB 字体) 瞬时占用过多内存
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except Exception as e:
            if _is_client_disconnect(e):
                return
            if not body_started:
                # 响应头尚未发出：仍可安全返回 500
                try:
                    self.send_response(500)
                    self.end_headers()
                except Exception:
                    pass
            else:
                # 响应头已发出：不能再补状态行（会污染响应流、产生错乱的 HTTP 报文），
                # 唯一正确的做法是直接断开连接，让客户端以截断错误感知失败
                self.close_connection = True

    def do_OPTIONS(self):
        """处理 CORS 跨域预检请求（仅放行白名单来源）"""
        if not self._origin_allowed():
            self.send_response(403)
            self.end_headers()
            return
        self.send_response(204)
        self._send_cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Content-Length, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_HEAD(self):
        """
        历史问题：原先对任意路径（含 /api/nonexistent）恒返回 200，
        会误导浏览器、代理与缓存预检。此处复用 GET 的路由判定，仅把响应体写入降级为丢弃。
        """
        if not self._origin_allowed():
            self.send_response(403)
            self.end_headers()
            return
        # 抑制响应体写入，但保证响应头正常落盘（headers 在 end_headers 时一次性写出）
        real_wfile, self.wfile = self.wfile, _HeadOnlySink(self.wfile)
        try:
            self._handle_get()
        except Exception as e:
            # 响应头可能已写出无法回填状态码，但异常本身必须落日志，不能静默吞掉
            if not _is_client_disconnect(e):
                self._log_exception("HEAD", e)
        finally:
            self.wfile = real_wfile

    def do_GET(self):
        if not self._origin_allowed():
            self._send_json(403, {"error": "跨域来源不被允许"})
            return
        try:
            self._handle_get()
        except Exception as e:
            if _is_client_disconnect(e):
                return
            self._log_exception("GET", e)
            try:
                self._send_json(500, {"error": f"服务内部错误: {e}"})
            except Exception:
                pass

    def _handle_get(self):
        parsed = urllib.parse.urlparse(self.path)

        # 0. 社交分享预览图：由服务端动态生成，优先于静态资源路由处理
        if parsed.path == seo.OG_IMAGE:
            self._serve_og_cover()
            return

        # 1. 静态资源托管路由 (/static/css/..., /static/js/...)
        if parsed.path.startswith("/static/"):
            rel_path = parsed.path[len("/static/"):].lstrip("/")
            file_path = os.path.join(STATIC_DIR, rel_path)
            # 安全防路径穿越检查（必须以基准目录加路径分隔符为前缀）
            real_base = os.path.realpath(STATIC_DIR)
            real_target = os.path.realpath(file_path)
            if (real_target == real_base or real_target.startswith(real_base + os.path.sep)) and os.path.isfile(real_target):
                self._serve_file(real_target, cache_seconds=0)
            else:
                self.send_response(404)
                self.end_headers()
            return

        # 1.5 站长平台验证文件
        # Google / 百度等平台的「HTML 文件」验证要求文件位于站点根路径
        # （如 /google7edc209a0eca8c73.html），而非 /static/ 下，故单独开一条路由。
        #
        # 安全约束：此处必须先过 GSC_FILE_WHITELIST，再读取文件。
        # 若为图省事写成「匹配任意 /xxx.html 再拼路径」，等于新开一条
        # 带路径穿越面的读文件通道，把 /static/ 那段 realpath 校验的防线绕开了。
        # 白名单是精确文件名比对，未来新增验证文件必须显式加入集合。
        if parsed.path in GSC_VERIFY_FILES:
            rel = parsed.path.lstrip("/")
            target = os.path.join(STATIC_DIR, rel)
            real_base = os.path.realpath(STATIC_DIR)
            real_target = os.path.realpath(target)
            # 双重保险：即便白名单被误改，也仍受 realpath 边界约束
            if (real_target.startswith(real_base + os.path.sep)
                    and os.path.isfile(real_target)):
                self._serve_file(real_target, content_type="text/html", cache_seconds=0)
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
            page = _int_arg(qs, "page", 1, lo=1, hi=MAX_PAGE)
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
                self._send_cors_headers()
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
                self._send_cors_headers()
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



        # 10. 搜索引擎爬虫识别
        elif parsed.path == "/robots.txt":
            body = build_robots().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        # 11. 站点地图（未配置域名时返回 404，避免输出无效的相对路径 sitemap）
        # 走 seo_pages 的缓存入口：条目已上万，不能每次请求都重查库、重拼 2.7MB 字符串
        elif parsed.path == "/sitemap.xml":
            xml_text = seo_pages.get_cached_sitemap(engine)
            if not xml_text:
                self.send_response(404)
                self.end_headers()
            else:
                body = xml_text.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/xml; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "public, max-age=3600")
                self.end_headers()
                self.wfile.write(body)

        # 12.5 单字详情页：站内数量最大的可收录集合（/char/<汉字>）
        # 路径里的汉字可能是百分号编码（浏览器的正常形态），也可能是直接的中文
        # （部分客户端不编码），一律先 unquote，再交给引擎做统一归一化。
        elif parsed.path.startswith("/char/"):
            self._serve_char_page(
                urllib.parse.unquote(parsed.path[len("/char/"):]).strip()
            )

        # 13. SEO 字表落地页：服务端渲染真实汉字，供爬虫收录
        elif parsed.path in ("/chars", "/chars.html"):
            self._serve_chars_page()

        # 14. 汉字乐高独立页面
        elif parsed.path in ("/lego", "/lego.html"):
            self._serve_seo_page("lego", "lego.html", "/lego")

        # 15. 根页面与默认检索模板页面
        elif parsed.path in ("/", "/index.html"):
            self._serve_seo_page("home", "index.html", "/")

        # 16. API 路由未命中时返回标准 JSON 404，防止前端收到 HTML 页面
        elif parsed.path.startswith("/api/"):
            self._send_json(404, {"error": f"API 接口不存在: {parsed.path}"})

        # 17. 其它未知路径返回 404。
        # 历史问题：原先回退渲染首页（200 软 404），搜索引擎会收录大量
        # 「任意垃圾 URL 都返回首页」的重复页面，稀释站点权重。
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            body = "404 Not Found"
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

    def _ua(self) -> str:
        """当前请求的 User-Agent"""
        return self.headers.get("User-Agent", "")

    def _send_html(self, rendered, cache_seconds: int = 0):
        """把 (html_text, status, content_type) 三元组写回客户端"""
        if rendered is None:
            self.send_response(404)
            self.end_headers()
            return
        text, status, content_type = rendered
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if cache_seconds > 0:
            self.send_header("Cache-Control", f"public, max-age={cache_seconds}")
        else:
            self.send_header("Cache-Control", "no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def _serve_seo_page(self, page_key: str, template_name: str, canonical_path: str):
        """渲染带 SEO 元标签的静态页面（/ 与 /lego）"""
        self._send_html(
            seo_pages.render_seo_page(page_key, template_name, canonical_path, self._ua())
        )

    def _serve_chars_page(self):
        """SEO 字表落地页：服务端渲染真实汉字，供爬虫收录"""
        parsed_q = urllib.parse.urlparse(self.path)
        self._send_html(
            seo_pages.render_chars_page(engine, parsed_q.query, self._ua()),
            cache_seconds=1800,
        )

    def _serve_og_cover(self):
        """社交分享预览图"""
        body = seo_pages.render_og_cover().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(body)

    def _serve_char_page(self, raw: str):
        """
        单字详情页：服务端渲染单字档案与关联字内链，供爬虫收录。

        内容基本不变（字形、笔画、部首都是静态数据），缓存一天 ——
        爬虫批量遍历两万页时，不能让 2 核小机把每次都算一遍。
        """
        if not raw:
            self.send_response(404)
            self.end_headers()
            return
        self._send_html(
            seo_pages.render_char_page(engine, raw, self._ua()),
            cache_seconds=86400,
        )

    def do_POST(self):
        if not self._origin_allowed():
            self._send_json(403, {"success": False, "error": "跨域来源不被允许"})
            return
        try:
            self._handle_post()
        except Exception as e:
            if _is_client_disconnect(e):
                return
            self._log_exception("POST", e)
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

            try:
                content_length = int(self.headers.get("Content-Length", 0))
            except (ValueError, TypeError):
                self._send_json(400, {"success": False, "error": "无效的 Content-Length 请求头"})
                return

            if content_length > MAX_FONT_BYTES:
                self._send_json(413, {"success": False, "error": f"字体文件过大（上限 {MAX_FONT_BYTES // (1024 * 1024)}MB）"})
                return
            if content_length <= 0:
                self._send_json(400, {"success": False, "error": "文件内容为空"})
                return

            font_data = self.rfile.read(content_length)

            # 先落临时文件做解析校验，确认是合法字体后再原子替换正式文件。
            # 直接写 CUSTOM_FONT_PATH 的历史问题：非法字体会立即覆盖用户已上传的有效字体，
            # 且 /api/font_file 仍以 font/ttf 下发，浏览器加载失败而前端状态显示「已就绪」。
            os.makedirs(os.path.dirname(CUSTOM_FONT_PATH), exist_ok=True)
            tmp_path = CUSTOM_FONT_PATH + ".uploading"
            try:
                with open(tmp_path, "wb") as f:
                    f.write(font_data)

                try:
                    font_name, codepoints = parse_font_file(tmp_path)
                except Exception:
                    font_name, codepoints = "", set()

                if not codepoints:
                    # cmap 表为空 => 不是可识别的字体，丢弃临时文件并保留原有字体
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                    self._send_json(400, {
                        "success": False,
                        "error": "文件不是可识别的字体（TTF / OTF / WOFF / TTC），cmap 表为空或解析失败",
                    })
                    return

                # 解析成功：原子替换正式字体文件
                os.replace(tmp_path, CUSTOM_FONT_PATH)
            except Exception:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                raise

            # fontTools 解析成功时返回的是临时文件名，说明内部名称提取失败，回退到用户提供的名字
            if not font_name or font_name == os.path.basename(tmp_path):
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
            if parsed.path.startswith("/api/"):
                self._send_json(404, {"success": False, "error": f"API 接口不存在: {parsed.path}"})
            else:
                self.send_response(404)
                self.end_headers()

    def finish(self):
        """
        请求收尾钩子：把本请求线程占用的 SQLite 连接归还引擎连接池复用。
        ThreadingHTTPServer 每请求一线程且不复用线程，若不归还，
        连接只能等线程对象 GC 时被动关闭，低配 VPS 上持续 FD / 内存 churn。
        """
        try:
            engine.recycle_connection()
        except Exception:
            pass
        super().finish()

    def log_message(self, format, *args):
        pass

    def log_error(self, format, *args):
        pass

    def _log_exception(self, tag: str, exc: Exception):
        """
        5xx 落日志。原先 log_message 全量丢弃，服务端零日志，
        出错时只能靠响应体猜，且 log_message 的静默也会掩盖部分传输层异常。
        """
        try:
            import traceback
            print(f"[{tag}] {self.path} -> {type(exc).__name__}: {exc}", flush=True)
            traceback.print_exc()
        except Exception:
            pass
