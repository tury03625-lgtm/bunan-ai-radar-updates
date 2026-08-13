#!/bin/bash
set -euo pipefail
APP="$HOME/Library/Application Support/GaoxinRadar"
SERVER="$APP/server.py"
HELPER="$APP/update_helper.py"
LABEL="com.gaoxin.radar.v02"
PORT="$(cat "$APP/port.txt" 2>/dev/null || echo 18765)"
BACKUP="$APP/backups/V0.2.4_hotfix-$(date +%Y%m%d-%H%M%S)"
PY="/usr/bin/python3"; [ -x "$PY" ] || PY="$(command -v python3 || true)"
[ -n "$PY" ] || { echo '❌ 未找到Python3'; exit 1; }
[ -f "$SERVER" ] && [ -f "$HELPER" ] || { echo '❌ 未找到V0.2.4程序文件'; exit 1; }
mkdir -p "$BACKUP"; cp "$SERVER" "$BACKUP/server.py"; cp "$HELPER" "$BACKUP/update_helper.py"
echo '✅ 已备份V0.2.4，开始修复更新网络层……'
"$PY" - "$SERVER" "$HELPER" <<'PY'
from pathlib import Path
import sys,py_compile
sp,hp=map(Path,sys.argv[1:3])
s=sp.read_text(encoding='utf-8')
if 'APP_VERSION = "V0.2.4.1"' not in s:
    s=s.replace('V0.2.4 - Mac Local Web Console','V0.2.4.1 - Mac Local Web Console')
    s=s.replace('APP_VERSION = "V0.2.4"','APP_VERSION = "V0.2.4.1"')
old='UPDATE_RAW_BASE = "https://raw.githubusercontent.com/tury03625-lgtm/bunan-ai-radar-updates/main"\nUPDATE_MANIFEST_URL = UPDATE_RAW_BASE + "/manifest.json"'
new='''UPDATE_REPO = "tury03625-lgtm/bunan-ai-radar-updates"\nUPDATE_BRANCH = "main"\nUPDATE_RAW_BASE = f"https://raw.githubusercontent.com/{UPDATE_REPO}/{UPDATE_BRANCH}"\nUPDATE_API_BASE = f"https://api.github.com/repos/{UPDATE_REPO}/contents"\nUPDATE_CDN_BASE = f"https://cdn.jsdelivr.net/gh/{UPDATE_REPO}@{UPDATE_BRANCH}"\nUPDATE_MANIFEST_PATH = "manifest.json"\nUPDATE_MANIFEST_URL = UPDATE_RAW_BASE + "/" + UPDATE_MANIFEST_PATH'''
if old in s:s=s.replace(old,new)
oldfn='''def _curl_text(url, timeout=25):\n    args=[CURL,"-sS","--connect-timeout","10","--max-time",str(timeout)]\n    if USE_CA_NATIVE: args.append("--ca-native")\n    args.append(url)\n    p=subprocess.run(args,capture_output=True,timeout=timeout+5)\n    if p.returncode!=0:\n        raise RuntimeError((p.stderr or b"").decode("utf-8",errors="replace") or "更新源连接失败")\n    return p.stdout.decode("utf-8",errors="replace")\n'''
newfn='''def _curl_bytes(url, timeout=25, headers=None):\n    args=[CURL,"-sS","-L","--retry","2","--retry-delay","1","--connect-timeout","8","--max-time",str(timeout)]\n    if USE_CA_NATIVE: args.append("--ca-native")\n    for k,v in (headers or {}).items(): args.extend(["-H",f"{k}: {v}"])\n    args.append(url)\n    p=subprocess.run(args,capture_output=True,timeout=timeout+8)\n    if p.returncode!=0: raise RuntimeError((p.stderr or b"").decode("utf-8",errors="replace") or "更新源连接失败")\n    return p.stdout\n\ndef _fetch_repo_text(path, timeout=25):\n    path=str(path).lstrip("/"); errors=[]\n    channels=[("GitHub Raw",f"{UPDATE_RAW_BASE}/{path}","raw"),("GitHub API",f"{UPDATE_API_BASE}/{path}?ref={UPDATE_BRANCH}","api"),("jsDelivr CDN",f"{UPDATE_CDN_BASE}/{path}","raw")]\n    for name,url,kind in channels:\n        try:\n            data=_curl_bytes(url,timeout,{"Accept":"application/vnd.github+json"} if kind=="api" else None)\n            if kind=="api":\n                obj=json.loads(data.decode("utf-8",errors="replace")); import base64\n                data=base64.b64decode(obj.get("content") or "") if obj.get("encoding")=="base64" else str(obj.get("content") or "").encode("utf-8")\n            text=data.decode("utf-8",errors="replace")\n            if text.strip(): log(f"update fetch OK via {name}: {path}"); return text\n            raise RuntimeError("返回为空")\n        except Exception as e:\n            errors.append(f"{name}: {e}"); log(f"update fetch failed via {name}: {e}")\n    raise RuntimeError("三个更新通道均失败："+" | ".join(errors))\n'''
if oldfn in s:s=s.replace(oldfn,newfn)
s=s.replace('manifest=json.loads(_curl_text(UPDATE_MANIFEST_URL,25))','manifest=json.loads(_fetch_repo_text(UPDATE_MANIFEST_PATH,25))')
s=s.replace('[sys.executable,str(UPDATE_HELPER),UPDATE_MANIFEST_URL,str(PORT),APP_VERSION],','[sys.executable,str(UPDATE_HELPER),UPDATE_MANIFEST_PATH,str(PORT),APP_VERSION],')
if '_fetch_repo_text' not in s or 'APP_VERSION = "V0.2.4.1"' not in s: raise SystemExit('server.py补丁未完整应用')
sp.write_text(s,encoding='utf-8')

