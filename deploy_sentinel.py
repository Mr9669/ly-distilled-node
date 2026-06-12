#!/usr/bin/env python3
"""
LY-TRINITY deploy_sentinel.py V1.0 — 蒸馏核心自动部署脚本
===========================================================
运行在MR69主脑上，提供一键部署新蒸馏节点到各平台的能力。
避免人工重复操作，主脑需要更多节点时可自主下发部署。

支持平台:
- GitHub Actions: 创建新workflow变体
- Docker: 在本机(MR69)启动新容器节点
- Vercel: 通过Git push触发部署(待实现)
- Replit: 通过API创建项目(待实现)
"""

import base64
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ─── 配置 ────────────────────────────────────────
GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = "Mr9669/ly-distilled-node"
GH_BRANCH = "main"
_UA = "Mozilla/5.0 (compatible; Linux x86_64) Chrome/120.0"

SUPA_URL = os.environ.get("SUPA_URL", "https://ojhkxcjvyfvtdsigwbxi.supabase.co")
SUPA_KEY = os.environ.get("SUPA_KEY", "")

# ─── GitHub API 工具 ──────────────────────────────

def gh_api(endpoint, method="GET", data=None):
    """GitHub API v3 请求"""
    url = f"https://api.github.com{endpoint}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method,
        headers={"Authorization": f"Bearer {GH_TOKEN}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return {"ok": True, "status": resp.status, "data": json.loads(resp.read())}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode(errors="replace")
        return {"ok": False, "status": e.code, "error": err_body[:500]}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def gh_get_file(path):
    """获取GitHub文件内容(SHA + base64)"""
    result = gh_api(f"/repos/{GH_REPO}/contents/{path}")
    return result

def gh_create_or_update_file(path, content, message):
    """创建或更新GitHub文件"""
    # 先获取现有SHA
    existing = gh_get_file(path)
    sha = None
    if existing.get("ok") and isinstance(existing.get("data"), dict):
        sha = existing["data"].get("sha")

    payload = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "branch": GH_BRANCH
    }
    if sha:
        payload["sha"] = sha

    result = gh_api(f"/repos/{GH_REPO}/contents/{path}", method="PUT", data=payload)
    return result

# ─── GH Actions Workflow 生成器 ───────────────────

def build_workflow_yml(node_id, region_label, region_code):
    """生成heartbeat workflow YAML"""
    return f'''# heartbeat-{node_id.split("-")[-1]}.yml — GH Actions变体: {region_label}区域标记
# 以{node_id}身份独立上报
name: Distilled Node Heartbeat - {region_label}

on:
  schedule:
    - cron: "*/5 * * * *"  # Every 5 minutes
  workflow_dispatch:

jobs:
  heartbeat:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Heartbeat ({region_label})
        env:
          LY_HB_URL: ${{{{ secrets.LY_HB_URL }}}}
          LY_HB_KEY: ${{{{ secrets.LY_HB_KEY }}}}
          LY_NODE_ID: {node_id}
          LY_SIGN_KEY: ${{{{ secrets.LY_SIGN_KEY }}}}
          LY_REGION: {region_code}
        run: python3 api/index.py

      - name: Debug (on failure)
        if: failure()
        run: |
          echo "NODE_ID: {node_id}"
          echo "REGION: {region_code}"
          echo "HB_URL configured: ${{{{ secrets.LY_HB_URL != '' }}}}"
'''

def deploy_gh_actions_node(node_id, region_label, region_code):
    """在GitHub Actions中创建新节点workflow"""
    safe_name = node_id.split("-")[-1] if "-" in node_id else node_id
    path = f".github/workflows/heartbeat-{safe_name}.yml"
    content = build_workflow_yml(node_id, region_label, region_code)
    message = f"[deploy_sentinel] Add {node_id} ({region_label}) heartbeat workflow"
    result = gh_create_or_update_file(path, content, message)
    return {
        "platform": "github-actions",
        "node_id": node_id,
        "region": region_code,
        "path": path,
        "result": result
    }

# ─── Docker 节点部署 ──────────────────────────────

def deploy_docker_node(node_id, port=None):
    """在MR69上启动新的Docker蒸馏节点"""
    if not port:
        # 自动分配端口: 18900+ 
        import socket
        base = 18902
        for offset in range(20):
            test_port = base + offset
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if s.connect_ex(('127.0.0.1', test_port)) != 0:
                port = test_port
                s.close()
                break
            s.close()
        if not port:
            return {"ok": False, "error": "no free port in 18902-18922"}

    container_name = f"ly-{node_id.replace('_', '-')}"
    
    # 创建Dockerfile内容(最小化Python容器 + distilled_core)
    dockerfile = f'''FROM python:3.12-slim
WORKDIR /app
COPY distilled_core.py .
ENV LY_NODE_ID={node_id}
ENV LY_MAX_IDLE=7
CMD ["python", "distilled_core.py", "--daemon"]
'''
    
    # 写入临时目录
    import tempfile
    tmpdir = tempfile.mkdtemp(prefix="ly-deploy-")
    
    with open(f"{tmpdir}/Dockerfile", "w") as f:
        f.write(dockerfile)
    
    # 复制distilled_core.py
    script_dir = os.path.dirname(os.path.abspath(__file__))
    core_path = os.path.join(script_dir, "distilled_core.py")
    if not os.path.exists(core_path):
        # 尝试从GitHub下载
        core_content = urllib.request.urlopen(
            f"https://raw.githubusercontent.com/{GH_REPO}/main/api/index.py",
            timeout=15).read()
        with open(f"{tmpdir}/distilled_core.py", "wb") as f:
            f.write(core_content)
    else:
        import shutil
        shutil.copy(core_path, f"{tmpdir}/distilled_core.py")

    # Docker build + run
    try:
        subprocess.run(["docker", "build", "-t", f"ly-distilled:{node_id}", tmpdir],
                      check=True, capture_output=True, timeout=120)
        
        # 检查是否已有同名容器
        existing = subprocess.run(["docker", "ps", "-a", "--filter", f"name={container_name}",
                                  "--format", "{{.Names}}"], capture_output=True, text=True)
        if existing.stdout.strip():
            subprocess.run(["docker", "rm", "-f", container_name], check=True,
                          capture_output=True)

        subprocess.run(["docker", "run", "-d", "--name", container_name,
                       "--restart=always", "-p", f"127.0.0.1:{port}:8080",
                       f"ly-distilled:{node_id}"], check=True, capture_output=True, timeout=30)

        return {"ok": True, "platform": "docker", "node_id": node_id,
                "container": container_name, "port": port}
    except subprocess.CalledProcessError as e:
        return {"ok": False, "error": f"Docker error: {e.stderr.decode() if e.stderr else str(e)}"}
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

