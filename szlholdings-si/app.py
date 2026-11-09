#!/usr/bin/env python3
"""szlholdings.si — flagship back-end.

Fail-closed, receipts-first API. Reads only public HF data; never fabricates.
Endpoints:
  /            -> the flagship front page (index.html)
  /healthz     -> {"ok": true} only when the app is actually serving
  /api/honest  -> the always-receipts contract
  /api/census  -> live cross-lab abstain census (from the public receipts dataset)
  /api/receipts -> latest benchmark/energy receipts
"""
import json, os, urllib.request
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="szlholdings.si", version="1.0.0")
DS = "SZLHOLDINGS/frontier-54-runs"
HF = "https://huggingface.co"

def hf_json(path, timeout=20):
    req = urllib.request.Request(f"{HF}/api/datasets/{DS}/tree/main?recursive=true",
                                 headers={"User-Agent": "szlholdings.si/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def fetch_file(path, timeout=20):
    req = urllib.request.Request(f"{HF}/datasets/{DS}/resolve/main/{path}",
                                 headers={"User-Agent": "szlholdings.si/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def safe(fallback):
    """Fail closed: if the receipts source is unreachable, say so — never fake."""
    def wrap():
        try:
            return f()
        except Exception as e:
            raise HTTPException(status_code=503, detail={
                "error": "receipts_source_unavailable",
                "honest_note": "This endpoint serves receipts only. When the source is unreachable it fails closed rather than serving cached or fabricated data.",
                "cause": str(e)[:120]})
    return wrap

@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "szlholdings.si", "version": app.version}

@app.get("/api/honest")
def honest():
    return {
        "rule": "Every claim carries a source, exact revision, test result, limitation, or settlement receipt. If that receipt is missing, the status stays UNKNOWN, BLOCKED, or ROADMAP.",
        "canonical_source": "github.com/szl-holdings",
        "artifacts": "huggingface.co/SZLHOLDINGS",
        "receipts": f"huggingface.co/datasets/{DS}",
        "known_gaps": {
            "x402_settlement": "UNSETTLED_UNTIL_PROVEN",
            "energy_publish_loop": "PUBLISHER_SHIPPED_PENDING_MEASURED_ROWS",
            "qmc_full_vmc": "DEEPQMC_RUN_PENDING_ON_A6000_STACK",
        },
    }

@app.get("/api/census")
def census():
    @safe(None)
    def _():
        tree = hf_json(None)
        rows = []
        for f in tree:
            if f["path"].startswith("census/") and f["path"].endswith(".json"):
                rows.append(fetch_file(f["path"]))
        if not rows:
            raise HTTPException(503, "census receipts not yet published")
        return {"battery": "szl.cross-lab-confabulation/v1", "legs": rows}
    return _()

@app.get("/api/receipts")
def receipts():
    @safe(None)
    def _():
        tree = hf_json(None)
        rows = []
        for f in tree:
            if (f["path"].startswith(("benchmark/", "receipts/"))
                    and f["path"].endswith(".json")):
                try:
                    rows.append({"path": f["path"], "data": fetch_file(f["path"])})
                except Exception:
                    rows.append({"path": f["path"], "data": None, "status": "UNREADABLE"})
        if not rows:
            raise HTTPException(503, "no receipts published yet")
        return {"dataset": DS, "count": len(rows), "receipts": rows}
    return _()

app.mount("/", StaticFiles(directory="/app/static", html=True), name="static")
