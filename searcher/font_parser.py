"""
字体文件解析与 Unicode 码位提取工具
支持 TTF / OTF / WOFF 格式的 cmap 字符集提取
提供纯 Python 无依赖解析与 fontTools 加速双重保障
"""

import os
import struct
from typing import Set, Tuple, Optional

def extract_codepoints_from_bytes(font_bytes: bytes) -> Set[int]:
    """
    纯 Python 二进制解析 TTF / OTF 字体文件的 cmap 表，提取所支持的所有 Unicode 码位
    无需第三方依赖库，支持 Format 4 (BMP) 与 Format 12 (Full Unicode)
    """
    if len(font_bytes) < 12:
        return set()

    # 1. 读取 SFNT 头部
    sfnt_version, num_tables = struct.unpack(">4sH", font_bytes[:6])
    
    # 2. 遍历表目录寻找 cmap 表
    cmap_offset = None
    offset = 12
    for _ in range(num_tables):
        if offset + 16 > len(font_bytes):
            break
        tag, checksum, tbl_offset, tbl_length = struct.unpack(">4sIII", font_bytes[offset:offset+16])
        offset += 16
        if tag == b"cmap":
            cmap_offset = tbl_offset
            break

    if cmap_offset is None or cmap_offset + 4 > len(font_bytes):
        return set()

    # 3. 读取 cmap 头部
    version, num_subtables = struct.unpack(">HH", font_bytes[cmap_offset:cmap_offset+4])
    subtable_offsets = []
    sub_off = cmap_offset + 4
    for _ in range(num_subtables):
        if sub_off + 8 > len(font_bytes):
            break
        platform_id, encoding_id, st_offset = struct.unpack(">HHI", font_bytes[sub_off:sub_off+8])
        sub_off += 8
        subtable_offsets.append((platform_id, encoding_id, cmap_offset + st_offset))

    codepoints = set()

    # 4. 遍历子表，优先提取 Format 12 和 Format 4
    for pid, eid, st_off in subtable_offsets:
        if st_off + 2 > len(font_bytes):
            continue
        fmt = struct.unpack(">H", font_bytes[st_off:st_off+2])[0]

        # Format 12: 32位段式映射 (适用于全 Unicode，包括拓展区)
        if fmt == 12:
            if st_off + 16 > len(font_bytes):
                continue
            _, _, length, lang, n_groups = struct.unpack(">HHIII", font_bytes[st_off:st_off+16])
            grp_off = st_off + 16
            for _ in range(n_groups):
                if grp_off + 12 > len(font_bytes):
                    break
                start_c, end_c, start_g = struct.unpack(">III", font_bytes[grp_off:grp_off+12])
                grp_off += 12
                for cp in range(start_c, end_c + 1):
                    codepoints.add(cp)

        # Format 4: 16位段式映射 (用于 BMP 基本多文种平面)
        elif fmt == 4:
            if st_off + 8 > len(font_bytes):
                continue
            _, length, lang, seg_count_x2 = struct.unpack(">HHHH", font_bytes[st_off:st_off+8])
            seg_count = seg_count_x2 // 2
            end_off = st_off + 14
            if end_off + seg_count * 2 > len(font_bytes):
                continue
            end_codes = struct.unpack(f">{seg_count}H", font_bytes[end_off:end_off + seg_count * 2])
            start_off = end_off + seg_count * 2 + 2
            if start_off + seg_count * 2 > len(font_bytes):
                continue
            start_codes = struct.unpack(f">{seg_count}H", font_bytes[start_off:start_off + seg_count * 2])
            id_delta_off = start_off + seg_count * 2
            if id_delta_off + seg_count * 2 > len(font_bytes):
                continue
            id_deltas = struct.unpack(f">{seg_count}h", font_bytes[id_delta_off:id_delta_off + seg_count * 2])
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
                ro = struct.unpack(">H", font_bytes[ro_pos:ro_pos+2])[0]
                for cp in range(sc, ec + 1):
                    if ro == 0:
                        gid = (cp + delta) & 0xFFFF
                    else:
                        g_pos = ro_pos + ro + (cp - sc) * 2
                        if g_pos + 2 <= len(font_bytes):
                            gid = struct.unpack(">H", font_bytes[g_pos:g_pos+2])[0]
                            if gid != 0:
                                gid = (gid + delta) & 0xFFFF
                        else:
                            gid = 0
                    if gid != 0:
                        codepoints.add(cp)

    return codepoints

def parse_font_file(file_path: str) -> Tuple[str, Set[int]]:
    """
    解析字体文件并返回 (字体名称, 支持的 Unicode 码位集合)
    优先尝试 fontTools，若未安装则自动回退至纯 Python 二进制解析
    """
    font_name = os.path.basename(file_path)
    try:
        from fontTools.ttLib import TTFont
        font = TTFont(file_path)
        cmap = font.getBestCmap()
        if cmap:
            # 尝试提取内部字体名称
            try:
                name_record = font["name"].getName(1, 3, 1) or font["name"].getName(4, 3, 1)
                if name_record:
                    font_name = name_record.toUnicode()
            except Exception:
                pass
            return font_name, set(cmap.keys())
    except Exception:
        pass

    # 回退到纯 Python 二进制提取
    with open(file_path, "rb") as f:
        bytes_data = f.read()
    codepoints = extract_codepoints_from_bytes(bytes_data)
    return font_name, codepoints
