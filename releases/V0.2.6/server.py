#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V0.2.6 extension: local image/screenshot OCR via Apple Vision.

Architecture:
- Reuses the already-validated V0.2.5 runtime for all招商/Feishu/DeepSeek/update logic.
- Adds local-only OCR endpoints and injects ocr.js/ocr.css into the existing Web UI.
- Original images are written only to a temporary local file and deleted immediately.
- OCR text is NOT sent to DeepSeek until the user explicitly clicks AI分析.
"""
from pathlib import Path
import base64
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import traceback
import uuid

APP_DIR = Path.home() / "Library" / "Application Support" / "GaoxinRadar"
V025_RUNTIME = APP_DIR / "server_v025_runtime.py"
ASSET_DIR = APP_DIR / "update_assets"
JXA_SCRIPT = ASSET_DIR / "ocr_vision.jxa"
SWIFT_SOURCE = ASSET_DIR / "ocr_vision.swift"
BIN_DIR = APP_DIR / "bin"
SWIFT_BIN = BIN_DIR / "ocr_vision"
TARGET_VERSION = "V0.2.6"
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_OCR_CHARS = 30000
ALLOWED_MIME = {"image/png": ".png", "image/jpeg": ".jpg"}


def _load_v025():
    if not V025_RUNTIME.exists():
        raise RuntimeError("缺少V0.2.5运行核心，更新助手将自动回滚。")
    spec = importlib.util.spec_from_file_location("bunan_radar_v025_runtime", str(V025_RUNTIME))
    if not spec or not spec.loader:
        raise RuntimeError("无法加载V0.2.5运行核心")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


v025 = _load_v025()
core = v025.core
core.APP_VERSION = TARGET_VERSION


def _json_bytes(obj):
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


def _send_html(handler, html):
    data = html.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _injected_index():
    index = core.STATIC_DIR / "index.html"
    html = index.read_text(encoding="utf-8")
    if "ocr.css?v=026" not in html:
        html = html.replace("</head>", '<link rel="stylesheet" href="/ocr.css?v=026" /></head>')
    if "ocr.js?v=026" not in html:
        html = html.replace("</body>", '<script src="/ocr.js?v=026"></script></body>')
    return html


def _find_xcrun_swiftc():
    try:
        p = subprocess.run(["/usr/bin/xcrun", "--find", "swiftc"], capture_output=True, text=True, timeout=10)
        path = (p.stdout or "").strip()
        if p.returncode == 0 and path and Path(path).exists():
            return path
    except Exception:
        pass
    for p in ("/usr/bin/swiftc", "/usr/local/bin/swiftc"):
        if Path(p).exists():
            return p
    return ""


def _ensure_swift_binary():
    if not SWIFT_SOURCE.exists():
        raise RuntimeError("Swift OCR资源缺失")
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    if SWIFT_BIN.exists() and SWIFT_BIN.stat().st_mtime >= SWIFT_SOURCE.stat().st_mtime:
        return SWIFT_BIN
    swiftc = _find_xcrun_swiftc()
    if not swiftc:
        raise RuntimeError("未找到Apple Swift编译器")
    tmp = SWIFT_BIN.with_name(SWIFT_BIN.name + ".new")
    p = subprocess.run([swiftc, str(SWIFT_SOURCE), "-o", str(tmp)], capture_output=True, text=True, timeout=90)
    if p.returncode != 0:
        raise RuntimeError("Swift OCR编译失败：" + ((p.stderr or p.stdout or "")[-1200:]))
    os.chmod(tmp, 0o755)
    tmp.replace(SWIFT_BIN)
    return SWIFT_BIN


def _parse_ocr_output(stdout, engine):
    raw = (stdout or "").strip()
    if not raw:
        raise RuntimeError(f"{engine}没有返回识别结果")
    candidates = [x.strip() for x in raw.splitlines() if x.strip()]
    obj = None
    for line in reversed(candidates):
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                obj = value
                break
        except Exception:
            continue
    if obj is None:
        try:
            obj = json.loads(raw)
        except Exception as e:
            raise RuntimeError(f"{engine}返回格式异常：{raw[-800:]}") from e
    if not obj.get("ok", True):
        raise RuntimeError(str(obj.get("error") or f"{engine}识别失败"))
    text = str(obj.get("text") or "").strip()
    if len(text) > MAX_OCR_CHARS:
        text = text[:MAX_OCR_CHARS] + "\n【OCR内容过长，已截断】"
    return {"text": text, "lines": int(obj.get("lines") or (len(text.splitlines()) if text else 0)), "engine": engine}


def _ocr_with_jxa(image_path):
    if not Path("/usr/bin/osascript").exists() or not JXA_SCRIPT.exists():
        raise RuntimeError("JXA OCR不可用")
    p = subprocess.run(["/usr/bin/osascript", "-l", "JavaScript", str(JXA_SCRIPT), str(image_path)], capture_output=True, text=True, timeout=55)
    if p.returncode != 0:
        raise RuntimeError("Apple Vision(JXA)失败：" + ((p.stderr or p.stdout or "")[-1000:]))
    return _parse_ocr_output(p.stdout, "Apple Vision · 本地")


def _ocr_with_swift(image_path):
    binary = _ensure_swift_binary()
    p = subprocess.run([str(binary), str(image_path)], capture_output=True, text=True, timeout=55)
    if p.returncode != 0:
        raise RuntimeError("Apple Vision(Swift)失败：" + ((p.stderr or p.stdout or "")[-1000:]))
    return _parse_ocr_output(p.stdout, "Apple Vision · 本地(Swift)")


def local_ocr(image_path):
    errors = []
    # Swift Vision is the most deterministic path when Apple developer tools exist; JXA is the zero-install fallback.
    for fn in (_ocr_with_swift, _ocr_with_jxa):
        try:
            result = fn(image_path)
            core.log(f"OCR OK via {result['engine']}; chars={len(result['text'])}")
            return result
        except Exception as e:
            errors.append(str(e))
            core.log("OCR engine failed: " + str(e))
    raise RuntimeError("本地OCR暂时不可用。" + " | ".join(errors))


def ocr_status():
    return {"ok": True, "platform": sys.platform, "local_only": True, "vision_jxa": Path("/usr/bin/osascript").exists() and JXA_SCRIPT.exists(), "vision_swift_fallback": bool(_find_xcrun_swiftc()) and SWIFT_SOURCE.exists(), "max_image_mb": MAX_IMAGE_BYTES // (1024 * 1024), "formats": ["PNG", "JPG", "JPEG"], "privacy": "原图仅在本机临时处理，OCR完成后立即删除；不会上传给DeepSeek。"}


def ocr_request(body):
    mime = str(body.get("mime") or "").lower().strip()
    name = str(body.get("name") or "截图").strip()[:200]
    encoded = str(body.get("image_b64") or "").strip()
    if mime not in ALLOWED_MIME:
        raise RuntimeError("V0.2.6目前只支持 PNG / JPG / JPEG 图片。")
    if not encoded:
        raise RuntimeError("没有收到图片内容。")
    if encoded.startswith("data:"):
        encoded = encoded.split(",", 1)[-1]
    try:
        data = base64.b64decode(encoded, validate=True)
    except Exception as e:
        raise RuntimeError("图片数据无法解析。") from e
    if not data:
        raise RuntimeError("图片为空。")
    if len(data) > MAX_IMAGE_BYTES:
        raise RuntimeError(f"单张图片不能超过 {MAX_IMAGE_BYTES // (1024*1024)}MB。")
    suffix = ALLOWED_MIME[mime]
    tmp_dir = APP_DIR / "tmp" / "ocr"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    path = tmp_dir / f"{uuid.uuid4().hex}{suffix}"
    try:
        path.write_bytes(data)
        result = local_ocr(path)
        result.update({"ok": True, "name": name, "chars": len(result["text"]), "local_only": True, "image_retained": False})
        return result
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


_old_progress = core.get_progress

def _progress_v026():
    d = _old_progress()
    items = d.get("items", [])
    if not any(x.get("name") == "V0.2.6 图片/截图投喂" for x in items):
        items.insert(3, {"name": "V0.2.6 图片/截图投喂", "status": "done", "detail": "PNG/JPG/JPEG · 拖拽 · ⌘V粘贴 · Apple Vision本地OCR · 图片+文字合并分析"})
    done = sum(1 for x in items if x.get("status") == "done")
    d["items"] = items
    d["percent"] = round(done / len(items) * 100) if items else 0
    return d

core.get_progress = _progress_v026

_old_get = core.Handler.do_GET

def _get_v026(self):
    p = core.urlparse(self.path).path
    if p in ("/", "/index.html"):
        try:
            return _send_html(self, _injected_index())
        except Exception:
            core.log("OCR UI injection failed: " + traceback.format_exc())
    if p == "/api/ocr/status":
        return self._json(ocr_status())
    return _old_get(self)

core.Handler.do_GET = _get_v026

_old_post = core.Handler.do_POST

def _post_v026(self):
    p = core.urlparse(self.path).path
    if p == "/api/ocr":
        try:
            body = self._body()
            return self._json(ocr_request(body))
        except Exception as e:
            core.log("ERROR V0.2.6 OCR: " + traceback.format_exc())
            return self._json({"ok": False, "error": str(e)}, 500)
    return _old_post(self)

core.Handler.do_POST = _post_v026

if __name__ == "__main__":
    core.main()
