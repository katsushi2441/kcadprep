"""1回の設計（説明 → AI がコード → 検査 → 隔離して実行 → 失敗ならエラーを返して直させる）。"""
import json
import time
from pathlib import Path

import llm
import sandbox

MAX_TRY = {"gemma": 3, "codex": 2}   # Codex は1回で約1.8万トークン使うので2回まで


def run_job(job: Path, request: str, engine: str, params: dict, log) -> dict:
    (job / "params.json").write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")
    error, code, memo = "", "", ""
    tries = []
    for n in range(1, MAX_TRY[engine] + 1):
        log(f"{n}回目: AI（{'Codex' if engine == 'codex' else 'gemma4'}）がコードを書いています")
        t0 = time.time()
        try:
            text = llm.ask(engine, llm.build_prompt(request, error, code), str(job))
        except Exception as e:
            tries.append({"n": n, "stage": "ai", "error": str(e)[-400:], "sec": round(time.time() - t0, 1)})
            log(f"AI の呼び出しに失敗しました: {str(e)[-200:]}")
            break
        new_code, new_memo, want = llm.parse(text)
        ai_sec = round(time.time() - t0, 1)
        (job / f"ai_{n}.txt").write_text(text, encoding="utf-8")
        if not new_code:
            error = "コードのブロック（```python）がありませんでした。決まりの出力の形で書いてください。"
            tries.append({"n": n, "stage": "parse", "error": error, "sec": ai_sec})
            log("コードが見つからなかったので、書き直してもらいます")
            continue
        code, memo = new_code, new_memo or memo
        (job / "part_code.py").write_text(code, encoding="utf-8")
        try:
            sandbox.check_code(code)
        except sandbox.CodeRejected as e:
            error = f"このコードは実行できません: {e}"
            tries.append({"n": n, "stage": "check", "error": str(e), "sec": ai_sec})
            log(f"コードの検査で止めました（{e}）。書き直してもらいます")
            continue
        log("CAD で形を作り、型を上下に分けています")
        for f in job.glob("*.st[el]*"):
            f.unlink()
        (job / "error.json").unlink(missing_ok=True)
        t1 = time.time()
        try:
            r = sandbox.run_cad(job)
            cad_sec = round(time.time() - t1, 1)
        except Exception as e:
            r, cad_sec = None, round(time.time() - t1, 1)
            error = f"CAD の実行が時間内に終わりませんでした: {e}"
        if r is not None and (job / "metrics.json").exists() and not (job / "error.json").exists():
            tries.append({"n": n, "stage": "ok", "sec": ai_sec, "cad_sec": cad_sec})
            metrics = json.loads((job / "metrics.json").read_text(encoding="utf-8"))
            got = sorted(metrics["size"])
            # AI が書いた外形と、実際にできた形の大きさが合うか（合わなければ、形の組み方を間違えている）
            if want and n < MAX_TRY[engine] and any(abs(g - w) > max(1.0, w * 0.06) for g, w in zip(got, want)):
                error = (f"できあがった形の外形は {' × '.join(f'{v:g}' for v in metrics['size'])} mm でしたが、"
                         f"あなたの書いた外形は {' × '.join(f'{v:g}' for v in want)} mm です。"
                         "高さの指定（box の高さ・extrude の長さ・workplane の offset）や、cut で天井や壁を消していないかを見直してください。")
                tries.append({"n": n, "stage": "size", "error": error, "sec": ai_sec, "cad_sec": cad_sec})
                log("できた形の大きさが説明と合わないので、直してもらいます")
                continue
            metrics["want_size"] = want
            return {"ok": True, "code": code, "memo": memo, "metrics": metrics, "tries": tries}
        if r is not None:
            if (job / "error.json").exists():
                error = json.loads((job / "error.json").read_text(encoding="utf-8"))["message"]
            else:
                error = (r.stderr or "CAD の実行が止まりました")[-1500:]
        tries.append({"n": n, "stage": "cad", "error": error[-600:], "sec": ai_sec, "cad_sec": cad_sec})
        log("CAD でエラーが出たので、エラーを AI に返して直してもらいます")
    return {"ok": False, "code": code, "memo": memo, "error": error[-800:], "tries": tries}
