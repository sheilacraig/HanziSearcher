"""
自定义字体管理模块：处理用户上传字体的持久化存储、元数据提取与解析
"""

import json
import os
from typing import Optional, Dict, Any

CUSTOM_FONT_PATH = "data/custom_font.ttf"
CUSTOM_FONT_META_PATH = "data/custom_font_meta.json"
MAX_FONT_BYTES = 100 * 1024 * 1024  # 上传字体大小上限 100MB，防内存耗尽


def load_font_meta() -> Optional[Dict[str, Any]]:
    """读取已存储的自定义字体元数据"""
    if os.path.exists(CUSTOM_FONT_META_PATH) and os.path.exists(CUSTOM_FONT_PATH):
        try:
            with open(CUSTOM_FONT_META_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def save_font_meta(meta: Dict[str, Any]) -> None:
    """保存自定义字体元数据"""
    os.makedirs(os.path.dirname(CUSTOM_FONT_META_PATH), exist_ok=True)
    with open(CUSTOM_FONT_META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def remove_custom_font() -> None:
    """清除当前自定义字体与元数据文件，恢复系统默认渲染"""
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
