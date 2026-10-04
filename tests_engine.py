"""引擎层回归测试：验证 P0-2 / P1-1 / P1-2 / P0 兜底 修复是否生效

关键：本测试用「能区分新旧行为」的样本，而非仅验证功能仍可用。
- 边界匹配：多字符 token（旧 LIKE '%方%' 会误中 token「乙方」）
- 通配符注入：token 含字面 _ / %（旧 LIKE 未转义会命中全表）
- 后裔计数：构造 62 个后裔（>LIMIT 48），旧实现恒返回 48
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from searcher.engine import HanziEngine

DB = os.path.join("data", "test_hanzi.db")   # 独立测试库，不触碰真实 hanzi.db
if not os.path.exists(DB):
    raise SystemExit("测试库不存在，请先运行: python tests_build_db.py")
eng = HanziEngine(db_path=DB)
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""))


def old_like_count(comp):
    """用旧逻辑(裸 LIKE '%x%')统计命中数，用于对照证明修复必要性"""
    conn = sqlite3.connect(DB)
    n = conn.execute("SELECT count(*) FROM characters WHERE ids_tokens LIKE ?",
                     (f"%{comp}%",)).fetchone()[0]
    conn.close()
    return n


print("=" * 74)
print("P0-2 部件检索：逗号边界整词匹配 + LIKE 通配符转义")
print("=" * 74)

# 1) 多字符 token 边界：旧 LIKE '%方%' 会命中 token「𠮛方」内部
total_fang, res_fang = eng.search_by_components(["方"])
chars_fang = sorted(r["character"] for r in res_fang)
old_fang = old_like_count("方")
print(f"       搜『方』-> 新逻辑命中 {chars_fang} / 旧逻辑子串命中 {old_fang} 条")
check("搜『方』不跨 token 命中多字符 token 内部",
      chars_fang == [] and old_fang > 0,
      f"新={chars_fang} 旧={old_fang}（旧逻辑误中 token『𠮛方』）")
total_full, res_full = eng.search_by_components(["𠮛方"])
check("搜完整多字符 token『𠮛方』仍能命中",
      any(r["character"] == "龥" for r in res_full),
      f"命中 {[r['character'] for r in res_full]}")

# 2) 通配符注入：旧 LIKE '%_%' 会命中所有非空 token
n_underscore = len(eng.search_by_components(["_"])[1])
old_underscore = old_like_count("_")
print(f"       搜『_』-> 新逻辑命中 {n_underscore} 条 (旧逻辑={old_underscore} 条)")
check("搜『_』不再被当单字符通配符命中全表",
      n_underscore < old_underscore, f"新={n_underscore} 旧={old_underscore}")

n_pct = len(eng.search_by_components(["%"])[1])
old_pct = old_like_count("%")
print(f"       搜『%』-> 新逻辑命中 {n_pct} 条 (旧逻辑={old_pct} 条)")
check("搜『%』不再被当任意通配符命中全表",
      n_pct < old_pct, f"新={n_pct} 旧={old_pct}")

# 3) 正常部件检索仍然可用
total, res = eng.search_by_components(["氵"])
check("搜『氵』仍能命中『河』", [r["character"] for r in res] == ["河"])
conn = sqlite3.connect(DB)
expect_kou = conn.execute(
    "SELECT count(*) FROM characters WHERE (',' || REPLACE(ids_tokens,' ','') || ',') LIKE '%,口,%'"
).fetchone()[0]
conn.close()
total_kou, res_kou = eng.search_by_components(["口"])
check("搜『口』total_count 为真实命中数（不受分页影响）",
      total_kou == expect_kou and total_kou > 48,
      f"total_count={total_kou} 期望={expect_kou}")

print()
print("=" * 74)
print("P0 兜底：ids_tokens 为 NULL 的字参与检索/血缘不崩溃")
print("=" * 74)
try:
    fam = eng.get_character_family("U+3400")
    check("ids_tokens=NULL 的字可正常取血缘", fam is not None and fam["parents"] == [],
          f"parents={fam['parents'] if fam else None}")
except Exception as e:
    check("ids_tokens=NULL 的字可正常取血缘", False, f"{type(e).__name__}: {e}")

print()
print("=" * 74)
print("P1-1 码位误判：拼音/纯数字不再被劫持为十六进制码位")
print("=" * 74)
for q, expect_not_code in [("cafe", True), ("face", True), ("beef", True),
                           ("2024", True), ("5678", True), ("dad0", True)]:
    r = eng.smart_search(q)
    check(f"搜 '{q}' 不被判为 exact_code", (r["mode"] != "exact_code") == expect_not_code,
          f"mode={r['mode']}")
check("搜 'shu' 走拼音模式", eng.smart_search("shu")["mode"] == "pinyin")
r = eng.smart_search("U+4E01")
check("搜 'U+4E01' 仍正常命中", r["mode"] == "exact_code" and r["total_count"] == 1)
r = eng.smart_search("4E01")
check("搜裸hex '4E01' 仍正常命中", r["mode"] == "exact_code" and r["total_count"] == 1)
r = eng.smart_search("丁")
check("搜单字 '丁' 仍走精确直查", r["mode"] == "exact_code" and r["total_count"] == 1)

print()
print("=" * 74)
print("P1-2 后裔计数：真实总数而非 LIMIT 48 截断长度（构造 62 个后裔）")
print("=" * 74)
fam = eng.get_character_family("U+53E3")   # 口
check("血缘返回 descendants 字段", fam is not None and "descendants" in fam)
if fam:
    n_list = len(fam["descendants"])
    n_count = fam["descendants_count"]
    # 动态计算期望值：tokens 含「口」且非自身
    conn = sqlite3.connect(DB)
    expect = conn.execute(
        "SELECT count(*) FROM characters WHERE (',' || REPLACE(ids_tokens,' ','') || ',') "
        "LIKE '%,口,%' AND code_point != ?", (0x53E3,)).fetchone()[0]
    conn.close()
    print(f"       口 的后裔：列表长度={n_list} (上限48)，真实总数={n_count}，期望={expect}")
    check("列表被 LIMIT 48 截断", n_list == 48, f"len={n_list}")
    check(f"descendants_count 为真实总数({expect})而非列表长度",
          n_count == expect and n_count > 48, f"count={n_count}")

print()
print("=" * 74)
print("回归：既有检索路径未破坏")
print("=" * 74)
r = eng.smart_search("", strokes=2)
check("纯笔画检索", r["mode"] == "strokes_only" and r["total_count"] == 2,
      f"mode={r['mode']} count={r['total_count']}")
r = eng.smart_search("⿰氵可")
check("IDS 模式检索", r["mode"].startswith("ids_pattern"), f"mode={r['mode']}")
r = eng.smart_search("回")
check("单字直查『回』", r["total_count"] == 1)
check("search_by_code 单字符", (eng.search_by_code("一") or {}).get("character") == "一")
check("search_by_code 支持 U+ 前缀", (eng.search_by_code("U+4E00") or {}).get("character") == "一")
check("search_by_code 不支持随意字符串", eng.search_by_code("ZZZZ") is None)
f2 = eng.get_character_family("U+56DE")
check("简繁异体字段可取", f2 is not None and f2["root"]["traditional"] == "迴")

print()
print("=" * 74)
print(f"结果: {len(PASS)} 通过 / {len(FAIL)} 失败")
for f in FAIL:
    print("  失败 -", f)
print("=" * 74)
sys.exit(1 if FAIL else 0)
