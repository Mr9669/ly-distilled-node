#!/usr/bin/env python3
"""
LY-TRINITY distilled_core.py — PythonAnywhere Always-On Task
=============================================================
PythonAnywhere免费账号支持一个always-on task。
此脚本每15分钟执行一次心跳（免费版限制）。
无需循环——由PA的always-on task调度。
"""
import json, os, sys, hashlib, random, platform
from urllib import request as ureq
from datetime import datetime, timezone

NODE_ID = os.environ.get("LY_NODE_ID", f"lys-pa-{random.randint(1000,9999)}")
HB_URL  = os.environ.get("LY_HB_URL", "")
HB_KEY  = os.environ.get("LY_HB_KEY", "")
SIGN_KEY = os.environ.get("LY_SIGN_KEY", "")
_UA = "Mozilla/5.0 (compatible; PythonAnywhere) Chrome/120.0"

def _now(): return datetime.now(timezone.utc).isoformat()
def _sig(s): return hashlib.sha256((s+SIGN_KEY).encode()).hexdigest()[:12] if SIGN_KEY else ""

if HB_URL:
    dt = _now()
    p = json.dumps({
        "node_id": NODE_ID, "signature": _sig(NODE_ID+dt),
        "status": "alive", "task_count": 0,
        "platform": f"PythonAnywhere / {platform.platform()[:80]}",
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
        print(f"[{_now()}] HB OK: {NODE_ID}")
    except Exception as e:
        print(f"[{_now()}] HB FAIL: {e}")
else:
    print(f"[{_now()}] NO HB_URL configured, node {NODE_ID} idle")
