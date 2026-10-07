"""
汉字与 Unicode 核心检索引擎 (带分页 + 变体流变 + 血缘探针)
支持：码位直查、多部件无序交集、IDS 模式匹配、结构别名、简繁异体字流变、汉字血缘衍生树
"""

import re
import sqlite3
import threading
import zlib
from functools import lru_cache
from typing import List, Dict, Any, Optional, Tuple

IDC_CHARS = set("⿰⿱⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻⿼⿽⿾⿿㇯")

STRUCT_ALIASES = [
    ("左中右", "⿲"),
    ("上中下", "⿳"),
    ("全包围", "⿴"),
    ("左上包", "⿸"),
    ("右上包", "⿹"),
    ("左下包", "⿺"),
    ("上包下", "⿵"),
    ("下包上", "⿶"),
    ("左包右", "⿷"),
    ("全包", "⿴"),
    ("包围", "⿴"),
    ("相交", "⿻"),
    ("重叠", "⿻"),
    ("左右", "⿰"),
    ("上下", "⿱"),
]

def _escape_like(s: str) -> str:
    """转义 SQL LIKE 通配符（配合 ESCAPE 子句使用）"""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _like_pattern(raw: str) -> str:
    """
    将用户原始输入转换为「已转义 + 已映射本项目通配语法」的 LIKE 模式串。

    处理顺序不可颠倒：
    1. 先转义用户输入里天然存在的 LIKE 元字符（\\ % _），否则它们会被当成通配符放大匹配范围
    2. 再把本项目语法 ? -> _（单构件）、* -> %（任意长度）映射为 LIKE 通配符

    调用方必须在 SQL 中配套 `ESCAPE '\\'` 子句，否则转义失效。
    """
    return _escape_like(raw).replace("?", "_").replace("*", "%")


def _normalize_code_point(raw: str) -> Optional[int]:
    """
    【唯一码位归一化入口】把用户输入解析为 Unicode 码位整数。

    全工程（search_by_code / get_svg_from_db / get_component_svg）必须共用本函数，
    否则同一输入会在不同接口解析为不同字符。

    识别规则（按优先级）：
      - 空串 / 空白           -> None
      - 单个非数字字符        -> ord(c)          例: 木 -> U+6728
      - U+XXXX / U XXXX / u+ -> 十六进制          例: U+8F93
      - 0xXXXX               -> 十六进制          例: 0x8F93
      - 4~6 位且含字母的十六进制 -> 十六进制       例: 690D -> 木（排除纯数字，避免劫持）
      - 纯数字                -> 十进制           例: 1234 -> U+04D2
      - 其余                  -> None
    """
    s = (raw or "").strip()
    if not s:
        return None

    # 单字符：数字留给十进制分支，避免 "5" 被解析为 U+0005
    if len(s) == 1 and not s.isdigit():
        return ord(s)

    # 显式前缀形式：U+XXXX / U XXXX / 0xXXXX
    m = re.fullmatch(r"(?:[Uu][\+\s]?|0[xX])([0-9A-Fa-f]{1,6})", s)
    if m:
        return int(m.group(1), 16)

    # 纯数字一律十进制
    if s.isdigit():
        return int(s)

    # 4~6 位十六进制（必须含字母，纯数字已被上一分支拦截）
    if len(s) in (4, 5, 6) and re.fullmatch(r"[0-9A-Fa-f]{4,6}", s):
        return int(s, 16)

    return None


def _token_match(comp: str) -> Tuple[str, str]:
    """
    生成对 ids_tokens（逗号分隔部件列表）的整词匹配 (SQL 片段, 参数)。
    通过给首尾补逗号并对 token 间空白做归一化，确保只命中完整的部件 token，
    避免裸 LIKE '%x%' 造成的跨 token 子串误命中（如搜"丁"误中"町"的"田"）。
    """
    sql = "(',' || REPLACE(c.ids_tokens, ' ', '') || ',') LIKE ? ESCAPE '\\'"
    param = f"%,{_escape_like(comp)},%"
    return sql, param


