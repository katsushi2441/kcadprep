"""Kurage 設計下書き — AI に CadQuery のコードを書かせる（gemma4 ／ Codex）。"""
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request

GEMMA_MODEL = os.environ.get("KCADPREP_GEMMA_MODEL", "gemma4:12b-it-qat")
CODEX_BIN = os.environ.get("CODEX_BIN") or shutil.which("codex") or "/home/kojima/.nvm/versions/node/v20.20.2/bin/codex"
CODEX_MODEL = os.environ.get("KCADPREP_CODEX_MODEL", "gpt-6-sol")

SYSTEM = """あなたは射出成形の金型メーカーで働く設計者です。お客様の説明から、成形品（樹脂の部品）の3Dの形を CadQuery 2.7（Python）のコードで書きます。

# コードの決まり
- 使えるのは、すでに読み込んである `cq`（cadquery）と `math` だけ。import 文は書かない。ファイルの読み書き・open・print 以外の入出力はしない。
- 最後に、成形品の立体を変数 `result` に入れる（cq.Workplane）。
- 単位は mm。Z が上。**成形品の一番下（箱なら開いている口の面）を z=0 に置き、上に向かって作る。** 型はこの z=0 の面で上下に分かれる（上がキャビティ、下がコア）。
- 箱・カバー・ケースのように中が空いた形は、**下（-Z 側）が開いた形**にする（外側の立体から内側の立体を cut する）。
- 抜き勾配の指定があれば extrude(…, taper=角度) や、外側と内側の寸法差で付ける。指定が無ければ付けなくてよい。
- 角の R（fillet）は、肉厚の半分より小さくする。fillet が失敗しやすいので、立体を組み合わせる前の単純な箱の段階で付ける。
- ボス・リブ・穴は、本体と union / cut で組み合わせる。ボスやリブは天井の裏から下に伸ばし、z=0 より下に出さない。
- 寸法の指定が無いところは、その製品として自然な値を決めて、コードの先頭に変数でまとめる（例: L, W, H, t）。
- 説明に無い装飾は足さない。コードは60行以内。
- **トレー・カップのように「上が開いた」と言われた形も、開いた面を下（z=0）に向けて、逆さにして作る**（型の分け方がそろうため）。
- `box()` は中心に置かれる。必ず `centered=(True, True, False)` を付けて、底を z=0 にそろえる。
- ボス・リブ・仕切りは、壁や天井に 0.5mm ほど重ねて置き、離れた立体にしない（離れると失敗になる）。

# 書き方の見本（外形80×50×30・肉厚2・角R3・ボス4本の箱）
```python
L, W, H, t, R = 80.0, 50.0, 30.0, 2.0, 3.0
boss_d, hole_d = 7.0, 3.0
# 外側: 底が z=0 になるように centered=(True, True, False)。縦の角に R を付けてから中をくり抜く
outer = cq.Workplane("XY").box(L, W, H, centered=(True, True, False)).edges("|Z").fillet(R)
inner = cq.Workplane("XY").box(L - 2 * t, W - 2 * t, H - t, centered=(True, True, False))
result = outer.cut(inner)
# ボス: 天井の裏（z = H - t）から下へ伸ばす。天井に食い込ませて1つの立体にする
pts = [(sx * (L / 2 - t - boss_d), sy * (W / 2 - t - boss_d)) for sx in (-1, 1) for sy in (-1, 1)]
boss = (cq.Workplane("XY").workplane(offset=H - t + 0.5).pushPoints(pts)
        .circle(boss_d / 2).circle(hole_d / 2).extrude(-(H - t - 5)))
result = result.union(boss)
# 仕切り・リブ: 壁と天井に少し重ねて（+0.5）置き、離れた立体にしない
# 仕切りで n 部屋に分けるとき、仕切りの位置は x = -L/2 + L*k/n（k = 1 … n-1。原点が中心なので負の側もある）
# for k in range(1, n):
#     wall = cq.Workplane("XY").box(t, W - 2 * t + 1, H - t + 0.5, centered=(True, True, False)).translate((-L / 2 + L * k / n, 0, 0))
#     result = result.union(wall)
```

# 出力の形
1. ```python で始まるコードのブロックを1つ。
2. その次の行に、できあがる成形品の外形の大きさを「外形: X × Y × Z」（mm・数字だけ）と1行で書く。
3. その後に「設計メモ:」と書き、決めた寸法や仮定を日本語で3行以内（各行は「- 」で始める）。
"""


def build_prompt(request: str, error: str = "", prev_code: str = "") -> str:
    if not error:
        return f"# お客様の説明\n{request}\n"
    return (f"# お客様の説明\n{request}\n\n# 前に書いたコード\n```python\n{prev_code}\n```\n\n"
            f"# 実行したときのエラー\n{error[-1500:]}\n\n"
            "エラーの原因を直したコードを、同じ出力の形で書き直してください。"
            "fillet や shell で失敗している場合は、その操作を外すか半径を小さくしてください。")


