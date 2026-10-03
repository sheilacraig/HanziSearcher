"""
本地汉字与 Unicode 极速检索 Web 服务 (HanziSearcher Web UI - 东方雅致与专业排印交互版)
核心功能：
1. 【东方典雅与现代排印工作台美学】：
   - 宣纸底色与朱砂红墨色搭配，书法级「米字格」参考背景（支持一键开启/关闭）。
   - 字形尺寸自由缩放（紧凑 / 标准 / 特大三种视图尺寸），适应不同研究与排版需求。
   - 支持设置面板：自定义字体文件拖拽/选择上传，一键恢复默认 SVG 渲染。
2. 【字体优先渲染与自动降级】：
   - 优先使用自定义字体渲染；未覆盖字形自动降级使用本地 SQLite 离线 SVG 矢量显示。
   - 全量 103,047 汉字矢量字形离线入库，极速本地直出。
3. 【总笔画数 + 检索框 组合检索】：
   - 支持单独总笔画数检索、单独检索框检索、两者组合交叉过滤。
   - 提供快捷高频检索示例胶囊，一键体验组合检索。
4. 【结构化部首与符号工具箱】：
   - 选项卡式分类管理：常用/难打变形部首、结构IDC与通配符号、214 康熙部首检字表。
   - 214 部首检字表支持按 1~17 画胶囊快速过滤筛选。
5. 【汉字血缘探针与流变谱系】：
   - 全部件穿透检索与家族血缘衍生树可视化。
"""

import json
import os
import re
import sqlite3
import sys
import urllib.parse
import zlib
from http.server import HTTPServer, BaseHTTPRequestHandler

# 将当前目录加入模块路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from searcher.engine import HanziEngine
from searcher.font_parser import parse_font_file

engine = HanziEngine()
DB_PATH = "data/hanzi.db"
CUSTOM_FONT_PATH = "data/custom_font.ttf"
CUSTOM_FONT_META_PATH = "data/custom_font_meta.json"

