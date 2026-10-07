"""
SEO 配置与元数据生成模块

集中管理站点级 SEO 参数，避免 meta 标签散落在各模板中难以统一维护。

设计要点：
1. 域名一处配置（SITE_DOMAIN / ALT_DOMAINS），BASE_URL 及 canonical / og:url / sitemap
   全部由它派生，部署到公网时只需改这里。
2. 爬虫与浏览器返回不同内容：爬虫拿到完整静态 HTML（收录需要），
   浏览器拿到的仍是原交互页面（不影响使用体验）——
   依据是Baiduspider / Googlebot 等 UA 特征。
"""

import datetime
import html
import json
from typing import Dict, List, Optional, Tuple

# ============ 站点级配置 ============

# 站点域名：全项目唯一的域名定义处，其余代码一律引用这里的常量，不得再写死域名。
# 主域名（生产环境）：canonical / og:url / sitemap / robots 的 Sitemap 行
# 全部由它派生为绝对地址；留空则降级为相对路径（本地开发可用，但 SEO 效果打折，
# 且 /sitemap.xml 会返回 404 —— 相对路径的 sitemap 会被搜索引擎直接拒绝）。
SITE_DOMAIN: Optional[str] = "hanzi.jdkba.com"

# 备用域名：与主域名提供同一站点、同样可正常访问（不跳转），
# 仅加入跨域来源白名单；canonical 等 SEO 地址仍统一指向主域名，避免重复收录。
ALT_DOMAINS: Tuple[str, ...] = ("char.jdkba.com",)

# 站点根地址：由 SITE_DOMAIN 派生，勿单独修改
BASE_URL: Optional[str] = f"https://{SITE_DOMAIN}" if SITE_DOMAIN else None

# GoatCounter 访问统计上报地址：全项目唯一定义处。由 build_meta_tags 随 SEO 元标签
# 注入到每个 HTML 页面，模板中不再手写统计脚本；留空则不注入。
# count.js 自托管于 /static/gc-count.js（官方 CDN gc.zgo.at 在国内无法访问）。
GOATCOUNTER_ENDPOINT: Optional[str] = "https://jdkbachar.goatcounter.com/count"

SITE_NAME = "HanziSearcher"
SITE_NAME_CN = "汉字探针"
DEFAULT_LANG = "zh-CN"

# 社交分享预览图（部署时换成真实可访问的绝对 URL）
OG_IMAGE = "/static/og-cover.svg"

# ============ 备案公示 ============

# ICP 备案号。国内搜索引擎（尤其百度）对未公示备案信息的站点收录意愿很低，
# 且《互联网信息服务管理办法》要求经营性/非经营性站点在首页底部公示备案号。
# 留空则页脚不输出备案信息。
# 注意：这是主域名 jdkba.com 的备案号，子域名 hanzi.jdkba.com 直接继承，
# 无需单独备案（备案按主域名层级登记）。
ICP_RECORD: Optional[str] = "京ICP备2024061605号"

# 工信部备案查询地址：备案号必须链接到此，否则不视为有效公示
ICP_QUERY_URL = "https://beian.miit.gov.cn/"

# ============ 站长平台验证 ============

# Google Search Console 验证串。
# 从 GSC「网址前缀」方式验证时拿到的是 content 值，形如：
#   <meta name="google-site-verification" content="AbC123..." />
# 只填引号里的那串 token，不要连标签一起贴。
# 留空则完全不输出该标签（本地开发 / 未验证时保持页面干净）。
# 提示：若用「域名」方式（DNS TXT）验证，无需在页面里放任何标签，
#       本项保持为空即可，但那样就要去 DNS 服务商加解析记录。
GSC_VERIFICATION: Optional[str] = ""

# 百度站长平台同理（HTML 标签方式）。留空则不输出。
BAIDU_VERIFICATION: Optional[str] = ""

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
    # 单字详情页（/char/<汉字>）的兜底元数据。
    # 真实的 title / description 由 render_char_page 按字生成后再覆盖（_swap_meta），
    # 这里只保证 build_meta_tags 拿得到一份合法默认值。
    "char": {
        "title": f"汉字详情 - 拼音部首笔画与 IDS 结构 | {SITE_NAME}",
        "description": (
            "单个汉字的完整档案：拼音、部首、总笔画与部外笔画、IDS 结构描述、"
            "Unicode 码位，并附同部首与同笔画的关联字。"
        ),
        "priority": "0.5",
        "freq": "monthly",
    },
}


