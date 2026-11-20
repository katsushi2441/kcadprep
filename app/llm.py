"""Kurage 設計下書き — AI に CadQuery のコードを書かせる（gemma4 ／ Codex）。"""
import json
import os
import re
import shutil
import subprocess
import urllib.request

OLLAMA_URL = os.environ.get("KCADPREP_OLLAMA_URL", "http://192.168.0.3:11434")   # 直接叩くときは 0.3（CLAUDE.md）
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


def ask_gemma(prompt: str) -> str:
    body = {"model": GEMMA_MODEL, "stream": False, "think": False,   # gemma4 は思考型。think:false が要る（CLAUDE.md）
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
            "options": {"temperature": 0.2, "num_predict": 3000, "num_ctx": 8192}}
    req = urllib.request.Request(OLLAMA_URL + "/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())["message"]["content"]


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


def ask(engine: str, prompt: str, workdir: str) -> str:
    return ask_codex(prompt, workdir) if engine == "codex" else ask_gemma(prompt)