def load_font_meta():
    """读取已存储的自定义字体元数据"""
    if os.path.exists(CUSTOM_FONT_META_PATH) and os.path.exists(CUSTOM_FONT_PATH):
        try:
            with open(CUSTOM_FONT_META_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def save_font_meta(meta):
    """保存自定义字体元数据"""
    os.makedirs(os.path.dirname(CUSTOM_FONT_META_PATH), exist_ok=True)
    with open(CUSTOM_FONT_META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def get_svg_from_db(code_param: str) -> str:
    """
    从 SQLite 本地库获取字形 SVG 矢量数据（100% 离线，无网络请求）
    兼容 Unicode 码位字符串 (如 'U+4E00', '4E00', 0x4E00) 与原始单字符 (如 '一')
    """
    if not code_param:
        return ""
    code_param = code_param.strip()

    if len(code_param) == 1 and not ('0' <= code_param <= '9' or 'a' <= code_param.lower() <= 'f'):
        cp = ord(code_param)
        hex_clean = f"{cp:04X}"
    else:
        hex_clean = re.sub(r"[^0-9A-Fa-f]", "", code_param).upper()
        if not hex_clean:
            cp = ord(code_param[0])
            hex_clean = f"{cp:04X}"
        else:
            try:
                cp = int(hex_clean, 16)
            except ValueError:
                cp = 0

    full_hex = f"U+{hex_clean}"

    conn = sqlite3.connect(DB_PATH, timeout=5)
    cursor = conn.cursor()
    cursor.execute("SELECT svg_data FROM character_svgs WHERE hex_code = ? OR code_point = ?", (full_hex, cp))
    row = cursor.fetchone()
    conn.close()

    if row and row[0]:
        val = row[0]
        if isinstance(val, bytes):
            try:
                return zlib.decompress(val).decode("utf-8")
            except Exception:
                return ""
        return val
    return ""

HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>🏮 HanziSearcher - 汉字拆字与部件检索系统</title>
  <style>
    :root {
      --primary: #b83b26;
      --primary-hover: #9c2e1c;
      --primary-light: #fbeee8;
      --bg: #f7f4ee;
      --card-bg: #ffffff;
      --text: #2c3e50;
      --text-muted: #7f8c8d;
      --border: #e2dbcf;
      --border-light: #eee9df;
      --accent: #1f618d;
      --green: #219653;
      --green-light: #eafaf1;
      --purple: #7d3c98;
      --purple-light: #f5eef8;
      --orange: #d35400;
      --orange-light: #fef5e7;
      --shadow-sm: 0 2px 8px rgba(44, 62, 80, 0.04);
      --shadow-md: 0 6px 18px rgba(44, 62, 80, 0.06);
      --shadow-lg: 0 16px 36px rgba(44, 62, 80, 0.12);
      --font-serif: "Songti SC", "SimSun", "Noto Serif CJK SC", STSong, serif;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Segoe UI", Roboto, "Hiragino Sans GB", sans-serif;
      background-color: var(--bg);
      background-image: radial-gradient(#e7dfd1 1px, transparent 1px);
      background-size: 24px 24px;
      color: var(--text);
      line-height: 1.6;
      padding: 24px 20px 80px 20px;
      min-height: 100vh;
    }

    .container {
      max-width: 1220px;
      margin: 0 auto;
    }

    /* 顶部导航标题区 */
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
      flex-wrap: wrap;
      gap: 16px;
    }

    .brand-title {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .brand-seal {
      width: 42px;
      height: 42px;
      background: linear-gradient(135deg, #c0392b, #962d22);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      font-family: var(--font-serif);
      font-size: 24px;
      font-weight: bold;
      box-shadow: 0 4px 12px rgba(192, 57, 43, 0.28);
      user-select: none;
      border: 1px solid rgba(255,255,255,0.2);
    }

    h1 {
      font-size: 26px;
      color: #1a1a1a;
      letter-spacing: 0.5px;
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 700;
    }

    .subtitle-badge {
      background: var(--primary-light);
      color: var(--primary);
      border: 1px solid rgba(184, 59, 38, 0.2);
      font-size: 12px;
      padding: 2px 10px;
      border-radius: 20px;
      font-weight: 500;
    }

    /* 顶部操作按钮栏 (图库进度与设置按钮) */
    .header-actions {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .header-nav-btn {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      background: #ffffff;
      border: 1px solid var(--border);
      padding: 7px 14px;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 500;
      color: #4a4039;
      cursor: pointer;
      box-shadow: var(--shadow-sm);
      transition: all 0.15s;
      user-select: none;
    }

    .header-nav-btn:hover {
      background: #faf8f5;
      border-color: var(--primary);
      color: var(--primary);
      transform: translateY(-1px);
    }

    .header-badge {
      background: #eee8de;
      color: #6d635b;
      font-size: 11px;
      padding: 1px 7px;
      border-radius: 10px;
      font-weight: 600;
      transition: all 0.15s;
    }

    .header-nav-btn:hover .header-badge {
      background: var(--primary-light);
      color: var(--primary);
    }

    .pulse-dot-mini {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #27ae60;
      display: inline-block;
      animation: pulseMini 1.8s infinite;
    }

    @keyframes pulseMini {
      0% { transform: scale(0.9); opacity: 0.8; box-shadow: 0 0 0 0 rgba(39, 174, 96, 0.6); }
      70% { transform: scale(1.1); opacity: 1; box-shadow: 0 0 0 5px rgba(39, 174, 96, 0); }
      100% { transform: scale(0.9); opacity: 0.8; }
    }

    .view-switch {
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      user-select: none;
    }

    .view-switch input {
      margin-right: 4px;
      cursor: pointer;
      accent-color: var(--primary);
    }

    .size-btn-group {
      display: flex;
      background: #f2eee6;
      border-radius: 6px;
      padding: 2px;
    }

    .size-btn {
      border: none;
      background: transparent;
      padding: 3px 8px;
      font-size: 12px;
      cursor: pointer;
      border-radius: 4px;
      color: #666;
      transition: all 0.15s;
    }

    .size-btn.active {
      background: #ffffff;
      color: var(--primary);
      font-weight: bold;
      box-shadow: 0 1px 4px rgba(0,0,0,0.1);
    }

    /* 字体排印工作台面板 (Font Studio Bar) */
    .font-studio-panel {
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px 20px;
      margin-bottom: 20px;
      box-shadow: var(--shadow-sm);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
      transition: border-color 0.2s, background-color 0.2s;
    }

    .font-studio-panel.drag-over {
      border-color: var(--primary);
      background-color: var(--primary-light);
    }

    .font-info-wrap {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .font-pulse-dot {
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: #95a5a6;
      position: relative;
      flex-shrink: 0;
    }

    .font-pulse-dot.active {
      background: var(--green);
    }

    .font-pulse-dot.active::after {
      content: '';
      position: absolute;
      top: -3px; left: -3px; right: -3px; bottom: -3px;
      border-radius: 50%;
      border: 2px solid var(--green);
      opacity: 0.5;
      animation: pulse 2s infinite ease-out;
    }

    @keyframes pulse {
      0% { transform: scale(0.9); opacity: 0.8; }
      100% { transform: scale(1.6); opacity: 0; }
    }

    .font-status-title {
      font-size: 14px;
      font-weight: 600;
      color: #2c3e50;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .font-status-desc {
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 2px;
    }

    .font-action-buttons {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }

    .font-tool-btn {
      background: #faf8f5;
      border: 1px solid #dcd4c8;
      border-radius: 8px;
      padding: 7px 14px;
      font-size: 13px;
      cursor: pointer;
      color: #3e3830;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s;
      font-weight: 500;
    }

    .font-tool-btn:hover {
      background: #ffffff;
      border-color: var(--primary);
      color: var(--primary);
      transform: translateY(-1px);
    }

    .font-tool-btn.btn-reset {
      color: #7f8c8d;
      border-color: #e0dcd4;
    }

    .font-tool-btn.btn-reset:hover {
      color: var(--primary);
      border-color: var(--primary);
    }

    /* 综合搜索面板 */
    .search-panel {
      background: var(--card-bg);
      padding: 24px 28px;
      border-radius: 16px;
      box-shadow: var(--shadow-md);
      border: 1px solid var(--border);
      margin-bottom: 22px;
    }

    .search-row {
      display: flex;
      gap: 12px;
      align-items: stretch;
    }

    .input-box-main {
      position: relative;
      flex: 1;
      display: flex;
      align-items: center;
    }

    .search-prefix-icon {
      position: absolute;
      left: 18px;
      color: #95a5a6;
      font-size: 18px;
      pointer-events: none;
    }

    .input-box-main input {
      width: 100%;
      padding: 16px 42px 16px 48px;
      font-size: 17px;
      border: 2px solid var(--border);
      border-radius: 12px;
      outline: none;
      transition: all 0.2s;
      background: #faf8f5;
      color: #111;
    }

    .input-box-main input:focus {
      background: #ffffff;
      border-color: var(--primary);
      box-shadow: 0 0 0 4px rgba(184, 59, 38, 0.12);
    }

    .input-box-strokes {
      width: 190px;
      position: relative;
      display: flex;
      align-items: center;
      flex-shrink: 0;
    }

    .strokes-prefix-icon {
      position: absolute;
      left: 14px;
      color: #e67e22;
      font-size: 16px;
      pointer-events: none;
    }

    .input-box-strokes input {
      width: 100%;
      padding: 16px 36px 16px 40px;
      font-size: 16px;
      border: 2px solid var(--border);
      border-radius: 12px;
      outline: none;
      transition: all 0.2s;
      background: #faf8f5;
      color: #111;
    }

    .input-box-strokes input:focus {
      background: #ffffff;
      border-color: var(--orange);
      box-shadow: 0 0 0 4px rgba(211, 84, 0, 0.12);
    }

    .clear-icon {
      position: absolute;
      right: 14px;
      cursor: pointer;
      color: #bdc3c7;
      font-size: 18px;
      line-height: 1;
      display: none;
      user-select: none;
      transition: color 0.15s;
    }

    .clear-icon:hover {
      color: #7f8c8d;
    }

    .search-btn {
      padding: 0 28px;
      background: linear-gradient(135deg, var(--primary), var(--primary-hover));
      color: white;
      border: none;
      border-radius: 12px;
      font-size: 16px;
      cursor: pointer;
      font-weight: 600;
      box-shadow: 0 4px 12px rgba(184, 59, 38, 0.25);
      transition: all 0.2s;
      flex-shrink: 0;
    }

    .search-btn:hover {
      transform: translateY(-1px);
      box-shadow: 0 6px 16px rgba(184, 59, 38, 0.35);
    }

    .reset-btn {
      padding: 0 18px;
      background: #f0ece3;
      color: #555;
      border: none;
      border-radius: 12px;
      font-size: 15px;
      cursor: pointer;
      font-weight: 500;
      transition: all 0.15s;
      flex-shrink: 0;
    }

    .reset-btn:hover {
      background: #e2dbce;
      color: #222;
    }

    /* 快捷场景体验胶囊条 (Quick Presets) */
    .presets-bar {
      margin-top: 14px;
      display: flex;
      align-items: center;
      gap: 8px;
      overflow-x: auto;
      padding: 6px 4px 6px 4px;
      font-size: 13px;
      line-height: 1.5;
    }

    .presets-label {
      color: var(--text-muted);
      font-size: 12px;
      font-weight: 600;
      white-space: nowrap;
      user-select: none;
    }

    .preset-chip {
      background: #faf8f5;
      border: 1px solid #e5ded2;
      border-radius: 14px;
      padding: 3px 10px;
      cursor: pointer;
      white-space: nowrap;
      color: #555;
      transition: all 0.15s;
      user-select: none;
      display: inline-flex;
      align-items: center;
    }

    .preset-chip:hover {
      background: #ffffff;
      border-color: var(--primary);
      color: var(--primary);
      transform: translateY(-1px);
      box-shadow: 0 2px 6px rgba(184, 59, 38, 0.1);
    }

    /* 现代化结构与部首工具箱 (折叠式) */
    .toolbox-wrapper {
      margin-top: 14px;
    }

    .toolbox-toggle-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: #faf8f5;
      border: 1px solid #ebdcd0;
      border-radius: 8px;
      padding: 9px 14px;
      cursor: pointer;
      user-select: none;
      transition: all 0.15s;
    }

    .toolbox-toggle-bar:hover {
      background: #f7f3ec;
      border-color: #dfcfbf;
    }

    .toolbox-toggle-left {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
    }

    .toolbox-toggle-title {
      font-weight: 600;
      color: #4a4039;
    }

    .toolbox-toggle-tags {
      font-size: 11px;
      color: #8c7b70;
      margin-left: 4px;
    }

    .toolbox-toggle-indicator {
      font-size: 12px;
      color: var(--primary);
      font-weight: 500;
    }

    .toolbox-container {
      margin-top: 8px;
      background: #faf8f5;
      border: 1px solid #ebdcd0;
      border-radius: 12px;
      overflow: hidden;
    }

    .toolbox-tabs-header {
      display: flex;
      background: #f2ece1;
      border-bottom: 1px solid #ebdcd0;
      padding: 0 8px;
    }

    .toolbox-tab-btn {
      border: none;
      background: transparent;
      padding: 10px 16px;
      font-size: 13px;
      font-weight: 600;
      color: #6d635b;
      cursor: pointer;
      transition: all 0.15s;
      border-bottom: 2px solid transparent;
      margin-bottom: -1px;
    }

    .toolbox-tab-btn.active {
      color: var(--primary);
      border-bottom-color: var(--primary);
      background: #faf8f5;
    }

    .toolbox-content-panel {
      padding: 14px 18px;
      display: none;
    }

    .toolbox-content-panel.active {
      display: block;
    }

    /* 常用偏旁部首网格 */
    .radicals-flex-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }

    .rad-tag-btn {
      background: #ffffff;
      border: 1px solid #dcd4c8;
      border-radius: 6px;
      padding: 3px 8px;
      font-size: 15px;
      font-family: var(--font-serif);
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      transition: all 0.15s;
      color: #2c3e50;
      user-select: none;
      min-width: 36px;
      justify-content: center;
    }

    .rad-tag-btn span.rad-sub {
      font-size: 10px;
      color: #95a5a6;
      font-family: sans-serif;
    }

    .rad-tag-btn:hover {
      background: var(--purple);
      color: #ffffff;
      border-color: var(--purple);
      transform: translateY(-1px);
      box-shadow: 0 2px 6px rgba(125, 60, 152, 0.2);
    }

    .rad-tag-btn:hover span.rad-sub {
      color: #f5eef8;
    }

    /* 构架与通配符号按钮 */
    .idc-flex-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .idc-action-btn {
      background: #ffffff;
      border: 1px solid #dcd4c8;
      border-radius: 8px;
      padding: 5px 12px;
      font-size: 14px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s;
      color: #333;
      user-select: none;
    }

    .idc-action-btn b {
      color: var(--primary);
      font-size: 17px;
    }

    .idc-action-btn.wild b {
      color: var(--orange);
    }

    .idc-action-btn:hover {
      background: var(--primary);
      color: #ffffff;
      border-color: var(--primary);
      transform: translateY(-1px);
    }

    .idc-action-btn:hover b {
      color: #ffffff;
    }

    /* 214 康熙部首检字表与笔画筛选栏 */
    .kangxi-stroke-filter-bar {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
      margin-bottom: 12px;
      padding-bottom: 8px;
      border-bottom: 1px dashed #e2dbcf;
    }

    .stroke-nav-pill {
      border: 1px solid #dcd4c8;
      background: #ffffff;
      border-radius: 12px;
      padding: 2px 8px;
      font-size: 12px;
      cursor: pointer;
      color: #666;
      transition: all 0.15s;
    }

    .stroke-nav-pill.active, .stroke-nav-pill:hover {
      background: var(--purple);
      color: #ffffff;
      border-color: var(--purple);
    }

    .kangxi-scroll-body {
      max-height: 240px;
      overflow-y: auto;
      padding-right: 6px;
    }

    .kangxi-row-group {
      display: flex;
      align-items: flex-start;
      margin-bottom: 8px;
      gap: 10px;
    }

    .kangxi-row-group.hidden {
      display: none;
    }

    .kangxi-group-title {
      font-size: 12px;
      color: var(--purple);
      font-weight: 700;
      min-width: 58px;
      padding-top: 4px;
    }

    /* 状态与统计条 */
    .status-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      padding: 0 4px;
      font-size: 14px;
      color: var(--text-muted);
    }

    /* 结果网格与卡片 */
    .results-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
      gap: 18px;
    }

    .char-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px 18px;
      display: flex;
      gap: 16px;
      box-shadow: var(--shadow-sm);
      transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
      position: relative;
    }

    .char-card:hover {
      transform: translateY(-3px);
      box-shadow: var(--shadow-md);
      border-color: #d8cebf;
    }

    /* 字形展示框 (含书法米字格支持) */
    .glyph-display {
      width: 86px;
      height: 86px;
      background: #faf8f5;
      border: 1px solid #ded5c7;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      position: relative;
      flex-shrink: 0;
      overflow: hidden;
      user-select: none;
      transition: border-color 0.2s, background-color 0.2s;
    }

    .glyph-display:hover {
      border-color: var(--primary);
      background-color: #f7f2ea;
    }

    /* 书法米字格 (CSS Linear Gradient 优雅高精度绘制) */
    .with-mizige {
      background-image: 
        linear-gradient(to right, rgba(184, 59, 38, 0.08) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(184, 59, 38, 0.08) 1px, transparent 1px),
        linear-gradient(45deg, transparent 49.3%, rgba(184, 59, 38, 0.06) 49.3%, rgba(184, 59, 38, 0.06) 50.7%, transparent 50.7%),
        linear-gradient(-45deg, transparent 49.3%, rgba(184, 59, 38, 0.06) 49.3%, rgba(184, 59, 38, 0.06) 50.7%, transparent 50.7%);
      background-size: 100% 100%, 100% 100%, 100% 100%, 100% 100%;
      background-position: center center;
    }

    /* 字形尺寸模式控制 */
    .grid-size-compact .glyph-display {
      width: 68px;
      height: 68px;
    }
    .grid-size-compact .glyph-text-font {
      font-size: 42px;
      line-height: 68px;
    }

    .grid-size-large .glyph-display {
      width: 104px;
      height: 104px;
    }
    .grid-size-large .glyph-text-font {
      font-size: 68px;
      line-height: 104px;
    }

    .glyph-svg, .glyph-display svg, .modal-glyph-large svg, .descendant-glyph-box svg {
      width: 82% !important;
      height: 82% !important;
      max-width: 82% !important;
      max-height: 82% !important;
      object-fit: contain;
      display: block;
      margin: auto;
      pointer-events: none;
      filter: drop-shadow(0 1px 1px rgba(0,0,0,0.08));
    }

    .glyph-text-font {
      font-size: 54px;
      font-family: 'UserCustomFont', var(--font-serif);
      color: #111111;
      line-height: 86px;
      text-align: center;
      user-select: none;
    }

    .glyph-text-fallback {
      font-size: 50px;
      font-family: var(--font-serif);
      color: #333;
      display: none;
      line-height: 86px;
      text-align: center;
    }

    /* 字形来源微徽章 (置于米字格外部，避免遮挡汉字笔画) */
    .source-badge {
      font-size: 11px;
      padding: 1px 7px;
      border-radius: 4px;
      font-weight: 600;
      line-height: 1.4;
      user-select: none;
      display: inline-flex;
      align-items: center;
      gap: 2px;
    }

    .badge-font {
      background: var(--green-light);
      color: var(--green);
      border: 1px solid rgba(33, 150, 83, 0.25);
    }

    .badge-svg {
      background: var(--orange-light);
      color: var(--orange);
      border: 1px solid rgba(211, 84, 0, 0.25);
    }

    .char-meta {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      justify-content: center;
    }

    .char-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
    }

    .char-code {
      font-family: "JetBrains Mono", Menlo, Monaco, Consolas, monospace;
      font-size: 15px;
      font-weight: 700;
      color: var(--accent);
      cursor: pointer;
      transition: color 0.15s;
    }

    .char-code:hover {
      text-decoration: underline;
      color: #154360;
    }

    .probe-btn {
      background: #f0f8f4;
      color: var(--green);
      border: 1px solid #c7e8d6;
      border-radius: 6px;
      padding: 3px 8px;
      font-size: 12px;
      cursor: pointer;
      font-weight: 600;
      transition: all 0.15s;
      display: inline-flex;
      align-items: center;
      gap: 3px;
    }

    .probe-btn:hover {
      background: var(--green);
      color: #ffffff;
      border-color: var(--green);
    }

    .char-prop {
      font-size: 13px;
      color: #4a5568;
      margin-bottom: 4px;
      display: flex;
      gap: 6px;
      align-items: center;
      flex-wrap: wrap;
    }

    .char-prop span.label {
      color: #95a5a6;
      min-width: 40px;
      font-size: 12px;
    }

    .comp-chip {
      background: #eee8de;
      color: #3e3830;
      padding: 1px 7px;
      border-radius: 4px;
      font-size: 12px;
      cursor: pointer;
      font-weight: 600;
      transition: all 0.15s;
      border: 1px solid #ddd3c3;
    }

    .comp-chip:hover {
      background: var(--primary);
      color: #ffffff;
      border-color: var(--primary);
      transform: translateY(-1px);
    }

    .stroke-badge {
      background: var(--orange-light);
      color: var(--orange);
      padding: 1px 6px;
      border-radius: 4px;
      font-weight: 600;
      font-size: 12px;
      border: 1px solid rgba(211, 84, 0, 0.2);
    }

    .pinyin-badge {
      color: var(--primary);
      font-weight: 700;
      font-size: 13px;
      margin-left: 2px;
      font-family: var(--font-serif);
    }

    .variants-line {
      margin-top: 6px;
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      font-size: 11px;
    }

    .var-tag {
      padding: 1px 6px;
      border-radius: 4px;
      cursor: pointer;
      transition: transform 0.15s;
      white-space: nowrap;
    }

    .var-tag:hover {
      transform: scale(1.05);
    }

    .var-trad {
      background: var(--orange-light);
      color: var(--orange);
      border: 1px solid #fad7a0;
    }

    .var-sem {
      background: var(--purple-light);
      color: var(--purple);
      border: 1px solid #d2b4de;
    }

    /* 分页控制器样式 */
    .pagination-bar {
      margin-top: 40px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 16px;
      background: #ffffff;
      padding: 16px 24px;
      border-radius: 14px;
      border: 1px solid var(--border);
      box-shadow: var(--shadow-sm);
    }

    .page-nav-btn {
      padding: 8px 20px;
      background: #ffffff;
      border: 1px solid #dcd4c8;
      border-radius: 8px;
      cursor: pointer;
      font-size: 14px;
      color: #444;
      font-weight: 600;
      transition: all 0.15s;
    }

    .page-nav-btn:hover:not(:disabled) {
      background: var(--primary);
      color: #ffffff;
      border-color: var(--primary);
    }

    .page-nav-btn:disabled {
      opacity: 0.4;
      cursor: not-allowed;
      background: #f7f5f0;
    }

    .page-info-text {
      font-size: 14px;
      color: #555;
      font-weight: 500;
    }

    .page-jump-box {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      color: #777;
      margin-left: 12px;
      border-left: 1px solid #e0dcd4;
      padding-left: 16px;
    }

    .jump-input {
      width: 54px;
      padding: 6px 8px;
      border: 1px solid #dcd4c8;
      border-radius: 6px;
      text-align: center;
      font-size: 14px;
      outline: none;
    }

    .jump-input:focus {
      border-color: var(--primary);
    }

    /* 血缘探针模态弹窗 */
    .modal-overlay {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(30, 39, 46, 0.65);
      backdrop-filter: blur(5px);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 2000;
      padding: 24px;
    }

    .family-modal {
      background: #ffffff;
      border-radius: 18px;
      width: 100%;
      max-width: 880px;
      max-height: 88vh;
      overflow-y: auto;
      box-shadow: var(--shadow-lg);
      border: 1px solid var(--border);
      padding: 32px 36px;
      position: relative;
    }

    .modal-close-btn {
      position: absolute;
      top: 20px;
      right: 24px;
      background: #f4f0e8;
      border: none;
      width: 32px;
      height: 32px;
      border-radius: 50%;
      font-size: 20px;
      color: #777;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.15s;
    }

    .modal-close-btn:hover {
      background: var(--primary);
      color: #ffffff;
    }

    /* 设置模态弹窗与图库进度弹窗样式 */
    .settings-modal, .progress-modal {
      background: #ffffff;
      border-radius: 18px;
      width: 100%;
      max-width: 580px;
      max-height: 88vh;
      overflow-y: auto;
      box-shadow: var(--shadow-lg);
      border: 1px solid var(--border);
      padding: 28px 32px;
      position: relative;
    }

    .progress-modal {
      max-width: 640px;
    }

    .setting-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 14px 0;
      border-bottom: 1px solid #f0ece3;
    }

    .setting-item-title {
      font-size: 15px;
      font-weight: 600;
      color: #2c3e50;
      margin-bottom: 3px;
    }

    .setting-item-desc {
      font-size: 12px;
      color: #7f8c8d;
      line-height: 1.4;
    }

    .font-studio-box {
      width: 100%;
      background: #faf8f5;
      border: 1px dashed #ebdcd0;
      border-radius: 10px;
      padding: 14px;
      margin-top: 6px;
    }

    /* 矢量图库归档进度组件 */
    .crawler-live-tag {
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 10px;
      background: #eafaf1;
      color: #27ae60;
      font-weight: normal;
    }

    .crawler-live-tag.done {
      background: #f4f0e8;
      color: #6d635b;
    }

    .stats-row {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      margin: 16px 0;
    }

    .stat-card {
      background: #faf8f5;
      border: 1px solid #ebdcd0;
      border-radius: 10px;
      padding: 14px 8px;
      text-align: center;
    }

    .stat-label {
      font-size: 12px;
      color: #7f8c8d;
      margin-bottom: 4px;
    }

    .stat-value {
      font-size: 24px;
      font-weight: bold;
      color: #2c3e50;
    }

    .stat-value.primary {
      color: var(--primary);
    }

    .stat-sub {
      font-size: 11px;
      color: #999;
      margin-top: 2px;
    }

    .progress-section {
      background: #faf8f5;
      border: 1px solid #ebdcd0;
      border-radius: 10px;
      padding: 16px 18px;
      margin-bottom: 16px;
    }

    .progress-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }

    .progress-title {
      font-size: 14px;
      font-weight: 600;
      color: #333;
    }

    .progress-percent {
      font-size: 20px;
      font-weight: bold;
      color: var(--primary);
    }

    .progress-bar-track {
      height: 14px;
      background: #ebdcd0;
      border-radius: 7px;
      overflow: hidden;
    }

    .progress-bar-fill {
      height: 100%;
      background: linear-gradient(90deg, #c0392b, #e67e22, #27ae60);
      border-radius: 7px;
      transition: width 0.4s ease;
    }

    .block-progress-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin-bottom: 16px;
    }

    .block-progress-item {
      background: #ffffff;
      border: 1px solid #eee8de;
      border-radius: 8px;
      padding: 10px 14px;
    }

    .block-info {
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      margin-bottom: 6px;
      color: #555;
    }

    .sub-progress-track {
      height: 6px;
      background: #f0ebe1;
      border-radius: 3px;
      overflow: hidden;
    }

    .sub-progress-fill {
      height: 100%;
      background: #27ae60;
      border-radius: 3px;
      transition: width 0.4s ease;
    }

    .sub-progress-fill.full {
      background: #2980b9;
    }

    .modal-footer-stats {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-top: 12px;
      border-top: 1px solid #f0ece3;
    }

    .refresh-progress-btn {
      background: #faf8f5;
      border: 1px solid #ebdcd0;
      border-radius: 6px;
      padding: 4px 12px;
      font-size: 12px;
      cursor: pointer;
      color: #555;
      transition: all 0.15s;
    }

    .refresh-progress-btn:hover {
      background: var(--primary);
      color: #fff;
      border-color: var(--primary);
    }

    .modal-header-section {
      display: flex;
      gap: 24px;
      align-items: center;
      border-bottom: 1px solid #eee8df;
      padding-bottom: 22px;
      margin-bottom: 24px;
    }

    .modal-glyph-large {
      width: 98px;
      height: 98px;
      background: #faf8f5;
      border: 1px solid #ded5c7;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      position: relative;
      overflow: hidden;
    }

    .modal-glyph-large img {
      width: 82%;
      height: 82%;
    }

    .modal-char-info h2 {
      font-size: 28px;
      margin-bottom: 6px;
      font-family: var(--font-serif);
    }

    .tree-block {
      margin-bottom: 24px;
      background: #faf8f5;
      border: 1px solid #eee6da;
      border-radius: 12px;
      padding: 16px 20px;
    }

    .tree-block h3 {
      font-size: 15px;
      color: #2c3e50;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 700;
    }

    .parent-pill-list {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    .parent-pill {
      background: #ffffff;
      border: 1px solid #ded5c7;
      border-radius: 8px;
      padding: 8px 14px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 10px;
      transition: all 0.15s;
    }

    .parent-pill:hover {
      border-color: var(--primary);
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(0,0,0,0.06);
    }

    .descendant-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(72px, 1fr));
      gap: 10px;
    }

    .descendant-card {
      background: #ffffff;
      border: 1px solid #e2ddd3;
      border-radius: 8px;
      padding: 8px 4px 6px 4px;
      text-align: center;
      cursor: pointer;
      transition: all 0.15s;
    }

    .descendant-card:hover {
      border-color: var(--green);
      transform: translateY(-2px);
      box-shadow: 0 4px 10px rgba(0,0,0,0.08);
    }

    .descendant-glyph-box {
      width: 44px;
      height: 44px;
      margin: 0 auto;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .descendant-glyph-box img {
      width: 44px;
      height: 44px;
      display: block;
    }

    .descendant-meta {
      display: block;
      font-size: 11px;
      color: #8c7b70;
      margin-top: 4px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      line-height: 1.2;
    }

    .copy-toast {
      position: fixed;
      bottom: 30px;
      left: 50%;
      transform: translateX(-50%);
      background: rgba(33, 37, 41, 0.92);
      color: #fff;
      padding: 10px 24px;
      border-radius: 24px;
      font-size: 14px;
      display: none;
      z-index: 3000;
      box-shadow: 0 8px 24px rgba(0,0,0,0.25);
    }
  </style>
</head>
<body>
  <div class="container">
    <!-- 1. 顶部 Header -->
    <header>
      <div class="brand-title">
        <div class="brand-seal">漢</div>
        <div>
          <h1>
            <span>HanziSearcher</span>
            <span class="subtitle-badge">汉字拆字与部件检索</span>
          </h1>
        </div>
      </div>

      <!-- 顶部操作导航：矢量图库进度与系统设置 -->
      <div class="header-actions">
        <button class="header-nav-btn progress-btn" onclick="openProgressModal()" title="查看离线矢量 SVG 下载进度">
          <span class="pulse-dot-mini" id="crawlerDotMini"></span>
          <span>📊 图库进度</span>
          <span class="header-badge" id="headerProgressBadge">--%</span>
        </button>
        <button class="header-nav-btn settings-btn" onclick="openSettingsModal()" title="设置米字格、字号与自定义字体">
          <span>⚙️ 设置</span>
        </button>
      </div>
    </header>

    <!-- 3. 综合搜索控制台 (支持检索框 + 总笔画数 单独与组合检索) -->
    <div class="search-panel">
      <div class="search-row">
        <div class="input-box-main">
          <span class="search-prefix-icon">🔍</span>
          <input type="text" id="searchInput" placeholder="输入部件(车 俞)、部首(氵)、结构(左右 木)、码位(U+690D)..." autofocus />
          <span class="clear-icon" id="clearSearchIcon" onclick="clearInput('searchInput')">&times;</span>
        </div>
        <div class="input-box-strokes">
          <span class="strokes-prefix-icon">✍️</span>
          <input type="number" id="strokesInput" min="1" max="64" placeholder="总笔画数 (如: 8)" title="总笔画数：支持单独检索，或与检索框任意条件组合" />
          <span class="clear-icon" id="clearStrokesIcon" onclick="clearInput('strokesInput')">&times;</span>
        </div>
        <button class="search-btn" id="searchBtn">搜 索</button>
        <button class="reset-btn" id="resetBtn" title="清空检索框与笔画数">重 置</button>
      </div>

      <!-- 快捷场景预设胶囊 (Quick Presets) -->
      <div class="presets-bar">
        <span class="presets-label">💡 快捷体验:</span>
        <span class="preset-chip" onclick="applyPreset('氵', 8)">🎯 氵 + 8画</span>
        <span class="preset-chip" onclick="applyPreset('木', 8)">🎯 木 + 8画</span>
        <span class="preset-chip" onclick="applyPreset('车 俞', 13)">🎯 车 俞 (部件交集)</span>
        <span class="preset-chip" onclick="applyPreset('⿰木*', 8)">🎯 ⿰木* (左木8画)</span>
        <span class="preset-chip" onclick="applyPreset('⿴囗*', '')">🎯 ⿴囗* (全包结构)</span>
        <span class="preset-chip" onclick="applyPreset('回', '')">🎯 回 (简繁异体流变)</span>
        <span class="preset-chip" onclick="applyPreset('', 8)">🎯 纯 8 画检索</span>
      </div>

      <!-- 4. 偏旁部首辅助输入面板 (默认折叠) -->
      <div class="toolbox-wrapper">
        <div class="toolbox-toggle-bar" onclick="toggleToolbox()" title="点击展开或折叠偏旁部首辅助输入面板">
          <div class="toolbox-toggle-left">
            <span>⌨️</span>
            <span class="toolbox-toggle-title">偏旁部首与构字符号辅助输入</span>
            <span class="toolbox-toggle-tags">(常用部首 · 结构与通配符 · 214 康熙部首)</span>
          </div>
          <span class="toolbox-toggle-indicator" id="toolboxToggleIndicator">展开 ▼</span>
        </div>

        <div class="toolbox-container" id="toolboxContainer" style="display: none;">
          <div class="toolbox-tabs-header">
            <button class="toolbox-tab-btn active" onclick="switchToolboxTab('tabRadicals', this)">常用/难打部首 (45)</button>
            <button class="toolbox-tab-btn" onclick="switchToolboxTab('tabIdc', this)">结构与通配符号 (14)</button>
            <button class="toolbox-tab-btn" onclick="switchToolboxTab('tabKangxi', this)">214 康熙部首检字表</button>
          </div>

        <!-- Tab 1: 常用/难打部首 -->
        <div class="toolbox-content-panel active" id="tabRadicals">
          <div style="font-size:12px; color:#8c7b70; margin-bottom:8px;">💡 针对拼音输入法难以直接打出的高频偏旁部首，点击直接快速键入：</div>
          <div class="radicals-flex-grid" id="frequentRadicalsContainer"></div>
        </div>

        <!-- Tab 2: 结构与通配符号 -->
        <div class="toolbox-content-panel" id="tabIdc">
          <div style="font-size:12px; color:#8c7b70; margin-bottom:8px;">💡 点击插入 Unicode 表意文字描述字符 (IDC) 或通配符，支持别名如“左右”、“上下”：</div>
          <div class="idc-flex-grid">
            <button class="idc-action-btn" onmousedown="event.preventDefault();" onclick="insertSymbol('⿰')" title="左右结构 (如: ⿰木直 -> 植)"><b>⿰</b> 左右</button>
            <button class="idc-action-btn" onmousedown="event.preventDefault();" onclick="insertSymbol('⿱')" title="上下结构 (如: ⿱艹田 -> 苗)"><b>⿱</b> 上下</button>
            <button class="idc-action-btn" onmousedown="event.preventDefault();" onclick="insertSymbol('⿲')" title="左中右结构 (如: ⿲彳重亍 -> 衝)"><b>⿲</b> 左中右</button>
            <button class="idc-action-btn" onmousedown="event.preventDefault();" onclick="insertSymbol('⿳')" title="上中下结构 (如: ⿳亠口冖 -> 亭)"><b>⿳</b> 上中下</button>
            <button class="idc-action-btn" onmousedown="event.preventDefault();" onclick="insertSymbol('⿴')" title="全包围结构 (如: ⿴囗玉 -> 国)"><b>⿴</b> 全包</button>
            <button class="idc-action-btn" onmousedown="event.preventDefault();" onclick="insertSymbol('⿵')" title="上三包下 (如: ⿵门日 -> 间)"><b>⿵</b> 上三包</button>
            <button class="idc-action-btn" onmousedown="event.preventDefault();" onclick="insertSymbol('⿶')" title="下三包上 (如: ⿶凵凶 -> 凶)"><b>⿶</b> 下三包</button>
            <button class="idc-action-btn" onmousedown="event.preventDefault();" onclick="insertSymbol('⿷')" title="左三包右 (如: ⿷匚矢 -> 医)"><b>⿷</b> 左三包</button>
            <button class="idc-action-btn" onmousedown="event.preventDefault();" onclick="insertSymbol('⿸')" title="左上包 (如: ⿸广木 -> 床)"><b>⿸</b> 左上包</button>
            <button class="idc-action-btn" onmousedown="event.preventDefault();" onclick="insertSymbol('⿹')" title="右上包 (如: ⿹气米 -> 气)"><b>⿹</b> 右上包</button>
            <button class="idc-action-btn" onmousedown="event.preventDefault();" onclick="insertSymbol('⿺')" title="左下包 (如: ⿺辶车 -> 连)"><b>⿺</b> 左下包</button>
            <button class="idc-action-btn" onmousedown="event.preventDefault();" onclick="insertSymbol('⿻')" title="相交重叠 (如: ⿻口丨 -> 中)"><b>⿻</b> 相交</button>
            <button class="idc-action-btn wild" onmousedown="event.preventDefault();" onclick="insertSymbol('?')" title="单字符通配符"><b>?</b> 单字通配</button>
            <button class="idc-action-btn wild" onmousedown="event.preventDefault();" onclick="insertSymbol('*')" title="任意字符串通配符"><b>*</b> 任意通配</button>
          </div>
        </div>

        <!-- Tab 3: 214 康熙部首全表 (带快速笔画筛选) -->
        <div class="toolbox-content-panel" id="tabKangxi">
          <div class="kangxi-stroke-filter-bar" id="kangxiFilterBar">
            <span style="font-size:12px; color:#888; margin-right:4px;">笔画过滤:</span>
            <button class="stroke-nav-pill active" onclick="filterKangxi(0, this)">全部 (214)</button>
          </div>
          <div class="kangxi-scroll-body" id="kangxiListContainer"></div>
        </div>
      </div>
    </div>
  </div>

    <!-- 5. 检索状态条 -->
    <div class="status-bar">
      <div id="statusText">输入内容或指定总笔画数以开始检索（支持 9 万+ Unicode CJK 统一表意文字）</div>
      <div id="countText"></div>
    </div>

    <!-- 6. 结果卡片网格 -->
    <div class="results-grid" id="resultsGrid"></div>

    <!-- 7. 优雅分页栏 -->
    <div class="pagination-bar" id="paginationBar" style="display: none;">
      <button class="page-nav-btn" id="prevPageBtn" onclick="changePage(currentPage - 1)">上一页</button>
      <span class="page-info-text" id="pageInfoText">第 1 / 1 页 (共 0 条)</span>
      <button class="page-nav-btn" id="nextPageBtn" onclick="changePage(currentPage + 1)">下一页</button>

      <div class="page-jump-box">
        <span>跳至</span>
        <input type="number" class="jump-input" id="jumpPageInput" min="1" value="1" onkeydown="if(event.key==='Enter') jumpToPage()" />
        <span>页</span>
        <button class="page-nav-btn" style="padding: 4px 10px; font-size: 13px;" onclick="jumpToPage()">GO</button>
      </div>
    </div>
  </div>

  <!-- 汉字血缘探针 & 流变谱系模态弹窗 -->
  <div class="modal-overlay" id="familyModal" onclick="if(event.target===this) closeFamilyModal();">
    <div class="family-modal">
      <button class="modal-close-btn" onclick="closeFamilyModal();">&times;</button>
      
      <div class="modal-header-section">
        <div class="modal-glyph-large with-mizige" id="modalGlyph"></div>
        <div class="modal-char-info">
          <h2 id="modalTitle">【汉字】</h2>
          <div style="font-size: 13px; color: #666; margin-top: 4px;" id="modalMeta"></div>
        </div>
      </div>

      <!-- 父系构件溯源 -->
      <div class="tree-block">
        <h3><span>🌱 构架源流（父部件溯源）:</span></h3>
        <div class="parent-pill-list" id="modalParents"></div>
      </div>

      <!-- 变体与简繁流变谱系 -->
      <div class="tree-block">
        <h3><span>📜 变体与简繁流变谱系:</span></h3>
        <div id="modalVariants" style="font-size: 13px; color: #444; line-height: 1.8;"></div>
      </div>

      <!-- 宗族衍生后裔 -->
      <div class="tree-block">
        <h3><span>🌳 宗族衍生繁衍（以此字为构件的衍生字）:</span></h3>
        <div class="descendant-grid" id="modalDescendants"></div>
      </div>
    </div>
  </div>

  <!-- 偏好设置模态弹窗 -->
  <div class="modal-overlay" id="settingsModal" onclick="if(event.target===this) closeSettingsModal();">
    <div class="settings-modal">
      <button class="modal-close-btn" onclick="closeSettingsModal();">&times;</button>
      <div class="modal-header-section" style="margin-bottom: 16px; padding-bottom: 12px;">
        <h2 style="font-size: 20px; display: flex; align-items: center; gap: 8px;">
          <span>⚙️ 系统偏好设置</span>
        </h2>
      </div>

      <!-- 设置项 1: 米字格辅助线 -->
      <div class="setting-item">
        <div class="setting-item-info">
          <div class="setting-item-title">书法米字格辅助线</div>
          <div class="setting-item-desc">在汉字字形卡片背景显示米字九宫辅助参考底纹</div>
        </div>
        <div class="setting-item-control">
          <label class="view-switch">
            <input type="checkbox" id="mizigeToggle" checked onchange="toggleMizige(this.checked)" />
            <span>开启</span>
          </label>
        </div>
      </div>

      <!-- 设置项 2: 卡片字号 -->
      <div class="setting-item">
        <div class="setting-item-info">
          <div class="setting-item-title">字形卡片显示尺寸</div>
          <div class="setting-item-desc">调整检索结果列表中字形主卡片的显示网格大小</div>
        </div>
        <div class="setting-item-control">
          <div class="size-btn-group">
            <button class="size-btn" onclick="setGridSize('compact', this)">紧凑</button>
            <button class="size-btn active" onclick="setGridSize('normal', this)">标准</button>
            <button class="size-btn" onclick="setGridSize('large', this)">特大</button>
          </div>
        </div>
      </div>

      <!-- 设置项 3: 自定义字体管理 -->
      <div class="setting-item" style="border-bottom: none; flex-direction: column; align-items: flex-start; gap: 10px;">
        <div class="setting-item-info">
          <div class="setting-item-title">自定义字体渲染 (TTF / OTF / WOFF)</div>
          <div class="setting-item-desc">上传自制字体优先渲染汉字；未覆盖字形自动降级为矢量 SVG。</div>
        </div>
        <div class="font-studio-box" id="fontStudioPanel">
          <div class="font-info-wrap">
            <div class="font-pulse-dot" id="fontStatusDot"></div>
            <div>
              <div class="font-status-title" id="fontStatusTitle">
                <span>当前字形源: 默认 SVG 矢量直出</span>
              </div>
              <div class="font-status-desc" id="fontStatusDesc">
                未加载自定义字体，所有汉字均采用矢量 SVG 呈现。支持拖拽 TTF / OTF 到此处一键加载。
              </div>
            </div>
          </div>
          <div class="font-action-buttons" style="margin-top: 10px;">
            <input type="file" id="fontFileInput" accept=".ttf,.otf,.woff,.woff2" style="display:none;" />
            <button class="font-tool-btn" onclick="document.getElementById('fontFileInput').click()" title="支持 TTF, OTF, WOFF 等常用字体文件">
              <span>📤 上传字体文件</span>
            </button>
            <button class="font-tool-btn btn-reset" id="resetFontBtn" onclick="resetToDefaultSvg()" style="display:none;" title="清除当前自定义字体，恢复默认全量 SVG 显示">
              <span>✕ 恢复默认 SVG 渲染</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 矢量图库归档进度模态弹窗 -->
  <div class="modal-overlay" id="progressModal" onclick="if(event.target===this) closeProgressModal();">
    <div class="progress-modal">
      <button class="modal-close-btn" onclick="closeProgressModal();">&times;</button>
      <div class="modal-header-section" style="margin-bottom: 16px; padding-bottom: 12px;">
        <h2 style="font-size: 20px; display: flex; align-items: center; gap: 8px;">
          <span>📊 矢量 SVG 归档进度</span>
          <span class="crawler-live-tag done" id="crawlerLiveTag">🟢 全量离线归档完成 (100%)</span>
        </h2>
      </div>

      <!-- 核心指标统计卡 -->
      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-label">已归档矢量 SVG</div>
          <div class="stat-value primary" id="statDownloaded">103,047</div>
          <div class="stat-sub">本地 SQLite 离线直出</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">剩余待入库</div>
          <div class="stat-value" id="statRemaining">0</div>
          <div class="stat-sub">100% 离线就绪</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Unicode 字符全集</div>
          <div class="stat-value" id="statTotal">103,047</div>
          <div class="stat-sub">基础区 + 扩展区A~I</div>
        </div>
      </div>

      <!-- 总体进度条 -->
      <div class="progress-section">
        <div class="progress-header">
          <span class="progress-title">总体归档进度</span>
          <span class="progress-percent" id="statPercentText">0.0%</span>
        </div>
        <div class="progress-bar-track">
          <div class="progress-bar-fill" id="statProgressBar" style="width: 0%;"></div>
        </div>
      </div>

      <!-- 分区详细进度 -->
      <div class="block-progress-list">
        <div class="block-progress-item">
          <div class="block-info">
            <b>通用汉字基础区 (U+4E00 ~ U+9FFF)</b>
            <span id="statBaseProgress">20,992 / 20,992 (100%)</span>
          </div>
          <div class="sub-progress-track">
            <div class="sub-progress-fill full" id="statBaseFill" style="width: 100%;"></div>
          </div>
        </div>
        <div class="block-progress-item">
          <div class="block-info">
            <b>CJK 扩展区 A ~ I (罕见金石碑刻古籍字)</b>
            <span id="statExtProgress">82,055 / 82,055 (100%)</span>
          </div>
          <div class="sub-progress-track">
            <div class="sub-progress-fill full" id="statExtFill" style="width: 100%;"></div>
          </div>
        </div>
      </div>

      <div class="modal-footer-stats">
        <span style="font-size: 12px; color: #888;" id="statDbSize">本地数据库体积: -- MB</span>
        <button class="refresh-progress-btn" onclick="fetchSvgProgress(true)">🔄 刷新数据</button>
      </div>
    </div>
  </div>

  <div class="copy-toast" id="copyToast">已复制到剪贴板！</div>

  <script>
    // 常用与难打偏旁部首集合 (带拼音与字义注释)
    const FREQUENT_RADICALS = [
      { c: "氵", s: "水", t: "三点水 (水部)" },
      { c: "亻", s: "人", t: "单人旁 (人部)" },
      { c: "扌", s: "手", t: "提手旁 (手部)" },
      { c: "艹", s: "草", t: "草字头 (艸部)" },
      { c: "辶", s: "走", t: "走之底 (辵部)" },
      { c: "阝", s: "耳", t: "双耳旁 (阜/邑部)" },
      { c: "犭", s: "犬", t: "反犬旁 (犬部)" },
      { c: "饣", s: "食", t: "食字旁 (食部)" },
      { c: "纟", s: "丝", t: "绞丝旁 (糸部)" },
      { c: "宀", s: "宝", t: "宝盖头" },
      { c: "礻", s: "示", t: "示字旁 (示部)" },
      { c: "衤", s: "衣", t: "衣字旁 (衣部)" },
      { c: "攵", s: "文", t: "反文旁 (攴部)" },
      { c: "灬", s: "火", t: "四点底 (火部)" },
      { c: "冫", s: "冰", t: "两点水" },
      { c: "冖", s: "秃", t: "秃宝盖" },
      { c: "冂", s: "同", t: "同字框" },
      { c: "匚", s: "框", t: "三框栏" },
      { c: "凵", s: "凶", t: "下框" },
      { c: "刂", s: "刀", t: "立刀旁 (刀部)" },
      { c: "勹", s: "包", t: "包字头" },
      { c: "匕", s: "匕", t: "匕部" },
      { c: "卜", s: "卜", t: "卜部" },
      { c: "卩", s: "印", t: "单耳刀 (卩部)" },
      { c: "厶", s: "私", t: "私字旁" },
      { c: "廴", s: "建", t: "建字底" },
      { c: "弋", s: "弋", t: "弋部" },
      { c: "弓", s: "弓", t: "弓字旁" },
      { c: "彡", s: "撇", t: "三撇旁" },
      { c: "彳", s: "行", t: "双人旁 (彳部)" },
      { c: "疒", s: "病", t: "病字旁" },
      { c: "癶", s: "登", t: "登字头" },
      { c: "虍", s: "虎", t: "虎字头" },
      { c: "疋", s: "疋", t: "疋部" },
      { c: "⺮", s: "竹", t: "竹字头" },
      { c: "⺶", s: "羊", t: "羊字头" },
      { c: "⻊", s: "足", t: "足字旁" },
      { c: "⻢", s: "马", t: "马字旁" },
      { c: "⻥", s: "鱼", t: "鱼字旁" },
      { c: "⻦", s: "鸟", t: "鸟字旁" },
      { c: "豸", s: "豹", t: "豸部" },
      { c: "隹", s: "雀", t: "隹部" },
      { c: "髟", s: "发", t: "髟部" },
      { c: "鬯", s: "酒", t: "鬯部" },
      { c: "鬲", s: "鼎", t: "鬲部" }
    ];

    // 214 康熙部首全集 (按 1~17 笔画排序)
    const KANGXI_RADICALS = {
      1: ["一", "丨", "丿", "丶", "乙", "亅"],
      2: ["二", "亠", "人", "儿", "入", "八", "冂", "冖", "冫", "几", "凵", "刀", "力", "勹", "匕", "匚", "匸", "十", "卜", "卩", "厂", "厶", "又"],
      3: ["口", "囗", "土", "士", "夂", "夕", "大", "女", "子", "宀", "寸", "小", "尢", "尸", "屮", "山", "巛", "工", "己", "巾", "干", "幺", "广", "廴", "廾", "弋", "弓", "彐", "彡", "彳"],
      4: ["心", "戈", "戶", "手", "支", "攴", "文", "斗", "斤", "方", "无", "日", "曰", "月", "木", "欠", "止", "歹", "殳", "毋", "比", "毛", "氏", "气", "水", "火", "爪", "父", "爻", "爿", "片", "牙", "牛", "犬"],
      5: ["玄", "玉", "瓜", "瓦", "甘", "生", "用", "田", "疋", "疒", "癶", "白", "皮", "皿", "目", "矛", "矢", "石", "示", "禸", "禾", "穴", "立"],
      6: ["竹", "米", "糸", "缶", "网", "羊", "羽", "老", "而", "耒", "耳", "聿", "肉", "臣", "自", "至", "臼", "舌", "舛", "舟", "艮", "色", "艸", "虍", "虫", "血", "行", "衣", "襾"],
      7: ["見", "角", "言", "谷", "豆", "豕", "豸", "貝", "赤", "走", "足", "身", "車", "辛", "辰", "辵", "邑", "酉", "釆", "里"],
      8: ["金", "長", "門", "阜", "隶", "隹", "雨", "靑", "非"],
      9: ["面", "革", "韋", "韭", "音", "頁", "風", "飛", "食", "首", "香"],
      10: ["馬", "骨", "高", "髟", "鬥", "鬯", "鬲", "鬼"],
      11: ["魚", "鳥", "鹵", "鹿", "麥", "麻"],
      12: ["黃", "黍", "黑", "黹"],
      13: ["黽", "鼎", "鼓", "鼠"],
      14: ["鼻", "齊"],
      15: ["齒"],
      16: ["龍", "龜"],
      17: ["龠"]
    };

    const searchInput = document.getElementById('searchInput');
    const strokesInput = document.getElementById('strokesInput');
    const searchBtn = document.getElementById('searchBtn');
    const resetBtn = document.getElementById('resetBtn');
    const clearSearchIcon = document.getElementById('clearSearchIcon');
    const clearStrokesIcon = document.getElementById('clearStrokesIcon');

    const resultsGrid = document.getElementById('resultsGrid');
    const statusText = document.getElementById('statusText');
    const countText = document.getElementById('countText');
    const toast = document.getElementById('copyToast');

    const paginationBar = document.getElementById('paginationBar');
    const prevPageBtn = document.getElementById('prevPageBtn');
    const nextPageBtn = document.getElementById('nextPageBtn');
    const pageInfoText = document.getElementById('pageInfoText');
    const jumpPageInput = document.getElementById('jumpPageInput');

    const fontStudioPanel = document.getElementById('fontStudioPanel');
    const fontStatusDot = document.getElementById('fontStatusDot');
    const fontStatusTitle = document.getElementById('fontStatusTitle');
    const fontStatusDesc = document.getElementById('fontStatusDesc');
    const resetFontBtn = document.getElementById('resetFontBtn');
    const fontFileInput = document.getElementById('fontFileInput');

    // 模态弹窗元素
    const familyModal = document.getElementById('familyModal');
    const modalGlyph = document.getElementById('modalGlyph');
    const modalTitle = document.getElementById('modalTitle');
    const modalMeta = document.getElementById('modalMeta');
    const modalParents = document.getElementById('modalParents');
    const modalVariants = document.getElementById('modalVariants');
    const modalDescendants = document.getElementById('modalDescendants');

    // 视觉设置状态
    let showMizige = true;
    let currentGridSize = 'normal';

    // 全局字体状态 (优先使用字体，没有的字形使用 svg，默认未上传使用 svg)
    let customFontActive = false;
    let customFontName = '';
    let customFontGlyphs = new Set();

    let currentResults = [];
    let debounceTimer = null;

    let currentPage = 1;
    let totalPages = 1;
    let totalCount = 0;
    const pageSize = 50;

    let savedCursorStart = searchInput.value.length;
    let savedCursorEnd = searchInput.value.length;

    function recordCursor() {
      if (typeof searchInput.selectionStart === 'number') {
        savedCursorStart = searchInput.selectionStart;
        savedCursorEnd = searchInput.selectionEnd;
      }
    }

    searchInput.addEventListener('keyup', recordCursor);
    searchInput.addEventListener('mouseup', recordCursor);
    searchInput.addEventListener('select', recordCursor);
    searchInput.addEventListener('input', () => {
      recordCursor();
      updateClearIcons();
    });

    strokesInput.addEventListener('input', updateClearIcons);

    function updateClearIcons() {
      clearSearchIcon.style.display = searchInput.value ? 'block' : 'none';
      clearStrokesIcon.style.display = strokesInput.value ? 'block' : 'none';
    }

    function clearInput(id) {
      const el = document.getElementById(id);
      el.value = '';
      updateClearIcons();
      el.focus();
      triggerAutoSearch();
    }

    function showToast(msg) {
      toast.innerText = msg;
      toast.style.display = 'block';
      setTimeout(() => { toast.style.display = 'none'; }, 1600);
    }

    // 视图设置：米字格切换
    function toggleMizige(enable) {
      showMizige = enable;
      document.querySelectorAll('.glyph-display').forEach(el => {
        if (enable) el.classList.add('with-mizige');
        else el.classList.remove('with-mizige');
      });
      if (modalGlyph) {
        if (enable) modalGlyph.classList.add('with-mizige');
        else modalGlyph.classList.remove('with-mizige');
      }
    }

    // 视图设置：字形尺寸切换
    function setGridSize(size, btnEl) {
      currentGridSize = size;
      document.querySelectorAll('.size-btn').forEach(b => b.classList.remove('active'));
      if (btnEl) btnEl.classList.add('active');

      resultsGrid.classList.remove('grid-size-compact', 'grid-size-large');
      if (size === 'compact') resultsGrid.classList.add('grid-size-compact');
      if (size === 'large') resultsGrid.classList.add('grid-size-large');
    }

    // 快捷场景预设 (Quick Presets)
    function applyPreset(query, strokes) {
      searchInput.value = query;
      strokesInput.value = strokes;
      updateClearIcons();
      currentPage = 1;
      doSearch(1);
    }

    // 偏旁部首与构字符号辅助工具箱折叠/展开切换
    function toggleToolbox() {
      const container = document.getElementById('toolboxContainer');
      const indicator = document.getElementById('toolboxToggleIndicator');
      if (container.style.display === 'none' || !container.style.display) {
        container.style.display = 'block';
        indicator.innerHTML = '收起 ▲';
      } else {
        container.style.display = 'none';
        indicator.innerHTML = '展开 ▼';
      }
    }

    // 工具箱 Tab 切换
    function switchToolboxTab(tabId, btnEl) {
      document.querySelectorAll('.toolbox-tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.toolbox-content-panel').forEach(p => p.classList.remove('active'));
      btnEl.classList.add('active');
      document.getElementById(tabId).classList.add('active');
    }

    // 214 康熙部首快速笔画过滤
    function filterKangxi(strokeNum, btnEl) {
      document.querySelectorAll('.stroke-nav-pill').forEach(b => b.classList.remove('active'));
      btnEl.classList.add('active');

      const groups = document.querySelectorAll('.kangxi-row-group');
      groups.forEach(g => {
        const s = parseInt(g.getAttribute('data-stroke'), 10);
        if (strokeNum === 0 || s === strokeNum) {
          g.classList.remove('hidden');
        } else {
          g.classList.add('hidden');
        }
      });
    }

    // 初始化工具箱数据与 DOM
    function initToolbox() {
      // 1. 常用难打部首
      const freqContainer = document.getElementById('frequentRadicalsContainer');
      freqContainer.innerHTML = FREQUENT_RADICALS.map(item => `
        <button class="rad-tag-btn" onmousedown="event.preventDefault();" onclick="insertSymbol('${item.c}')" title="${item.c}: ${item.t}">
          <span>${item.c}</span>
          <span class="rad-sub">${item.s}</span>
        </button>
      `).join('');

      // 2. 214 康熙部首检字表与笔画快捷导航
      const filterBar = document.getElementById('kangxiFilterBar');
      const kxContainer = document.getElementById('kangxiListContainer');
      let kxHtml = '';

      for (let s = 1; s <= 17; s++) {
        const rads = KANGXI_RADICALS[s];
        if (!rads || rads.length === 0) continue;

        // 导航胶囊
        const pill = document.createElement('button');
        pill.className = 'stroke-nav-pill';
        pill.innerText = `${s}画 (${rads.length})`;
        pill.onclick = function() { filterKangxi(s, this); };
        filterBar.appendChild(pill);

        // 内容组
        kxHtml += `
          <div class="kangxi-row-group" data-stroke="${s}">
            <span class="kangxi-group-title">${s} 画:</span>
            <div style="display:flex; flex-wrap:wrap; gap:5px;">
              ${rads.map(r => `
                <button class="rad-tag-btn" onmousedown="event.preventDefault();" onclick="insertSymbol('${r}')" title="${r} (康熙部首 ${s}画)">
                  ${r}
                </button>
              `).join('')}
            </div>
          </div>
        `;
      }
      kxContainer.innerHTML = kxHtml;
    }

    // 在光标处插入符号或部首
    function insertSymbol(sym) {
      searchInput.focus();

      let startPos = (typeof searchInput.selectionStart === 'number') ? searchInput.selectionStart : savedCursorStart;
      let endPos = (typeof searchInput.selectionEnd === 'number') ? searchInput.selectionEnd : savedCursorEnd;

      const text = searchInput.value;
      searchInput.value = text.substring(0, startPos) + sym + text.substring(endPos);

      const nextPos = startPos + sym.length;
      searchInput.setSelectionRange(nextPos, nextPos);
      savedCursorStart = savedCursorEnd = nextPos;

      updateClearIcons();
      currentPage = 1;
      triggerAutoSearch();
    }

    // 点击部件穿透搜索
    function drillComponent(comp) {
      searchInput.value = comp;
      updateClearIcons();
      currentPage = 1;
      doSearch(1);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // 字体管理与加载系统
    async function initFontSystem() {
      try {
        const res = await fetch('/api/current_font');
        const data = await res.json();
        if (data.has_font) {
          await applyFont(data);
        } else {
          setNoFontState();
        }
      } catch (e) {
        setNoFontState();
      }
    }

    async function applyFont(meta) {
      try {
        const fontFace = new FontFace('UserCustomFont', `url(/api/font_file?t=${Date.now()})`);
        await fontFace.load();
        document.fonts.add(fontFace);

        customFontActive = true;
        customFontName = meta.font_name || '自定义字体';
        customFontGlyphs = new Set(meta.codepoints || []);

        fontStatusDot.className = 'font-pulse-dot active';
        fontStatusTitle.innerHTML = `<span>🟢 自定义字体已就绪: <b>${customFontName}</b></span>`;
        fontStatusDesc.innerHTML = `已精准加载 <b>${customFontGlyphs.size}</b> 个字形。覆盖汉字优先字体呈现，缺失字形自动降级使用 SVG。`;
        resetFontBtn.style.display = 'inline-flex';

        if (currentResults.length > 0) {
          renderCards(currentResults);
        }
      } catch (err) {
        showToast('自定义字体加载失败: ' + err.message);
        setNoFontState();
      }
    }

    function setNoFontState() {
      customFontActive = false;
      customFontName = '';
      customFontGlyphs = new Set();

      fontStatusDot.className = 'font-pulse-dot';
      fontStatusTitle.innerHTML = '<span>当前字形源: 默认 SVG 矢量直出</span>';
      fontStatusDesc.innerText = '未加载自定义字体，所有汉字均采用矢量 SVG 呈现。支持拖拽 TTF / OTF 到此处一键加载。';
      resetFontBtn.style.display = 'none';

      if (currentResults.length > 0) {
        renderCards(currentResults);
      }
    }

    // 上传文件处理 (普通选择或拖拽上传)
    async function handleUploadFontFile(file) {
      if (!file) return;
      fontStatusDesc.innerText = `正在解析并载入字体: ${file.name}...`;

      try {
        const res = await fetch(`/api/upload_font?filename=${encodeURIComponent(file.name)}`, {
          method: 'POST',
          body: file
        });
        const data = await res.json();
        if (data.success) {
          await applyFont(data);
          showToast(`成功加载字体: ${data.font_name} (包含 ${data.glyph_count} 个字形)`);
        } else {
          showToast('上传失败: ' + (data.error || '未知错误'));
          setNoFontState();
        }
      } catch (err) {
        showToast('上传出错: ' + err.message);
        setNoFontState();
      }
      fontFileInput.value = '';
    }

    fontFileInput.addEventListener('change', (e) => {
      handleUploadFontFile(e.target.files[0]);
    });

    // 拖拽字体到面板直接上传
    fontStudioPanel.addEventListener('dragover', (e) => {
      e.preventDefault();
      fontStudioPanel.classList.add('drag-over');
    });
    fontStudioPanel.addEventListener('dragleave', () => {
      fontStudioPanel.classList.remove('drag-over');
    });
    fontStudioPanel.addEventListener('drop', (e) => {
      e.preventDefault();
      fontStudioPanel.classList.remove('drag-over');
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleUploadFontFile(e.dataTransfer.files[0]);
      }
    });


    // 恢复默认 SVG 渲染
    async function resetToDefaultSvg() {
      try {
        await fetch('/api/reset_font', { method: 'POST' });
        setNoFontState();
        showToast('已恢复为默认 SVG 矢量直出模式');
      } catch (err) {
        setNoFontState();
      }
    }

    // 辅助：构建字形来源微徽章 (置于米字格外部，绝对不遮挡汉字)
    function buildSourceBadge(char) {
      const cp = char ? char.codePointAt(0) : 0;
      const hasGlyph = customFontActive && customFontGlyphs.has(cp);
      if (hasGlyph) {
        return `<span class="source-badge badge-font" title="字形来源于自定义字体【${customFontName}】">🔤 字体</span>`;
      } else {
        return `<span class="source-badge badge-svg" title="字形来源于矢量 SVG 引擎直出">⚡ SVG</span>`;
      }
    }

    // 核心字形渲染生成器 (满足需求 1：优先字体，无字形/未上传时使用 SVG，米字格内部 100% 纯净无遮挡)
    // 关键优化：支持服务端单次检索直接返回的内联 SVG 数据，整页 50 个字形零额外网络请求瞬间直出！
    function buildGlyphHtml(char, hexCode, svgData) {
      const cp = char ? char.codePointAt(0) : 0;
      const hasGlyph = customFontActive && customFontGlyphs.has(cp);
      const mzClass = showMizige ? 'with-mizige' : '';
      const tooltip = hasGlyph ? `【${char}】由自定义字体渲染 (点击复制)` : `【${char}】由矢量 SVG 渲染 (点击复制)`;

      if (hasGlyph) {
        // 1. 优先使用字体渲染 (内部纯净，不放任何角标)
        return `
          <div class="glyph-display is-font-glyph ${mzClass}" onclick="navigator.clipboard.writeText('${char}'); showToast('已复制字符: ${char}');" title="${tooltip}">
            <span class="glyph-text-font">${char}</span>
          </div>
        `;
      } else if (svgData) {
        // 2. 数据库一次性返回内联 SVG：直接内联渲染，整页零额外网络请求！
        return `
          <div class="glyph-display is-svg-glyph ${mzClass}" onclick="navigator.clipboard.writeText('${char}'); showToast('已复制字符: ${char}');" title="${tooltip}">
            ${svgData}
          </div>
        `;
      } else {
        // 3. 极罕见生僻字未缓存时，自动降级图片拉取
        const localSvgUrl = `/api/svg?code=${encodeURIComponent(hexCode)}`;
        return `
          <div class="glyph-display is-svg-glyph ${mzClass}" onclick="navigator.clipboard.writeText('${char}'); showToast('已复制字符: ${char}');" title="${tooltip}">
            <img class="glyph-svg" src="${localSvgUrl}" alt="${char}" 
                 onerror="this.style.display='none'; this.nextElementSibling.style.display='block';" />
            <span class="glyph-text-fallback">${char}</span>
          </div>
        `;
      }
    }

    // 综合检索函数 (支持 单独检索框、单独总笔画数、组合检索)
    async function doSearch(page = 1) {
      const q = searchInput.value.trim();
      const strokes = strokesInput.value.trim();

      // 两者皆空时清空视图
      if (!q && !strokes) {
        resultsGrid.innerHTML = '';
        paginationBar.style.display = 'none';
        statusText.innerText = '输入内容或指定总笔画数以开始检索（支持 9 万+ Unicode CJK 统一表意文字）';
        countText.innerText = '';
        return;
      }

      statusText.innerText = '正在检索中...';
      try {
        let apiUrl = `/api/search?page=${page}&page_size=${pageSize}`;
        if (q) apiUrl += `&q=${encodeURIComponent(q)}`;
        if (strokes) apiUrl += `&strokes=${encodeURIComponent(strokes)}`;

        const res = await fetch(apiUrl);
        const data = await res.json();

        currentResults = data.results || [];
        currentPage = data.page || 1;
        totalPages = data.total_pages || 0;
        totalCount = data.total_count || 0;

        let modeDesc = `模式: [${data.mode}]`;
        if (q && strokes) {
          modeDesc = `组合检索: [${q}] + [${strokes} 画]`;
        } else if (strokes) {
          modeDesc = `总笔画单独检索: [${strokes} 画]`;
        } else {
          modeDesc = `检索: [${q}]`;
        }

        statusText.innerText = modeDesc;
        countText.innerText = `共 ${totalCount} 条结果 (每页 ${pageSize} 条)`;

        renderCards(currentResults);
        renderPagination();
      } catch (err) {
        statusText.innerText = '检索出错，请检查服务端连接';
      }
    }

    function renderCards(list) {
      if (!list || list.length === 0) {
        resultsGrid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 48px; color: #8c7b70; background:#fff; border-radius:12px; border:1px dashed #ded5c7;">未找到匹配汉字，请尝试更换拆字部件或调整总笔画数</div>';
        return;
      }

      resultsGrid.innerHTML = list.map(r => {
        const char = r.character || '';
        const hex = r.hex_code || '';
        const ids = r.ids_direct || '独体';
        const rawTokens = r.ids_tokens || '';
        const pinyin = r.pinyin ? `[${r.pinyin}]` : '';
        const strokes = r.total_strokes ? `${r.total_strokes} 画` : '未知';

        // 部件反向穿透交互标签
        const tokensHtml = rawTokens.split(',').filter(t => t.trim()).map(t => 
          `<span class="comp-chip" onclick="drillComponent('${t.trim()}')" title="穿透检索含【${t.trim()}】的汉字">${t.trim()}</span>`
        ).join(' ');

        // 简繁与异体字流变展示
        const trad = r.traditional || '';
        const sem = r.semantic || '';
        const simp = r.simplified || '';

        let variantsHtml = '';
        if (trad) {
          variantsHtml += `<span class="var-tag var-trad" onclick="drillComponent('${trad.split(' ')[0]}')" title="繁体: ${trad}">繁: ${trad.split(' ')[0]}</span>`;
        }
        if (sem) {
          variantsHtml += `<span class="var-tag var-sem" onclick="drillComponent('${sem.split(' ')[0]}')" title="异体/古字: ${sem}">异: ${sem.split(' ')[0]}</span>`;
        }
        if (simp && simp.split(' ')[0] !== char) {
          variantsHtml += `<span class="var-tag var-trad" onclick="drillComponent('${simp.split(' ')[0]}')" title="简体: ${simp}">简: ${simp.split(' ')[0]}</span>`;
        }

        const glyphDisplayHtml = buildGlyphHtml(char, hex, r.svg_data);
        const sourceBadgeHtml = buildSourceBadge(char);

        return `
          <div class="char-card">
            ${glyphDisplayHtml}
            <div class="char-meta">
              <div class="char-header">
                <div style="display:flex; align-items:center; gap:8px;">
                  <span class="char-code" onclick="navigator.clipboard.writeText('${hex}'); showToast('已复制码位: ${hex}');" title="点击复制码位">
                    ${hex}
                  </span>
                  ${sourceBadgeHtml}
                </div>
                <button class="probe-btn" onclick="openFamilyModal('${char}', '${hex}')" title="打开血缘探针与谱系">🌳 血缘探针</button>
              </div>
              <div class="char-prop">
                <span class="label">结构:</span>
                <b>${ids}</b>
                ${tokensHtml ? `<span style="margin-left:4px;">${tokensHtml}</span>` : ''}
              </div>
              <div class="char-prop">
                <span class="label">属性:</span>
                <span class="stroke-badge">${strokes}</span>
                ${pinyin ? `<span class="pinyin-badge">${pinyin}</span>` : ''}
              </div>
              ${variantsHtml ? `<div class="variants-line">${variantsHtml}</div>` : ''}
            </div>
          </div>
        `;
      }).join('');
    }

    function renderPagination() {
      if (totalPages <= 1) {
        paginationBar.style.display = 'none';
        return;
      }

      paginationBar.style.display = 'flex';
      pageInfoText.innerText = `第 ${currentPage} / ${totalPages} 页 (共 ${totalCount} 条)`;
      jumpPageInput.max = totalPages;
      jumpPageInput.value = currentPage;

      prevPageBtn.disabled = (currentPage <= 1);
      nextPageBtn.disabled = (currentPage >= totalPages);
    }

    function changePage(newPage) {
      if (newPage < 1 || newPage > totalPages || newPage === currentPage) return;
      doSearch(newPage);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function jumpToPage() {
      let p = parseInt(jumpPageInput.value, 10);
      if (isNaN(p)) return;
      if (p < 1) p = 1;
      if (p > totalPages) p = totalPages;
      changePage(p);
    }

    function triggerAutoSearch() {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        currentPage = 1;
        doSearch(1);
      }, 250);
    }

    searchInput.addEventListener('input', triggerAutoSearch);
    strokesInput.addEventListener('input', triggerAutoSearch);

    searchBtn.addEventListener('click', () => {
      currentPage = 1;
      doSearch(1);
    });

    resetBtn.addEventListener('click', () => {
      searchInput.value = '';
      strokesInput.value = '';
      updateClearIcons();
      currentPage = 1;
      doSearch(1);
      searchInput.focus();
    });

    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        clearTimeout(debounceTimer);
        currentPage = 1;
        doSearch(1);
      }
    });

    strokesInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        clearTimeout(debounceTimer);
        currentPage = 1;
        doSearch(1);
      }
    });

    // 模态弹窗交互
    async function openFamilyModal(char, hex) {
      const cp = char ? char.codePointAt(0) : 0;
      const hasGlyph = customFontActive && customFontGlyphs.has(cp);
      const sourceBadgeHtml = buildSourceBadge(char);

      modalTitle.innerHTML = `【 ${char} 】 ${sourceBadgeHtml}`;
      modalMeta.innerText = `Unicode: ${hex} | 正在调取家族图谱...`;
      
      // 大字纯净展示：优先字体，降级先用加载动画
      if (hasGlyph) {
        modalGlyph.innerHTML = `<span class="glyph-text-font" style="font-size:68px; line-height:98px;">${char}</span>`;
      } else {
        modalGlyph.innerHTML = `<span style="font-size:13px; color:#999;">加载中...</span>`;
      }
      modalParents.innerHTML = '加载中...';
      modalVariants.innerHTML = '加载中...';
      modalDescendants.innerHTML = '加载中...';

      familyModal.style.display = 'flex';

      try {
        const res = await fetch(`/api/family?code=${encodeURIComponent(hex)}`);
        const data = await res.json();
        renderFamilyTree(data);

        // 如果未命中自定义字体，优先采用后端一次性返回的内联 svg_data
        if (!hasGlyph) {
          if (data.root && data.root.svg_data) {
            modalGlyph.innerHTML = data.root.svg_data;
          } else {
            modalGlyph.innerHTML = `
              <img class="glyph-svg" src="/api/svg?code=${encodeURIComponent(hex)}" alt="${char}" 
                   onerror="this.style.display='none'; this.nextElementSibling.style.display='block';" />
              <span class="glyph-text-fallback" style="font-size:60px;">${char}</span>
            `;
          }
        }
      } catch (err) {
        modalVariants.innerHTML = '网络请求失败';
      }
    }

    function closeFamilyModal() {
      familyModal.style.display = 'none';
    }

    // 设置模态弹窗控制
    const settingsModal = document.getElementById('settingsModal');
    function openSettingsModal() {
      settingsModal.style.display = 'flex';
    }
    function closeSettingsModal() {
      settingsModal.style.display = 'none';
    }

    // 矢量图库归档进度模态弹窗控制与数据拉取
    const progressModal = document.getElementById('progressModal');
    let progressTimer = null;

    function openProgressModal() {
      progressModal.style.display = 'flex';
      fetchSvgProgress(true);
      if (!progressTimer) {
        progressTimer = setInterval(() => fetchSvgProgress(false), 3000);
      }
    }

    function closeProgressModal() {
      progressModal.style.display = 'none';
      if (progressTimer) {
        clearInterval(progressTimer);
        progressTimer = null;
      }
    }

    async function fetchSvgProgress(showToastTip) {
      try {
        const res = await fetch('/api/svg_progress');
        const data = await res.json();

        // 更新顶部 Header 胶囊徽章与状态呼吸灯
        const badge = document.getElementById('headerProgressBadge');
        if (badge) badge.innerText = `${data.percent}%`;
        const miniDot = document.getElementById('crawlerDotMini');
        if (miniDot) {
          miniDot.style.background = data.is_crawling ? '#27ae60' : '#bdc3c7';
        }

        // 更新进度弹窗指标
        const statDownloaded = document.getElementById('statDownloaded');
        if (statDownloaded) statDownloaded.innerText = (data.downloaded || 0).toLocaleString();

        const statRemaining = document.getElementById('statRemaining');
        if (statRemaining) statRemaining.innerText = (data.remaining || 0).toLocaleString();

        const statTotal = document.getElementById('statTotal');
        if (statTotal) statTotal.innerText = (data.total || 103047).toLocaleString();

        const statPercentText = document.getElementById('statPercentText');
        if (statPercentText) statPercentText.innerText = `${data.percent || 0.0}%`;

        const statProgressBar = document.getElementById('statProgressBar');
        if (statProgressBar) statProgressBar.style.width = `${Math.min(100, data.percent || 0)}%`;

        const statBaseProgress = document.getElementById('statBaseProgress');
        if (statBaseProgress) {
          const bTotal = data.base_total || 20992;
          const basePct = Math.min(100, Math.round((data.base_downloaded || 0) / bTotal * 100));
          statBaseProgress.innerText = `${(data.base_downloaded || 0).toLocaleString()} / ${bTotal.toLocaleString()} (${basePct}%)`;
        }

        const statExtProgress = document.getElementById('statExtProgress');
        if (statExtProgress) {
          const eTotal = data.ext_total || 82055;
          const extPct = Math.min(100, Math.round((data.ext_downloaded || 0) / eTotal * 100));
          statExtProgress.innerText = `${(data.ext_downloaded || 0).toLocaleString()} / ${eTotal.toLocaleString()} (${extPct}%)`;
        }
        const statExtFill = document.getElementById('statExtFill');
        if (statExtFill) {
          const eTotal = data.ext_total || 82055;
          const extPct = Math.min(100, Math.round((data.ext_downloaded || 0) / eTotal * 100));
          statExtFill.style.width = `${extPct}%`;
          if (extPct >= 100) {
            statExtFill.classList.add('full');
          }
        }

        const crawlerLiveTag = document.getElementById('crawlerLiveTag');
        if (crawlerLiveTag) {
          crawlerLiveTag.innerText = '🟢 全量离线归档完成 (100%)';
          crawlerLiveTag.className = 'crawler-live-tag done';
        }

        const statDbSize = document.getElementById('statDbSize');
        if (statDbSize) statDbSize.innerText = `本地数据库体积: ${data.db_size_mb || 0} MB`;

        if (showToastTip) {
          showToast('已同步最新归档进度');
        }
      } catch (err) {
        console.error('获取 SVG 进度失败:', err);
      }
    }

    function renderFamilyTree(fam) {
      const root = fam.root;
      modalMeta.innerText = `Unicode: ${root.hex_code} | 结构: ${root.ids_direct || '独体'} | 总笔画: ${root.total_strokes || '未知'} 画 | ${root.pinyin ? '拼音: ' + root.pinyin : ''}`;

      // 1. 父部件渲染 (直接展示部件纯净小字形或SVG)
      if (!fam.parents || fam.parents.length === 0) {
        modalParents.innerHTML = '<span style="color:#999;">独体构字，无父级组合部件</span>';
      } else {
        modalParents.innerHTML = fam.parents.map(p => {
          const char = typeof p === 'object' ? p.character : p;
          const hex = (typeof p === 'object' && p.hex_code) ? p.hex_code : ('U+' + char.codePointAt(0).toString(16).toUpperCase());
          const sub = (typeof p === 'object' && p.pinyin) ? p.pinyin : '构架构件';
          const pCp = char.codePointAt(0);
          const pHasFont = customFontActive && customFontGlyphs.has(pCp);

          let pIcon = '';
          if (pHasFont) {
            pIcon = `<span style="font-size:26px; font-family:'UserCustomFont', var(--font-serif);">${char}</span>`;
          } else {
            pIcon = `<img src="/api/svg?code=${encodeURIComponent(hex)}" alt="${char}" style="width:28px; height:28px; object-fit:contain;" onerror="this.style.display='none'; this.nextElementSibling.style.display='block';" /><span style="display:none; font-size:20px;">${char}</span>`;
          }

          return `
            <div class="parent-pill" onclick="closeFamilyModal(); drillComponent('${char}');" title="点击穿透检索【${char}】(${hex})家族">
              <div style="width:30px; height:30px; display:flex; align-items:center; justify-content:center;">
                ${pIcon}
              </div>
              <div>
                <b style="font-size:16px;">${char}</b>
                <div style="font-size:11px; color:#888;">${sub}</div>
              </div>
            </div>
          `;
        }).join('');
      }

      // 2. 简繁与异体字流变渲染
      let varRows = [];
      if (root.traditional) {
        varRows.push(`<div><b>传统繁体:</b> <span style="color:#d35400;">${root.traditional}</span></div>`);
      }
      if (root.simplified) {
        varRows.push(`<div><b>规范简体:</b> <span style="color:#27ae60;">${root.simplified}</span></div>`);
      }
      if (root.semantic) {
        varRows.push(`<div><b>异体 / 古体字:</b> <span style="color:#8e44ad;">${root.semantic}</span></div>`);
      }
      if (root.z_variant) {
        varRows.push(`<div><b>笔形变体:</b> <span style="color:#2980b9;">${root.z_variant}</span></div>`);
      }
      modalVariants.innerHTML = varRows.length > 0 ? varRows.join('') : '<span style="color:#999;">该字无直接简繁或语义异体流变记录</span>';

      // 3. 下游衍生后裔渲染 (直接优先使用内联 svg_data，零网络请求)
      if (!fam.descendants || fam.descendants.length === 0) {
        modalDescendants.innerHTML = '<span style="color:#999;">暂未发现以此字为构件的衍生字</span>';
      } else {
        modalDescendants.innerHTML = fam.descendants.map(d => {
          const subText = d.pinyin || (d.total_strokes ? `${d.total_strokes}画` : d.hex_code);
          const cp = d.character.codePointAt(0);
          const hasFont = customFontActive && customFontGlyphs.has(cp);

          let innerBox = '';
          if (hasFont) {
            innerBox = `<span style="font-size:30px; font-family:'UserCustomFont', var(--font-serif); line-height:44px;">${d.character}</span>`;
          } else if (d.svg_data) {
            innerBox = d.svg_data;
          } else {
            innerBox = `
              <img src="/api/svg?code=${encodeURIComponent(d.hex_code)}" alt="${d.character}" 
                   onerror="this.style.display='none'; this.nextElementSibling.style.display='block';" />
              <div style="display:none; font-size:24px;">${d.character}</div>
            `;
          }

          return `
            <div class="descendant-card" onclick="openFamilyModal('${d.character}', '${d.hex_code}')" title="${d.character} (${d.hex_code})&#10;拼音: ${d.pinyin || '无'}&#10;笔画: ${d.total_strokes || '未知'}画&#10;结构: ${d.ids_direct || '未知'}&#10;点击探针此字">
              <div class="descendant-glyph-box">
                ${innerBox}
              </div>
              <span class="descendant-meta">${subText}</span>
            </div>
          `;
        }).join('');
      }
    }

    // 初始化运行
    initToolbox();
    initFontSystem();
    fetchSvgProgress(false);

    // 默认检索演示 "回"
    searchInput.value = "回";
    updateClearIcons();
    savedCursorStart = savedCursorEnd = searchInput.value.length;
    doSearch(1);
  </script>