def get_base_url() -> str:
    """取得站点根地址（去掉末尾斜杠）。未配置 BASE_URL 时返回空串，调用方需降级为相对路径"""
    return (BASE_URL or "").rstrip("/")


def get_alt_base_urls() -> List[str]:
    """取得备用域名的根地址列表（https），供跨域白名单等使用"""
    return [f"https://{d.strip().rstrip('/')}" for d in ALT_DOMAINS if d and d.strip()]


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


def build_verification_tags() -> List[str]:
    """
    生成站长平台验证用 meta 标签。

    集中在此处而非散落到各模板：验证串只配一次，全站三个页面同时生效，
    避免「首页验证通过、/chars 忘了加」这类漏配。

    纯静态标签，不加载任何外部脚本，对首屏性能零影响。
    """
    tags: List[str] = []
    for name, token in (
        ("google-site-verification", GSC_VERIFICATION),
        ("baidu-site-verification", BAIDU_VERIFICATION),
    ):
        token = (token or "").strip()
        if token:
            tags.append(f'<meta name="{name}" content="{_esc(token)}" />')
    return tags


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

    # 站长平台验证（未配置 token 时为空列表，不产生任何多余输出）
    tags += build_verification_tags()

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

    stats = build_stats_snippet()
    if stats:
        tags.append(stats)

    return "\n".join(tags)


def build_stats_snippet() -> str:
    """生成 GoatCounter 统计脚本标签；未配置 GOATCOUNTER_ENDPOINT 时返回空串"""
    if not GOATCOUNTER_ENDPOINT:
        return ""
    return (f'<script data-goatcounter="{_esc(GOATCOUNTER_ENDPOINT)}" '
            'async src="/static/gc-count.js"></script>')


def build_footer() -> str:
    """
    生成全站统一页脚（站点标识 + 站内导航 + 备案公示）。

    由各模板中的 <!--SEO_FOOTER--> 占位符承载，改这一处即全站生效 ——
    避免「首页加了备案号、/chars 忘了加」这类漏配（备案公示是合规要求，
    漏一个页面就等于没做）。

    样式放在 static/css/style.css 的 .site-footer 一组规则里，此处不内联：
    页脚出现在每个页面上，挂在共用 CSS 文件里才能被浏览器缓存复用，
    而不是每页多传一段重复的样式文本。

    页脚里的三个站内链接是有意为之：既方便用户跳转，也让每张单字详情页
    都多出指向字表与乐高的内链，对收录有正面作用。
    """
    record = (ICP_RECORD or "").strip()
    if not record:
        return ""

    year = datetime.date.today().year
    nav_links = "".join(
        f'<a href="{href}">{label}</a>'
        for href, label in (("/", "拆字检索"), ("/chars", "汉字字表"), ("/lego", "汉字乐高"))
    )
    return (
        '<footer class="site-footer">'
        '<div class="sf-rule" aria-hidden="true"></div>'
        '<div class="sf-main">'
        '<div class="sf-brand">'
        '<span class="sf-seal" aria-hidden="true">字</span>'
        '<div class="sf-brand-text">'
        f'<div class="sf-name">{_esc(SITE_NAME_CN)}<em>{_esc(SITE_NAME)}</em></div>'
        '<p class="sf-tagline">离线汉字拆字与部件检索 · 全量矢量字形</p>'
        '</div>'
        '</div>'
        f'<nav class="sf-nav" aria-label="页脚导航">{nav_links}</nav>'
        '</div>'
        '<div class="sf-legal">'
        f'<span>© {year} {_esc(SITE_NAME)}</span>'
        '<i class="sf-sep" aria-hidden="true"></i>'
        f'<a href="{_esc(ICP_QUERY_URL)}" target="_blank" rel="noopener">{_esc(record)}</a>'
        '</div>'
        '</footer>'
    )


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
        "# 汉字详情页：单字长尾入口，是站内数量最大的可收录集合",
        "Allow: /char/",
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