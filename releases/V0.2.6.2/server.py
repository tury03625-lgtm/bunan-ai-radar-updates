#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V0.2.6.2: image/screenshot feed with Mac-local Apple Vision OCR + UI interaction hotfix."""
from pathlib import Path
import base64
import importlib.util
import json
import subprocess
import sys
import traceback
import urllib.parse
import uuid

APP_DIR = Path.home() / "Library" / "Application Support" / "GaoxinRadar"
V025_RUNTIME = APP_DIR / "server_v025_runtime.py"
JXA_SCRIPT = APP_DIR / "update_assets" / "ocr_vision.jxa"
TARGET_VERSION = "V0.2.6.2"
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_OCR_CHARS = 30000
ALLOWED_MIME = {"image/png": ".png", "image/jpeg": ".jpg"}


def load_v025():
    if not V025_RUNTIME.exists():
        raise RuntimeError("缺少V0.2.5运行核心，更新助手将自动回滚。")
    spec = importlib.util.spec_from_file_location("bunan_radar_v025_runtime", str(V025_RUNTIME))
    if not spec or not spec.loader:
        raise RuntimeError("无法加载V0.2.5运行核心。")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


v025 = load_v025()
core = v025.core
core.APP_VERSION = TARGET_VERSION


def send_html(handler, html):
    data = html.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def injected_index():
    html = (core.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    if "ocr.css?v=0262" not in html:
        html = html.replace("</head>", '<link rel="stylesheet" href="/ocr.css?v=0262" /></head>')
    if "ocr.js?v=0262" not in html:
        html = html.replace("</body>", '<script src="/ocr.js?v=0262"></script></body>')
    return html


def parse_vision_output(stdout):
    raw = (stdout or "").strip()
    if not raw:
        raise RuntimeError("Apple Vision没有返回识别结果。")
    obj = None
    for line in reversed([x.strip() for x in raw.splitlines() if x.strip()]):
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                obj = value
                break
        except Exception:
            pass
    if obj is None:
        raise RuntimeError("Apple Vision返回格式异常。")
    if not obj.get("ok", False):
        raise RuntimeError(str(obj.get("error") or "Apple Vision识别失败。"))
    text = str(obj.get("text") or "").strip()
    if len(text) > MAX_OCR_CHARS:
        text = text[:MAX_OCR_CHARS] + "\n【OCR内容过长，已截断】"
    return text, int(obj.get("lines") or (len(text.splitlines()) if text else 0))


def local_ocr(image_path):
    if not Path("/usr/bin/osascript").exists() or not JXA_SCRIPT.exists():
        raise RuntimeError("Mac本地Apple Vision OCR资源不可用。")
    p = subprocess.run(
        ["/usr/bin/osascript", "-l", "JavaScript", str(JXA_SCRIPT), str(image_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if p.returncode != 0:
        raise RuntimeError("Apple Vision OCR失败：" + ((p.stderr or p.stdout or "")[-900:]))
    text, lines = parse_vision_output(p.stdout)
    core.log(f"OCR OK via Apple Vision local; chars={len(text)}")
    return {"text": text, "lines": lines, "engine": "Apple Vision · Mac本地"}


def ocr_request(body):
    mime = str(body.get("mime") or "").lower().strip()
    name = str(body.get("name") or "截图").strip()[:200]
    encoded = str(body.get("image_b64") or "").strip()
    if mime not in ALLOWED_MIME:
        raise RuntimeError("目前只支持 PNG / JPG / JPEG 图片。")
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
        raise RuntimeError("单张图片不能超过10MB。")

    tmp_dir = APP_DIR / "tmp" / "ocr"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    path = tmp_dir / f"{uuid.uuid4().hex}{ALLOWED_MIME[mime]}"
    try:
        path.write_bytes(data)
        result = local_ocr(path)
        result.update({
            "ok": True,
            "name": name,
            "chars": len(result["text"]),
            "local_only": True,
            "image_retained": False,
        })
        return result
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


old_progress = getattr(core, "get_progress", None)
if callable(old_progress):
    def progress_v0262():
        d = old_progress()
        items = d.get("items", [])
        if not any(x.get("name") == "V0.2.6 图片/截图投喂" for x in items):
            items.insert(3, {
                "name": "V0.2.6 图片/截图投喂",
                "status": "done",
                "detail": "PNG/JPG/JPEG · 拖拽 · ⌘V粘贴 · Apple Vision本地OCR · 图片+文字合并分析",
            })
        done = sum(1 for x in items if x.get("status") == "done")
        d["items"] = items
        d["percent"] = round(done / len(items) * 100) if items else 0
        return d
    core.get_progress = progress_v0262


old_get = core.Handler.do_GET
def get_v0262(self):
    path = urllib.parse.urlparse(self.path).path
    if path == "/api/health":
        return self._json({
            "ok": True,
            "product": "bunan-ai-radar",
            "name": "不楠先生AI招商雷达预警评估体系系统",
            "version": TARGET_VERSION,
            "ui_contract": "interactive-v1",
        })
    if path in ("/", "/index.html"):
        try:
            return send_html(self, injected_index())
        except Exception:
            core.log("OCR UI injection failed: " + traceback.format_exc())
    if path == "/api/ocr/status":
        available = Path("/usr/bin/osascript").exists() and JXA_SCRIPT.exists()
        return self._json({
            "ok": True,
            "local_only": True,
            "vision_jxa": available,
            "vision_swift_fallback": False,
            "max_image_mb": 10,
            "formats": ["PNG", "JPG", "JPEG"],
            "privacy": "原图只在Mac本地临时处理，OCR完成后立即删除；不会上传给DeepSeek。",
        })
    return old_get(self)

core.Handler.do_GET = get_v0262


old_post = core.Handler.do_POST
def post_v0262(self):
    path = urllib.parse.urlparse(self.path).path
    if path == "/api/ocr":
        try:
            return self._json(ocr_request(self._body()))
        except Exception as e:
            core.log("ERROR V0.2.6.2 OCR: " + traceback.format_exc())
            return self._json({"ok": False, "error": str(e)}, 500)
    return old_post(self)

core.Handler.do_POST = post_v0262


if __name__ == "__main__":
    core.main()
