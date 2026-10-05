"""
汉字与 Unicode 核心检索引擎 (带分页 + 变体流变 + 血缘探针)
支持：码位直查、多部件无序交集、IDS 模式匹配、结构别名、简繁异体字流变、汉字血缘衍生树
"""

import math
import re
import sqlite3
import threading
import zlib
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


def _token_match(comp: str) -> Tuple[str, str]:
    """
    生成对 ids_tokens（逗号分隔部件列表）的整词匹配 (SQL 片段, 参数)。
    通过给首尾补逗号并对 token 间空白做归一化，确保只命中完整的部件 token，
    避免裸 LIKE '%x%' 造成的跨 token 子串误命中（如搜"丁"误中"町"的"田"）。
    """
    sql = "(',' || REPLACE(c.ids_tokens, ' ', '') || ',') LIKE ? ESCAPE '\\'"
    param = f"%,{_escape_like(comp)},%"
    return sql, param


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



class HanziEngine:
    """汉字多模态检索引擎 (全功能增强版)"""

    def __init__(self, db_path: str = "data/hanzi.db"):
        self.db_path = db_path
        self._local = threading.local()

    def get_connection(self) -> sqlite3.Connection:
        """
        线程局部连接：配合 ThreadingHTTPServer 每个请求线程独享连接，
        避免多线程共享同一 Connection 造成的游标错乱与递归使用异常。
        引擎只做只读查询，统一开启 query_only 从根本上杜绝写竞争。
        """
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only = 1")
            self._local.conn = conn
        return conn

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
        code_str = code_str.strip()
        code_point = None

        if len(code_str) == 1 and not code_str.isdigit():
            code_point = ord(code_str)
        elif code_str.upper().startswith("U+") or code_str.lower().startswith("0x"):
            hex_part = code_str[2:]
            try:
                code_point = int(hex_part, 16)
            except ValueError:
                return None
        elif (len(code_str) in (4, 5, 6)
              and re.fullmatch(r"[0-9A-Fa-f]{4,6}", code_str) is not None
              and not code_str.isdigit()):
            # 仅 4~6 位且含十六进制字母的才视为裸码位（如 690D）；
            # 纯数字(如 2024)不再误判为 0x2024，落到下方十进制分支
            try:
                code_point = int(code_str, 16)
            except ValueError:
                return None
        elif code_str.isdigit():
            code_point = int(code_str)

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
        raw_query: str,
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
                    sub_forward.append("c.ids_direct LIKE ?")
                    rank_params.append(f"%{_escape_like(v1)}%{_escape_like(v2)}%")
            if sub_forward:
                rank_cases.append(f"WHEN {' OR '.join(sub_forward)} THEN 1")

            sub_backward = []
            for v2 in v2_list:
                for v1 in v1_list:
                    sub_backward.append("c.ids_direct LIKE ?")
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
        page_size: int = 50
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        IDS 模式通配符匹配（支持总笔画数过滤、分页、变体谱系与 SVG 矢量数据）
        """
        clean_pat = pattern.strip()
        conn = self.get_connection()
        cursor = conn.cursor()

        sql_like = clean_pat.replace("?", "_").replace("*", "%")

        conditions = ["c.ids_direct LIKE ?"]
        params = [sql_like]

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
            conditions.append("c.block_name LIKE ?")
            params.append(f"%{block_name}%")

        if pinyin:
            conditions.append("c.pinyin LIKE ?")
            params.append(f"%{pinyin.strip()}%")

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
                    "total_pages": math.ceil(total / page_size) if total > 0 else 0,
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
        is_explicit_code = (
            q.upper().startswith("U+") or
            q.lower().startswith("0x") or
            (len(q) in (4, 5, 6)
             and bool(re.fullmatch(r"[0-9A-Fa-f]{4,6}", q))
             and not q.isdigit())   # 纯数字不劫持，避免吞掉普通数字输入
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
            total, results = self.search_by_ids_pattern(clean_idc_query, strokes=strokes, page=page, page_size=page_size)
            mode_name = "ids_pattern_and_strokes" if strokes is not None else "ids_pattern"
            return {
                "mode": mode_name,
                "query": clean_idc_query,
                "strokes": strokes,
                "page": page,
                "page_size": page_size,
                "total_count": total,
                "total_pages": math.ceil(total / page_size) if total > 0 else 0,
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
                "total_pages": math.ceil(total / page_size) if total > 0 else 0,
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
            mode_name = "pinyin_and_strokes" if strokes is not None else "pinyin"
            return {
                "mode": mode_name,
                "query": q,
                "strokes": strokes,
                "page": page,
                "page_size": page_size,
                "total_count": total,
                "total_pages": math.ceil(total / page_size) if total > 0 else 0,
                "results": results
            }

        # 7.5 连写免空格合字检索 (如 "入水" -> 汆, "车俞" -> 输, "木寸" -> 村, "木木木" -> 森, "火火火火" -> 燚)
        if 2 <= len(q) <= 6 and all(_is_chinese_char(c) for c in q):
            clean_parts = list(q)
            total, results = self.search_by_joint_components(
                clean_parts,
                raw_query=q,
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
                    "total_pages": math.ceil(total / page_size) if total > 0 else 0,
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
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
            "results": results
        }

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

        # 解析部件列表
        tokens = [t.strip() for t in (ids_tokens or "").split(",") if t.strip()]

        clean_direct = []
        if ids_direct:
            for ch in ids_direct:
                if ch not in IDC_CHARS and not ch.isspace() and ch not in "[]GTKVJZ":
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

        # 批量获取部件 SVG 矢量
        components = []
        for comp_char in all_comp_chars:
            comp_svg = self.get_component_svg(comp_char)
            components.append({
                "char": comp_char,
                "hex_code": f"U+{ord(comp_char[0]):04X}",
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

    def get_preset_radicals(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取预置分类优质汉字部件/部首积木库，供汉字乐高直接取用。
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

