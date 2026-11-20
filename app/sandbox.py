"""AI が書いたコードの検査と、bwrap の中での実行。

公開デモの入力から AI がコードを書くので、悪意のある説明でコードが書き換えられても困らないようにする。
1) 構文の検査（import・下線で始まる名前・入出力の関数を拒否）
2) bwrap で隔離（ネットワーク無し・/home と /mnt は見せない・書けるのはその回のフォルダだけ）
3) CPU 時間・メモリ・実行時間の上限
"""
import ast
import os
import resource
import subprocess
from pathlib import Path

APP = Path(__file__).resolve().parent
ROOT = APP.parent
VENV = ROOT / ".venv"

BANNED_NAMES = {
    "open", "exec", "eval", "compile", "input", "globals", "locals", "vars", "getattr", "setattr", "delattr",
    "__import__", "breakpoint", "help", "dir", "type", "object", "memoryview", "bytearray", "exit", "quit",
}
BANNED_ATTRS = {
    "os", "sys", "subprocess", "system", "popen", "importers", "exporters", "importStep", "importStl", "exportStep",
    "exportStl", "export", "importBrep", "exportBrep", "save", "load", "builtins", "modules", "environ", "path",
    "read", "write", "remove", "unlink", "rmdir", "spawn", "fork", "socket", "urllib", "request", "shutil",
}


class CodeRejected(Exception):
    pass


def check_code(code: str):
    if not code.strip():
        raise CodeRejected("コードが空です")
    if len(code) > 12000:
        raise CodeRejected("コードが長すぎます")
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise CodeRejected(f"構文エラー: {e}")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise CodeRejected("import 文は使えません（cq と math は読み込み済みです）")
        if isinstance(node, (ast.Global, ast.Nonlocal, ast.AsyncFunctionDef, ast.Await, ast.With, ast.AsyncWith)):
            raise CodeRejected(f"使えない書き方です: {type(node).__name__}")
        if isinstance(node, ast.Name) and (node.id in BANNED_NAMES or node.id.startswith("_")):
            raise CodeRejected(f"使えない名前です: {node.id}")
        if isinstance(node, ast.Attribute) and (node.attr.startswith("_") or node.attr in BANNED_ATTRS):
            raise CodeRejected(f"使えない属性です: {node.attr}")
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and ("__" in node.value):
            raise CodeRejected("下線2つを含む文字列は使えません")
    if "result" not in code:
        raise CodeRejected("変数 result がありません")


def _limits():
    resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
    resource.setrlimit(resource.RLIMIT_AS, (6 * 1024 ** 3, 6 * 1024 ** 3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (200 * 1024 ** 2, 200 * 1024 ** 2))
    os.nice(10)


def run_cad(job: Path, timeout: int = 120) -> subprocess.CompletedProcess:
    job = job.resolve()
    cmd = ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp",
           *[x for d in ("/home", "/mnt", "/root", "/data", "/srv", "/opt") if Path(d).exists() for x in ("--tmpfs", d)],
           "--ro-bind", str(VENV), str(VENV), "--ro-bind", str(APP), str(APP),
           "--bind", str(job), str(job),
           "--unshare-all", "--die-with-parent", "--new-session", "--chdir", str(job),
           "--setenv", "HOME", "/tmp", "--unsetenv", "PYTHONPATH",
           str(VENV / "bin" / "python"), "-I", str(APP / "cad_worker.py"), str(job)]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, preexec_fn=_limits,
                          env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
