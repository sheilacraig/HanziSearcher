# HanziSearcher

本地汉字拆字检索与矢量字形展示系统。基于 Unicode 15.1 Unihan、CJKVI-IDS 与 GlyphWiki 数据集，离线收录 103,047 个汉字（基础区及扩展区 A~I）的属性元数据与全量 SVG 矢量字形。

## 功能概述

- **全量离线数据**：收录 103,047 个汉字元数据及对应的本地 SVG 矢量字形，未安装生僻字字体的环境下亦可正常显示。
  - 通用汉字基础区（U+4E00 ~ U+9FFF）：20,992 字
  - CJK 扩展区 A ~ I：82,055 字
- **多维度检索**：
  - 部件检索：支持多部件空格分隔求交集（如 `车 俞`）。
  - 结构检索：支持表意描述符（IDC）与中文别名（如 `⿰木直`、`左右 木 直`）。
  - 通配检索：支持 `?` 通配符（如 `⿰木?`）。
  - 笔画与部首：支持按总笔画数过滤，内置 214 康熙部首检字表。
- **字形流变与构字衍生**：
  - 显示字形组成的父构件及下游派生汉字列表。
  - 展示规范简繁对应、语义异体字及笔形变体。
- **自定义字体渲染**：
  - 支持上传本地 TTF/OTF 字体文件，自动解析 cmap 字符覆盖范围。
  - 字体未覆盖字符自动降级为本地 SVG 矢量渲染。
  - 支持紧凑 / 标准 / 特大视图切换与米字格辅助线开关。

## 运行方式

### 运行环境
- Python 3.8+
- SQLite 3

### 启动服务
默认监听端口为 `8088`。

前台运行：
```bash
.venv/bin/python web_server.py 8088
```
访问地址：http://127.0.0.1:8088

后台运行：
```bash
nohup .venv/bin/python web_server.py 8088 > web_server.log 2>&1 &
```

停止后台服务：
```bash
kill $(lsof -t -i :8088)
```

## 检索语法

| 检索类型 | 输入示例 | 说明 |
| :--- | :--- | :--- |
| 单字 / 码位 | `输`、`U+8F93`、`0x8F93` | 精确匹配单字或 Unicode 码位 |
| 拼音检索 | `shu` | 匹配对应拼音的汉字 |
| 部件交集 | `车 俞` | 空格分隔，检索同时包含指定构件的汉字 |
| 空间结构 | `⿰木直`、`左右 木 直` | 支持 IDC 符号或中文别名（左右、上下、全包等） |
| 通配符 | `⿰木?` | `?` 代表任意单一构件 |
| 笔画过滤 | 笔画框输入数值 | 可单独按笔画检索，也可与搜索词叠加筛选 |

## API 说明

### 1. 汉字检索
- **URL**：`GET /api/search`
- **参数**：
  - `q`：检索词（字符、部件、IDS 表达式、拼音、码位）
  - `strokes`：（可选）总笔画数
  - `page`：（可选）页码，默认 `1`
  - `page_size`：（可选）每页条数，默认 `50`
- **返回**：JSON，包含 `total_count`、`total_pages`、`results` 列表。

### 2. 构字衍生关系
- **URL**：`GET /api/family`
- **参数**：`code`（字符或码位）
- **返回**：JSON，包含当前字属性、父部件 `parents` 与衍生字 `descendants`。

### 3. SVG 矢量图片
- **URL**：`GET /api/svg`
- **参数**：`code`（字符或码位）
- **返回**：`image/svg+xml` 图片流。

### 4. 归档状态
- **URL**：`GET /api/svg_progress`
- **返回**：JSON，包含全集总数、已入库数、分区分组统计与数据库体积。

### 5. 字体管理
- **上传字体**：`POST /api/upload_font?filename=<name>`（Body 为字体二进制内容）
- **获取当前字体状态**：`GET /api/current_font`
- **获取字体文件**：`GET /api/font_file`
- **恢复默认设置**：`POST /api/reset_font`

## 目录结构

```text
.
├── web_server.py         # HTTP 服务及前端页面
├── searcher/
│   ├── __init__.py       # 模块包导出
│   ├── engine.py         # 检索逻辑、构件索引与异体字处理
│   └── font_parser.py    # 字体 cmap 二进制解析
├── data/
│   └── hanzi.db          # SQLite 数据库（内联 zlib 压缩，约 156MB）
│       ├── characters         # 103,047 条汉字基础元数据
│       ├── character_svgs     # 103,047 条离线 SVG 矢量数据（压缩 BLOB）
│       └── character_variants # 16,825 条简繁及异体字关联数据
└── README.md
```

## 数据来源

- [Unicode Unihan Database](https://www.unicode.org/charts/unihan.html)
- [CJKVI-IDS](https://github.com/cjkvi/cjkvi-ids)
- [GlyphWiki](https://glyphwiki.org/)
