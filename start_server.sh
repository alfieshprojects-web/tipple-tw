#!/bin/bash
# NIGHTLY — 本機開發伺服器
# 執行方式：bash start_server.sh
# 或直接雙擊（Mac 需先允許執行）

echo "🍸 NIGHTLY 本機伺服器啟動中..."
echo ""
echo "   開啟瀏覽器後，前往："
echo "   http://localhost:8080"
echo ""
echo "   按 Ctrl+C 停止"
echo ""

# 優先使用 Python 3，備選 Python 2
if command -v python3 &> /dev/null; then
    python3 -m http.server 8080
elif command -v python &> /dev/null; then
    python -m SimpleHTTPServer 8080
else
    echo "❌ 找不到 Python，請先安裝 Python 3"
    echo "   下載：https://www.python.org/downloads/"
fi
