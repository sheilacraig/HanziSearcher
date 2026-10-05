"""
SEO 配置与元数据生成模块

集中管理站点级 SEO 参数，避免 meta 标签散落在各模板中难以统一维护。

设计要点：
1. BASE_URL 一处配置，canonical / og:url / sitemap 全部由它派生，
   部署到公网时只需改这一个值。
2. 爬虫与浏览器返回不同内容：爬虫拿到完整静态 HTML（收录需要），
   浏览器拿到的仍是原交互页面（不影响使用体验）——
   依据是Baiduspider / Googlebot 等 UA 特征。
"""

import html
import json
from typing import Dict, List, Optional

# ============ 站点级配置 ============

# 站点根地址（生产环境）。
# 部署到char.jdkba.com 后 canonical / og:url / sitemap / robots 的 Sitemap 行
# 全部由它派生为绝对地址；留空则降级为相对路径（本地开发可用，但 SEO 效果打折，
# 且 /sitemap.xml 会返回 404 —— 相对路径的 sitemap 会被搜索引擎直接拒绝）。
BASE_URL: Optional[str] = "https://char.jdkba.com"

SITE_NAME = "HanziSearcher"
SITE_NAME_CN = "汉字探针"
DEFAULT_LANG = "zh-CN"

# 社交分享预览图（部署时换成真实可访问的绝对 URL）
OG_IMAGE = "/static/og-cover.svg"

# 各页面的元数据：(title, description, 优先级)
# 优先级影响 sitemap 中的相对权重，也影响页面间的重要度传递
PAGE_META: Dict[str, Dict[str, str]] = {
    "home": {
        "title": f"{SITE_NAME} - 汉字拆字与部件检索 | 10 万字库离线拆字",
        "description": (
            "离线汉字拆字与部件检索系统。支持形声字部件拆解、IDS 表意文字描述符、"
            "214 康熙部首检字、笔画筛选、拼音与 Unicode 码位检索，"
            "收录 103,047 个汉字元数据与全量 SVG 矢量字形，无需联网。"
        ),
        "priority": "1.0",
        "freq": "daily",
    },
    "chars": {
        "title": "汉字字表 - 按笔画与部首浏览全量汉字 | HanziSearcher",
        "description": (
            "按笔画数、部首浏览完整汉字字表，每个汉字均含拼音、笔画数、部首、"
            "IDS 结构描述与 Unicode 码位，覆盖 CJK 基础区与扩展区共103,047 字。"
        ),
        "priority": "0.9",
        "freq": "weekly",
    },
    "lego": {
        "title": "汉字乐高 - 部首骨架自由拼装与汉字造字 | HanziSearcher",
        "description": (
            "在线汉字拼装工具：以 8 种基础间架自由嵌套部首骨架，"
            "实时合成标准 IDS 表意文字描述符，支持 SVG 矢量与高清 PNG 导出、"
            "宣纸造字档案卡生成。"
        ),
        "priority": "0.8",
        "freq": "monthly",
    },
}


def get_base_url() -> str:
    """取得站点根地址（去掉末尾斜杠）。未配置 BASE_URL 时返回空串，调用方需降级为相对路径"""
    return (BASE_URL or "").rstrip("/")


def absolute_url(path: str) -> str:
    """
    将站内路径转为绝对 URL。

    未配置 BASE_URL 时原样返回相对路径：本地开发不产生误导，
    且 canonical 写成相对路径不会造成错误的索引指向。
    """
    if not path.startswith("/"):
        path = "/" + path
    base = get_base_url()
    return f"{base}{path}" if base else path


# ============ 爬虫识别============

# 主流搜索引擎 UA 特征串
CRAWLER_PATTERNS = (
    "baiduspider",     # 百度
    "bingbot",         # Bing
    "googlebot",       # Google
    "yandexbot",
    "duckduckbot",
    "sogou",           # 搜狗
    "360se",           # 360
    "bytespider",      # 头条
    "petalbot",        # 字节跳动
    "ahrefsbot",
    "semrushbot",
    "applebot",
)


def is_crawler(user_agent: str) -> bool:
    """判断 UA 是否为搜索引擎爬虫"""
    if not user_agent:
        return False
    ua = user_agent.lower()
    return any(p in ua for p in CRAWLER_PATTERNS)


# ============ 元数据生成 ============

def _esc(text: str) -> str:
    """HTML 属性值转义"""
    return html.escape(text or "", quote=True)


