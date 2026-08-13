#!/bin/bash
set -euo pipefail

RAW_URL="https://raw.githubusercontent.com/tury03625-lgtm/bunan-ai-radar-updates/main/bootstrap/v0.2.4.py.zlib.b64"
API_URL="https://api.github.com/repos/tury03625-lgtm/bunan-ai-radar-updates/contents/bootstrap/v0.2.4.py.zlib.b64?ref=main"
CDN_URL="https://cdn.jsdelivr.net/gh/tury03625-lgtm/bunan-ai-radar-updates@main/bootstrap/v0.2.4.py.zlib.b64"
EXPECTED="3e7eb1d40dbb9ed0bfc6577235a448424142629dc2afd64032f7c199050a1a7a"
TMP="$(mktemp -d /tmp/bunan-v024.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

echo ""
echo "========================================================"
echo " 不楠先生 AI招商雷达 V0.2.4｜最后一次引导升级"
echo "========================================================"
echo ""

PY="/usr/bin/python3"
if [ ! -x "$PY" ]; then PY="$(command -v python3 || true)"; fi
if [ -z "$PY" ]; then
  echo "❌ 未找到 Python 3，请截图发给 ChatGPT。"
  exit 1
fi

SUCCESS=0

echo "⏳ 通道1：GitHub Raw（自动重试）……"
if /usr/bin/curl -fL --retry 4 --retry-delay 2 --retry-all-errors --connect-timeout 10 --max-time 50 "$RAW_URL" -o "$TMP/bootstrap.b64"; then
  if [ -s "$TMP/bootstrap.b64" ]; then SUCCESS=1; fi
fi

if [ "$SUCCESS" -ne 1 ]; then
  echo "⚠️ Raw通道超时，自动切换通道2：GitHub API……"
  rm -f "$TMP/bootstrap.b64" "$TMP/api.json"
  if /usr/bin/curl -fL --retry 4 --retry-delay 2 --retry-all-errors --connect-timeout 10 --max-time 50 \
      -H "Accept: application/vnd.github+json" \
      -H "User-Agent: bunan-ai-radar-updater" \
      "$API_URL" -o "$TMP/api.json"; then
    if "$PY" - "$TMP/api.json" "$TMP/bootstrap.b64" <<'PYCODE'
import sys, json, base64
from pathlib import Path
src, dst = sys.argv[1:3]
obj = json.loads(Path(src).read_text(encoding='utf-8'))
content = obj.get('content')
if not content:
    raise SystemExit(2)
raw = base64.b64decode(content)
Path(dst).write_bytes(raw)
PYCODE
    then
      if [ -s "$TMP/bootstrap.b64" ]; then SUCCESS=1; fi
    fi
  fi
fi

if [ "$SUCCESS" -ne 1 ]; then
  echo "⚠️ GitHub API仍不可用，自动切换通道3：CDN……"
  rm -f "$TMP/bootstrap.b64"
  if /usr/bin/curl -fL --retry 4 --retry-delay 2 --retry-all-errors --connect-timeout 10 --max-time 50 "$CDN_URL" -o "$TMP/bootstrap.b64"; then
    if [ -s "$TMP/bootstrap.b64" ]; then SUCCESS=1; fi
  fi
fi

if [ "$SUCCESS" -ne 1 ]; then
  echo ""
  echo "❌ 三个更新通道都无法访问。现有V0.2.3没有被修改。"
  echo "请把这一屏截图发给 ChatGPT。"
  exit 1
fi

echo "✅ 更新器下载成功，正在做SHA256安全校验……"

"$PY" - "$TMP/bootstrap.b64" "$TMP/bootstrap.py" "$EXPECTED" <<'PYCODE'
import sys,base64,zlib,hashlib
from pathlib import Path
src,out,expected=sys.argv[1:4]
try:
    raw=zlib.decompress(base64.b64decode(Path(src).read_text().strip()))
except Exception as e:
    raise SystemExit(f"❌ 更新器解压失败：{e}")
h=hashlib.sha256(raw).hexdigest()
if h.lower()!=expected.lower():
    raise SystemExit("❌ 更新器SHA256校验失败，已停止安装。")
Path(out).write_bytes(raw)
print("✅ 更新器SHA256校验通过")
PYCODE

"$PY" "$TMP/bootstrap.py"
