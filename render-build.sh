#!/usr/bin/env bash
#
# Render 构建脚本：准备运行时所需文件。
# 应用是纯标准库 Python，无第三方依赖，无需 pip install。
set -euo pipefail

# 1. 下载 SQLite 数据库（~164MB，固定版本 v1.0.0，与 Dockerfile.vercel 一致）
mkdir -p data
if [ ! -f data/hanzi.db ] || [ "$(wc -c < data/hanzi.db)" -lt 100000000 ]; then
  echo "downloading hanzi.db ..."
  curl -sSL -o data/hanzi.db \
    https://github.com/sheilacraig/HanziSearcher/releases/download/v1.0.0/hanzi.db
fi
test "$(wc -c < data/hanzi.db)" -gt 100000000
echo "hanzi.db ready: $(wc -c < data/hanzi.db) bytes"

# 2. 预编译字节码，加速冷启动
python3 -m compileall -q web_server.py searcher server
echo "build done"
