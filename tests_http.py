"""HTTP 层端到端测试：在本进程内启动真实 ThreadingHTTPServer 后验证各接口

覆盖：非法参数不崩、家族 404、SVG 严格解析、进度缓存、上传限额、并发不串话
自托管服务，避免依赖外部后台进程；请求绕过环境 HTTP 代理。
"""
import concurrent.futures
import json
import os
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request

from http.server import ThreadingHTTPServer

import web_server
from searcher.engine import HanziEngine

# 指向独立测试库，绝不触碰真实 data/hanzi.db
TEST_DB = os.path.join("data", "test_hanzi.db")
if not os.path.exists(TEST_DB):
    raise SystemExit("测试库不存在，请先运行: python tests_build_db.py")
web_server.DB_PATH = TEST_DB
web_server.engine = HanziEngine(db_path=TEST_DB)

PORT = 18088
BASE = f"http://127.0.0.1:{PORT}"
PASS, FAIL = [], []

# 启动被测服务（daemon 线程，测试结束随进程退出）
_server = ThreadingHTTPServer(("127.0.0.1", PORT), web_server.HanziSearchHandler)
_server.daemon_threads = True
threading.Thread(target=_server.serve_forever, daemon=True).start()

# 绕过环境 HTTP 代理（沙箱设置了 http_proxy，会拦截 127.0.0.1 返回 502）
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""))


