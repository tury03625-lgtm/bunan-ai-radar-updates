#!/bin/bash
set -euo pipefail

BASE_RAW="https://raw.githubusercontent.com/tury03625-lgtm/bunan-ai-radar-updates/main"
BASE_API="https://api.github.com/repos/tury03625-lgtm/bunan-ai-radar-updates/contents"
BASE_CDN="https://cdn.jsdelivr.net/gh/tury03625-lgtm/bunan-ai-radar-updates@main"
EXPECTED_BUNDLE="f61ddc6cb5a95db3f8e9d3921de1454238a4288972c6ff67e7eb126299d193f8"
EXPECTED_PY="44439005be277fda02d15145482acd7658df546e66fa58d17f54e0922ca07dd2"
TMP="$(mktemp -d /tmp/bunan-v0241-full.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT
PY="/usr/bin/python3"; [ -x "$PY" ] || PY="$(command -v python3 || true)"
[ -n "$PY" ] || { echo '❌ 未找到Python3，请截图给ChatGPT。'; exit 1; }

echo ''
echo '========================================================'
echo ' 不楠先生 AI招商雷达 V0.2.4.1｜完整文件热修复'
echo '========================================================'
echo ''
echo 'ℹ️ 本次不再修改现有代码片段，而是安装已校验的完整程序文件。'

fetch_part(){
  local path="$1" out="$2"
  echo "⏳ 下载 $path"
  if /usr/bin/curl -fL --retry 3 --retry-delay 1 --retry-all-errors --connect-timeout 8 --max-time 45 "$BASE_RAW/$path" -o "$out" 2>/dev/null && [ -s "$out" ]; then
    echo '   ✅ GitHub Raw'
    return 0
  fi
  rm -f "$out"
  echo '   ⚠️ Raw失败，切换GitHub API'
  if /usr/bin/curl -fL --retry 3 --retry-delay 1 --retry-all-errors --connect-timeout 8 --max-time 45 -H 'Accept: application/vnd.github+json' "$BASE_API/$path?ref=main" -o "$TMP/api.json" 2>/dev/null; then
    if "$PY" - "$TMP/api.json" "$out" <<'PYCODE'
import sys,json,base64
from pathlib import Path
obj=json.loads(Path(sys.argv[1]).read_text())
content=obj.get('content') or ''
if obj.get('encoding')=='base64': data=base64.b64decode(content)
else: data=str(content).encode()
Path(sys.argv[2]).write_bytes(data)
PYCODE
    then
      if [ -s "$out" ]; then echo '   ✅ GitHub API'; return 0; fi
    fi
  fi
  rm -f "$out"
  echo '   ⚠️ API失败，切换jsDelivr CDN'
  if /usr/bin/curl -fL --retry 3 --retry-delay 1 --retry-all-errors --connect-timeout 8 --max-time 45 "$BASE_CDN/$path" -o "$out" 2>/dev/null && [ -s "$out" ]; then
    echo '   ✅ jsDelivr CDN'
    return 0
  fi
  echo "❌ 三个通道都无法下载：$path"
  return 1
}

for n in 1 2 3 4; do
  fetch_part "bootstrap/v0.2.4.1-full.part$n" "$TMP/part$n"
done
cat "$TMP/part1" "$TMP/part2" "$TMP/part3" "$TMP/part4" > "$TMP/bundle.b64"

ACTUAL=$(/usr/bin/shasum -a 256 "$TMP/bundle.b64" | awk '{print $1}')
if [ "$ACTUAL" != "$EXPECTED_BUNDLE" ]; then
  echo '❌ 更新包SHA256校验失败，已停止，不会修改现有程序。'
  exit 1
fi
echo '✅ 下载包SHA256校验通过'

"$PY" - "$TMP/bundle.b64" "$TMP/hotfix.py" "$EXPECTED_PY" <<'PYCODE'
import sys,base64,zlib,hashlib
from pathlib import Path
src,out,expected=sys.argv[1:4]
raw=zlib.decompress(base64.b64decode(Path(src).read_text().strip()))
h=hashlib.sha256(raw).hexdigest()
if h!=expected: raise SystemExit('❌ 热修复程序SHA256校验失败，已停止。')
Path(out).write_bytes(raw)
print('✅ 热修复程序SHA256校验通过')
PYCODE

"$PY" "$TMP/hotfix.py"
