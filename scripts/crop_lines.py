#!/usr/bin/env python3
"""本文 OCR の行を、指定した文字列で探して原本画像から切り出し、横に並べた 1 枚にする（シートに出ない行を確かめる用）。
使い方: ~/tools/textvenv/bin/python scripts/crop_lines.py [--tsushaku] <曲名> <出力.jpg> <文字列> [<文字列> ...]
  --tsushaku で通釈の行から探す。
  ヒットした行ごとに、その行の周り（行頭から下へ約 1000px）を赤枠付きで切り出す。右から左へ並ぶ。"""
import sys, json, time, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / 'work/img'; SPLIT = ROOT / 'work/split'

def half(pid, stem):
    """OCR に使ったのと同じ切り方の片ページ画像（make_checks.py と同じキャッシュ）"""
    p = IMG / pid / f'{stem}.jpg'
    if p.exists(): return Image.open(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    f = int(stem[1:5])
    url = f'https://dl.ndl.go.jp/api/iiif/{pid}/R{f:07d}/full/full/0/default.jpg'
    tmp = p.with_suffix('.spread.jpg'); tmp.write_bytes(urllib.request.urlopen(url, timeout=60).read()); time.sleep(0.5)
    im = Image.open(tmp); w, h = im.size
    for s, box in (('L', (0, 0, w // 2 + w // 50, h)), ('R', (w // 2 - w // 50, 0, w, h))):
        im.crop(box).save(IMG / pid / f'{stem[:5]}{s}.jpg', quality=92)
    tmp.unlink()
    return Image.open(p)

args = sys.argv[1:]
part = 'tsushaku' if args[0] == '--tsushaku' else 'honbun'
if part == 'tsushaku': args = args[1:]
title, out, subs = args[0], args[1], args[2:]
txt = (SPLIT / f'{title}.{part}.txt').read_text(encoding='utf-8').splitlines()
lj = json.loads((SPLIT / f'{title}.{part}.lines.json').read_text(encoding='utf-8'))
crops = []
for s in subs:
    for t, m in zip(txt, lj):
        if m and s in t:
            im = half(m['pid'], m['img']).convert('RGB'); x0, y0, x1, y1 = m['box']
            left = max(0, x0 - 90)
            c = im.crop((left, max(0, y0 - 60), x1 + 90, y0 + 1000))
            ImageDraw.Draw(c).rectangle((x0 - left, 60, x1 - left, 60 + y1 - y0), outline='red', width=2)
            crops.append(c); print(m['page'], t)
if not crops: sys.exit('見つからない')
W = sum(c.width for c in crops) + 10 * len(crops); H = max(c.height for c in crops)
sheet = Image.new('RGB', (W, H), 'white'); x = W
for c in crops: x -= c.width + 10; sheet.paste(c, (x, 0))
sheet.save(out, quality=85)
