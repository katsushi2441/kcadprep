"""RQDB4AI worker entrypoint for Kurage 設計下書き (kcadprep).

0.14 の Ollama は rqdb4ai のキュー経由でだけ使う（ワークスペース規約）。
このファイルは rqdb4ai の h3-worker（0.3 で動き、0.14 の GPU 仕事を直列化する）が
PYTHONPATH の /home/kojima/work/kcadprep から import する。依存は requests だけにする。
"""
from __future__ import annotations

import json
import os
from typing import Any

import requests

DEFAULT_OLLAMA_URL = "http://192.168.0.14:11434"
MAX_MESSAGES_CHARS = 60_000


def ollama_chat_job(
    messages: list[dict[str, str]],
    model: str = "gemma4:12b-it-qat",
    temperature: float = 0.2,
    num_predict: int = 4000,
    request_timeout: int = 600,
    source: str = "kcadprep",
    **_: Any,
) -> dict[str, Any]:
    if not isinstance(messages, list) or not messages:
        raise RuntimeError("messages are required")
    serialized = json.dumps(messages, ensure_ascii=False)
    if len(serialized) > MAX_MESSAGES_CHARS:
        raise RuntimeError(f"messages are too large ({len(serialized)} > {MAX_MESSAGES_CHARS})")
    url = os.environ.get("KCADPREP_WORKER_OLLAMA_URL", DEFAULT_OLLAMA_URL).rstrip("/")
    payload = {
        "model": str(model),
        "messages": messages,
        "stream": False,
        "think": False,  # gemma4 は思考型。無いと num_predict を食い潰して空応答になる
        "options": {"temperature": float(temperature), "num_predict": int(num_predict)},
    }
    r = requests.post(f"{url}/api/chat", json=payload, timeout=max(30, int(request_timeout)))
    r.raise_for_status()
    body = r.json()
    text = str((body.get("message") or {}).get("content") or "").strip()
    if not text:
        raise RuntimeError(f"Ollama returned an empty response (done_reason={body.get('done_reason', 'unknown')})")
    return {
        "ok": True,
        "status": "completed",
        "completion_scope": "business_result",
        "business_terminal": True,
        "items": 1,
        "response": text,
        "response_chars": len(text),
        "model": str(model),
        "source": source,
        "ollama_host": "192.168.0.14",
        "eval_seconds": round((body.get("total_duration") or 0) / 1e9, 1),
        "note": "Kurage 設計下書き: part code drafted through the 0.14 Ollama queue",
    }
