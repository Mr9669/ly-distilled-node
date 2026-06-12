#!/usr/bin/env python3
"""
LY-TRINITY distilled_core.py — Replit Daemon版
===============================================
为Replit免费环境优化的常驻版本。
使用while True + sleep替代cron，配合Replit keep_alive。
每5分钟发送一次心跳。
"""
import json, os, sys, time, hashlib, random, platform
from urllib import request as ureq
from datetime import datetime, timezone
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

NODE_ID = os.environ.get("LY_NODE_ID", f"lys-replit-{random.randint(1000,9999)}")
HB_URL  = os.environ.get("LY_HB_URL", "")
HB_KEY  = os.environ.get("LY_HB_KEY", "")
SIGN_KEY = os.environ.get("LY_SIGN_KEY", "")
_UA = "Mozilla/5.0 (compatible; Replit) Chrome/120.0"

def _now(): return datetime.now(timezone.utc).isoformat()
def _sig(s): return hashlib.sha256((s+SIGN_KEY).encode()).hexdigest()[:12] if SIGN_KEY else ""

def heartbeat(status="alive"):
    if not HB_URL: return False
    dt = _now()
    p = json.dumps({
        "node_id": NODE_ID, "signature": _sig(NODE_ID+dt),
        "status": status, "task_count": 0,
        "platform": f"Replit / {platform.platform()[:80]}",
        "python": sys.version[:40], "anomaly_flags": [],
        "last_seen": dt
    }).encode()
    try:
        r = ureq.Request(HB_URL, data=p, method="POST",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {HB_KEY}",
                     "apikey": HB_KEY,
                     "Prefer": "return=minimal",
                     "User-Agent": _UA})
        ureq.urlopen(r, timeout=15)
        return True
    except Exception as e:
        print(f"[{_now()}] HB FAIL: {e}", flush=True)
        return False

# Keep-alive web server (Replit需要HTTP端口保活)
class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "node_id": NODE_ID, "status": "alive",
            "timestamp": _now()
        }).encode())
    def log_message(self, *args): pass  # 静默日志

def run_keepalive_server():
    server = HTTPServer(("0.0.0.0", 8080), KeepAliveHandler)
    server.serve_forever()

if __name__ == "__main__":
    print(f"[{_now()}] NODE={NODE_ID} Replit daemon starting...", flush=True)
    
    # Start keep-alive HTTP server in background thread
    t = threading.Thread(target=run_keepalive_server, daemon=True)
    t.start()
    print(f"[{_now()}] Keep-alive server on :8080", flush=True)
    
    # Initial heartbeat
    heartbeat("alive")
    
    # Main loop: heartbeat every 5 minutes
    while True:
        time.sleep(300 + random.randint(0, 30))  # 5min + jitter
        heartbeat("alive")
        print(f"[{_now()}] Heartbeat sent", flush=True)
