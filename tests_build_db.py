"""
构建用于回归验证的最小测试库 data/test_hanzi.db（结构与真实库一致，含边界样本）

⚠️ 安全约束：本脚本**只写 test_hanzi.db**，绝不触碰真实的 data/hanzi.db。
   测试库是随时可丢弃的临时产物（已被 .gitignore 的 data/*.db 覆盖）。

用于验证 P0-2 部件边界匹配、P1-1 码位误判、P1-2 后裔计数等修复。
"""
import os
import sqlite3
import zlib

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
TEST_DB_PATH = os.path.join(DB_DIR, "test_hanzi.db")
REAL_DB_PATH = os.path.join(DB_DIR, "hanzi.db")

# 双保险：路径一旦指向真实库立即中止
assert os.path.abspath(TEST_DB_PATH) != os.path.abspath(REAL_DB_PATH), \
    "拒绝操作真实数据库 data/hanzi.db"

os.makedirs(DB_DIR, exist_ok=True)
if os.path.exists(TEST_DB_PATH):
    os.remove(TEST_DB_PATH)
DB_PATH = TEST_DB_PATH

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.executescript("""
CREATE TABLE characters(
  code_point INTEGER PRIMARY KEY, hex_code TEXT, character TEXT, block_name TEXT,
  ids_direct TEXT, ids_tokens TEXT, radical INTEGER, residual_strokes INTEGER,
  total_strokes INTEGER, pinyin TEXT);
CREATE TABLE character_variants(
  code_point INTEGER PRIMARY KEY, simplified TEXT, traditional TEXT,
  semantic TEXT, z_variant TEXT);
CREATE TABLE character_svgs(
  code_point INTEGER PRIMARY KEY, hex_code TEXT, svg_data BLOB);
""")


def svg(ch):
    raw = f'<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><text y="80" font-size="80">{ch}</text></svg>'
    return zlib.compress(raw.encode("utf-8"))


# (码位, 字, IDS, tokens, 部首, 余笔, 总笔, 拼音, 简, 繁, 异体, 笔形)
ROWS = [
    (0x4E00, "一", "一", "一", 1, 0, 1, "yi", "", "", "", ""),
    (0x4E01, "丁", "一亅", "丁,一,丨", 1, 1, 2, "ding", "", "", "", ""),
    (0x5341, "十", "一丨", "十,一,丨", 24, 0, 2, "shi", "", "", "", ""),
    (0x5883, "土", "⿱士⺊", "土,士,⺊", 32, 0, 3, "tu", "", "", "", ""),
    (0x753A, "町", "⿰田丁", "町,田,丁", 102, 2, 7, "ting", "", "", "", ""),
    (0x6CB3, "河", "⿰氵可", "河,氵,可", 85, 5, 8, "he", "", "", "", ""),
    (0x62DB, "招", "⿰扌召", "招,扌,召", 64, 5, 8, "zhao", "", "", "", ""),
    (0x56DE, "回", "囗口", "回,囗,口", 31, 3, 6, "hui", "回", "迴", "囬", ""),
    (0x56D5, "囕", "⿰口監", "囕,口,監", 30, 22, 25, "lan", "囕", "", "", ""),
    # ids_tokens 为 NULL 的边界样本（验证 P0 兜底不崩）
    (0x3400, "㐀", None, None, 1, 4, 5, "qiu", "", "", "", ""),
    # 多字符 token 边界样本（验证整词匹配：旧裸 LIKE '%方%' 会误中 token「𠮛方」）
    (0x9FA5, "龥", "⿰口𠮛方", "龥,口,𠮛方", 214, 8, 26, "yu", "", "", "", ""),
    (0x53E3, "口", "口", "口", 30, 0, 3, "kou", "", "", "", ""),
    # 通配符注入样本：token 含字面下划线/百分号（验证 ESCAPE 转义）
    (0x4E0B, "下", "一卜", "下,_,%", 1, 2, 3, "xia", "", "", "", ""),
]
# 生成 60 个以「口」为部件的衍生字，用于验证 descendants_count 真实总数（>LIMIT 48）
for i in range(60):
    cp = 0x6000 + i
    ch = chr(cp)
    ROWS.append((cp, ch, f"⿰口{i}", f"合,口,{chr(0x4E00 + i)}", 30, 3, 6, f"x{i}", "", "", "", ""))
for cp, ch, ids, toks, rad, res, tot, py, simp, trad, sem, zv in ROWS:
    c.execute("INSERT INTO characters VALUES(?,?,?,?,?,?,?,?,?,?)",
              (cp, f"U+{cp:04X}", ch, "CJK", ids, toks, rad, res, tot, py))
    c.execute("INSERT INTO character_variants VALUES(?,?,?,?,?)", (cp, simp, trad, sem, zv))
    c.execute("INSERT INTO character_svgs VALUES(?,?,?)", (cp, f"U+{cp:04X}", svg(ch)))

conn.commit()
print(f"测试库已生成: {DB_PATH}")
print(f"characters={c.execute('SELECT count(*) FROM characters').fetchone()[0]} "
      f"svgs={c.execute('SELECT count(*) FROM character_svgs').fetchone()[0]}")
conn.close()
