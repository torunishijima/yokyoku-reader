#!/usr/bin/env python3
"""照合結果（work/collate/<曲>.json）の要確認箇所（check / stage）を、大観の画像から縦の帯で切り出し、
番号つきで横に並べた確認用シートを作る（右から左へ 1, 2, 3…）。
出力: work/checks/<曲>/sheetNN.jpg と list.txt（番号・頁・半魚・大観・前後）
使い方: make_checks.py <曲名> [...]"""
import sys, json, time, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / 'work/img'; COL = ROOT / 'work/collate'; OUT = ROOT / 'work/checks'
PER_SHEET = 10; STRIP_H = 760
FONT = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 30)

def half(pid, stem):
    """OCR に使ったのと同じ切り方の片ページ画像（キャッシュ）"""
    p = IMG / pid / f'{stem}.jpg'
    if p.exists(): return Image.open(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    f = int(stem[1:5]); side = stem[5]
    url = f'https://dl.ndl.go.jp/api/iiif/{pid}/R{f:07d}/full/full/0/default.jpg'
    tmp = p.with_suffix('.spread.jpg'); tmp.write_bytes(urllib.request.urlopen(url, timeout=60).read()); time.sleep(0.5)
    im = Image.open(tmp); w, h = im.size
    for s, box in (('L', (0, 0, w // 2 + w // 50, h)), ('R', (w // 2 - w // 50, 0, w, h))):
        im.crop(box).save(IMG / pid / f'{stem[:5]}{s}.jpg', quality=92)
    tmp.unlink()
    return Image.open(p)

def strip(d):
    m = d['line']; im = half(m['pid'], m['img']); W, H = im.size
    x0, y0, x1, y1 = m['box']; lw = max(x1 - x0, 40)
    cx0, cx1 = max(0, x0 - int(lw * 1.2)), min(W, x1 + int(lw * 1.2))
    cy0, cy1 = int(H * 0.26), int(H * 0.69)
    c = im.crop((cx0, cy0, cx1, cy1)).convert('RGB')
    dr = ImageDraw.Draw(c)
    dr.rectangle((x0 - cx0 - 3, y0 - cy0 - 3, x1 - cx0 + 3, y1 - cy0 + 3), outline=(220, 0, 0), width=3)
    s = STRIP_H / c.height
    return c.resize((max(1, int(c.width * s)), STRIP_H))

for title in sys.argv[1:]:
    r = json.loads((COL / f'{title}.json').read_text(encoding='utf-8'))
    items = [d for d in r['diffs'] if d['kind'] == 'check' and d.get('line')]
    od = OUT / title; od.mkdir(parents=True, exist_ok=True)
    for old in od.glob('sheet*.jpg'): old.unlink()
    lst = []
    for k in range(0, len(items), PER_SHEET):
        group = items[k:k + PER_SHEET]
        strips = [strip(d) for d in group]
        W = sum(s.width for s in strips) + 8 * (len(strips) + 1)
        sheet = Image.new('RGB', (W, STRIP_H + 50), 'white'); dr = ImageDraw.Draw(sheet)
        x = W - 8
        for n, (d, s) in enumerate(zip(group, strips), k + 1):
            x -= s.width; sheet.paste(s, (x, 50)); dr.text((x + 4, 8), str(n), fill=(220, 0, 0), font=FONT); x -= 8
        sheet.save(od / f'sheet{k // PER_SHEET + 1:02d}.jpg', quality=85)
        for n, d in enumerate(group, k + 1):
            lst.append(f"{n}\tp{d['page']}\t{d['kind']}\t半魚「{d['hangyo']}」\t大観OCR「{d['taikan']}」\t{d['ctx']}")
    (od / 'list.txt').write_text('\n'.join(lst) + '\n', encoding='utf-8')
    print(title, len(items), '箇所', (len(items) + PER_SHEET - 1) // PER_SHEET, '枚')
