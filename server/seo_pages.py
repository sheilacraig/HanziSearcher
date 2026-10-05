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
from typing import Optional, Tuple

from server import seo

TEMPLATES_DIR = "templates"

# SEO 字表页分页边界与每页字数
SEO_MAX_PAGE = 5_000
SEO_CHARS_PER_PAGE = 60


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

    # --- 笔画导航：真实内部链接，是页面权重传递的主要路径 ---
    nav_parts = []
    for s, count in engine.get_stroke_distribution():
        cls = "active" if s == stroke else ""
        nav_parts.append(
            f'<a href="/chars?stroke={s}" class="{cls}" '
            f'title="{s}画的汉字共 {count:,} 个">{s}画</a>'
        )
    stroke_nav = "\n    ".join(nav_parts)

    # --- 汉字卡片 ---
    cards = []
    for c in chars:
        ch = html.escape(c["character"], quote=False)
        py = html.escape((c["pinyin"] or "").split(",")[0][:12], quote=False)
        bits = []
        if c["strokes"]:
            bits.append(f'{c["strokes"]}画')
        if c["radical"]:
            bits.append(f'部{html.escape(str(c["radical"]), quote=True)}')
        if c["hex_code"]:
            bits.append(html.escape(c["hex_code"], quote=True))
        ids = html.escape((c["ids"] or "")[:10], quote=True)
        title = f"{ch} {py} {' '.join(bits)}".strip()
        cards.append(
            f'<a class="char-card" href="/?q={urllib.parse.quote(c["character"])}" '
            f'title="{html.escape(title, quote=True)}">'
            f'<div class="char-glyph">{ch}</div>'
            f'<div class="char-py">{py}</div>'
            f'<div class="char-meta">{" · ".join(bits)}</div>'
            f'<div class="char-ids">{ids}</div>'
            f"</a>"
        )
    char_cards = "\n    ".join(cards) if cards else (
        '<div style="grid-column:1/-1;text-align:center;padding:48px;color:#8c7b70;">'
        "该笔画下暂无数据</div>"
    )

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


def build_sitemap_entries(engine) -> list:
    """
    构造 sitemap 条目。

    字表页按笔画分片全部纳入：每片都是服务端渲染的独立可抓 URL，
    通过 /chars?stroke=N 的内部链接互相连通。
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
    return entries