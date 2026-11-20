#!/usr/bin/env python3
"""公開ページの api.php 経由で、見本のお題を gemma4 で順に流して時間と結果を測る。
  /usr/bin/python3 scripts/eval_live.py [0,2,3 のようにお題の番号]
"""
import json, sys, time, urllib.request
BASE = "https://proto.exbridge.jp/kcadprep/api.php"
EX = [
    "外形80×50×30mm、肉厚2mmの箱形のケース。外側の角R3。天井の裏に、ねじ止め用のボスを4本（外径7mm・穴径3mm）。",
    "直径60mm・高さ25mmの丸いキャップ。肉厚1.5mm。内側の天井から十字のリブ（厚さ1.2mm・高さ10mm）。",
    "長さ120mm・幅40mm・高さ15mmのトレー。上が開いていて、仕切りで3つの部屋に分ける。肉厚2mm。",
    "幅70mm・奥行き120mm・高さ8mmの薄いカバー。肉厚1.6mm。中央に20×30mmの角穴。四隅にφ4の取付穴のボス。",
    # 見本に無いお題
    "外形100×60×25mm、肉厚2.5mmの電源ボックスのふた。外側の角R4。天井の裏に、長い辺と平行なリブを2本（厚さ1.5mm・高さ8mm）。",
]
def req(url, body=None):
    r = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                               headers={"Content-Type": "application/json", "User-Agent": "kcadprep-eval"})
    with urllib.request.urlopen(r, timeout=60) as f:
        return json.loads(f.read())
sel = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else range(len(EX))
for t in [EX[i] for i in sel]:
    t0 = time.time()
    jid = req(BASE + "?a=create", {"request": t, "engine": "gemma", "material": "ABS", "passcode": ""})["id"]
    while True:
        time.sleep(5)
        d = req(f"{BASE}?a=job&id={jid}")
        if d["status"] in ("done", "failed"):
            break
    m = (d.get("result") or {}).get("metrics") or {}
    print(json.dumps({"id": jid, "status": d["status"], "sec": round(time.time() - t0), "size": m.get("size"),
                      "mold_ok": m.get("mold_ok"), "log": [x[1] for x in d.get("log", [])][-6:],
                      "error": ((d.get("result") or {}).get("error") or "")[-200:]}, ensure_ascii=False), flush=True)
