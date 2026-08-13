#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Small verified loader for V0.2.5.
The self-updater verifies this loader and every runtime chunk independently.
"""
from pathlib import Path
import base64, zlib, hashlib, runpy

APP_DIR=Path.home()/"Library"/"Application Support"/"GaoxinRadar"
ASSET_DIR=APP_DIR/"update_assets"
RUNTIME=APP_DIR/"server_v025_runtime.py"
EXPECTED_RUNTIME_SHA256="2c021835d88638b048818987febe2ae26069b73973eebf6c11323f9318fc9fc3"
PARTS=[f"v025_runtime.part{i}.txt" for i in range(1,6)]

def ensure_runtime():
    chunks=[]
    for name in PARTS:
        p=ASSET_DIR/name
        if not p.exists():
            raise RuntimeError(f"V0.2.5运行资源缺失：{name}，更新助手将自动回滚。")
        chunks.append(p.read_text(encoding="ascii").strip())
    raw=zlib.decompress(base64.b64decode("".join(chunks)))
    if hashlib.sha256(raw).hexdigest()!=EXPECTED_RUNTIME_SHA256:
        raise RuntimeError("V0.2.5运行资源内部校验失败，更新助手将自动回滚。")
    tmp=RUNTIME.with_name(RUNTIME.name+".new")
    tmp.write_bytes(raw);tmp.replace(RUNTIME)

if __name__=="__main__":
    ensure_runtime()
    runpy.run_path(str(RUNTIME),run_name="__main__")
