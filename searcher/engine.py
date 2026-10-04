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
