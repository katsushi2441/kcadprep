#!/usr/bin/env python3
"""OGP 画像 1200×630（ライトテーマ・検索の言葉を一番大きく・マスコット入り・数字は焼き込まない）。
  /usr/bin/python3 scripts/make_ogp.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "public", "kcadprep-ogp.png")
MASCOT = "/home/kojima/work/kurage_web/images/kurage-mascot-cutout.png"
FB = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
FM = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FR = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

img = Image.new("RGB", (W, H), "#ffffff")
dr = ImageDraw.Draw(img, "RGBA")
dr.ellipse([-180, -240, 480, 380], fill=(230, 244, 242, 255))
dr.ellipse([W - 460, H - 330, W + 220, H + 240], fill=(255, 244, 226, 255))
# 型の絵（上の型・成形品・下の型を、開いた形で簡単に）
ox, oy = 860, 150
dr.rounded_rectangle([ox, oy, ox + 250, oy + 70], radius=10, fill=(61, 123, 217, 200))
dr.rounded_rectangle([ox + 55, oy + 95, ox + 195, oy + 150], radius=8, fill=(138, 149, 161, 255))
dr.rounded_rectangle([ox, oy + 175, ox + 250, oy + 245], radius=10, fill=(224, 138, 43, 210))
dr.rectangle([ox + 70, oy + 150, ox + 180, oy + 175], fill=(224, 138, 43, 210))
f_cap = ImageFont.truetype(FM, 20)
dr.text((ox + 125, oy + 35), "キャビティ", font=f_cap, fill="#ffffff", anchor="mm")
dr.text((ox + 125, oy + 122), "成形品", font=f_cap, fill="#ffffff", anchor="mm")
dr.text((ox + 125, oy + 215), "コア", font=f_cap, fill="#ffffff", anchor="mm")

cx = 430
f_badge = ImageFont.truetype(FM, 26)
badge = "射出成形の金型づくりの下ごしらえ"
bw = dr.textlength(badge, font=f_badge) + 40
dr.rounded_rectangle([cx - bw / 2, 88, cx + bw / 2, 136], radius=24, fill="#e6f4f2", outline="#bfe3de")
dr.text((cx, 112), badge, font=f_badge, fill="#0a726b", anchor="mm")
dr.text((cx, 225), "AIで金型の設計", font=ImageFont.truetype(FB, 76), fill="#12202f", anchor="mm")
dr.text((cx, 315), "の下書きを作る", font=ImageFont.truetype(FB, 56), fill="#0a9a8f", anchor="mm")
f_s = ImageFont.truetype(FR, 27)
dr.text((cx, 385), "形と寸法を日本語で書くと、CADで3Dの形と", font=f_s, fill="#5d6b7a", anchor="mm")
dr.text((cx, 425), "キャビティ・コアを作り、STEPで書き出します。", font=f_s, fill="#5d6b7a", anchor="mm")
dr.rounded_rectangle([cx - 210, 472, cx + 210, 534], radius=16, fill="#0a9a8f")
dr.text((cx, 503), "Kurage 設計下書き", font=ImageFont.truetype(FM, 32), fill="#ffffff", anchor="mm")
if os.path.exists(MASCOT):
    m = Image.open(MASCOT).convert("RGBA")
    mh = 210
    m = m.resize((int(m.width * mh / m.height), mh))
    img.paste(m, (W - m.width - 50, H - m.height - 20), m)
dr.text((40, H - 36), "proto.exbridge.jp/kcadprep/", font=ImageFont.truetype(FR, 22), fill="#5d6b7a", anchor="lm")
img.save(OUT, optimize=True)
print(OUT, img.size)
