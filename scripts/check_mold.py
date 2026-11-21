#!/usr/bin/env python3
"""型の分け方の検査。ジョブの写しで cad_worker を流し直し、コアが成形品の内側を受け持っているか・キャビティが内側に入り込んでいないかを数える。
  .venv/bin/python scripts/check_mold.py <ジョブ番号> ...   （写しは outputs/regress/<番号>）"""
import shutil, subprocess, sys
from pathlib import Path
import cadquery as cq
ROOT = Path(__file__).resolve().parents[1]
for jid in sys.argv[1:]:
    src, dst = ROOT / "outputs/jobs" / jid, ROOT / "outputs/regress" / jid
    shutil.rmtree(dst, ignore_errors=True); dst.mkdir(parents=True)
    for f in ("part_code.py", "params.json"):
        shutil.copy(src / f, dst / f)
    r = subprocess.run([str(ROOT / ".venv/bin/python"), str(ROOT / "app/cad_worker.py"), str(dst)], capture_output=True, text=True, timeout=300)
    if not (dst / "core.step").exists():
        print(jid, "失敗", (r.stderr or r.stdout)[-300:]); continue
    part = cq.importers.importStep(str(dst / "part.step")).val(); bb = part.BoundingBox()
    core = cq.importers.importStep(str(dst / "core.step")).val(); cav = cq.importers.importStep(str(dst / "cavity.step")).val()
    prism = cq.Solid.makeBox(bb.xlen, bb.ylen, bb.zlen, cq.Vector(bb.xmin, bb.ymin, bb.zmin))
    void = prism.cut(part).Volume()
    core_in = core.intersect(prism).Volume(); cav_in = cav.intersect(prism).Volume()
    clash = core.intersect(cav).Volume() + core.intersect(part).Volume() + cav.intersect(part).Volume()
    print(f"{jid}  外形内の空き {void:,.0f}  うちコア {core_in:,.0f}・キャビティ {cav_in:,.0f}  重なり {clash:.1f}  キャビティ{len(cav.Solids())}個・コア{len(core.Solids())}個")
