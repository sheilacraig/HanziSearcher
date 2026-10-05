"""
字体文件解析与 Unicode 码位提取工具
支持 TTF / OTF / WOFF 格式的 cmap 字符集提取
提供纯 Python 无依赖解析与 fontTools 加速双重保障
"""

import os
import struct
from typing import Set, Tuple

# 单个字体允许解析出的最大码位数封顶。
# 恶意 / 畸形字体可通过大量 segment 放大解析耗时，Format 12 与 Format 4
# 两个分支都必须熔断，否则防护会被绕过。
MAX_CODEPOINTS = 300000

def _iter_cmap_offsets(font_bytes: bytes):
    """
    遍历字体中所有 cmap 子表，产出 (platform_id, encoding_id, 子表绝对偏移) 三元组。

    兼容 TrueType Collection (.ttc)：ttc 头之后是若干「文件内绝对偏移」，
    每个偏移指向一个完整的 sfnt 结构，需逐个解析再合并 cmap。

    关键点：sfnt 表目录里的表偏移是「相对整个文件起点」的绝对偏移。
    即使该sfnt 位于 .ttc 内某个 base 位置，也不能再叠加 base（叠加会导致
    cmap 头读出垃圾子表数，本项目曾因此把微软雅黑解析成 0 码位）。
    """
    if len(font_bytes) < 12:
        return

    def _walk_sfnt(base: int, seen: set):
        """解析 font_bytes[base:] 处的 sfnt 表目录"""
        if base + 12 > len(font_bytes):
            return
        try:
            num_tables = struct.unpack(">H", font_bytes[base + 4:base + 6])[0]
        except struct.error:
            return
        if num_tables == 0 or num_tables > 512:
            return
        offset = base + 12
        for _ in range(num_tables):
            if offset + 16 > len(font_bytes):
                return
            tag, _checksum, tbl_offset, _tbl_length = struct.unpack(
                ">4sIII", font_bytes[offset:offset + 16])
            offset += 16
            if tag != b"cmap":
                continue
            # tbl_offset 已是文件内绝对偏移，不可再叠加 base
            if tbl_offset + 4 > len(font_bytes):
                continue
            try:
                _version, num_subtables = struct.unpack(
                    ">HH", font_bytes[tbl_offset:tbl_offset + 4])
            except struct.error:
                continue
            # 子表数不合理说明偏移基准错误，放弃该 cmap 表而非产出垃圾
            if num_subtables == 0 or num_subtables > 256:
                continue
            sub_off = tbl_offset + 4
            for _ in range(num_subtables):
                if sub_off + 8 > len(font_bytes):
                    return
                pid, eid, st_offset = struct.unpack(">HHI", font_bytes[sub_off:sub_off + 8])
                sub_off += 8
                key = (pid, eid, tbl_offset + st_offset)
                if key in seen:
                    continue
                seen.add(key)
                yield key

    if font_bytes[:4] == b"ttcf":
        # 字体集合：ttcHeader = magic(4) + version(4) + numFonts(4) + 偏移数组
        try:
            num_fonts = struct.unpack(">I", font_bytes[8:12])[0]
        except struct.error:
            return
        if num_fonts == 0 or num_fonts > 1024:
            return
        seen: set = set()
        for i in range(num_fonts):
            pos = 12 + i * 4
            if pos + 4 > len(font_bytes):
                return
            base = struct.unpack(">I", font_bytes[pos:pos + 4])[0]
            yield from _walk_sfnt(base, seen)
    else:
        yield from _walk_sfnt(0, set())


