"""
SEO 页面渲染模块

把模板渲染逻辑独立于此，规避在 handlers.py 里手写大段方法时的缩进风险；
对外暴露三个渲染函数，由 HanziSearchHandler 方法薄封装调用。
"""

import datetime
import html
import os
import re
import urllib.parse
from typing import Dict, List, Optional, Tuple

from server import seo

TEMPLATES_DIR = "templates"

# SEO 字表页分页边界与每页字数
SEO_MAX_PAGE = 5_000
SEO_CHARS_PER_PAGE = 60

# 纳入 sitemap 的汉字码位区间：只收 CJK 基础区（U+4E00~U+9FFF，共 20992 字）。
#
# 为什么不把扩展区那 7 万多字一并提交：它们是 GB18030 之外、几乎无人检索的生僻字，
# 批量生成空壳页推给搜索引擎，会被判定成低质内容农场，反而拖累整站权重。
# 基础区已覆盖全部简体常用字，长尾价值最高、风险最低。
# 将来要放开更多区段，改这两个常量即可，其余逻辑自动跟随。
SEO_INDEX_MIN_CP = 0x4E00
SEO_INDEX_MAX_CP = 0x9FFF


def _total_pages(total: int, page_size: int) -> int:
    if total <= 0 or page_size <= 0:
        return 0
    return -(-total // page_size)


def is_crawler(user_agent: str) -> bool:
    return seo.is_crawler(user_agent)


# ============ 通用 SEO 页面 ============

def render_seo_page(page_key: str, template_name: str, canonical_path: str,
                    user_agent: str) -> Optional[Tuple[str, int, str]]:
    """
    渲染带 SEO 元标签的静态页面。

    做法：读取静态模板，把 <!--SEO_META:xxx--> 占位符替换为生成的标签，
    并覆盖 <title>。模板本身保持可独立打开（占位符原样保留），
    便于本地直接调试样式。
    """
    tpl_path = os.path.join(TEMPLATES_DIR, template_name)
    try:
        with open(tpl_path, "r", encoding="utf-8") as f:
            page_html = f.read()
    except OSError:
        return None

    meta_tags = seo.build_meta_tags(
        page_key,
        canonical_path=canonical_path,
        is_crawler_view=is_crawler(user_agent),
    )
    page_meta = seo.PAGE_META.get(page_key, seo.PAGE_META["home"])

    # build_meta_tags 自带 <title>，模板里也有，必须先摘掉模板原有的，
    # 否则会出现两个 <title>（HTML 规范只允许一个，搜索引擎会取第一个，行为不可控）。
    page_html = re.sub(r"[ \t]*<title>.*?</title>\s*", "\n", page_html,
                       count=1, flags=re.S)
    page_html = page_html.replace(f"<!--SEO_META:{page_key}-->", meta_tags)
    page_html = page_html.replace("<!--SEO_FOOTER-->", seo.build_footer())
    return page_html, 200, "text/html; charset=utf-8"


# ============ 社交分享预览图 ============

def render_og_cover() -> str:
    """动态生成社交分享预览图，避免依赖外部图片资源"""
    return '''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#fdf8f0"/>
      <stop offset="100%" stop-color="#f0e4d4"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  <rect x="48" y="48" width="1104" height="534" fill="none" stroke="#8b5a2b" stroke-width="3" rx="16"/>
  <text x="600" y="250" font-size="150" font-family="Kaiti SC,STKaiti,serif" fill="#8b5a2b" text-anchor="middle">漢字</text>
  <text x="600" y="360" font-size="72" font-weight="bold" fill="#5a4632" text-anchor="middle" font-family="sans-serif">HanziSearcher</text>
  <text x="600" y="430" font-size="34" fill="#8a7358" text-anchor="middle" font-family="sans-serif">103,047 字 · 离线拆字 · 部件检索 · 矢量字形</text>
  <text x="600" y="510" font-size="26" fill="#a08a6d" text-anchor="middle" font-family="sans-serif">汉字拆字 · IDS 表意文字描述符 · 康熙部首</text>
</svg>'''


# ============ 字表落地页 ============

def render_chars_page(engine, query: str, user_agent: str):
    """
    SEO 字表落地页：服务端渲染真实汉字 + 笔画筛选 + 分页。

    每个汉字卡片是真实可抓的内部链接，指向对应检索页，
    使爬虫能沿链接遍历整个字库——这是纯 JS 渲染页面做不到的。
    """
    qs = urllib.parse.parse_qs(query or "")
    raw_page = qs.get("page", ["1"])[0]
    raw_stroke = qs.get("stroke", [""])[0].strip()

    try:
        page = int(raw_page)
        if page < 1:
            page = 1
        if page > SEO_MAX_PAGE:
            page = SEO_MAX_PAGE
    except (TypeError, ValueError):
        page = 1

    stroke = None
    if raw_stroke:
        try:
            candidate = int(raw_stroke)
            if 1 <= candidate <= 64:
                stroke = candidate
        except (TypeError, ValueError):
            stroke = None

    total, chars = engine.get_chars_for_seo(
        page=page, page_size=SEO_CHARS_PER_PAGE, stroke=stroke)
    stats = engine.get_alphabet_stats()

    # --- 元标签（分页/筛选页用专属标题，分页 canonical 统一指回第 1 页）---
    crawler = is_crawler(user_agent)
    if stroke:
        page_title = f"{stroke}画汉字大全 - 笔画{stroke}的汉字字表 | {seo.SITE_NAME}"
        page_desc = (f"按笔画数 {stroke} 筛选的汉字字表，共 {total:,} 字，"
                     f"每个汉字含拼音、部首、IDS 结构描述与 Unicode 码位。")
        extra_kw = [f"{stroke}画汉字", "笔画查字", "笔画数汉字大全"]
    else:
        page_title = seo.PAGE_META["chars"]["title"]
        page_desc = seo.PAGE_META["chars"]["description"]
        extra_kw = ["汉字字表", "汉字大全", "汉字列表"]

    # 分页统一指回第 1 页，避免各分页互相重复竞争（canonical 规范做法）
    canonical = f"/chars?stroke={stroke}" if stroke else "/chars"
    meta_tags = seo.build_meta_tags(
        "chars", canonical_path=canonical,
        extra_keywords=extra_kw, is_crawler_view=crawler)

    # build_meta_tags 自带 title / description，这里用分页专属值覆盖
    meta_tags = _swap_meta(meta_tags, "title", page_title)
    meta_tags = _swap_meta(meta_tags, "og:title", page_title, attr="property")
    meta_tags = _swap_meta(meta_tags, "description", page_desc)
    meta_tags = _swap_meta(meta_tags, "og:description", page_desc, attr="property")
    meta_tags = _swap_meta(meta_tags, "twitter:title", page_title)
    meta_tags = _swap_meta(meta_tags, "twitter:description", page_desc)

    tpl_path = os.path.join(TEMPLATES_DIR, "chars.html")
    try:
        with open(tpl_path, "r", encoding="utf-8") as f:
            page_html = f.read()
    except OSError:
        return None
    page_html = page_html.replace("<!--SEO_META:chars-->", meta_tags)
    # 模板自带的 title 同样要先摘掉，避免与 meta_tags 里的 <title> 并存
    page_html = re.sub(r"[ \t]*<title>.*?</title>\s*", "\n", page_html,
                       count=1, flags=re.S)
    page_html = page_html.replace("<!--SEO_FOOTER-->", seo.build_footer())

    # --- 笔画导航：真实内部链接，是页面权重传递的主要路径 ---
    nav_parts = []
    for s, count in engine.get_stroke_distribution():
        cls = "active" if s == stroke else ""
        nav_parts.append(
            f'<a href="/chars?stroke={s}" class="{cls}" '
            f'title="{s}画的汉字共 {count:,} 个">{s}画</a>'
        )
    stroke_nav = "\n    ".join(nav_parts)

    # --- 汉字卡片（与检索结果页共用同一实现，保证两处结构一致）---
    char_cards = _char_cards_html(chars, "该笔画下暂无数据")

    # --- 分页器 ---
    total_pages = _total_pages(total, SEO_CHARS_PER_PAGE)
    q_suffix = f"stroke={stroke}&amp;" if stroke else ""
    pager_parts = []
    if page > 1:
        pager_parts.append(f'<a href="/chars?{q_suffix}page={page - 1}">上一页</a>')
    else:
        pager_parts.append('<span class="dis">上一页</span>')

    window = {1, total_pages}
    for off in range(-2, 3):
        p = page + off
        if 1 <= p <= total_pages:
            window.add(p)
    prev = 0
    for p in sorted(window):
        if prev and p - prev > 1:
            pager_parts.append('<span class="dis">…</span>')
        if p == page:
            pager_parts.append(f'<span class="cur">{p}</span>')
        else:
            pager_parts.append(f'<a href="/chars?{q_suffix}page={p}">{p}</a>')
        prev = p

    if page < total_pages:
        pager_parts.append(f'<a href="/chars?{q_suffix}page={page + 1}">下一页</a>')
    else:
        pager_parts.append('<span class="dis">下一页</span>')
    pager = "\n    ".join(pager_parts)

    sample_char = chars[0]["character"] if chars else "木"

    for token, value in (
        ("{{TOTAL}}", f"{stats['total']:,}"),
        ("{{SIMPLE}}", f"{stats['simple']:,}"),
        ("{{EXTENDED}}", f"{stats['extended']:,}"),
        ("{{ALL_ACTIVE}}", "" if stroke else "active"),
        ("{{STROKE_NAV}}", stroke_nav),
        ("{{CHAR_CARDS}}", char_cards),
        ("{{PAGER}}", pager),
        ("{{SAMPLE_CHAR}}", html.escape(sample_char, quote=False)),
    ):
        page_html = page_html.replace(token, value)

    return page_html, 200, "text/html; charset=utf-8"


# ============ 检索结果页（爬虫视图）============

# 检索结果页每页条数。与前端 app.js 的请求参数保持一致 —— 同一个 URL，
# 人类与爬虫看到的结果条数不该不同，否则会被视作内容作弊。
SEARCH_PER_PAGE = 50

# IDS 结构符 -> 中文结构名。
# 用来把 ⿰氵* 这类检索式翻译成人话：既让 title/description 带上
# 「氵字旁的字」这类真实搜索词，也让爬虫拿到的标题不是一串符号。
IDS_STRUCT_NAMES = {
    "⿰": "左右结构", "⿱": "上下结构", "⿲": "左中右结构", "⿳": "上中下结构",
    "⿴": "全包围结构", "⿵": "上三包围结构", "⿶": "下三包围结构",
    "⿷": "左三包围结构", "⿸": "左上包围结构", "⿹": "右上包围结构",
    "⿺": "左下包围结构", "⿻": "笔画交叠结构",
}

# 结构符 -> 首个部件所在位置，用于「左为木」这类描述
IDS_HEAD_POS = {
    "⿰": "左", "⿱": "上", "⿲": "最左", "⿳": "最上", "⿴": "外围",
    "⿵": "上部", "⿶": "下部", "⿷": "左侧", "⿸": "左上", "⿹": "右上",
    "⿺": "左下", "⿻": "",
}

# 检索页收录阈值：下界挡薄页，上界挡 q=*（10 万条、等同首页）这类过宽查询
SEARCH_INDEX_MIN_RESULTS = 30
SEARCH_INDEX_MAX_RESULTS = 20000

# 检索式长度上限：⿰木* 为 3 字符，再留 1 个字符余量
SEARCH_INDEX_MAX_QUERY_LEN = 4


def _char_cards_html(chars, empty_text: str = "没有匹配的汉字") -> str:
    """
    把汉字记录渲染成卡片网格。

    /chars 字表页与检索结果页共用此实现，两处卡片结构必须一致 ——
    爬虫在两类页面上看到的是同一套语义。

    卡片本身是 <a>，指向该字的详情页 /char/<汉字>：详情页才是收录主体，
    列表页的职责是让爬虫顺着链接一路爬进去。所以 href 必须指向详情页而
    不是检索页 —— 检索页多数会被判 noindex，导向那边等于把权重送进死路。

    字段名做了兼容：/chars 走 get_chars_for_seo()（strokes / ids），
    检索走 smart_search()（total_strokes / ids_direct）。
    """
    cards = []
    for c in chars:
        strokes = c.get("total_strokes") or c.get("strokes")
        hexc = c.get("hex_code") or ""
        radical = c.get("radical")
        ids_raw = c.get("ids_direct") or c.get("ids") or ""

        ch = html.escape(c["character"], quote=False)
        py = html.escape((c.get("pinyin") or "").split(",")[0][:12], quote=False)
        bits = []
        if strokes:
            bits.append(f"{strokes}画")
        if radical:
            bits.append(f"部{html.escape(str(radical), quote=True)}")
        if hexc:
            bits.append(html.escape(hexc, quote=True))
        ids = html.escape(ids_raw[:10], quote=True)
        title = f"{ch} {py} {' '.join(bits)}".strip()
        cards.append(
            f'<a class="char-card" href="/char/{urllib.parse.quote(c["character"])}" '
            f'title="{html.escape(title, quote=True)}">'
            f'<div class="char-glyph">{ch}</div>'
            f'<div class="char-py">{py}</div>'
            f'<div class="char-meta">{" · ".join(bits)}</div>'
            f'<div class="char-ids">{ids}</div>'
            f"</a>"
        )
    if cards:
        return "\n    ".join(cards)
    return ('<div style="grid-column:1/-1;text-align:center;padding:48px;'
            f'color:#8c7b70;">{html.escape(empty_text)}</div>')


def _describe_ids_query(q: str) -> Tuple[str, List[str]]:
    """把 IDS 检索式翻译成人类描述与关键词；无法识别时返回 ("", [])"""
    op = next((c for c in q if c in IDS_STRUCT_NAMES), None)
    body = [c for c in q if c != op] if op else list(q)
    named = [c for c in body if c != "*"]
    if not named:
        return "", []
    head = named[0]
    if op:
        pos = IDS_HEAD_POS.get(op, "")
        desc = IDS_STRUCT_NAMES[op] + (f"、{pos}为「{head}」" if pos else f"、含「{head}」")
    elif "*" in q:
        desc = f"含「{head}」"
    else:
        # 无结构符也无通配：单字的精确匹配，恒 1 条。措辞不能说「含」——
        # 那不是这个查询的语义（引擎走的是 exact_code 分支）。
        desc = f"「{head}」"
    kws = [f"含{head}的汉字", f"{head}部汉字"]
    if op == "⿰":
        kws.append(f"{head}字旁的字")
    if op:
        kws.append(f"{IDS_STRUCT_NAMES[op]}的汉字")
    return desc, kws


def classify_search_page(q: str, page: int, total: int) -> Tuple[bool, str]:
    """
    判断检索结果页能否被搜索引擎收录，返回 (是否收录, 原因)。

    为什么必须白名单：q 是检索框里自由输入的文本，可组合空间无穷
    （任意字符串 × 笔画 1~64 × 页码），整体放行等于向搜索引擎批量推送
    空壳页，会被判低质内容农场、反噬整站权重。所以兜底方向固定为
    「默认不收录」—— 任何解析疏漏都只会落到 noindex 一侧。

    实测各形态产出（engine.smart_search）：
        q=木    -> exact_code，恒 1 条。它是「精确匹配该字本身」，
                   而 /char/木 才是这种查询的正确落点，不在这里收录
        q=*     -> ids_pattern，102999 条，等于全库，与首页重复
        q=⿰木*  -> 2329 条（左右结构、左为木）
        q=⿰氵*  -> 2907 条（三点水的字）
        q=*木*  -> 3088 条（含木的字）
        q=⿱木*  -> 53 条（结果偏少，接近薄页）
    """
    if page != 1:
        return False, "翻页不单独收录（canonical 已归一回第 1 页）"
    q = (q or "").strip()
    if not q:
        return False, "空查询"
    if q == "*":
        return False, "通配全库，与首页内容重复"
    if len(q) > SEARCH_INDEX_MAX_QUERY_LEN:
        return False, "检索式过长"
    # 必须含结构符（如 ⿰氵*）或通配符（如 *木*）之一 —— 这两种写法都表达
    # 「含某部件」，才可能产出成规模的列表。纯单字走的是 exact_code
    # 精确匹配、恒 1 条，它的正确落点是 /char/<汉字>，不在这里收录。
    if not any(c in IDS_STRUCT_NAMES for c in q) and "*" not in q:
        return False, "非 IDS 模式；单字是精确匹配，正确落点为 /char/<汉字>"
    if total < SEARCH_INDEX_MIN_RESULTS:
        return False, f"结果仅 {total} 条，属薄页"
    if total > SEARCH_INDEX_MAX_RESULTS:
        return False, f"结果 {total} 条过于宽泛，与首页重复"
    return True, "IDS 模式检索"


def render_search_page(engine, query: str, user_agent: str):
    """
    检索结果页的爬虫视图。

    人类访客走 app.js 的交互式检索；这里只服务搜索引擎 —— 把真实结果以
    「汉字文本 + 指向 /char/<汉字> 的链接」直出。数据源与前端同为
    engine.smart_search()、每页条数也一致，所以两边结果集相同，差异只在
    呈现方式（爬虫得文本与链接，人类得 SVG 与交互），不构成内容作弊。

    收录策略见 classify_search_page()：默认 noindex，只有 IDS 模式白名单才
    index；无论收录与否都保留 follow，让爬虫继续沿页内详情页内链爬走。
    """
    qs = urllib.parse.parse_qs(query or "")
    raw_q = qs.get("q", [""])[0].strip()
    raw_strokes = qs.get("strokes", [""])[0].strip()
    raw_page = qs.get("page", ["1"])[0]

    try:
        page = max(1, int(raw_page))
    except (TypeError, ValueError):
        page = 1

    strokes = None
    if raw_strokes:
        try:
            cand = int(raw_strokes)
            if 1 <= cand <= 64:
                strokes = cand
        except (TypeError, ValueError):
            strokes = None

    result = engine.smart_search(raw_q, strokes=strokes, page=page,
                                 page_size=SEARCH_PER_PAGE)
    total = result.get("total_count", 0)
    chars = result.get("results") or []

    indexable, _reason = classify_search_page(raw_q, page, total)

    # --- 元标签：canonical 一律去掉 page，把分页权重归回第 1 页 ---
    desc_txt, kws = _describe_ids_query(raw_q) if raw_q else ("", [])
    # 通配全库时不能把 "*" 直接写进标题
    label = "全库" if raw_q == "*" else (desc_txt or raw_q or "全库")
    scope = f"{strokes} 画" if strokes else ""
    page_title = (f"{scope}{label}的汉字（共 {total:,} 个）"
                  f" - 汉字拆字检索 | {seo.SITE_NAME}")
    page_desc = (
        f"按 IDS 表意文字描述符检索「{raw_q}」的结果：共 {total:,} 个汉字"
        + (f"，限 {strokes} 画" if strokes else "")
        + "。每个字附拼音、总笔画、康熙部首与 Unicode 码位，"
          "可点入查看完整字形档案。"
    )

    params = {"q": raw_q}
    if strokes:
        params["strokes"] = strokes
    canonical_path = "/?" + urllib.parse.urlencode(params)
    meta_tags = seo.build_meta_tags(
        "home", canonical_path=canonical_path, extra_keywords=kws,
        is_crawler_view=is_crawler(user_agent),
        robots=("index,follow,max-image-preview:large" if indexable
                else "noindex,follow"),
    )
    meta_tags = _swap_meta(meta_tags, "title", page_title)
    meta_tags = _swap_meta(meta_tags, "og:title", page_title, attr="property")
    meta_tags = _swap_meta(meta_tags, "description", page_desc)
    meta_tags = _swap_meta(meta_tags, "og:description", page_desc, attr="property")
    meta_tags = _swap_meta(meta_tags, "twitter:title", page_title)
    meta_tags = _swap_meta(meta_tags, "twitter:description", page_desc)

    tpl_path = os.path.join(TEMPLATES_DIR, "index.html")
    try:
        with open(tpl_path, "r", encoding="utf-8") as f:
            page_html = f.read()
    except OSError:
        return None

    page_html = re.sub(r"[ \t]*<title>.*?</title>\s*", "\n", page_html,
                       count=1, flags=re.S)
    page_html = page_html.replace("<!--SEO_META:home-->", meta_tags)
    page_html = page_html.replace("<!--SEO_FOOTER-->", seo.build_footer())

    # 把真实结果注入结果网格：爬虫看到的是汉字文本 + 详情页链接。
    # 刻意不给分页链接 —— 后续页一律 noindex，让爬虫停在第 1 页就好，
    # 省下的抓取预算留给 /char/ 那两万张详情页。
    cards = _char_cards_html(chars, f"没有匹配「{raw_q}」的汉字")
    page_html = re.sub(
        r'<div class="results-grid" id="resultsGrid"></div>',
        lambda _m: f'<div class="results-grid" id="resultsGrid">{cards}</div>',
        page_html, count=1)

    return page_html, 200, "text/html; charset=utf-8"


def _swap_meta(meta_tags: str, marker: str, new_value: str, attr: str = "name") -> str:
    """
    替换生成好的标签中某个字段的值（用于分页 / 筛选的差异化标题描述）。

    marker 传「字段名」本身（如 description / og:title），
    attr 指明该字段是 name 还是 property 属性的。
    """
    esc_val = html.escape(new_value, quote=True)

    if marker == "title":
        return re.sub(r"<title>.*?</title>",
                      lambda _m: f"<title>{html.escape(new_value, quote=False)}</title>",
                      meta_tags, count=1, flags=re.S)

    prefix = f'<meta {attr}="{marker}" content="'
    idx = meta_tags.find(prefix)
    if idx < 0:
        return meta_tags
    start = idx + len(prefix)
    end = meta_tags.find('" />', start)
    if end < 0:
        return meta_tags
    return meta_tags[:start] + esc_val + meta_tags[end:]


# ============ 单字详情页 ============

# 变体字段的展示顺序与中文标签。
# 库中这些字段形如 "國 U+570B | 髮 U+9AEE"（| 分隔多个字形，每项「汉字 空格 码位」）
_VARIANT_FIELD_LABELS = (
    ("simplified", "简体"),
    ("traditional", "繁体"),
    ("z_variant", "异体"),
    ("semantic", "通假／义符"),
)


def _parse_variant_chars(raw: str) -> List[str]:
    """从变体字段中抽出其中的汉字字形，用于生成内链"""
    out: List[str] = []
    for part in (raw or "").split("|"):
        part = part.strip()
        if not part:
            continue
        head = part.split()[0]
        # 只认单个非 ASCII 字符（汉字 / 部首），其余（码位残片、空串）一律丢弃
        if len(head) == 1 and not head.isascii() and head not in out:
            out.append(head)
    return out


def _char_link(char: str, pinyin: str = "") -> str:
    """生成一个指向单字详情页的内链卡片"""
    py = (pinyin or "").split(",")[0].strip()[:12]
    title = f"{char} {py}".strip()
    return (
        f'<a href="/char/{urllib.parse.quote(char)}" '
        f'title="{html.escape(title, quote=True)}">'
        f'<span class="g">{html.escape(char, quote=False)}</span>'
        f'<span class="p">{html.escape(py, quote=False)}</span>'
        f'</a>'
    )


def _char_links(items: List[Dict[str, object]]) -> str:
    """把关联字列表渲染成内链卡片组"""
    if not items:
        return '<span style="color:#a89e91;font-size:13px;">暂无关联字</span>'
    return "\n      ".join(
        _char_link(str(it.get("character", "")), str(it.get("pinyin", "") or ""))
        for it in items
    )


def _build_variants_html(detail: Dict[str, object], char: str) -> str:
    """渲染简繁异体等关联字形区块；无数据时返回空串（模板不留空盒子）"""
    link_tpl = ('<a href="/char/{}" style="color:var(--primary);'
                'text-decoration:none;font-size:15px;">{}</a>')
    rows = []
    for key, label in _VARIANT_FIELD_LABELS:
        chars = [c for c in _parse_variant_chars(str(detail.get(key) or "")) if c != char]
        if not chars:
            continue
        links = " ".join(
            link_tpl.format(urllib.parse.quote(c), html.escape(c, quote=False))
            for c in chars[:8]
        )
        rows.append(
            f'<div><span class="lbl">{label}</span>{links}</div>'
        )
    if not rows:
        return ""
    return '<div class="ids-box" style="line-height:2.2;">' + "".join(rows) + '</div>'


def render_char_page(engine, code_str: str, user_agent: str) -> Optional[Tuple[str, int, str]]:
    """
    单字详情页（/char/<汉字>）。

    这是站内数量最大的可收录集合。页内用「同部首 / 同笔画 / 简繁异体」三组
    真实内部链接互相连通，爬虫沿链接即可持续深入，不必只依赖 sitemap。
    """
    detail = engine.get_seo_char_detail(code_str)
    if not detail:
        return None

    ch = str(detail["character"])
    pinyin = str(detail.get("pinyin") or "")
    pinyin_show = pinyin or "（暂无拼音）"
    strokes = detail.get("total_strokes")
    radical = str(detail.get("radical_char") or "") or "—"
    residual = detail.get("residual_strokes")
    hex_code = str(detail.get("hex_code") or "")
    ids = str(detail.get("ids_direct") or "") or "—"
    block = str(detail.get("block_name") or "") or "—"

    # canonical 一律用汉字形式：/char/木 与 /char/U+6728 都能打开同一页
    # （引擎统一归一化），不指定 canonical 就是多份重复内容互相竞争。
    # 注意 /char/6728 这类裸十六进制串不会命中 —— 引擎对纯数字一律按十进制
    # 解析（防劫持的既有设计，全站一致），4E00 这类含字母的写法才走十六进制。
    canonical = f"/char/{urllib.parse.quote(ch)}"

    title = (f"{ch}字详解 - 拼音 {pinyin_show}、{strokes} 画、{radical} 部、"
             f"Unicode {hex_code} | {seo.SITE_NAME}")
    desc = (f"{ch}（{pinyin_show}），共 {strokes} 画，部首「{radical}」，"
            f"部外 {residual} 画，Unicode 码位 {hex_code}，所属 {block}。"
            f"含 IDS 结构描述与同部首、同笔画关联字，可继续拆字检索与部件拼装。")

    meta_tags = seo.build_meta_tags(
        "char",
        canonical_path=canonical,
        extra_keywords=[
            f"{ch}字", f"{ch}的拼音", f"{ch}的笔画", f"{ch}的部首", f"{ch}字怎么读",
            f"{radical}部汉字", f"{strokes}画汉字", f"{hex_code} 汉字",
        ],
        is_crawler_view=is_crawler(user_agent),
    )
    meta_tags = _swap_meta(meta_tags, "title", title)
    meta_tags = _swap_meta(meta_tags, "og:title", title, attr="property")
    meta_tags = _swap_meta(meta_tags, "description", desc)
    meta_tags = _swap_meta(meta_tags, "og:description", desc, attr="property")
    meta_tags = _swap_meta(meta_tags, "twitter:title", title)
    meta_tags = _swap_meta(meta_tags, "twitter:description", desc)

    tpl_path = os.path.join(TEMPLATES_DIR, "char.html")
    try:
        with open(tpl_path, "r", encoding="utf-8") as f:
            page_html = f.read()
    except OSError:
        return None

    # 模板自带的 title 必须先摘掉，否则与 meta_tags 里的 <title> 并存
    page_html = re.sub(r"[ \t]*<title>.*?</title>\s*", "\n", page_html,
                       count=1, flags=re.S)
    page_html = page_html.replace("<!--SEO_META:char-->", meta_tags)
    page_html = page_html.replace("<!--SEO_FOOTER-->", seo.build_footer())

    replacements = {
        "{{CHAR}}": html.escape(ch, quote=False),
        "{{PINYIN}}": html.escape(pinyin_show, quote=False),
        "{{STROKES}}": str(strokes),
        "{{RADICAL}}": html.escape(radical, quote=False),
        "{{RESIDUAL}}": str(residual if residual is not None else "—"),
        "{{HEX}}": html.escape(hex_code, quote=False),
        "{{DECIMAL}}": str(detail.get("code_point")),
        "{{BLOCK}}": html.escape(block, quote=False),
        "{{IDS}}": html.escape(ids, quote=False),
        "{{VARIANTS}}": _build_variants_html(detail, ch),
        "{{RADICAL_LINKS}}": _char_links(detail.get("siblings_by_radical") or []),
        "{{STROKE_LINKS}}": _char_links(detail.get("siblings_by_stroke") or []),
    }
    for token, value in replacements.items():
        page_html = page_html.replace(token, value)

    return page_html, 200, "text/html; charset=utf-8"


def build_sitemap_entries(engine) -> list:
    """
    构造 sitemap 条目。

    - 静态页：首页 / 字表 / 乐高
    - 笔画分片：/chars?stroke=N，服务端渲染且互相连通
    - 单字详情页：/char/<汉字>，数量最大的一批（基础区 2 万余字）

    详情页是 sitemap 的主体。不提交它们，全站可收录 URL 就只有 50 多条，
    等于把十万字库的长尾价值整个浪费掉。
    """
    today = datetime.date.today().isoformat()
    entries = []
    for key, path in (("home", "/"), ("chars", "/chars"), ("lego", "/lego")):
        meta = seo.PAGE_META[key]
        entries.append({
            "loc": path,
            "lastmod": today,
            "priority": meta.get("priority", "0.5"),
            "freq": meta.get("freq", "weekly"),
        })
    try:
        for strokes, _count in engine.get_stroke_distribution():
            entries.append({
                "loc": f"/chars?stroke={strokes}",
                "lastmod": today,
                "priority": "0.6",
                "freq": "weekly",
            })
    except Exception:
        pass

    try:
        for ch in engine.get_seo_indexable_chars(SEO_INDEX_MIN_CP, SEO_INDEX_MAX_CP):
            entries.append({
                "loc": f"/char/{urllib.parse.quote(ch)}",
                "lastmod": today,
                "priority": "0.5",
                "freq": "monthly",
            })
    except Exception:
        pass
    return entries


# sitemap 进程内缓存。
#
# 条目数已上万，每次爬虫来访都重新查库 + 拼 2.7MB 字符串是纯浪费 CPU（生产机只有 2 核）。
# 按「日期」失效：站点内容本身按天更新，做更细粒度的时间失效没有收益，
# 反而容易引入时序 bug。进程重启即自然重建。
_sitemap_cache: Dict[str, str] = {"day": "", "xml": ""}


def get_cached_sitemap(engine) -> str:
    """带缓存的 sitemap 生成入口（未配置域名时返回空串，由调用方 404）"""
    today = datetime.date.today().isoformat()
    if _sitemap_cache["day"] == today and _sitemap_cache["xml"]:
        return _sitemap_cache["xml"]
    xml = seo.build_sitemap(build_sitemap_entries(engine))
    if xml:
        _sitemap_cache["day"] = today
        _sitemap_cache["xml"] = xml
    return xml