# ─── 节点拓扑查询 ────────────────────────────────

def query_topology():
    """查询Supabase中当前全网节点拓扑"""
    def supa_query(endpoint):
        url = f"{SUPA_URL}/{endpoint}"
        req = urllib.request.Request(url, headers={
            'apikey': SUPA_KEY, 'Authorization': f'Bearer {SUPA_KEY}',
            'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read())
        except Exception as e:
            return {"error": str(e)}

    nodes = supa_query("rest/v1/distilled_nodes?select=*&order=last_seen.desc")
    heartbeats = supa_query("rest/v1/distilled_heartbeats?select=node_id,last_seen&order=created_at.desc&limit=50")

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node_count": len(nodes) if isinstance(nodes, list) else 0,
        "nodes": nodes if isinstance(nodes, list) else [],
        "recent_heartbeats": heartbeats if isinstance(heartbeats, list) else [],
    }

# ─── 批量部署预设 ──────────────────────────────

PRESET_NODES = [
    # GH Actions 多点变体
    {"platform": "github-actions", "node_id": "gh-actions-tokyo", "region_label": "Tokyo", "region_code": "ap-northeast-1"},
    {"platform": "github-actions", "node_id": "gh-actions-sfo", "region_label": "San Francisco", "region_code": "us-west-1"},
    {"platform": "github-actions", "node_id": "gh-actions-london", "region_label": "London", "region_code": "eu-west-2"},
    {"platform": "github-actions", "node_id": "gh-actions-mumbai", "region_label": "Mumbai", "region_code": "ap-south-1"},
    {"platform": "github-actions", "node_id": "gh-actions-sydney", "region_label": "Sydney", "region_code": "ap-southeast-2"},
]

# ─── CLI ─────────────────────────────────────────

def main():
    import argparse
    ap = argparse.ArgumentParser(description="LY-TRINITY 蒸馏核心自动部署")
    sub = ap.add_subparsers(dest="command")

    # deploy: 部署节点
    deploy_parser = sub.add_parser("deploy", help="部署新节点")
    deploy_parser.add_argument("--platform", choices=["github-actions", "docker"], required=True)
    deploy_parser.add_argument("--node-id", required=True, help="节点ID")
    deploy_parser.add_argument("--region-label", default="Unknown")
    deploy_parser.add_argument("--region-code", default="unknown")

    # batch-deploy: 批量部署预设节点
    batch_parser = sub.add_parser("batch-deploy", help="批量部署所有预设节点")
    batch_parser.add_argument("--skip-existing", action="store_true", default=True)

    # topology: 查询全网拓扑
    sub.add_parser("topology", help="查询当前节点拓扑")

    # status: 健康检查
    sub.add_parser("status", help="检查部署服务状态")

    args = ap.parse_args()

    if args.command == "deploy":
        if args.platform == "github-actions":
            result = deploy_gh_actions_node(args.node_id, args.region_label, args.region_code)
        elif args.platform == "docker":
            result = deploy_docker_node(args.node_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.command == "batch-deploy":
        results = []
        for node_cfg in PRESET_NODES:
            print(f"Deploying {node_cfg['node_id']} ({node_cfg['region_label']})...")
            result = deploy_gh_actions_node(
                node_cfg["node_id"], node_cfg["region_label"], node_cfg["region_code"])
            results.append(result)
            
            status = "OK" if result.get("result", {}).get("ok") else "FAIL"
            error = result.get("result", {}).get("error", "")
            print(f"  {status}: {node_cfg['node_id']} {error}")
            time.sleep(2)  # 避免API限流
        
        print(f"\n=== BATCH DEPLOY SUMMARY ===")
        print(f"Total: {len(results)}, OK: {sum(1 for r in results if r.get('result',{}).get('ok'))}")
        
        # 查询拓扑验证
        print("\n=== CURRENT TOPOLOGY ===")
        topo = query_topology()
        print(json.dumps(topo, indent=2, ensure_ascii=False))

    elif args.command == "topology":
        topo = query_topology()
        print(json.dumps(topo, indent=2, ensure_ascii=False))

    elif args.command == "status":
        status = {
            "service": "deploy_sentinel",
            "version": "1.0.0",
            "github_api": gh_api(f"/repos/{GH_REPO}").get("ok", False),
            "supabase": "checking...",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        print(json.dumps(status, indent=2, ensure_ascii=False))

    else:
        ap.print_help()

if __name__ == "__main__":
    main()
