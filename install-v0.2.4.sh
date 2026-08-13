#!/bin/bash
set -euo pipefail
URL="https://raw.githubusercontent.com/tury03625-lgtm/bunan-ai-radar-updates/main/bootstrap/v0.2.4.py.zlib.b64"
EXPECTED="3e7eb1d40dbb9ed0bfc6577235a448424142629dc2afd64032f7c199050a1a7a"
TMP="$(mktemp -d /tmp/bunan-v024.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

echo ""
echo "========================================================"
echo " 不楠先生 AI招商雷达 V0.2.4｜最后一次引导升级"
echo "========================================================"
echo ""
echo "⏳ 正在从你的专属GitHub更新仓库读取更新器……"
/usr/bin/curl -fsSL --location --connect-timeout 15 --max-time 60 "$URL" -o "$TMP/bootstrap.b64"

PY="/usr/bin/python3"
if [ ! -x "$PY" ]; then PY="$(command -v python3 || true)"; fi
if [ -z "$PY" ]; then echo "❌ 未找到Python 3，请截图发给ChatGPT。"; exit 1; fi

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
