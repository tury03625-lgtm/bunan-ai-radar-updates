#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V0.2.5 launcher/extension for 不楠先生 AI招商雷达.

V0.2.5 deliberately turns the former monolithic server into a small extension layer.
On the first V0.2.5 start, the updater's verified V0.2.4.1 backup is promoted to
server_core_v0241.py. This file then adds the Today Workbench APIs and starts the
existing, already-validated core. User config and Feishu data are untouched.
"""
from pathlib import Path
import importlib.util, shutil, sys, urllib.parse
from datetime import datetime

APP_DIR=Path.home()/"Library"/"Application Support"/"GaoxinRadar"
CORE=APP_DIR/"server_core_v0241.py"
TARGET_VERSION="V0.2.5"


def _find_core_source():
    # update_helper always backs up the currently running server before replacement.
    candidates=[]
    backups=APP_DIR/"backups"
    if backups.exists():
        candidates=sorted(backups.glob("*/server.py"), key=lambda p:p.stat().st_mtime, reverse=True)
    for p in candidates:
        try:
            text=p.read_text(encoding="utf-8",errors="replace")
            if 'product":"bunan-ai-radar' in text.replace(" ","") or 'APP_VERSION = "V0.2.4.1"' in text:
                return p
        except Exception:
            pass
    return candidates[0] if candidates else None


def _ensure_core():
    if CORE.exists():
        return
    src=_find_core_source()
    if not src:
        raise RuntimeError("V0.2.5无法找到V0.2.4.1核心备份，更新助手将自动回滚。")
    shutil.copy2(src,CORE)


def _load_core():
    _ensure_core()
    spec=importlib.util.spec_from_file_location("bunan_radar_core_v0241",str(CORE))
    if not spec or not spec.loader:
        raise RuntimeError("无法加载招商雷达核心模块")
    mod=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=mod
    spec.loader.exec_module(mod)
    return mod


def _prepare_v025_static():
    """Decode all updater-verified UI assets without touching the live UI."""
    import base64,zlib
    asset_dir=APP_DIR/"update_assets"
    mapping={
        "v025_index.b64":"index.html",
        "v025_app.b64":"app.js",
        "v025_styles.b64":"styles.css",
    }
    prepared={}
    for asset,name in mapping.items():
        src=asset_dir/asset
        if not src.exists():
            raise RuntimeError(f"V0.2.5界面资源缺失：{asset}")
        prepared[name]=zlib.decompress(base64.b64decode(src.read_text(encoding="ascii").strip()))
    return prepared


def _install_prepared_static(prepared):
    """Atomically install UI files; restore the old UI if any write fails."""
    static=APP_DIR/"static"
    static.mkdir(parents=True,exist_ok=True)
    backups={}
    temps=[]
    try:
        # Write every new file first. Nothing live changes until all writes succeed.
        for name,data in prepared.items():
            dst=static/name
            tmp=dst.with_name(dst.name+".v025-new")
            tmp.write_bytes(data)
            temps.append(tmp)
            backups[name]=dst.read_bytes() if dst.exists() else None
        # Atomic rename on the same filesystem.
        for name in prepared:
            dst=static/name
            dst.with_name(dst.name+".v025-new").replace(dst)
    except Exception:
        for tmp in temps:
            try: tmp.unlink(missing_ok=True)
            except Exception: pass
        for name,old in backups.items():
            dst=static/name
            try:
                if old is None: dst.unlink(missing_ok=True)
                else: dst.write_bytes(old)
            except Exception: pass
        raise

core=_load_core()
core.APP_VERSION=TARGET_VERSION


def safe_records_with_ids(table_name, limit=20):
    cfg=core.load_config()
    if not cfg.get("table_ids",{}).get(table_name):
        return []
    token=core.tenant_token(cfg)
    rows=core.list_records(token,cfg["app_token"],cfg["table_ids"][table_name],500)
    rows=rows[-limit:]
    out=[]
    for r in reversed(rows):
        item=dict(r.get("fields",{}) or {})
        item["_record_id"]=r.get("record_id") or r.get("id") or ""
        out.append(item)
    return out


def _parse_dt(value):
    v=str(value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S","%Y-%m-%d %H:%M","%Y-%m-%d"):
        try:return datetime.strptime(v,fmt)
        except Exception:pass
    return None


def _score(row):
    level=str(row.get("级别","")).upper()
    status=str(row.get("状态","") or "待跟进").strip()
    if status in ("已转化","无效","已关闭","放弃"):
        return -10000
    score={"L5":100,"L4":70}.get(level,0)
    score += {"待跟进":18,"跟进中":12,"已联系":6}.get(status,8)
    dt=_parse_dt(row.get("预警时间"))
    if dt:
        age=(datetime.now()-dt).total_seconds()/86400
        if age<=1:score+=12
        elif age<=3:score+=7
        elif age<=7:score+=3
    area=str(row.get("预计面积","") or "")
    if area and area not in ("未知","未获取"):score+=2
    return score


def get_workbench():
    """Daily workbench. Feishu + deterministic rules only; zero DeepSeek token cost."""
    try:
        alerts=safe_records_with_ids("预警中心",200)
        signals=safe_records_with_ids("Signal_Inbox",200)
        feedbacks=safe_records_with_ids("AI反馈日志",200)
        today=datetime.now().strftime("%Y-%m-%d")
        active=[]
        for r in alerts:
            rr=dict(r)
            rr["状态"]=str(rr.get("状态","") or "待跟进")
            rr["_score"]=_score(rr)
            if rr["_score"]>-1000:active.append(rr)
        active.sort(key=lambda x:x.get("_score",0),reverse=True)
        l5=sum(1 for r in active if str(r.get("级别","")).upper()=="L5")
        pending=sum(1 for r in active if str(r.get("状态","") or "待跟进") in ("待跟进","跟进中"))
        today_new=sum(1 for r in signals if str(r.get("接收时间","")).startswith(today))
        fbs=[str(r.get("用户反馈","") or "") for r in feedbacks]
        fb_total=sum(1 for x in fbs if x in ("判断正确","判断偏高","判断偏低","无实际需求"))
        fb_correct=sum(1 for x in fbs if x=="判断正确")
        accuracy=round(fb_correct/fb_total*100) if fb_total else None
        priority=active[:8]
        if l5:summary=f"今天优先处理 {l5} 家 L5 企业，先联系明确找场地或空间矛盾最强的机会。"
        elif pending:summary=f"当前有 {pending} 家待跟进机会，先完成已有线索的首轮触达，再补充新情报。"
        elif today_new:summary=f"今天已新增 {today_new} 条情报，但尚无L4/L5，建议继续补充私域弱信号并等待关联。"
        else:summary="当前没有高优机会。今天优先补充3—5条同行、设备商、电话或微信原始情报。"
        actions=[]
        for i,r in enumerate(priority[:3],1):
            actions.append({"rank":i,"company":r.get("企业") or "未识别企业","level":r.get("级别") or "","action":r.get("推荐动作") or "尽快完成首轮联系"})
        if not actions:
            actions=[
                {"rank":1,"company":"补充私域信号","level":"","action":"整理今天来自同行、设备商、同事或客户的零散信息。"},
                {"rank":2,"company":"投喂原始情报","level":"","action":"无需整理措辞，直接粘贴给雷达做结构化判断。"},
                {"rank":3,"company":"检查近期企业变化","level":"","action":"优先关注扩产、设备、生产招聘、租约和场地承载信号。"},
            ]
        return {"ok":True,"date":today,"summary":summary,"stats":{"l5":l5,"pending":pending,"today_new":today_new,"feedback_accuracy":accuracy,"feedback_total":fb_total},"priority":priority,"top_focus":priority[0] if priority else None,"actions":actions,"recent_signals":signals[:8]}
    except Exception as e:
        return {"ok":True,"date":datetime.now().strftime("%Y-%m-%d"),"summary":"工作台暂时无法读取飞书数据，请到系统状态检查连接。","stats":{"l5":0,"pending":0,"today_new":0,"feedback_accuracy":None,"feedback_total":0},"priority":[],"top_focus":None,"actions":[],"recent_signals":[],"warning":str(e)}


def search_enterprises(query):
    q=str(query or "").strip().lower()
    if not q:return {"ok":True,"query":"","items":[]}
    sources=[("预警中心",safe_records_with_ids("预警中心",500)),("企业观察池",safe_records_with_ids("企业观察池",500)),("情报库",safe_records_with_ids("Signal_Inbox",500))]
    items=[];seen=set()
    for source,rows in sources:
        for r in rows:
            hay=" ".join(str(v) for k,v in r.items() if k!="_record_id").lower()
            if q not in hay:continue
            name=r.get("企业") or r.get("企业名称") or r.get("标准企业名") or r.get("原始企业名") or "未识别企业"
            key=(source,str(name),str(r.get("_record_id","")))
            if key in seen:continue
            seen.add(key)
            items.append({"source":source,"company":name,"level":r.get("级别") or r.get("机会级别") or "","status":r.get("状态") or r.get("处理状态") or "","time":r.get("预警时间") or r.get("最近更新时间") or r.get("接收时间") or "","summary":r.get("为什么值得联系") or r.get("AI摘要") or r.get("AI判断") or r.get("最近信号") or "","record_id":r.get("_record_id","")})
            if len(items)>=30:return {"ok":True,"query":query,"items":items}
    return {"ok":True,"query":query,"items":items}


def set_opportunity_status(payload):
    allowed={"待跟进","已联系","跟进中","已转化","无效"}
    rid=str(payload.get("record_id","") or "").strip()
    status=str(payload.get("status","") or "").strip()
    if not rid:raise RuntimeError("缺少机会记录ID")
    if status not in allowed:raise RuntimeError("不支持的跟进状态")
    cfg=core.load_config();tid=cfg.get("table_ids",{}).get("预警中心")
    if not tid:raise RuntimeError("未找到飞书预警中心")
    token=core.tenant_token(cfg)
    r=core.curl_request("PUT",f"{core.FEISHU_BASE}/bitable/v1/apps/{cfg['app_token']}/tables/{tid}/records/{rid}",{"fields":{"状态":status}},core.auth_headers(token))
    if r.get("code")!=0:raise RuntimeError(str(r))
    return {"ok":True,"record_id":rid,"status":status}


# Add V0.2.5 to the existing project progress without changing the validated core.
_old_progress=core.get_progress
def _progress_v025():
    d=_old_progress()
    items=d.get("items",[])
    if not any(x.get("name")=="V0.2.5 今日招商工作台" for x in items):
        items.insert(2,{"name":"V0.2.5 今日招商工作台","status":"done","detail":"优先联系 / 待跟进 / 企业搜索 / 快速投喂 / 反馈命中率"})
    done=sum(1 for x in items if x.get("status")=="done")
    d["items"]=items;d["percent"]=round(done/len(items)*100) if items else 0
    return d
core.get_progress=_progress_v025


_old_get=core.Handler.do_GET
def _get_v025(self):
    parsed=core.urlparse(self.path);p=parsed.path
    if p=="/api/workbench":return self._json(get_workbench())
    if p=="/api/search":
        q=urllib.parse.parse_qs(parsed.query).get("q",[""])[0]
        return self._json(search_enterprises(q))
    return _old_get(self)
core.Handler.do_GET=_get_v025

_old_post=core.Handler.do_POST
def _post_v025(self):
    p=core.urlparse(self.path).path
    if p=="/api/opportunity/status":
        try:return self._json(set_opportunity_status(self._body()))
        except Exception as e:
            core.log("ERROR V0.2.5 status update: "+str(e))
            return self._json({"ok":False,"error":str(e)},500)
    return _old_post(self)
core.Handler.do_POST=_post_v025


def main_v025():
    """Bind first, then install UI, then serve. A bind failure leaves the old UI untouched."""
    core.APP_DIR.mkdir(parents=True,exist_ok=True)
    prepared=_prepare_v025_static()
    server=core.RadarHTTPServer((core.HOST,core.PORT),core.Handler)
    try:
        _install_prepared_static(prepared)
        core.log(f"{TARGET_VERSION} web server ONLINE at http://{core.HOST}:{core.PORT}")
        core.threading.Thread(target=core.background_schema_check,daemon=True,name="schema-check").start()
        core.threading.Thread(target=core.background_update_loop,daemon=True,name="update-check").start()
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__=="__main__":
    main_v025()
