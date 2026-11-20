# Kurage 設計下書き（kcadprep）

射出成形の成形品を日本語で説明すると、AI が CadQuery（オープンソースの CAD）のコードを書き、
3D の形と、金型のキャビティ・コアの下書き、ゲート・冷却穴、型締め力の目安までを作るシステムです。
結果は STEP で書き出して、お使いの CAD で仕上げます。

デモ: https://proto.exbridge.jp/kcadprep/

## しくみ

1. AI（gemma4 または Codex）が成形品のコード（`result`）だけを書く
2. コードを検査し、外とつながらない隔離した環境（bubblewrap）で CadQuery を実行
3. 型の分割・ゲート・冷却穴・目安の計算は、決まった手順のコードで行う（AI に任せない）
4. エラーや、説明と大きさが合わないときは、その内容を AI に返して直させる

## 構成

- `app/` … FastAPI のサーバー（`server.py`）・AI の呼び出し（`llm.py`）・隔離実行（`sandbox.py`）・CAD の処理（`cad_worker.py`）
- `kcadprep/jobs.py` … gemma4 を rqdb4ai のキュー経由で呼ぶときのワーカー側の入口
- `public/` … 画面（PHP の中継・three.js の 3D 表示）
- `scripts/` … 公開・OGP 画像・通しテスト

## 動かす

```
python3.10 -m venv .venv && .venv/bin/pip install cadquery==2.7.* fastapi uvicorn
cp deploy/kcadprep.service ~/.config/systemd/user/ && systemctl --user enable --now kcadprep.service
```

`.env` に `KCADPREP_API_TOKEN`・`KCADPREP_CODEX_PASSCODE`・`KCADPREP_RQDB4AI_URL`・`KCADPREP_RQDB4AI_TOKEN` を置きます（リポジトリには含めません）。

株式会社エクスブリッジ — https://exbridge.jp/
