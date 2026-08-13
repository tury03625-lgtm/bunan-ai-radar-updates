#!/usr/bin/env python3
from pathlib import Path
import base64,zlib,json,hashlib,runpy
APP=Path.home()/"Library"/"Application Support"/"GaoxinRadar"
BUNDLE=APP/"update_assets"/"v026_bundle.b64"
EXPECTED_RAW="5f08fdd467082b4a456c8ef4354487a89d8b7089e8f28f96cba9bfecc12473b3"
def install_runtime():
    if not BUNDLE.exists(): raise RuntimeError("V0.2.6资源包缺失，更新助手将自动回滚。")
    raw=zlib.decompress(base64.b64decode(BUNDLE.read_text(encoding="ascii").strip()))
    if hashlib.sha256(raw).hexdigest()!=EXPECTED_RAW: raise RuntimeError("V0.2.6资源包内部校验失败，更新助手将自动回滚。")
    obj=json.loads(raw.decode("utf-8"))
    if obj.get("version")!="V0.2.6": raise RuntimeError("V0.2.6资源包版本不匹配。")
    for rel,b64 in obj.get("files",{}).items():
        target=APP/rel; target.parent.mkdir(parents=True,exist_ok=True)
        data=base64.b64decode(b64); tmp=target.with_name(target.name+".new")
        tmp.write_bytes(data); tmp.replace(target)
    return APP/"server_v026_runtime.py"
if __name__=="__main__": runpy.run_path(str(install_runtime()),run_name="__main__")