def get(path, params=None, timeout=10):
    """path 为路径，params 为 dict，自动做 URL 编码"""
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        with _OPENER.open(url, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def post(path, data=b"", headers=None):
    req = urllib.request.Request(BASE + path, data=data, method="POST")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with _OPENER.open(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


print("=" * 74)
print("P0-1 非法参数不再打挂连接（原 int() 直接抛 ValueError）")
print("=" * 74)
BAD_PARAMS = [
    {"q": "一", "page": "abc"},
    {"q": "一", "page": "1;DROP TABLE characters"},
    {"q": "一", "page": "3.5"},
    {"q": "一", "page": "-999"},
    {"q": "一", "page_size": "abc"},
    {"q": "一", "strokes": "abc"},
    {"q": "一", "strokes": "8.5"},
    {"q": "一", "strokes": "-3"},
    {"q": "一", "strokes": "²"},          # isdigit() 为 True 但 int() 会抛异常
    {"q": "一", "page": "999999999999999999999"},
    {"q": "一", "page_size": "-1"},
]
for ps in BAD_PARAMS:
    label = urllib.parse.urlencode(ps)
    try:
        st, body = get("/api/search", ps)
        ok = st == 200 and "results" in body
        check(f"?{label} -> HTTP {st} 返回合法 JSON", ok)
    except Exception as e:
        check(f"?{label} -> 未崩溃", False, f"{type(e).__name__}: {e}")

print()
print("=" * 74)
print("P0-2 部件检索边界（HTTP 层确认）")
print("=" * 74)
st, body = get("/api/search", {"q": "方"})
data = json.loads(body)
chars = [r["character"] for r in data.get("results", [])]
check("搜『方』不误中多字符 token", chars == [], f"命中 {chars}")
st, body = get("/api/search", {"q": "_"})
data = json.loads(body)
check("搜『_』不再命中全表", data["total_count"] < 70, f"total={data['total_count']}")

print()
print("=" * 74)
print("FE-1 /api/family 查无此字返回 404（原 200+空对象致前端崩溃）")
print("=" * 74)
st, body = get("/api/family", {"code": "U+4E01"})
check("已知字返回 200", st == 200, f"HTTP {st}")
try:
    d = json.loads(body)
    check("返回体含 root", "root" in d)
except Exception:
    check("返回体为合法 JSON", False)
st, body = get("/api/family", {"code": "U+FFFF"})
check("查无此字返回 404", st == 404, f"HTTP {st}, body={body[:60]}")
st, body = get("/api/family", {"code": ""})
check("空参数返回 404 不崩", st == 404, f"HTTP {st}")

print()
print("=" * 74)
print("P1-1 码位误判（HTTP 层确认）")
print("=" * 74)
st, body = get("/api/search", {"q": "cafe"})
d = json.loads(body)
check("搜 cafe 走拼音模式", d["mode"] != "exact_code", f"mode={d['mode']}")
st, body = get("/api/search", {"q": "U+4E01"})
d = json.loads(body)
check("搜 U+4E01 正常命中", d["mode"] == "exact_code" and d["total_count"] == 1, f"mode={d['mode']}")

print()
print("=" * 74)
print("P2-5 /api/svg 严格码位解析 + 连接不泄漏")
print("=" * 74)
st, body = get("/api/svg", {"code": "U+4E01"})
check("合法码位返回 SVG", st == 200 and "<svg" in body, f"HTTP {st}")
st, body = get("/api/svg", {"code": "ZZZZ1234"})
check("非法参数返回 404（原宽松清洗会误命中）", st == 404, f"HTTP {st}")
st, body = get("/api/svg", {"code": "4E01"})
check("裸十六进制仍可用", st == 200, f"HTTP {st}")
for _ in range(50):
    get("/api/svg", {"code": "U+4E01"})
st, body = get("/api/svg", {"code": "U+4E01"})
check("连续 50 次请求后仍正常（无连接泄漏）", st == 200, f"HTTP {st}")

print()
print("=" * 74)
print("P1-4 进度接口 + 60 秒缓存")
print("=" * 74)
st, body = get("/api/svg_progress")
d1 = json.loads(body)
check("进度接口返回 200", st == 200 and "percent" in d1, f"HTTP {st}")
st, body2 = get("/api/svg_progress")
check("二次请求命中缓存（结果一致）", json.loads(body2) == d1)

print()
print("=" * 74)
print("上传接口限额与错误处理")
print("=" * 74)
st, body = post("/api/upload_font?filename=x.ttf", b"", {"Content-Length": "0"})
check("空文件返回 400", st == 400, f"HTTP {st}, body={body[:60]}")
st, body = post("/api/upload_font?filename=x.ttf",
                b"x" * 1024, {"Content-Length": str(200 * 1024 * 1024)})
check("超大字体返回 413", st == 413, f"HTTP {st}, body={body[:60]}")

print()
print("=" * 74)
print("P1-5 线程化：并发请求不串话、不报错")
print("=" * 74)
QUERIES = ["一", "丁", "回", "河", "招", "U+4E01", "shu", "口"]


def one(i):
    q = QUERIES[i % len(QUERIES)]
    st, body = get("/api/search", {"q": q})
    return q, st, json.loads(body).get("total_count")


try:
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        results = list(ex.map(one, range(64)))
    all_ok = all(st == 200 for _, st, _ in results)
    check("64 个并发请求全部 HTTP 200", all_ok,
          f"失败 {sum(1 for _, st, _ in results if st != 200)} 个")
    groups = {}
    for q, st, cnt in results:
        groups.setdefault(q, set()).add(cnt)
    bad = {k: sorted(v) for k, v in groups.items() if len(v) > 1}
    check("相同查询的并发结果一致（无连接串话）", not bad, f"异常组 {bad}")
except Exception as e:
    check("并发测试未抛异常", False, f"{type(e).__name__}: {e}")

print()
print("=" * 74)
print("根页面与头部")
print("=" * 74)
st, body = get("/")
check("根页面返回 HTML", st == 200 and "<!DOCTYPE html>" in body and "HanziSearcher" in body)
check("页面已引入 esc 转义工具", "const esc = s =>" in body)
check("页面已移除内联 onclick 拼接", "onclick=\"drillComponent('${" not in body)
check("页面已引入 fetchJson 封装", "async function fetchJson" in body)
check("进度轮询已移除", "setInterval(() => fetchSvgProgress" not in body)

print()
print("=" * 74)
print(f"结果: {len(PASS)} 通过 / {len(FAIL)} 失败")
for f in FAIL:
    print("  失败 -", f)
print("=" * 74)
_server.shutdown()
sys.exit(1 if FAIL else 0)