h=hp.read_text(encoding='utf-8')
h=h.replace('import sys, os, json, time, hashlib, subprocess, shutil, urllib.request, ssl','import sys, os, json, time, hashlib, subprocess, shutil, urllib.request, ssl, base64')
if 'UPDATE_REPO="tury03625-lgtm/bunan-ai-radar-updates"' not in h:
    h=h.replace('CURL="/usr/bin/curl"','''CURL="/usr/bin/curl"\nUPDATE_REPO="tury03625-lgtm/bunan-ai-radar-updates"\nUPDATE_BRANCH="main"\nRAW_BASE=f"https://raw.githubusercontent.com/{UPDATE_REPO}/{UPDATE_BRANCH}"\nAPI_BASE=f"https://api.github.com/repos/{UPDATE_REPO}/contents"\nCDN_BASE=f"https://cdn.jsdelivr.net/gh/{UPDATE_REPO}@{UPDATE_BRANCH}"''')
old='''def curl_bytes(url,timeout=60):\n    args=[CURL,"-sS","--location","--connect-timeout","15","--max-time",str(timeout),url]\n    p=subprocess.run(args,capture_output=True,timeout=timeout+10)\n    if p.returncode!=0:\n        raise RuntimeError((p.stderr or b"").decode("utf-8",errors="replace") or "下载失败")\n    return p.stdout\n'''
new='''def curl_bytes(url,timeout=60,headers=None):\n    args=[CURL,"-sS","-L","--retry","3","--retry-delay","1","--connect-timeout","8","--max-time",str(timeout)]\n    for k,v in (headers or {}).items(): args.extend(["-H",f"{k}: {v}"])\n    args.append(url); p=subprocess.run(args,capture_output=True,timeout=timeout+12)\n    if p.returncode!=0: raise RuntimeError((p.stderr or b"").decode("utf-8",errors="replace") or "下载失败")\n    return p.stdout\n\ndef repo_bytes(path,timeout=60):\n    path=str(path).lstrip("/"); errors=[]\n    channels=[("GitHub Raw",f"{RAW_BASE}/{path}","raw"),("GitHub API",f"{API_BASE}/{path}?ref={UPDATE_BRANCH}","api"),("jsDelivr CDN",f"{CDN_BASE}/{path}","raw")]\n    for name,url,kind in channels:\n        try:\n            data=curl_bytes(url,timeout,{"Accept":"application/vnd.github+json"} if kind=="api" else None)\n            if kind=="api":\n                obj=json.loads(data.decode("utf-8",errors="replace")); content=obj.get("content") or ""\n                data=base64.b64decode(content) if obj.get("encoding")=="base64" else str(content).encode("utf-8")\n            if data:return data\n            raise RuntimeError("返回为空")\n        except Exception as e:errors.append(f"{name}: {e}")\n    raise RuntimeError("三个下载通道均失败："+" | ".join(errors))\n'''
if old in h:h=h.replace(old,new)
h=h.replace('manifest_url,port,current=sys.argv[1],int(sys.argv[2]),sys.argv[3]','manifest_path,port,current=sys.argv[1],int(sys.argv[2]),sys.argv[3]')
h=h.replace('manifest=json.loads(curl_bytes(manifest_url,30).decode("utf-8"))','manifest=json.loads(repo_bytes(manifest_path,30).decode("utf-8"))')
h=h.replace('''            url=item.get("url")\n            expected=str(item.get("sha256","")).lower()\n            if not url or len(expected)!=64:raise RuntimeError(f"文件校验信息不完整：{rel}")\n            data=curl_bytes(url,60)\n''','''            repo_path=item.get("repo_path") or item.get("path")\n            url=item.get("url")\n            expected=str(item.get("sha256","")).lower()\n            if len(expected)!=64:raise RuntimeError(f"文件校验信息不完整：{rel}")\n            if repo_path: data=repo_bytes(repo_path,60)\n            elif url: data=curl_bytes(url,60)\n            else: raise RuntimeError(f"文件下载地址不完整：{rel}")\n''')
if 'repo_bytes' not in h: raise SystemExit('update_helper.py补丁未完整应用')
hp.write_text(h,encoding='utf-8')
py_compile.compile(str(sp),doraise=True); py_compile.compile(str(hp),doraise=True)
print('✅ Python语法检查通过')
PY
/bin/launchctl kickstart -k "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
sleep 3
OK=0
for i in $(seq 1 45); do
  R=$(/usr/bin/curl --noproxy '*' -sS --connect-timeout 1 --max-time 2 "http://127.0.0.1:$PORT/api/health" 2>/dev/null || true)
  if echo "$R" | grep -q '"version"[[:space:]]*:[[:space:]]*"V0.2.4.1"'; then OK=1; break; fi
  sleep 1
done
if [ "$OK" -ne 1 ]; then
  echo '⚠️ 健康检查失败，自动回滚V0.2.4……'; cp "$BACKUP/server.py" "$SERVER"; cp "$BACKUP/update_helper.py" "$HELPER"; /bin/launchctl kickstart -k "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true; exit 1
fi
echo '🎉 V0.2.4.1 热修复成功：Web更新已切换三通道网络层。'
/usr/bin/open "http://127.0.0.1:$PORT/"
