#!/bin/bash
set -u
APP_DIR="$HOME/Library/Application Support/GaoxinRadar"
STATIC_DIR="$APP_DIR/static"
LABEL="com.gaoxin.radar.v02"
PORT_FILE="$APP_DIR/port.txt"
REPO="tury03625-lgtm/bunan-ai-radar-updates"
TARGET="V0.2.6.2"
SERVER_PATH="releases/V0.2.6.2/server.py"
OCR_PATH="releases/V0.2.6.2/static/ocr.js"
SERVER_SHA="1c6c2272e32dd0134ed47d05412a6b0ed99e3614151ee3408ddd419f0f0cd6e5"
OCR_SHA="6697b32b2c34eefbb889b80c077a9edebc57be2f2f1375800adeeb0242d22668"

echo ""
echo "========================================================"
echo " 不楠先生 AI招商雷达 V0.2.6.2｜救援修复"
echo "========================================================"
echo ""

if [ ! -f "$PORT_FILE" ]; then
  echo "❌ 找不到端口配置：$PORT_FILE"
  exit 1
fi
PORT="$(cat "$PORT_FILE")"
mkdir -p "$STATIC_DIR" "$APP_DIR/backups"
TMP="$(mktemp -d)"
BACKUP="$APP_DIR/backups/rescue-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP/static"
trap 'rm -rf "$TMP"' EXIT

[ -f "$APP_DIR/server.py" ] && cp "$APP_DIR/server.py" "$BACKUP/server.py"
[ -f "$STATIC_DIR/ocr.js" ] && cp "$STATIC_DIR/ocr.js" "$BACKUP/static/ocr.js"

download_file() {
  local repo_path="$1" out="$2"
  echo "⬇️  下载 $repo_path"
  if /usr/bin/curl --noproxy "*" -fL --retry 2 --retry-delay 1 --connect-timeout 8 --max-time 45 \
      "https://raw.githubusercontent.com/$REPO/main/$repo_path" -o "$out"; then return 0; fi
  echo "  Raw失败，切换 GitHub API…"
  if /usr/bin/curl --noproxy "*" -fL --retry 2 --retry-delay 1 --connect-timeout 8 --max-time 45 \
      -H "Accept: application/vnd.github.raw+json" \
      "https://api.github.com/repos/$REPO/contents/$repo_path" -o "$out"; then return 0; fi
  echo "  API失败，切换 jsDelivr…"
  /usr/bin/curl --noproxy "*" -fL --retry 2 --retry-delay 1 --connect-timeout 8 --max-time 45 \
      "https://cdn.jsdelivr.net/gh/$REPO@main/$repo_path" -o "$out"
}

download_file "$SERVER_PATH" "$TMP/server.py" || { echo "❌ server.py 下载失败"; exit 1; }
download_file "$OCR_PATH" "$TMP/ocr.js" || { echo "❌ ocr.js 下载失败"; exit 1; }

ACT_SERVER="$(/usr/bin/shasum -a 256 "$TMP/server.py" | awk '{print $1}')"
ACT_OCR="$(/usr/bin/shasum -a 256 "$TMP/ocr.js" | awk '{print $1}')"
if [ "$ACT_SERVER" != "$SERVER_SHA" ]; then echo "❌ server.py SHA256不一致，停止安装"; exit 1; fi
if [ "$ACT_OCR" != "$OCR_SHA" ]; then echo "❌ ocr.js SHA256不一致，停止安装"; exit 1; fi
if /usr/bin/grep -q "new MutationObserver" "$TMP/ocr.js"; then echo "❌ 检测到旧版MutationObserver，拒绝安装"; exit 1; fi
/usr/bin/python3 -m py_compile "$TMP/server.py" || { echo "❌ server.py语法检查失败"; exit 1; }

echo "✅ 下载与SHA256校验通过"
cp "$TMP/server.py" "$APP_DIR/server.py"
cp "$TMP/ocr.js" "$STATIC_DIR/ocr.js"

echo "🔄 正在重启后台服务…"
launchctl kickstart -k "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true

SUCCESS=0
for i in $(seq 1 40); do
  H=$(/usr/bin/curl --noproxy "*" --connect-timeout 1 --max-time 2 -s "http://127.0.0.1:$PORT/api/health" 2>/dev/null || true)
  if echo "$H" | /usr/bin/grep -Eq '"version"[[:space:]]*:[[:space:]]*"V0\.2\.6\.2"'; then
    SUCCESS=1
    break
  fi
  sleep 1
done

if [ "$SUCCESS" -eq 1 ]; then
  echo "🎉 V0.2.6.2 救援修复成功"
  open "http://127.0.0.1:$PORT/?repair=0262&ts=$(date +%s)"
  exit 0
fi

echo "❌ 新版健康检查失败，正在自动恢复旧版…"
[ -f "$BACKUP/server.py" ] && cp "$BACKUP/server.py" "$APP_DIR/server.py"
[ -f "$BACKUP/static/ocr.js" ] && cp "$BACKUP/static/ocr.js" "$STATIC_DIR/ocr.js"
launchctl kickstart -k "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
sleep 2

echo "---- launchd.err.log ----"
tail -60 "$APP_DIR/launchd.err.log" 2>/dev/null || true
echo "---- radar.log ----"
tail -80 "$APP_DIR/radar.log" 2>/dev/null || true
echo "⚠️ 已恢复旧版。请把这一屏截图发给ChatGPT。"
exit 1