def build_meta_tags(
    page_key: str,
    canonical_path: Optional[str] = None,
    extra_keywords: Optional[List[str]] = None,
    is_crawler_view: bool = False
) -> str:
    """
    生成 <head> 中的全部 SEO / OG / Twitter 元标签。

    page_key: PAGE_META 的键
    canonical_path: 该页面的规范路径，默认取 / 或 /chars 等默认值
    is_crawler_view: 爬虫视图下额外注入 JSON-LD 结构化数据
    """
    meta = PAGE_META.get(page_key, PAGE_META["home"])
    title = meta["title"]
    description = meta["description"]
    if canonical_path is None:
        canonical_path = "/"
    canonical = absolute_url(canonical_path)

    keywords = [
        "汉字拆字", "汉字检索", "形声字", "部件检索", "IDS表意文字描述符",
        "康熙部首", "汉字笔画", "unicode汉字", "汉字字形", "汉字矢量图",
        SITE_NAME, "在线汉字工具",
    ]
    if extra_keywords:
        keywords.extend(extra_keywords)
    kw_str = "、".join(dict.fromkeys(keywords))  # 去重且保序

    tags = [
        f'<title>{_esc(title)}</title>',
        f'<meta name="description" content="{_esc(description)}" />',
        f'<meta name="keywords" content="{_esc(kw_str)}" />',
        f'<meta name="author" content="{_esc(SITE_NAME)}" />',
        f'<link rel="canonical" href="{_esc(canonical)}" />',
        # 明确告诉爬虫这是简体中文站，避免误判为多语言版本
        f'<meta name="robots" content="index,follow,max-image-preview:large" />',
    ]

    # Open Graph —— 微信 / 微博 / Facebook 等分享卡片依赖这组
    tags += [
        f'<meta property="og:type" content="website" />',
        f'<meta property="og:site_name" content="{_esc(SITE_NAME_CN)}" />',
        f'<meta property="og:title" content="{_esc(title)}" />',
        f'<meta property="og:description" content="{_esc(description)}" />',
        f'<meta property="og:url" content="{_esc(canonical)}" />',
        f'<meta property="og:image" content="{_esc(absolute_url(OG_IMAGE))}" />',
        f'<meta property="og:locale" content="zh_CN" />',
    ]

    # Twitter Card
    tags += [
        '<meta name="twitter:card" content="summary_large_image" />',
        f'<meta name="twitter:title" content="{_esc(title)}" />',
        f'<meta name="twitter:description" content="{_esc(description)}" />',
        f'<meta name="twitter:image" content="{_esc(absolute_url(OG_IMAGE))}" />',
    ]

    if is_crawler_view:
        tags.append(build_json_ld(page_key, title, description, canonical))

    return "\n".join(tags)


def build_json_ld(page_key: str, title: str, description: str, canonical: str) -> str:
    """
    生成 JSON-LD 结构化数据。

    爬虫用结构化数据理解页面实体类型，Google 支持 WebSite / SoftwareApplication，
    百度亦支持这类标注。WebSite + SearchAction 是站内搜索类站点的标准范式。
    """
    site_url = get_base_url() or canonical
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebSite",
                "@id": f"{site_url}#website",
                "url": site_url,
                "name": SITE_NAME,
                "alternateName": SITE_NAME_CN,
                "description": description,
                "inLanguage": DEFAULT_LANG,
                "potentialAction": {
                    "@type": "SearchAction",
                    "target": {
                        "@type": "EntryPoint",
                        "urlTemplate": f"{site_url}/?q={{search_term_string}}",
                    },
                    "query-input": "required name=search_term_string",
                },
            },
            {
                "@type": "WebApplication",
                "name": SITE_NAME,
                "alternateName": SITE_NAME_CN,
                "url": site_url,
                "description": description,
                "applicationCategory": "EducationalApplication",
                "operatingSystem": "Any",
                "browserRequirements": "Requires JavaScript",
                "inLanguage": DEFAULT_LANG,
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "CNY"},
            },
        ],
    }
    # JSON-LD 内不应出现未转义的 </script>，否则会提前闭合 script 标签导致 JSON 解析失败。
    # 注意：不能写成 f-string 表达式内嵌反斜杠 —— Python 3.10/3.11 不允许，
    # 本项目需兼容 3.10（Ubuntu 22.04 默认版本），故拆成两步。
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    safe_payload = payload.replace("</", "<\\/")
    return f'<script type="application/ld+json">{safe_payload}</script>'


def build_sitemap(entries: List[Dict[str, object]]) -> str:
    """
    生成 sitemap.xml 文本。

    entries 每项形如 {"loc": "/", "lastmod": "2026-10-05", "priority": "1.0", "freq": "daily"}
    """
    base = get_base_url()
    # 未配置域名时返回空串：sitemap 必须用绝对 URL，无域名时输出会被搜索引擎拒绝
    if not base:
        return ""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for e in entries:
        loc = absolute_url(str(e["loc"]))
        parts = [f"<loc>{html.escape(loc, quote=False)}</loc>"]
        if e.get("lastmod"):
            parts.append(f"<lastmod>{e['lastmod']}</lastmod>")
        if e.get("priority"):
            parts.append(f"<priority>{e['priority']}</priority>")
        if e.get("freq"):
            parts.append(f"<changefreq>{e['freq']}</changefreq>")
        lines.append("  <url>" + "".join(parts) + "</url>")
    lines.append("</urlset>")
    return "\n".join(lines)


def build_robots(sitemap_url: str = "/sitemap.xml") -> str:
    """
    生成 robots.txt。

    局部接口（/api/*）无收录价值且拖慢爬虫，显式 Disallow；
    /lego 这类高价值页面显式 Allow 并给出优先级抓取路径。
    """
    lines = [
        "User-agent: *",
        "",
        "# 高价值页面：优先抓取",
        "Allow: /$",
        "Allow: /chars",
        "Allow: /lego",
        "",
        "# 接口与查询结果：无收录价值，浪费抓取预算",
        "Disallow: /api/",
        "Disallow: /?",
        "",
        "# 社交分享预览图：og:image 与 favicon 引用的路径需要放行",
        "Allow: /static/og-cover.svg",
        "",
        "# 静态资源与内部跳转",
        "Disallow: /static/",
        "Disallow: /data/",
        "",
        "Sitemap: " + absolute_url(sitemap_url),
        "",
    ]
    return "\n".join(lines)