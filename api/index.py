# LY-TRINITY distilled_core.py V3.0 — 报身0.2微节点 Vercel Handler
# For Vercel serverless (@vercel/python runtime)
import json, os, sys, hashlib, random, platform
from http.server import BaseHTTPRequestHandler
from urllib import request as ureq
from datetime import datetime, timezone

NODE_ID = os.environ.get("LY_NODE_ID", f"lys-{random.randint(1000,9999)}")
HB_URL  = os.environ.get("LY_HB_URL", "")
HB_KEY  = os.environ.get("LY_HB_KEY", "")
SIGN_KEY = os.environ.get("LY_SIGN_KEY", "")
_UA = "Mozilla/5.0 (compatible; Linux x86_64) Chrome/120.0"

def _now():
    return datetime.now(timezone.utc).isoformat()

def _sig(s):
    return hashlib.sha256((s + SIGN_KEY).encode()).hexdigest()[:12] if SIGN_KEY else ""

def env_anomaly():
    f = []
    if any(k in os.environ for k in ("CI", "GITHUB_ACTIONS", "JENKINS_HOME")):
        f.append("ci")
    if sys.gettrace():
        f.append("debugger")
    return f

def do_heartbeat():
    if not HB_URL:
        return {"ok": False, "error": "HB_URL not configured", "node_id": NODE_ID}
    dt = _now()
    p = json.dumps({
        "node_id": NODE_ID,
        "signature": _sig(NODE_ID + dt),
        "status": "alive",
        "task_count": 0,
        "platform": platform.platform()[:80],
        "python": sys.version[:40],
        "anomaly_flags": env_anomaly(),
        "last_seen": dt
    }).encode()
    try:
        r = ureq.Request(HB_URL, data=p, method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {HB_KEY}",
                "apikey": HB_KEY,
                "Prefer": "return=minimal",
                "User-Agent": _UA
            })
        resp = ureq.urlopen(r, timeout=15)
        return {"ok": True, "node_id": NODE_ID, "timestamp": dt, "http_status": resp.status}
    except Exception as e:
        return {"ok": False, "error": str(e), "node_id": NODE_ID}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        result = do_heartbeat()
        body = json.dumps(result, ensure_ascii=False).encode('utf-8')
        status = 200 if result.get("ok") else 500
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    
    def do_POST(self):
        self.do_GET()
    
    def log_message(self, format, *args):
        pass
