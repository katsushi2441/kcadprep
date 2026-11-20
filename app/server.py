"""Kurage 設計下書き（kcadprep）— 0.3 で動く API。公開ページ（proto.exbridge.jp/kcadprep/）の PHP から呼ぶ。

POST /api/jobs            {request, engine: gemma|codex, material, passcode?}  → {id}
GET  /api/jobs/{id}       進み具合と結果
GET  /api/jobs/{id}/{name} part.stl / cavity.step など
GET  /api/health

外から直接は呼ばせない（PHP が X-KCADPREP-TOKEN を付ける）。1本ずつ順番に処理する。
"""
import hmac
import json
import os
import queue
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

import pipeline

ROOT = Path(__file__).resolve().parent.parent
JOBS = ROOT / "outputs" / "jobs"
JOBS.mkdir(parents=True, exist_ok=True)


def load_env():
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


load_env()
API_TOKEN = os.environ.get("KCADPREP_API_TOKEN", "")
CODEX_PASS = os.environ.get("KCADPREP_CODEX_PASSCODE", "")
CODEX_DAILY = int(os.environ.get("KCADPREP_CODEX_DAILY", "20"))
GEMMA_HOURLY_PER_IP = int(os.environ.get("KCADPREP_GEMMA_HOURLY", "12"))
MAX_QUEUE = 6

app = FastAPI(title="kcadprep")
q: "queue.Queue[str]" = queue.Queue()
lock = threading.Lock()
recent_ip = defaultdict(deque)
FILES = {"part.stl", "part.step", "cavity.stl", "cavity.step", "core.stl", "core.step", "part_code.py"}
ENGINES = {"gemma", "codex"}
MATERIALS = {"PP", "ABS", "PC", "PA66", "POM"}


def jpath(jid: str) -> Path:
    if not re.fullmatch(r"[0-9]{8}-[0-9]{6}-[a-f0-9]{6}", jid):
        raise HTTPException(404, "not found")
    p = JOBS / jid
    if not (p / "job.json").exists():
        raise HTTPException(404, "not found")
    return p


def read(p: Path) -> dict:
    return json.loads((p / "job.json").read_text(encoding="utf-8"))


def write(p: Path, d: dict):
    t = p / "job.json.tmp"
    t.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    t.replace(p / "job.json")


def auth(tok: str):
    if not API_TOKEN or not hmac.compare_digest(tok or "", API_TOKEN):
        raise HTTPException(403, "forbidden")


def codex_used_today() -> int:
    day = time.strftime("%Y%m%d")
    n = 0
    for d in JOBS.glob(day + "-*"):
        try:
            if read(d).get("engine") == "codex":
                n += 1
        except Exception:
            pass
    return n


def worker():
    while True:
        jid = q.get()
        p = JOBS / jid
        d = read(p)
        d.update(status="running", started=time.time())
        write(p, d)

        def log(msg):
            with lock:
                x = read(p)
                x.setdefault("log", []).append([round(time.time() - x["started"], 1), msg])
                write(p, x)
        try:
            res = pipeline.run_job(p, d["request"], d["engine"], {"material": d["material"]}, log)
        except Exception as e:   # 想定外の失敗も、画面に出せる形で残す
            res = {"ok": False, "error": f"処理が止まりました: {e}"[-600:], "tries": []}
        with lock:
            x = read(p)
            x.update(status="done" if res.get("ok") else "failed", finished=time.time(), result=res)
            write(p, x)
        q.task_done()


threading.Thread(target=worker, daemon=True).start()
# 再起動で途中のまま残った回は失敗にしておく（画面が待ち続けないように）
for d in JOBS.glob("*/job.json"):
    try:
        x = json.loads(d.read_text(encoding="utf-8"))
        if x.get("status") in ("queued", "running"):
            x.update(status="failed", result={"ok": False, "error": "サーバーの再起動で中断しました。もう一度お試しください。", "tries": []})
            write(d.parent, x)
    except Exception:
        pass


@app.get("/api/health")
def health():
    return {"ok": True, "queue": q.qsize(), "codex_left": max(0, CODEX_DAILY - codex_used_today())}


@app.post("/api/jobs")
async def create(req: Request, x_kcadprep_token: str = Header(""), x_client_ip: str = Header("")):
    auth(x_kcadprep_token)
    b = await req.json()
    text = str(b.get("request", "")).strip()
    engine = str(b.get("engine", "gemma"))
    material = str(b.get("material", "ABS"))
    if not (5 <= len(text) <= 600):
        raise HTTPException(400, "説明は5〜600字で書いてください")
    if engine not in ENGINES or material not in MATERIALS:
        raise HTTPException(400, "選択肢が正しくありません")
    if q.qsize() >= MAX_QUEUE:
        raise HTTPException(429, "ただいま混み合っています。少し待ってからお試しください")
    ip = x_client_ip or (req.client.host if req.client else "")
    if engine == "codex":
        if not CODEX_PASS or not hmac.compare_digest(str(b.get("passcode", "")), CODEX_PASS):
            raise HTTPException(403, "Codex を使うには合言葉が必要です（商談の場でお伝えしています）")
        if codex_used_today() >= CODEX_DAILY:
            raise HTTPException(429, "本日の Codex の回数を使い切りました。gemma4 でお試しください")
    else:
        dq = recent_ip[ip]
        now = time.time()
        while dq and now - dq[0] > 3600:
            dq.popleft()
        if len(dq) >= GEMMA_HOURLY_PER_IP:
            raise HTTPException(429, "1時間に使える回数を超えました。少し時間をおいてお試しください")
        dq.append(now)
    jid = time.strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3)
    p = JOBS / jid
    p.mkdir()
    write(p, {"id": jid, "status": "queued", "created": time.time(), "request": text, "engine": engine,
              "material": material, "log": []})
    q.put(jid)
    return {"id": jid, "position": q.qsize()}


@app.get("/api/jobs/{jid}")
def get(jid: str, x_kcadprep_token: str = Header("")):
    auth(x_kcadprep_token)
    d = read(jpath(jid))
    d.pop("started", None)
    return JSONResponse(d)


@app.get("/api/jobs/{jid}/{name}")
def file(jid: str, name: str, x_kcadprep_token: str = Header("")):
    auth(x_kcadprep_token)
    if name not in FILES:
        raise HTTPException(404, "not found")
    f = jpath(jid) / name
    if not f.exists():
        raise HTTPException(404, "not found")
    mt = {"stl": "model/stl", "step": "application/step", "py": "text/plain; charset=utf-8"}[name.rsplit(".", 1)[1]]
    return FileResponse(f, media_type=mt, filename=name)