def extract_codepoints_from_bytes(font_bytes: bytes) -> Set[int]:
    """
    纯 Python 二进制解析 TTF / OTF / TTC 字体文件的 cmap 表，提取所支持的所有 Unicode 码位
    无需第三方依赖库，支持 Format 4 (BMP) 与 Format 12 (Full Unicode)
    """
    codepoints: Set[int] = set()

    for _pid, _eid, st_off in _iter_cmap_offsets(font_bytes):
        if st_off + 2 > len(font_bytes):
            continue
        if len(codepoints) > MAX_CODEPOINTS:
            return codepoints
        fmt = struct.unpack(">H", font_bytes[st_off:st_off + 2])[0]

        # Format 12: 32位段式映射 (适用于全 Unicode，包括拓展区)
        if fmt == 12:
            if st_off + 16 > len(font_bytes):
                continue
            try:
                _, _, _length, _lang, n_groups = struct.unpack(">HHIII", font_bytes[st_off:st_off + 16])
            except struct.error:
                continue
            grp_off = st_off + 16
            for _ in range(n_groups):
                # 双重上限：合法码位不超 0x10FFFF；总量封顶防恶意字体声明超长区间导致 CPU 打满
                if grp_off + 12 > len(font_bytes) or len(codepoints) > MAX_CODEPOINTS:
                    break
                start_c, end_c, _start_g = struct.unpack(">III", font_bytes[grp_off:grp_off + 12])
                grp_off += 12
                for cp in range(start_c, min(end_c, 0x10FFFF) + 1):
                    codepoints.add(cp)

        # Format 4: 16位段式映射 (用于 BMP 基本多文种平面)
        elif fmt == 4:
            if st_off + 8 > len(font_bytes):
                continue
            try:
                _, _length, _lang, seg_count_x2 = struct.unpack(">HHHH", font_bytes[st_off:st_off + 8])
            except struct.error:
                continue
            seg_count = seg_count_x2 // 2
            end_off = st_off + 14
            if end_off + seg_count * 2 > len(font_bytes):
                continue
            try:
                end_codes = struct.unpack(f">{seg_count}H", font_bytes[end_off:end_off + seg_count * 2])
                start_off = end_off + seg_count * 2 + 2
                if start_off + seg_count * 2 > len(font_bytes):
                    continue
                start_codes = struct.unpack(f">{seg_count}H", font_bytes[start_off:start_off + seg_count * 2])
                id_delta_off = start_off + seg_count * 2
                if id_delta_off + seg_count * 2 > len(font_bytes):
                    continue
                id_deltas = struct.unpack(f">{seg_count}h", font_bytes[id_delta_off:id_delta_off + seg_count * 2])
            except struct.error:
                continue
            id_range_off = id_delta_off + seg_count * 2

            for i in range(seg_count):
                sc = start_codes[i]
                ec = end_codes[i]
                if ec == 0xFFFF and sc == 0xFFFF:
                    continue
                delta = id_deltas[i]
                ro_pos = id_range_off + i * 2
                if ro_pos + 2 > len(font_bytes):
                    continue
                ro = struct.unpack(">H", font_bytes[ro_pos:ro_pos + 2])[0]
                for cp in range(sc, ec + 1):
                    # 与 Format 12 分支对称的总量熔断，防畸形字体用海量 segment 放大 CPU 消耗
                    if len(codepoints) > MAX_CODEPOINTS:
                        break
                    if ro == 0:
                        gid = (cp + delta) & 0xFFFF
                    else:
                        g_pos = ro_pos + ro + (cp - sc) * 2
                        if g_pos + 2 <= len(font_bytes):
                            gid = struct.unpack(">H", font_bytes[g_pos:g_pos + 2])[0]
                            if gid != 0:
                                gid = (gid + delta) & 0xFFFF
                        else:
                            gid = 0
                    if gid != 0:
                        codepoints.add(cp)

    return codepoints

def _parse_with_fonttools(file_path: str) -> Tuple[str, Set[int]]:
    """
    用 fontTools 解析字体，返回 (字体名称, 码位集合)；不可用时返回 ("", set())。

    支持 TrueType Collection (.ttc)：中文字体（微软雅黑、宋体-简、仿宋等）大量为 .ttc，
    单字体路径会抛 "TTC header contains no version"，必须遍历全部子字体并合并 cmap。
    """
    try:
        from fontTools.ttLib import TTFont, TTCollection
    except ImportError:
        return "", set()

    def _read_one(font, fallback_name: str) -> Tuple[str, Set[int]]:
        """从单个字体对象提取名称与 cmap，失败返回空结果"""
        name = fallback_name
        try:
            cmap = font.getBestCmap()
        except Exception:
            cmap = None
        if not cmap:
            return name, set()
        try:
            name_record = font["name"].getName(1, 3, 1) or font["name"].getName(4, 3, 1)
            if name_record:
                raw_name = name_record.toUnicode()
                # 防御：仅保留可打印字符并限长，防止恶意字体名注入前端展示
                cleaned = "".join(ch for ch in raw_name if ch.isprintable())[:200].strip()
                if cleaned:
                    name = cleaned
        except Exception:
            pass
        return name, set(cmap.keys())

    try:
        # 用 with 管理文件句柄：Windows 下句柄泄漏会导致后续覆盖写入失败
        with open(file_path, "rb") as f:
            try:
                font = TTFont(f)
            except Exception:
                # 单字体解析失败，尝试按字体集合（.ttc）处理
                f.seek(0)
                try:
                    collection = TTCollection(f)
                except Exception:
                    return "", set()

                merged: Set[int] = set()
                primary_name = os.path.basename(file_path)
                for sub_font in collection.fonts:
                    _, cps = _read_one(sub_font, primary_name)
                    merged |= cps
                    if len(merged) > MAX_CODEPOINTS:
                        break
                return primary_name, merged

            name, cps = _read_one(font, os.path.basename(file_path))
            try:
                font.close()
            except Exception:
                pass
            return name, cps
    except Exception:
        return "", set()


def parse_font_file(file_path: str) -> Tuple[str, Set[int]]:
    """
    解析字体文件并返回 (字体名称, 支持的 Unicode 码位集合)
    优先尝试 fontTools（含 .ttc 字体集合），若未安装或解析失败则回退至纯 Python 二进制解析
    """
    font_name, codepoints = _parse_with_fonttools(file_path)
    if codepoints:
        return font_name, codepoints

    # 回退到纯 Python 二进制提取
    with open(file_path, "rb") as f:
        bytes_data = f.read()
    fallback_name = font_name or os.path.basename(file_path)
    return fallback_name, extract_codepoints_from_bytes(bytes_data)
