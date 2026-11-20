import sys, cadquery as cq, math
src = open(sys.argv[1]).read(); g = {"cq": cq, "math": math}; exec(src, g)
s = g["result"].val(); bb = s.BoundingBox()
print("solids", len(g["result"].solids().vals()), "bbox", round(bb.xlen,2), round(bb.ylen,2), round(bb.zmin,2), round(bb.zmax,2), "vol", round(s.Volume()))