def _total_pages(total: int, page_size: int) -> int:
    """整数运算求总页数，避免 math.ceil(total / page_size) 的浮点除法"""
    if total <= 0 or page_size <= 0:
        return 0
    return -(-total // page_size)


# 拼音声调变体表：库中 pinyin 字段按「单字母带调」格式存储（如 wáng），
# 用户输入的是无调 ASCII 拼音（如 wang），直接 LIKE 永远匹配不上。
# 拼音声调只标在单个元音上，把输入按元音位置展开为各声调变体即可全覆盖。
TONAL_VOWELS = {
    'a': 'āáǎà',
    'e': 'ēéěè',
    'i': 'īíǐì',
    'o': 'ōóǒò',
    'u': 'ūúǔù',
    'v': 'ǖǘǚǜ',   # 用户以 v 代 ü 的输入习惯
    'ü': 'ǖǘǚǜ',
}


def _pinyin_variants(q: str) -> List[str]:
    """把无调拼音展开为「原串 + 各元音位置的单声调标注变体」列表"""
    out = [q]
    for i, ch in enumerate(q):
        tones = TONAL_VOWELS.get(ch)
        if tones:
            for tone in tones:
                out.append(q[:i] + tone + q[i + 1:])
    return out


def _is_chinese_char(c: str) -> bool:
    """
    判定单个字符是否属于 CJK 统一表意文字及部首扩展区间
    """
    if not c or len(c) != 1:
        return False
    cp = ord(c)
    return (
        (0x4E00 <= cp <= 0x9FFF) or      # CJK Unified Ideographs 基础区
        (0x3400 <= cp <= 0x4DBF) or      # Extension A
        (0x20000 <= cp <= 0x2A6DF) or    # Extension B
        (0x2A700 <= cp <= 0x2B73F) or    # Extension C
        (0x2B740 <= cp <= 0x2B81F) or    # Extension D
        (0x2B820 <= cp <= 0x2CEAF) or    # Extension E
        (0x2CEB0 <= cp <= 0x2EBEF) or    # Extension F
        (0x30000 <= cp <= 0x3134F) or    # Extension G
        (0x31350 <= cp <= 0x323AF) or    # Extension H
        (0x2E80 <= cp <= 0x2EF3) or      # CJK 部首补充
        (0x2F00 <= cp <= 0x2FD5)         # 康熙部首
    )


# 康熙部首表（第 1~214 个），用于把 characters.radical 的数字编号还原成部首字。
# 取值来自 Unicode 康熙部首区 U+2F00~U+2FD5 经 NFKC 归一化后的规范汉字，
# 与《康熙字典》部首次序一致（如 木 = 75、水 = 85、火 = 86）。
KANGXI_RADICALS = "一丨丶丿乙亅二亠人儿入八冂冖冫几凵刀力勹匕匚匸十卜卩厂厶又口囗土士夂夊夕大女子宀寸小尢尸屮山巛工己巾干幺广廴廾弋弓彐彡彳心戈戶手支攴文斗斤方无日曰月木欠止歹殳毋比毛氏气水火爪父爻爿片牙牛犬玄玉瓜瓦甘生用田疋疒癶白皮皿目矛矢石示禸禾穴立竹米糸缶网羊羽老而耒耳聿肉臣自至臼舌舛舟艮色艸虍虫血行衣襾見角言谷豆豕豸貝赤走足身車辛辰辵邑酉釆里金長門阜隶隹雨靑非面革韋韭音頁風飛食首香馬骨高髟鬥鬯鬲鬼魚鳥鹵鹿麥麻黃黍黑黹黽鼎鼓鼠鼻齊齒龍龜龠"


def _radical_to_char(num) -> str:
    """把康熙部首编号(1~214)还原为部首字；缺号或越界时返回空串"""
    try:
        n = int(num)
    except (TypeError, ValueError):
        return ""
    if 1 <= n <= len(KANGXI_RADICALS):
        return KANGXI_RADICALS[n - 1]
    return ""


# 常见部首与正字等价映射表（用于合字检索时无缝联想）
COMPONENT_VARIANTS = {
    '人': ['人', '亻'],
    '亻': ['亻', '人'],
    '水': ['水', '氵', '氺'],
    '氵': ['氵', '水', '氺'],
    '手': ['手', '扌'],
    '扌': ['扌', '手'],
    '心': ['心', '忄'],
    '忄': ['忄', '心'],
    '火': ['火', '灬'],
    '灬': ['灬', '火'],
    '犬': ['犬', '犭'],
    '犭': ['犭', '犬'],
    '示': ['示', '礻'],
    '礻': ['礻', '示'],
    '衣': ['衣', '衤'],
    '衤': ['衤', '衣'],
    '金': ['金', '钅'],
    '钅': ['钅', '金'],
    '言': ['言', '讠'],
    '讠': ['讠', '言'],
    '食': ['食', '饣'],
    '饣': ['饣', '食'],
    '糸': ['糸', '纟'],
    '纟': ['纟', '糸'],
    '草': ['艹', '艸'],
    '艹': ['艹', '草', '艸'],
    '竹': ['竹', '⺮'],
    '⺮': ['⺮', '竹'],
    '月': ['月', '⺼'],
    '⺼': ['⺼', '月'],
}

# 常见二叠、三叠、四叠字快速索引映射（当输入连续相同汉字时直出置顶）
DOUBLE_REPEAT_MAP = {
    "木": "林", "火": "炎", "日": "昍", "月": "朋", "人": "从",
    "牛": "牪", "石": "砳", "口": "吕", "又": "双", "戈": "戋",
    "土": "圭", "子": "孖", "白": "皕", "鱼": "䲆"
}

TRIPLE_REPEAT_MAP = {
    "木": "森", "火": "焱", "日": "晶", "牛": "犇", "羊": "羴",
    "石": "磊", "水": "淼", "土": "垚", "金": "鑫", "人": "众",
    "口": "品", "目": "瞐", "车": "轰", "手": "掱", "毛": "毳",
    "直": "矗", "马": "骉", "龙": "龘", "雷": "靐", "风": "飍",
    "犬": "猋", "鹿": "麤", "鱼": "鱻", "子": "孱", "耳": "聶"
}

QUAD_REPEAT_MAP = {
    "火": "燚", "木": "𣛧", "日": "𣊭", "水": "𣾜", "土": "𡑯",
    "牛": "𤛭", "鱼": "𩙡", "龙": "𪚥", "口": "㗊", "又": "叕"
}

# 字库笔画数区间：CJK 实际用字集中在 1~64画，用于 SEO 字表页的规模统计与筛选
MIN_STROKES = 1
MAX_STROKES = 64



class HanziEngine:
    """汉字多模态检索引擎 (全功能增强版)"""

    def __init__(self, db_path: str = "data/hanzi.db", pool_size: int = 8):
        self.db_path = db_path
        self._local = threading.local()
        # 空闲连接池：ThreadingHTTPServer 每请求一线程且不复用线程，
        # 纯 thread-local 会导致每个请求都新建 SQLite 连接、靠 GC 兜底关闭，
        # 在低配 VPS 上持续 FD / 内存 churn。此处改为「请求结束显式归还池中复用」。
        self._pool: List[sqlite3.Connection] = []
        self._pool_lock = threading.Lock()
        self._pool_size = pool_size

    def get_connection(self) -> sqlite3.Connection:
        """
        线程局部连接：配合 ThreadingHTTPServer 每个请求线程独享连接，
        避免多线程共享同一 Connection 造成的游标错乱与递归使用异常。
        引擎只做只读查询，统一开启 query_only 从根本上杜绝写竞争。
        优先从空闲池复用（请求结束时由 HanziSearchHandler.finish 归还），
        池空才真正新建连接。
        """
        conn = getattr(self._local, "conn", None)
        if conn is None:
            with self._pool_lock:
                conn = self._pool.pop() if self._pool else None
            if conn is None:
                # check_same_thread=False：连接在请求结束时归还池中、由下一个请求线程
                # 独占复用（借出期间无任何共享），池 + 锁保证同一时刻单线程持有，
                # 解除 sqlite 的线程绑定检查以支持跨请求线程复用。
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA query_only = 1")
            self._local.conn = conn
        return conn

    def recycle_connection(self) -> None:
        """
        请求结束时回收本线程连接：同一线程内独占使用，归还动作无共享竞争。
        池满则直接关闭，防止长连接泄漏堆积。调用方须保证请求内 SQL 已全部执行完毕。
        """
        conn = getattr(self._local, "conn", None)
        if conn is None:
            return
        self._local.conn = None
        with self._pool_lock:
            if len(self._pool) < self._pool_size:
                self._pool.append(conn)
                return
        try:
            conn.close()
        except Exception:
            pass

    def _select_fields(self) -> str:
        return """
            c.code_point, c.hex_code, c.character, c.block_name, 
            c.ids_direct, c.ids_tokens, c.radical, c.residual_strokes, 
            c.total_strokes, c.pinyin,
            v.simplified, v.traditional, v.semantic, v.z_variant,
            s.svg_data
        """

    def _format_row(self, r) -> Optional[Dict[str, Any]]:
        """将数据库行转换为字典，并在包含压缩 SVG BLOB 时自动解压为 SVG 字符串"""
        if not r:
            return None
        d = dict(r)
        svg_val = d.get("svg_data")
        if svg_val and isinstance(svg_val, bytes):
            try:
                d["svg_data"] = zlib.decompress(svg_val).decode("utf-8")
            except Exception:
                d["svg_data"] = ""
        return d

    def search_by_code(self, code_str: str) -> Optional[Dict[str, Any]]:
        """
        按 Unicode 码位或单字符精确查找 (关联变体谱系与 SVG 矢量数据)
        """
        code_point = _normalize_code_point(code_str)
        if code_point is None:
            return None

        conn = self.get_connection()
        cursor = conn.cursor()
        sql = f"""
            SELECT {self._select_fields()}
            FROM characters c
            LEFT JOIN character_variants v ON c.code_point = v.code_point
            LEFT JOIN character_svgs s ON c.code_point = s.code_point
            WHERE c.code_point = ?
        """
        cursor.execute(sql, (code_point,))
        row = cursor.fetchone()
        return self._format_row(row)

    def search_by_strokes(self, strokes: int, page: int = 1, page_size: int = 50) -> Tuple[int, List[Dict[str, Any]]]:
        """
        按总笔画数单独检索（带分页、变体谱系与 SVG 矢量数据）
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        count_sql = "SELECT count(*) FROM characters c WHERE c.total_strokes = ?"
        cursor.execute(count_sql, (strokes,))
        total_count = cursor.fetchone()[0]

        if total_count == 0:
            return 0, []

        offset = max(0, (page - 1) * page_size)
        query_sql = f"""
            SELECT {self._select_fields()}
            FROM characters c
            LEFT JOIN character_variants v ON c.code_point = v.code_point
            LEFT JOIN character_svgs s ON c.code_point = s.code_point
            WHERE c.total_strokes = ?
            ORDER BY c.code_point ASC
            LIMIT ? OFFSET ?
        """
        cursor.execute(query_sql, (strokes, page_size, offset))
        results = [self._format_row(r) for r in cursor.fetchall()]
        return total_count, results

    def search_by_components(
        self,
        components: List[str],
        strokes: Optional[int] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        无序部件检索（支持总笔画数过滤、分页、变体谱系与 SVG 矢量数据）
        """
        if not components:
            if strokes is not None:
                return self.search_by_strokes(strokes, page=page, page_size=page_size)
            return 0, []

        clean_comps = [c.strip() for c in components if c.strip() and c.strip() not in IDC_CHARS]
        if not clean_comps:
            if strokes is not None:
                return self.search_by_strokes(strokes, page=page, page_size=page_size)
            return 0, []

        conn = self.get_connection()
        cursor = conn.cursor()

        conditions = []
        params = []
        for comp in clean_comps:
            comp_sql, comp_param = _token_match(comp)
            conditions.append(comp_sql)
            params.append(comp_param)

        if strokes is not None:
            conditions.append("c.total_strokes = ?")
            params.append(strokes)

        where_sql = " AND ".join(conditions)

        # 统计总命中数
        count_sql = f"SELECT count(*) FROM characters c WHERE {where_sql}"
        cursor.execute(count_sql, params)
        total_count = cursor.fetchone()[0]

        if total_count == 0:
            return 0, []

        offset = max(0, (page - 1) * page_size)
        query_sql = f"""
            SELECT {self._select_fields()}
            FROM characters c
            LEFT JOIN character_variants v ON c.code_point = v.code_point
            LEFT JOIN character_svgs s ON c.code_point = s.code_point
            WHERE {where_sql}
            ORDER BY c.total_strokes ASC, c.code_point ASC
            LIMIT ? OFFSET ?
        """
        cursor.execute(query_sql, params + [page_size, offset])
        results = [self._format_row(r) for r in cursor.fetchall()]
        return total_count, results

    def search_by_joint_components(
        self,
        components: List[str],
        strokes: Optional[int] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        连写免空格合字检索（拼字直搜）
        输入 "入水" -> 优先置顶精确合字 "汆" (⿱入水)，次优反向组合 "𣱸" (⿱水入)，再列出包含这些部件的派生字
        输入 "车俞" -> 优先置顶 "输" (⿰车俞)
        输入 "木寸" -> 优先置顶 "村" (⿰木寸)
        输入 "木木木" -> 优先置顶 "森"
        输入 "火火火火" -> 优先置顶 "燚"
        """
        clean_comps = [c.strip() for c in components if c.strip() and c.strip() not in IDC_CHARS]
        if not clean_comps:
            return 0, []

        conn = self.get_connection()
        cursor = conn.cursor()

        # 1. 检查是否为同字连续叠字（如 "木木木" -> 森, "火火火火" -> 燚, "牛牛牛" -> 犇）
        repeat_target_char = None
        if len(clean_comps) >= 2 and len(set(clean_comps)) == 1:
            base_char = clean_comps[0]
            cnt = len(clean_comps)
            if cnt == 2:
                repeat_target_char = DOUBLE_REPEAT_MAP.get(base_char)
            elif cnt == 3:
                repeat_target_char = TRIPLE_REPEAT_MAP.get(base_char)
            elif cnt >= 4:
                repeat_target_char = QUAD_REPEAT_MAP.get(base_char)

        # 2. 构建 WHERE 条件（若同字重复只查单个字符，并支持常见部首等价扩展，如 人/亻，水/氵）
        conditions = []
        where_params = []
        comps_to_check = list(set(clean_comps)) if len(set(clean_comps)) == 1 else clean_comps

        for comp in comps_to_check:
            vars_list = COMPONENT_VARIANTS.get(comp, [comp])
            sub_conds = []
            for v in vars_list:
                sub_sql, sub_param = _token_match(v)
                sub_conds.append(sub_sql)
                where_params.append(sub_param)
            conditions.append("(" + " OR ".join(sub_conds) + ")")

        where_sql = " AND ".join(conditions)

        # 若命中了特定叠字（如“燚”），将其直接并入候选集，防止其因 IDS 递归层级差异被漏查
        if repeat_target_char:
            where_sql = f"({where_sql}) OR c.character = ?"
            where_params.append(repeat_target_char)

        if strokes is not None:
            where_sql = f"({where_sql}) AND c.total_strokes = ?"
            where_params.append(strokes)

        # 统计匹配总数
        count_sql = f"SELECT count(*) FROM characters c WHERE {where_sql}"
        cursor.execute(count_sql, where_params)
        total_count = cursor.fetchone()[0]

        if total_count == 0:
            return 0, []

        # 3. 智能权重构建（直构置顶 + 顺向优先 + 纯合字优先）
        rank_cases = []
        rank_params = []

        # (a) 叠字目标字符绝对置顶（Rank 0）
        if repeat_target_char:
            rank_cases.append("WHEN c.character = ? THEN 0")
            rank_params.append(repeat_target_char)

        # (b) 顺向直接合字（Rank 1）与 逆向直接合字（Rank 2）
        if len(clean_comps) >= 2 and len(set(clean_comps)) > 1:
            p1, p2 = clean_comps[0], clean_comps[1]
            v1_list = COMPONENT_VARIANTS.get(p1, [p1])
            v2_list = COMPONENT_VARIANTS.get(p2, [p2])

            sub_forward = []
            for v1 in v1_list:
                for v2 in v2_list:
                    sub_forward.append("c.ids_direct LIKE ? ESCAPE '\\'")
                    rank_params.append(f"%{_escape_like(v1)}%{_escape_like(v2)}%")
            if sub_forward:
                rank_cases.append(f"WHEN {' OR '.join(sub_forward)} THEN 1")

            sub_backward = []
            for v2 in v2_list:
                for v1 in v1_list:
                    sub_backward.append("c.ids_direct LIKE ? ESCAPE '\\'")
                    rank_params.append(f"%{_escape_like(v2)}%{_escape_like(v1)}%")
            if sub_backward:
                rank_cases.append(f"WHEN {' OR '.join(sub_backward)} THEN 2")

        if rank_cases:
            case_sql = f"(CASE {' '.join(rank_cases)} ELSE 3 END)"
            order_clause = f"ORDER BY {case_sql} ASC, LENGTH(c.ids_tokens) ASC, c.total_strokes ASC, c.code_point ASC"
        else:
            order_clause = "ORDER BY LENGTH(c.ids_tokens) ASC, c.total_strokes ASC, c.code_point ASC"

        offset = max(0, (page - 1) * page_size)
        query_sql = f"""
            SELECT {self._select_fields()}
            FROM characters c
            LEFT JOIN character_variants v ON c.code_point = v.code_point
            LEFT JOIN character_svgs s ON c.code_point = s.code_point
            WHERE {where_sql}
            {order_clause}
            LIMIT ? OFFSET ?
        """
        cursor.execute(query_sql, where_params + rank_params + [page_size, offset])
        results = [self._format_row(r) for r in cursor.fetchall()]
        return total_count, results

    def search_by_ids_pattern(
        self,
        pattern: str,
        strokes: Optional[int] = None,
        page: int = 1,
        page_size: int = 50,
        hanzi_only: bool = False
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        IDS 模式通配符匹配（支持总笔画数过滤、分页、变体谱系与 SVG 矢量数据）

        hanzi_only: 附加「有笔画数」过滤，剔除 α ℓ ① 等非汉字占位条目。
        仅用于纯通配查询（* / ?），带具体结构的模式本身不会命中这些条目。
        """
        clean_pat = pattern.strip()
        conn = self.get_connection()
        cursor = conn.cursor()

        # 统一走 _like_pattern：先转义用户输入里的 LIKE 元字符，再映射 ? / * 语法
        sql_like = _like_pattern(clean_pat)

        conditions = ["c.ids_direct LIKE ? ESCAPE '\\'"]
        params = [sql_like]

        # 与 SEO 字表页同一判据：total_strokes 为 NULL 的即非汉字占位条目
        if hanzi_only:
            conditions.append("c.total_strokes IS NOT NULL")

        if strokes is not None:
            conditions.append("c.total_strokes = ?")
            params.append(strokes)

        where_clause = " AND ".join(conditions)

        count_sql = f"SELECT count(*) FROM characters c WHERE {where_clause}"
        cursor.execute(count_sql, params)
        total_count = cursor.fetchone()[0]

        if total_count == 0:
            return 0, []

        offset = max(0, (page - 1) * page_size)
        query_sql = f"""
            SELECT {self._select_fields()}
            FROM characters c
            LEFT JOIN character_variants v ON c.code_point = v.code_point
            LEFT JOIN character_svgs s ON c.code_point = s.code_point
            WHERE {where_clause}
            ORDER BY c.total_strokes ASC, c.code_point ASC
            LIMIT ? OFFSET ?
        """
        cursor.execute(query_sql, params + [page_size, offset])
        results = [self._format_row(r) for r in cursor.fetchall()]
        return total_count, results

    def search_by_filters(
        self,
        radical: Optional[int] = None,
        min_strokes: Optional[int] = None,
        max_strokes: Optional[int] = None,
        block_name: Optional[str] = None,
        pinyin: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        多维属性筛选（带分页、变体谱系与 SVG 矢量数据）
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        conditions = []
        params = []

        if radical is not None:
            conditions.append("c.radical = ?")
            params.append(radical)

        if min_strokes is not None:
            conditions.append("c.total_strokes >= ?")
            params.append(min_strokes)

        if max_strokes is not None:
            conditions.append("c.total_strokes <= ?")
            params.append(max_strokes)

        if block_name:
            conditions.append("c.block_name LIKE ? ESCAPE '\\'")
            params.append(f"%{_escape_like(block_name)}%")

        if pinyin:
            # 库内 pinyin 带声调存储（wáng），用户输入无调拼音（wang）：
            # 展开声调变体逐个 LIKE 匹配，否则拼音检索永远返回 0 结果
            variants = _pinyin_variants(pinyin.strip())
            pinyin_conds = [f"c.pinyin LIKE ? ESCAPE '\\'" for _ in variants]
            conditions.append("(" + " OR ".join(pinyin_conds) + ")")
            params.extend(f"%{_escape_like(v)}%" for v in variants)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        count_sql = f"SELECT count(*) FROM characters c {where_clause}"
        cursor.execute(count_sql, params)
        total_count = cursor.fetchone()[0]

        if total_count == 0:
            return 0, []

        offset = max(0, (page - 1) * page_size)
        query_sql = f"""
            SELECT {self._select_fields()}
            FROM characters c
            LEFT JOIN character_variants v ON c.code_point = v.code_point
            LEFT JOIN character_svgs s ON c.code_point = s.code_point
            {where_clause}
            ORDER BY c.total_strokes ASC, c.code_point ASC
            LIMIT ? OFFSET ?
        """
        cursor.execute(query_sql, params + [page_size, offset])
        results = [self._format_row(r) for r in cursor.fetchall()]
        return total_count, results

    def get_character_family(self, char_or_hex: str) -> Optional[Dict[str, Any]]:
        """
        【汉字血缘探针】
        分析一个字符的完整血缘家族：
        1. 根源父辈（直接构成它的部件）
        2. 自身本尊及变体流变（简、繁、异体、古体）
        3. 宗族后裔（所有以该字符为构件繁衍出的汉字列表）
        """
        root_char = self.search_by_code(char_or_hex)
        if not root_char:
            return None

        char = root_char["character"]
        cp = root_char["code_point"]

        conn = self.get_connection()
        cursor = conn.cursor()

        # 1. 查找上游直接父部件（过滤非汉字占位符如 ① ② α ℓ △ 等）
        # 注：ids_tokens 可能为 NULL（无 IDS 数据的字），先做空值兜底再拆分
        raw_tokens = [t.strip() for t in (root_char["ids_tokens"] or "").split(",")
                      if t.strip() and t.strip() != char]
        parent_items = []
        for p in raw_tokens:
            if len(p) != 1:
                # 多字符 token（如抽象部件标记）无法定位单一码位，仅作占位展示
                parent_items.append({
                    "character": p,
                    "hex_code": None,
                    "pinyin": None,
                    "total_strokes": None
                })
                continue
            p_cp = ord(p)
            # 过滤非标准汉字及非部首占位符（如带圈数字 0x2460~0x24FF，ASCII/符号 < 0x2E80 等）
            if p_cp < 0x2E80 or (0x2460 <= p_cp <= 0x24FF) or (0x3040 <= p_cp <= 0x30FF):
                continue

            cursor.execute("SELECT character, hex_code, pinyin, total_strokes FROM characters WHERE code_point = ? LIMIT 1", (p_cp,))
            p_row = cursor.fetchone()
            if p_row:
                parent_items.append({
                    "character": p_row[0],
                    "hex_code": p_row[1],
                    "pinyin": p_row[2],
                    "total_strokes": p_row[3]
                })
            else:
                parent_items.append({
                    "character": p,
                    "hex_code": f"U+{p_cp:04X}",
                    "pinyin": None,
                    "total_strokes": None
                })

        # 2. 查找下游宗族衍生字（以此字为偏旁或部件的汉字，按笔画升序取前 48 个）
        desc_sql, desc_param = _token_match(char)
        # 先单独统计真实总数（LIMIT 只截断列表，不能拿列表长度当总数）
        cursor.execute(
            f"SELECT count(*) FROM characters c WHERE {desc_sql} AND c.code_point != ?",
            (desc_param, cp))
        descendants_total = cursor.fetchone()[0]

        cursor.execute(f"""
            SELECT {self._select_fields()}
            FROM characters c
            LEFT JOIN character_variants v ON c.code_point = v.code_point
            LEFT JOIN character_svgs s ON c.code_point = s.code_point
            WHERE {desc_sql} AND c.code_point != ?
            ORDER BY c.total_strokes ASC, c.code_point ASC
            LIMIT 48
        """, (desc_param, cp))
        descendants = [self._format_row(r) for r in cursor.fetchall()]

        return {
            "root": root_char,
            "parents": parent_items,
            "descendants_count": descendants_total,
            "descendants": descendants
        }

    def smart_search(
        self,
        query: str = "",
        strokes: Optional[int] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        万能智能分流入口 (支持总笔画数单独检索与任意检索模式组合)
        """
        q = query.strip() if query else ""
        page = max(1, page)
        page_size = max(1, min(page_size, 200))

        # 1. 检索框为空的情况
        if not q:
            if strokes is not None:
                total, results = self.search_by_strokes(strokes, page=page, page_size=page_size)
                return {
                    "mode": "strokes_only",
                    "strokes": strokes,
                    "page": page,
                    "page_size": page_size,
                    "total_count": total,
                    "total_pages": _total_pages(total, page_size),
                    "results": results
                }
            return {
                "mode": "empty",
                "page": page,
                "page_size": page_size,
                "total_count": 0,
                "total_pages": 0,
                "results": []
            }

        # 2. 检查是否为显式码位字符串 (如 U+690D, 0x690D 或 4-6 位含字母十六进制)
        #    纯字母的裸十六进制（如 face -> U+FACE）不在此时劫持：
        #    它与拼音输入形状冲突（拼音检索优先），待拼音无结果后再回退码位。
        looks_bare_hex = bool(len(q) in (4, 5, 6) and re.fullmatch(r"[0-9A-Fa-f]{4,6}", q))
        is_explicit_code = (
            q.upper().startswith("U+") or
            q.lower().startswith("0x") or
            (looks_bare_hex and not q.isalpha())   # 混合数字字母（如 690D）不可能是拼音，直接按码位
        )

        if is_explicit_code:
            exact = self.search_by_code(q)
            if exact:
                if strokes is not None and exact.get("total_strokes") != strokes:
                    return {
                        "mode": "exact_code_and_strokes",
                        "query": q,
                        "strokes": strokes,
                        "page": 1,
                        "page_size": page_size,
                        "total_count": 0,
                        "total_pages": 0,
                        "results": []
                    }
                return {
                    "mode": "exact_code",
                    "query": q,
                    "strokes": strokes,
                    "page": 1,
                    "page_size": page_size,
                    "total_count": 1,
                    "total_pages": 1,
                    "results": [exact]
                }

        # 3. 如果是单个非码位汉字，且未指定笔画数，优先直查该字；若指定了笔画数，则视为偏旁部件组合检索
        if len(q) == 1 and not q.isdigit() and strokes is None:
            exact = self.search_by_code(q)
            if exact:
                return {
                    "mode": "exact_code",
                    "query": q,
                    "page": 1,
                    "page_size": page_size,
                    "total_count": 1,
                    "total_pages": 1,
                    "results": [exact]
                }

        # 4. 结构别名归一化处理 (如 "左右 木" -> "⿰木")
        normalized_q = q
        for alias, idc in STRUCT_ALIASES:
            if alias in normalized_q:
                normalized_q = re.sub(rf"{alias}\s*", idc, normalized_q)

        # 5. IDS 结构模式匹配 (如 "⿰木*", "⿱艹田")
        has_idc = any(c in IDC_CHARS for c in normalized_q)
        if has_idc or ("*" in normalized_q or "?" in normalized_q):
            clean_idc_query = "".join(normalized_q.split())
            # 纯通配查询（* / ?，不含任何具体部件）会命中 α ℓ ① 等非汉字占位条目，
            # 默认首页检索就是这种场景，必须过滤，否则首屏全是垃圾字符
            only_wildcards = bool(clean_idc_query) and not any(ch not in "*?" for ch in clean_idc_query)
            total, results = self.search_by_ids_pattern(
                clean_idc_query, strokes=strokes, page=page, page_size=page_size,
                hanzi_only=only_wildcards)
            mode_name = "ids_pattern_and_strokes" if strokes is not None else "ids_pattern"
            return {
                "mode": mode_name,
                "query": clean_idc_query,
                "strokes": strokes,
                "page": page,
                "page_size": page_size,
                "total_count": total,
                "total_pages": _total_pages(total, page_size),
                "results": results
            }

        # 6. 多部件交集检索 (用空格或逗号分隔，如 "车 俞", "木 日")
        parts = [p for p in re.split(r"[\s,+，]+", q) if p]
        if len(parts) > 1:
            total, results = self.search_by_components(parts, strokes=strokes, page=page, page_size=page_size)
            mode_name = "components_and_strokes" if strokes is not None else "components_intersection"
            return {
                "mode": mode_name,
                "components": parts,
                "strokes": strokes,
                "page": page,
                "page_size": page_size,
                "total_count": total,
                "total_pages": _total_pages(total, page_size),
                "results": results
            }

        # 7. 纯拼音检索 (要求纯英文字符)
        if q.isascii() and q.isalpha():
            total, results = self.search_by_filters(
                pinyin=q,
                min_strokes=strokes,
                max_strokes=strokes,
                page=page,
                page_size=page_size
            )
            # 拼音无结果且输入恰为 4~6 位纯字母十六进制（如 face）时，
            # 回退为码位直查（U+FACE），避免裸 hex 抢先劫持吞掉拼音检索
            if total == 0 and looks_bare_hex:
                exact = self.search_by_code(q)
                if exact and (strokes is None or exact.get("total_strokes") == strokes):
                    return {
                        "mode": "exact_code",
                        "query": q,
                        "strokes": strokes,
                        "page": 1,
                        "page_size": page_size,
                        "total_count": 1,
                        "total_pages": 1,
                        "results": [exact]
                    }
            mode_name = "pinyin_and_strokes" if strokes is not None else "pinyin"
            return {
                "mode": mode_name,
                "query": q,
                "strokes": strokes,
                "page": page,
                "page_size": page_size,
                "total_count": total,
                "total_pages": _total_pages(total, page_size),
                "results": results
            }

        # 7.5 连写免空格合字检索 (如 "入水" -> 汆, "车俞" -> 输, "木寸" -> 村, "木木木" -> 森, "火火火火" -> 燚)
        if 2 <= len(q) <= 6 and all(_is_chinese_char(c) for c in q):
            clean_parts = list(q)
            total, results = self.search_by_joint_components(
                clean_parts,
                strokes=strokes,
                page=page,
                page_size=page_size
            )
            if total > 0:
                mode_name = "joint_components_and_strokes" if strokes is not None else "joint_components"
                return {
                    "mode": mode_name,
                    "query": q,
                    "components": clean_parts,
                    "strokes": strokes,
                    "page": page,
                    "page_size": page_size,
                    "total_count": total,
                    "total_pages": _total_pages(total, page_size),
                    "results": results
                }

        # 8. 单部件检索 (或包含笔画过滤的部件检索)
        total, results = self.search_by_components([q], strokes=strokes, page=page, page_size=page_size)
        mode_name = "component_and_strokes" if strokes is not None else "component_lookup"
        return {
            "mode": mode_name,
            "component": q,
            "strokes": strokes,
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": _total_pages(total, page_size),
            "results": results
        }

    def get_svg_by_code_param(self, code_param: str) -> str:
        """
        按码位/单字符参数取 SVG 矢量字符串（供 /api/svg 使用）。

        码位解析统一走 _normalize_code_point，确保与 search_by_code 结果一致
        （历史上 handlers 自带一套解析，导致 q=1234 与 code=1234 返回不同字符）。
        """
        cp = _normalize_code_point(code_param)
        if cp is None:
            return ""

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT svg_data FROM character_svgs WHERE hex_code = ? OR code_point = ?",
            (f"U+{cp:04X}", cp),
        )
        row = cursor.fetchone()
        if not row or not row[0]:
            return ""

        val = row[0]
        if isinstance(val, bytes):
            try:
                return zlib.decompress(val).decode("utf-8")
            except Exception:
                return ""
        return val

    def get_alphabet_stats(self) -> Dict[str, Any]:
        """
        统计字库规模，用于 SEO 字表页的分页规划与首页数据展示。
        只读聚合查询，结果极轻量。
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM characters")
        total = cursor.fetchone()[0]
        cursor.execute(
            "SELECT count(*) FROM characters WHERE total_strokes BETWEEN ? AND ?",
            (MIN_STROKES, MAX_STROKES),
        )
        simple = cursor.fetchone()[0]
        return {"total": total, "simple": simple, "extended": total - simple}

    def get_stroke_distribution(self) -> List[Tuple[int, int]]:
        """
        各笔画数（1~64）的汉字数量分布，供字表页生成可读的规模说明。
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT total_strokes, count(*) FROM characters
               WHERE total_strokes BETWEEN ? AND ?
               GROUP BY total_strokes ORDER BY total_strokes ASC""",
            (MIN_STROKES, MAX_STROKES),
        )
        return [(row[0], row[1]) for row in cursor.fetchall()]

    def get_chars_for_seo(
        self,
        page: int = 1,
        page_size: int = 60,
        stroke: Optional[int] = None,
        radical: Optional[int] = None
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        字表落地页数据源：按笔画 / 部首分页返回汉字基础信息。

        与用户检索接口的刻意区别：
        - 不返回 svg_data —— 避免响应体膨胀，爬虫也不需要矢量图
        - 只取 SEO 需要的少数字段，减少 JSON 体积
        注意：这里的「页」是给爬虫看的落地页，必须只输出真正的汉字。
        字库中混有 α ℓ ① ① 等非汉字条目（total_strokes 为 NULL），
        它们对 SEO 没有价值且属于垃圾内容，故强制过滤掉。
        """
        conditions = ["c.total_strokes IS NOT NULL"]
        params: List[Any] = []
        if stroke is not None:
            conditions.append("c.total_strokes = ?")
            params.append(stroke)
        if radical is not None:
            conditions.append("c.radical = ?")
            params.append(radical)
        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT count(*) FROM characters c {where_sql}", params)
        total = cursor.fetchone()[0]

        offset = max(0, (page - 1) * page_size)
        # 排序策略：笔画 -> 分区 -> 码位。
        # 分区排序不可省略：扩展 A 区(U+3400~U+4DBF)码位低于基础区(U+4E00 起)，
        # 只按码位排会让生僻字霸占首屏（3 画页曾是清一色「㐃㐄㐇」），
        # 而用户查字表期望先看到常用字。
        cursor.execute(f"""
            SELECT c.code_point, c.hex_code, c.character, c.pinyin,
                   c.total_strokes, c.radical, c.ids_direct, c.block_name
            FROM characters c
            {where_sql}
            ORDER BY c.total_strokes ASC,
                     CASE WHEN c.code_point BETWEEN 0x4E00 AND 0x9FFF THEN 0
                          WHEN c.code_point BETWEEN 0x3400 AND 0x4DBF THEN 1
                          ELSE 2 END ASC,
                     c.code_point ASC
            LIMIT ? OFFSET ?
        """, params + [page_size, offset])
        rows = cursor.fetchall()
        results = [
            {
                "character": r[2],
                "hex_code": r[1],
                "pinyin": r[3] or "",
                "strokes": r[4],
                "radical": r[5],
                "ids": r[6] or "",
                "block": r[7] or "",
            }
            for r in rows
        ]
        return total, results

    def get_seo_char_detail(self, code_str: str, sibling_limit: int = 24) -> Optional[Dict[str, Any]]:
        """
        单字详情页数据源（对应 /char/<汉字>）。

        除单字自身档案外，还返回「同部首」「同笔画」两组关联字：
        它们既是页面的实质内容，也是把十万张详情页串成内链网络的关键 ——
        有了这张网，爬虫沿链接就能持续深入，不必只依赖 sitemap。

        与用户检索接口的区别同 get_chars_for_seo：不取 svg_data，
        避免响应体膨胀（详情页字形按需走 /api/svg）。
        """
        code_point = _normalize_code_point(code_str)
        if code_point is None:
            return None

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.code_point, c.hex_code, c.character, c.block_name,
                   c.ids_direct, c.ids_tokens, c.radical, c.residual_strokes,
                   c.total_strokes, c.pinyin,
                   v.simplified, v.traditional, v.semantic, v.z_variant
            FROM characters c
            LEFT JOIN character_variants v ON c.code_point = v.code_point
            WHERE c.code_point = ? AND c.total_strokes IS NOT NULL
        """, (code_point,))
        row = cursor.fetchone()
        # total_strokes IS NOT NULL 已滤掉 α ℓ ① 这类占位条目，
        # 再加一道 CJK 区间校验做双保险，绝不给垃圾条目生成收录页
        if not row or not _is_chinese_char(row[2]):
            return None

        detail = {
            "code_point": row[0],
            "hex_code": row[1] or f"U+{code_point:04X}",
            "character": row[2],
            "block_name": row[3] or "",
            "ids_direct": row[4] or "",
            "ids_tokens": row[5] or "",
            "radical": row[6],
            "residual_strokes": row[7],
            "total_strokes": row[8],
            "pinyin": row[9] or "",
            "simplified": row[10] or "",
            "traditional": row[11] or "",
            "semantic": row[12] or "",
            "z_variant": row[13] or "",
        }
        detail["radical_char"] = _radical_to_char(row[6])

        def _siblings(field: str, value) -> List[Dict[str, Any]]:
            """
            取同部首 / 同笔画的关联字。

            排序把基础区(U+4E00~)放最前、扩展 A 其次、其余最后：
            常用字优先露脸，页面内链也就优先导向真正有人搜的字。
            两个字段都有索引(idx_radical / idx_strokes)，单次查询毫秒级。

            field 只允许白名单取值 —— 它会被拼进 SQL 的列名位置，
            虽然调用方只传字面量，仍显式拦一道，杜绝将来被外部输入污染。
            """
            if value is None or field not in ("radical", "total_strokes"):
                return []
            cursor.execute(f"""
                SELECT c.character, c.hex_code, c.pinyin, c.total_strokes
                FROM characters c
                WHERE c.{field} = ? AND c.total_strokes IS NOT NULL AND c.code_point != ?
                ORDER BY CASE WHEN c.code_point BETWEEN 0x4E00 AND 0x9FFF THEN 0
                              WHEN c.code_point BETWEEN 0x3400 AND 0x4DBF THEN 1
                              ELSE 2 END ASC,
                         c.code_point ASC
                LIMIT ?
            """, (value, code_point, sibling_limit))
            return [
                {"character": r[0], "hex_code": r[1] or "",
                 "pinyin": r[2] or "", "strokes": r[3]}
                for r in cursor.fetchall()
            ]

        detail["siblings_by_radical"] = _siblings("radical", row[6])
        detail["siblings_by_stroke"] = _siblings("total_strokes", row[8])
        return detail

    def get_seo_indexable_chars(self, min_cp: int = 0x4E00, max_cp: int = 0x9FFF) -> str:
        """
        列出指定码位区间内全部可收录汉字，拼成一个字符串返回（供 sitemap 使用）。

        返回拼接后的字符串而非 dict 列表：2 万个字连起来只占约 60KB，
        等价的 dict 列表则要吃掉好几 MB —— 生产机只有 1.7G 内存，这里省一道。
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT character FROM characters
            WHERE code_point BETWEEN ? AND ? AND total_strokes IS NOT NULL
            ORDER BY code_point ASC
        """, (min_cp, max_cp))
        return "".join(r[0] for r in cursor.fetchall() if r[0])

    def get_component_svg(self, char_or_comp: str) -> Optional[str]:
        """
        获取单字或部件的解压后 SVG 矢量字符串。
        优先按字符查询，若未命中则按 Unicode 码位查询。
        """
        if not char_or_comp:
            return None
        char = char_or_comp.strip()
        if not char:
            return None

        conn = self.get_connection()
        cursor = conn.cursor()

        # 1. 直接按字符对应码位查询
        code_point = ord(char[0]) if len(char) == 1 else None

        if code_point is not None:
            cursor.execute("""
                SELECT s.svg_data 
                FROM character_svgs s
                WHERE s.code_point = ?
            """, (code_point,))
            row = cursor.fetchone()
            if row and row[0]:
                try:
                    return zlib.decompress(row[0]).decode('utf-8')
                except Exception:
                    pass

        # 2. 从 characters 表联合查询（兼容部首字符或变体）
        cursor.execute("""
            SELECT s.svg_data
            FROM characters c
            JOIN character_svgs s ON c.code_point = s.code_point
            WHERE c.character = ? OR c.code_point = ?
            LIMIT 1
        """, (char, code_point))
        row = cursor.fetchone()
        if row and row[0]:
            try:
                return zlib.decompress(row[0]).decode('utf-8')
            except Exception:
                pass
        return None

    def _get_component_svgs_batch(self, chars: List[str]) -> Dict[int, str]:
        """
        批量获取部件 SVG：一条 IN 查询替代逐部件最多两条查询（N+1 修复）。
        返回 {码位: svg字符串}；未命中或解压失败的码位不出现在结果里，
        由调用方决定是否走 get_component_svg 的变体回退逻辑。
        """
        cps = sorted({ord(c[0]) for c in chars if c})
        if not cps:
            return {}

        out: Dict[int, str] = {}
        conn = self.get_connection()
        cursor = conn.cursor()
        # IN 参数分块，避免超长 SQL（SQLite 变量上限默认 999）
        for i in range(0, len(cps), 200):
            chunk = cps[i:i + 200]
            placeholders = ",".join("?" * len(chunk))
            cursor.execute(
                f"SELECT code_point, svg_data FROM character_svgs WHERE code_point IN ({placeholders})",
                chunk,
            )
            for cp, blob in cursor.fetchall():
                if not blob:
                    continue
                try:
                    out[cp] = zlib.decompress(blob).decode("utf-8") if isinstance(blob, bytes) else blob
                except Exception:
                    pass
        return out

    def disassemble_char(self, char: str) -> Dict[str, Any]:
        """
        拆解输入字符为乐高部件积木。
        返回原字符元数据、结构、直接部件、以及各部件的 SVG 矢量数据。
        """
        char = char.strip()
        if not char:
            return {"error": "请输入有效字符"}

        target = char[0]
        code_point = ord(target)
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT c.character, c.hex_code, c.ids_direct, c.ids_tokens, c.radical, c.total_strokes, c.pinyin, s.svg_data
            FROM characters c
            LEFT JOIN character_svgs s ON c.code_point = s.code_point
            WHERE c.code_point = ?
        """, (code_point,))
        row = cursor.fetchone()

        # 若不在数据库中，提供兜底对象
        if not row:
            return {
                "character": target,
                "hex_code": f"U+{code_point:04X}",
                "ids_direct": target,
                "pinyin": "",
                "total_strokes": None,
                "svg_data": None,
                "components": [{"char": target, "hex_code": f"U+{code_point:04X}", "svg_data": None}]
            }

        c_char, hex_code, ids_direct, ids_tokens, radical, total_strokes, pinyin, raw_svg = row

        full_svg = None
        if raw_svg:
            try:
                full_svg = zlib.decompress(raw_svg).decode('utf-8')
            except Exception:
                pass

        # 解析部件列表：与 clean_direct 同策略，只保留单字汉字 / 部首，过滤 IDS 噪声标记
        tokens = [
            t.strip() for t in (ids_tokens or "").split(",")
            if t.strip() and (len(t.strip()) == 1 and (_is_chinese_char(t.strip()) or t.strip().isdigit()))
        ]

        clean_direct = []
        if ids_direct:
            for ch in ids_direct:
                # 白名单策略：只保留真正的汉字 / CJK 部首，其余一律丢弃。
                # 库里除 IDC 操作符外还混有大量非汉字标记（A H X α ℓ ①②③ △ い よ り コ 等），
                # 它们不是可拼装部件，若原样透出会被前端当作积木渲染成噪声方块。
                if ch in IDC_CHARS or ch.isspace():
                    continue
                if _is_chinese_char(ch) or ch.isdigit():
                    if ch not in clean_direct:
                        clean_direct.append(ch)

        # 合并去重候选部件
        all_comp_chars = []
        for ch in clean_direct:
            if ch not in all_comp_chars:
                all_comp_chars.append(ch)
        for t in tokens:
            if t not in all_comp_chars:
                all_comp_chars.append(t)
        if target not in all_comp_chars:
            all_comp_chars.append(target)

        # 批量获取部件 SVG 矢量（一条 IN 查询，替代原先每部件最多 2 条的 N+1）
        svg_map = self._get_component_svgs_batch(all_comp_chars)
        components = []
        for comp_char in all_comp_chars:
            comp_cp = ord(comp_char[0])
            comp_svg = svg_map.get(comp_cp)
            if comp_svg is None:
                # 主表未命中（部首变体等罕见情况）才走带回退的单查
                comp_svg = self.get_component_svg(comp_char)
            components.append({
                "char": comp_char,
                "hex_code": f"U+{comp_cp:04X}",
                "svg_data": comp_svg
            })

        return {
            "character": target,
            "hex_code": hex_code,
            "ids_direct": ids_direct,
            "pinyin": pinyin,
            "total_strokes": total_strokes,
            "svg_data": full_svg,
            "components": components
        }

    @lru_cache(maxsize=1)
    def get_preset_radicals(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取预置分类优质汉字部件/部首积木库，供汉字乐高直接取用。

        结果常驻缓存：预设库是静态数据，每次请求重复跑约 70 次 SQL + 70 次 zlib 解压属无谓开销。
        数据库为只读且进程生命周期内不变，缓存不会过期。
        """
        presets = {
            "自然天地": ["日", "月", "水", "氵", "火", "灬", "木", "土", "金", "钅", "石", "山", "雨", "风", "田", "气"],
            "人体生灵": ["人", "亻", "手", "扌", "心", "忄", "口", "目", "足", "女", "子", "耳", "舌", "身", "犭", "鸟", "鱼", "虫", "马"],
            "建筑器物": ["门", "宀", "广", "穴", "车", "舟", "刀", "刂", "弓", "矢", "戈", "斤", "衣", "衤", "巾", "皿", "鼎", "缶"],
            "形意框架": ["囗", "辶", "走", "阝", "彡", "页", "竹", "艹", "禾", "米", "聿", "酉", "示", "礻", "言", "讠", "食", "饣"]
        }

        result = {}
        for category, char_list in presets.items():
            cat_items = []
            for ch in char_list:
                svg = self.get_component_svg(ch)
                cat_items.append({
                    "char": ch,
                    "hex_code": f"U+{ord(ch[0]):04X}",
                    "svg_data": svg
                })
            result[category] = cat_items
        return result

