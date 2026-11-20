"""Kurage 設計下書き — CAD の実行部（bwrap の中で1回ずつ動く）。

使い方: python cad_worker.py <job_dir>
  <job_dir>/part_code.py  … AI が書いた CadQuery のコード（変数 result に成形品の形を入れる）
  <job_dir>/params.json   … 型の作り方（材料・型の余白・パーティング面など）
出力: part.step / part.stl / cavity.* / core.* / metrics.json（エラーは error.json）

成形品の形だけを AI に書かせ、型の分け方（キャビティ・コア・ゲート・冷却穴）は
このファイルの決まった手順で作る。AI に任せると型の形が毎回変わり、デモの場で崩れるため。
"""
import json
import math
import sys
import traceback
from pathlib import Path

import cadquery as cq

# 樹脂の密度（g/cm3）と、型締め力の目安に使う型内の圧力（MPa）。どちらも一般的な目安の値
MATERIALS = {
    "PP": {"name": "PP（ポリプロピレン）", "density": 0.91, "pressure": 30, "shrink": 1.5},
    "ABS": {"name": "ABS", "density": 1.05, "pressure": 40, "shrink": 0.5},
    "PC": {"name": "PC（ポリカーボネート）", "density": 1.20, "pressure": 50, "shrink": 0.6},
    "PA66": {"name": "PA66（ナイロン）", "density": 1.14, "pressure": 50, "shrink": 1.2},
    "POM": {"name": "POM（ポリアセタール）", "density": 1.41, "pressure": 50, "shrink": 2.0},
}


def fail(job: Path, stage: str, msg: str):
    (job / "error.json").write_text(json.dumps({"stage": stage, "message": msg[-3000:]}, ensure_ascii=False), encoding="utf-8")
    sys.exit(2)


def as_solid(obj):
    """result に入っている形を1つの Solid/Compound にそろえる"""
    if isinstance(obj, cq.Workplane):
        vals = [v for v in obj.vals() if isinstance(v, cq.Shape)]
        if not vals:
            raise ValueError("result に形が入っていません（Workplane に立体がありません）")
        shape = vals[0] if len(vals) == 1 else cq.Compound.makeCompound(vals)
    elif isinstance(obj, cq.Shape):
        shape = obj
    else:
        raise ValueError("result は cadquery の Workplane か Shape にしてください")
    if not shape.Solids():
        raise ValueError("result に立体（Solid）がありません。面や線だけになっています")
    if shape.Volume() <= 1e-6:
        raise ValueError("立体の体積が0です")
    if len(shape.Solids()) > 1:
        vols = sorted((round(s.Volume(), 1) for s in shape.Solids()), reverse=True)
        raise ValueError(f"形が{len(vols)}個の離れた立体に分かれています（体積 {vols[:5]} mm3）。"
                         "ボス・リブ・仕切りが本体（天井や壁）につながっていません。高さや位置を見直して、全部を1つにつなげてください")
    return shape


def export(shape, base: Path):
    cq.exporters.export(shape, str(base) + ".step")
    cq.exporters.export(shape, str(base) + ".stl", tolerance=0.05, angularTolerance=0.2)