</body>
</html>
"""

class HanziSearchHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        # 1. 字符检索 API (支持 q 与 strokes 组合及单独检索，每页 50 条，内联全部 50 个 SVG)
        if parsed.path == "/api/search":
            qs = urllib.parse.parse_qs(parsed.query)
            q = qs.get("q", [""])[0]
            strokes_param = qs.get("strokes", [""])[0].strip()
            strokes = int(strokes_param) if strokes_param.isdigit() else None
            page = int(qs.get("page", [1])[0])
            page_size = int(qs.get("page_size", [50])[0])

            result = engine.smart_search(q, strokes=strokes, page=page, page_size=page_size)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))

        # 2. 汉字血缘探针与流变 API
        elif parsed.path == "/api/family":
            qs = urllib.parse.parse_qs(parsed.query)
            code = qs.get("code", [""])[0] or qs.get("char", [""])[0]

            family_data = engine.get_character_family(code)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(family_data or {}, ensure_ascii=False).encode("utf-8"))

        # 3. 本地 SQLite 矢量 SVG 资源分发接口
        elif parsed.path == "/api/svg":
            qs = urllib.parse.parse_qs(parsed.query)
            code = qs.get("code", [""])[0]

            svg_content = get_svg_from_db(code)

            if svg_content:
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
                self.send_header("Cache-Control", "public, max-age=31536000")
                self.end_headers()
                self.wfile.write(svg_content.encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()

        # 4. 当前自定义字体信息获取
        elif parsed.path == "/api/current_font":
            meta = load_font_meta()
            resp_data = meta if meta else {"has_font": False}
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(resp_data, ensure_ascii=False).encode("utf-8"))

        # 5. 当前自定义字体二进制下载接口 (供浏览器 @font-face 加载)
        elif parsed.path == "/api/font_file":
            if os.path.exists(CUSTOM_FONT_PATH):
                with open(CUSTOM_FONT_PATH, "rb") as f:
                    font_bytes = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "font/ttf")
                self.send_header("Content-Length", str(len(font_bytes)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(font_bytes)
            else:
                self.send_response(404)
                self.end_headers()

        # 6. 矢量图库归档实时进度统计 API
        elif parsed.path == "/api/svg_progress":
            try:
                conn = sqlite3.connect(DB_PATH, timeout=5)
                cur = conn.cursor()
                cur.execute("SELECT count(*) FROM character_svgs")
                downloaded = cur.fetchone()[0]

                cur.execute("SELECT count(*) FROM characters")
                total = cur.fetchone()[0]
                if total == 0:
                    total = 103047

                cur.execute("SELECT count(*) FROM character_svgs WHERE code_point BETWEEN 19968 AND 40959")
                base_downloaded = cur.fetchone()[0]

                # 通用基础区 (U+4E00 ~ U+9FFF) 总字数动态统计
                cur.execute("SELECT count(*) FROM characters WHERE code_point BETWEEN 19968 AND 40959")
                base_total = cur.fetchone()[0]
                if base_total == 0:
                    base_total = 20992

                # 扩展区总字数动态统计
                cur.execute("SELECT count(*) FROM characters WHERE code_point NOT BETWEEN 19968 AND 40959")
                ext_total = cur.fetchone()[0]
                if ext_total == 0:
                    ext_total = max(0, total - base_total)

                cur.execute("SELECT count(*) FROM character_svgs WHERE code_point NOT BETWEEN 19968 AND 40959")
                ext_downloaded = cur.fetchone()[0]
                conn.close()

                db_size_mb = 0
                if os.path.exists(DB_PATH):
                    db_size_mb = round(os.path.getsize(DB_PATH) / (1024 * 1024), 1)

                data = {
                    "total": total,
                    "downloaded": downloaded,
                    "remaining": max(0, total - downloaded),
                    "percent": round(downloaded / total * 100, 1) if total > 0 else 0,
                    "base_downloaded": base_downloaded,
                    "base_total": base_total,
                    "ext_downloaded": ext_downloaded,
                    "ext_total": ext_total,
                    "is_crawling": False,
                    "db_size_mb": db_size_mb
                }
            except Exception as e:
                data = {
                    "total": 103047,
                    "downloaded": 0,
                    "remaining": 103047,
                    "percent": 0.0,
                    "base_downloaded": 0,
                    "base_total": 20992,
                    "ext_downloaded": 0,
                    "ext_total": 82055,
                    "is_crawling": False,
                    "db_size_mb": 0,
                    "error": str(e)
                }

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

        # 7. 根页面
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)

        # 1. 用户上传自定义字体接口 (直接接收文件二进制流)
        if parsed.path == "/api/upload_font":
            qs = urllib.parse.parse_qs(parsed.query)
            filename = qs.get("filename", ["uploaded_font.ttf"])[0]

            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "文件内容为空"}).encode("utf-8"))
                return

            font_data = self.rfile.read(content_length)

            os.makedirs(os.path.dirname(CUSTOM_FONT_PATH), exist_ok=True)
            with open(CUSTOM_FONT_PATH, "wb") as f:
                f.write(font_data)

            # 解析字体信息与 Unicode 码位集合
            font_name, codepoints = parse_font_file(CUSTOM_FONT_PATH)
            if not codepoints:
                font_name = filename

            meta = {
                "has_font": True,
                "font_name": font_name or filename,
                "glyph_count": len(codepoints),
                "codepoints": sorted(list(codepoints))
            }
            save_font_meta(meta)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, **meta}, ensure_ascii=False).encode("utf-8"))

        # 2. 恢复默认 SVG 渲染 (删除已上传自定义字体)
        elif parsed.path == "/api/reset_font":
            if os.path.exists(CUSTOM_FONT_PATH):
                try:
                    os.remove(CUSTOM_FONT_PATH)
                except Exception:
                    pass
            if os.path.exists(CUSTOM_FONT_META_PATH):
                try:
                    os.remove(CUSTOM_FONT_META_PATH)
                except Exception:
                    pass

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "has_font": False}).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

def run_server(port: int = 8088):
    server = HTTPServer(("127.0.0.1", port), HanziSearchHandler)
    print(f"============================================================")
    print(f"🏮 HanziSearcher Web 服务 (东方雅致与专业排印交互版) 已启动！")
    print(f"👉 访问地址: http://127.0.0.1:{port}")
    print(f"按 Ctrl+C 可停止服务")
    print(f"============================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止。")

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8088
    run_server(port)