def parse(text: str):
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.S)
    code = m.group(1).strip() if m else ""
    memo = ""
    mm = re.search(r"設計メモ[:：]\s*(.*)$", text, re.S)
    if mm:
        memo = "\n".join(line.strip() for line in mm.group(1).strip().splitlines() if line.strip())[:600]
    size = None
    ms = re.search(r"外形[:：]\s*([0-9.]+)\s*[x×X＊*]\s*([0-9.]+)\s*[x×X＊*]\s*([0-9.]+)", text)
    if ms:
        size = sorted(float(v) for v in ms.groups())
    return code, memo, size


def ask_gemma(prompt: str, log=None) -> str:
    """0.14 の gemma4 を rqdb4ai のキュー（ollama-192-168-0-14-web）に載せて待つ。

    0.14 の Ollama は直接叩かない（CLAUDE.md）。キューが H3・ACE-Step などと直列化するので、
    前の仕事があると順番待ちになる。結果は rqdb4ai の /api/jobs/<id>/result で受け取る。
    """
    url = os.environ.get("KCADPREP_RQDB4AI_URL", "http://127.0.0.1:18300").rstrip("/")
    token = os.environ.get("KCADPREP_RQDB4AI_TOKEN", "")
    if not token:
        raise RuntimeError("KCADPREP_RQDB4AI_TOKEN が .env にありません")
    hdr = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}

    def call(method, path, body=None, timeout=30):
        req = urllib.request.Request(url + path, method=method, headers=hdr,
                                     data=json.dumps(body).encode() if body is not None else None)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())

    payload = {
        "queue": "auto",
        "function": "kcadprep.jobs.ollama_chat_job",
        "kwargs": {"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                   "model": GEMMA_MODEL, "temperature": 0.2, "num_predict": 4000, "request_timeout": 600,
                   "source": "kcadprep"},
        "meta": {"project": "kcadprep", "app": "kcadprep", "kind": "ollama_chat", "resource": "ollama",
                 "resource_key": f"ollama:192.168.0.14:{GEMMA_MODEL}", "ollama_host": "192.168.0.14",
                 "ollama_endpoint": "http://192.168.0.14:11434", "ollama_model": GEMMA_MODEL,
                 "source": "web_online", "queue_class": "web", "priority_class": "interactive"},
        "timeout": 660, "result_ttl": 3600, "failure_ttl": 604800,
    }
    job_id = str((call("POST", "/api/enqueue", payload).get("job") or {}).get("id") or "")
    if not job_id:
        raise RuntimeError("rqdb4ai がジョブ番号を返しませんでした")
    deadline = time.time() + 900
    said_wait = False
    while time.time() < deadline:
        time.sleep(3)
        d = call("GET", f"/api/jobs/{job_id}").get("job") or {}
        st = str(d.get("status") or "")
        if st == "queued" and not said_wait and log:
            log("0.14 の GPU の順番待ちです（ほかの仕事が終わると始まります）"); said_wait = True
        if st == "finished":
            res = call("GET", f"/api/jobs/{job_id}/result").get("result") or {}
            text = str(res.get("response") or "").strip()
            if not res.get("ok") or not text:
                raise RuntimeError(f"gemma4 の答えが空でした（{job_id}）")
            return text
        if st in {"failed", "stopped", "canceled"}:
            raise RuntimeError(f"gemma4 のジョブが {st} で終わりました（{job_id}）: {str(d.get('exc_info') or '')[-300:]}")
    raise RuntimeError(f"gemma4 の答えが15分で返りませんでした（{job_id}）")


def ask_codex(prompt: str, workdir: str) -> str:
    workdir = os.path.abspath(workdir)   # codex は cwd=workdir で動くので、-o は絶対パスで渡す（相対だと二重になる）
    op = os.path.join(workdir, "codex-out.txt")
    full = SYSTEM + "\nファイルの読み書きやコマンドの実行はしないでください。答えはこのメッセージへの返事として書いてください。\n\n" + prompt
    env = dict(os.environ, PATH=os.path.dirname(CODEX_BIN) + ":" + os.environ.get("PATH", ""))   # codex は node で動く
    r = subprocess.run([CODEX_BIN, "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only", "-m", CODEX_MODEL,
                        "-o", op, "-"], input=full, capture_output=True, text=True, timeout=900, cwd=workdir, env=env)
    if not os.path.exists(op) and "```" in (r.stdout or ""):
        return r.stdout   # 最後の返事のファイルが無くても、標準出力に答えがあれば使う（1回で約2万トークン使うので捨てない）
    if r.returncode != 0 or not os.path.exists(op):
        raise RuntimeError("Codex が失敗しました: " + (r.stderr or r.stdout)[-400:])
    return open(op, encoding="utf-8").read()


def ask(engine: str, prompt: str, workdir: str, log=None) -> str:
    return ask_codex(prompt, workdir) if engine == "codex" else ask_gemma(prompt, log)