def main():
    job = Path(sys.argv[1])
    params = json.loads((job / "params.json").read_text(encoding="utf-8"))
    code = (job / "part_code.py").read_text(encoding="utf-8")

    # 1) 成形品の形（AI のコード）
    ns = {"cq": cq, "math": math, "__builtins__": SAFE_BUILTINS}
    try:
        exec(compile(code, "part_code.py", "exec"), ns)
        part = as_solid(ns.get("result"))
    except SystemExit:
        raise
    except Exception:
        fail(job, "part", traceback.format_exc(limit=3))

    bb = part.BoundingBox()
    # 型の中心を原点に寄せる（AI が原点から離れた位置に作っても型を同じ作り方にできるように）
    part = part.translate(cq.Vector(-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))
    bb = part.BoundingBox()
    export(part, job / "part")

    mat = MATERIALS.get(params.get("material", "ABS"), MATERIALS["ABS"])
    vol_mm3 = part.Volume()
    metrics = {
        "size": [round(bb.xlen, 2), round(bb.ylen, 2), round(bb.zlen, 2)],
        "volume_cm3": round(vol_mm3 / 1000, 2),
        "material": mat["name"],
        "weight_g": round(vol_mm3 / 1000 * mat["density"], 1),
        "faces": len(part.Faces()),
        "solids": len(part.Solids()),
    }

    # 投影面積（上から見た面積）。型締め力の目安＝投影面積×型内の圧力
    try:
        # 上から見た影の面積。箱の形は肉厚の輪だけを切ると小さく出るので、外形の輪郭（穴を埋めた面）で測る
        area = 0.0
        for k in range(1, 6):
            z = bb.zmin + bb.zlen * k / 6
            sl = part.intersect(cq.Solid.makeBox(bb.xlen + 2, bb.ylen + 2, 0.01,
                                                 cq.Vector(bb.xmin - 1, bb.ymin - 1, z)))
            for f in sl.Faces():
                if abs(f.normalAt().z) > 0.99:
                    area = max(area, cq.Face.makeFromWires(f.outerWire()).Area())
        area = min(area, bb.xlen * bb.ylen) or bb.xlen * bb.ylen
        metrics["projected_cm2"] = round(area / 100, 1)
        metrics["clamp_ton"] = round(area * mat["pressure"] / 9806.65, 1)
        metrics["pressure_mpa"] = mat["pressure"]
    except Exception:
        pass
    metrics["shrink_percent"] = mat["shrink"]

    # 2) 型（キャビティ＝固定側・上、コア＝可動側・下）。パーティング面は成形品の一番下（開口部）
    try:
        m = float(params.get("margin", 20))
        bx, by = bb.xlen + 2 * m, bb.ylen + 2 * m
        ztop = bb.zmax + m
        zbot = bb.zmin - m
        pz = bb.zmin
        if params.get("parting") == "middle":
            pz = (bb.zmin + bb.zmax) / 2
        upper = cq.Solid.makeBox(bx, by, ztop - pz, cq.Vector(-bx / 2, -by / 2, pz))
        lower = cq.Solid.makeBox(bx, by, pz - zbot, cq.Vector(-bx / 2, -by / 2, zbot))
        up = upper.cut(part)
        lo = lower.cut(part)
        # 上の型から外れた島（箱の内側の空間＝コアの出っ張り）は、下の型に付ける
        sols = sorted(up.Solids(), key=lambda s: s.Volume(), reverse=True)
        cavity = sols[0]
        core = lo
        for s in sols[1:]:
            core = core.fuse(s)
        core = core.clean()

        # ゲート（スプルー）: 型の上から成形品の上面の中心へ、上が太い円すいの穴
        if params.get("gate", True):
            top_z = bb.zmax
            # 中心の真上に成形品が無ければ、成形品の一番上の面の中心を狙う
            try:
                face = cq.Workplane().add(part).faces(">Z").val()
                c = face.Center()
                gx, gy = c.x, c.y
            except Exception:
                gx, gy = 0.0, 0.0
            h = ztop - top_z + 0.5
            sprue = cq.Solid.makeCone(1.5, 4.0, h, cq.Vector(gx, gy, top_z - 0.5), cq.Vector(0, 0, 1))
            cavity = cavity.cut(sprue)
            metrics["gate"] = [round(gx, 1), round(gy, 1)]

        # 冷却穴: X 方向に通す直径8mm の穴。成形品から m/2 離した高さに、Y 方向に並べる
        if params.get("cooling", True):
            d = 8.0
            holes = 0
            n = max(2, int(by // 30))
            for i in range(n):
                y = -by / 2 + by * (i + 0.5) / n
                for z, tgt in ((bb.zmax + m / 2, "cavity"), (bb.zmin - m / 2, "core")):
                    cyl = cq.Solid.makeCylinder(d / 2, bx + 2, cq.Vector(-bx / 2 - 1, y, z), cq.Vector(1, 0, 0))
                    if tgt == "cavity":
                        if cavity.intersect(cyl).Volume() > 0:
                            cavity = cavity.cut(cyl)
                            holes += 1
                    else:
                        core = core.cut(cyl)
                        holes += 1
            metrics["cooling_holes"] = holes
        metrics["mold_size"] = [round(bx, 1), round(by, 1), round(ztop - zbot, 1)]
        metrics["parting_z"] = round(pz, 2)
        export(cavity, job / "cavity")
        export(core, job / "core")
        metrics["mold_ok"] = True
    except Exception:
        metrics["mold_ok"] = False
        metrics["mold_error"] = traceback.format_exc(limit=2)[-800:]

    (job / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False), encoding="utf-8")


import builtins as _b  # noqa: E402

SAFE_BUILTINS = {k: getattr(_b, k) for k in (
    "abs", "all", "any", "bool", "dict", "enumerate", "float", "int", "len", "list", "map", "max", "min",
    "pow", "range", "reversed", "round", "set", "sorted", "sum", "tuple", "zip", "print", "isinstance",
    "ValueError", "Exception", "True", "False", "None", "str", "divmod", "filter",
) if hasattr(_b, k)}


if __name__ == "__main__":
    main()
