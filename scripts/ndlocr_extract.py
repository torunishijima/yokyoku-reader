#!/usr/bin/env python3
"""NDLOCR-Lite の出力 JSON（謡曲大観の1ページ＝1画像）から、本文（中段）または通釈（下段）を取り出す。
段は行の上端の高さで判定する（頭注 <0.28 / 本文 0.28-0.6 / 通釈 >0.6、ページ高さ比）。
大きい字（詞章・台詞）と小さい字（型付・ト書き）は文字の大きさで分け、小さい字の行頭に「＊」を付ける。
使い方: ndlocr_extract.py <出力dir> <honbun|tsushaku> [ページ...]"""
import json, sys, re
from pathlib import Path
out = Path(sys.argv[1]); part = sys.argv[2]
rng = {'honbun': (0.28, 0.6), 'tsushaku': (0.6, 1.0)}[part]
files = sorted(out.glob('p*.json'), key=lambda p: int(re.sub(r'\D', '', p.stem)))
for f in files:
    d = json.load(open(f)); H = d['imginfo']['img_height']
    rows = []
    for it in d['contents'][0]:
        b = it['boundingBox']; xs = [q[0] for q in b]; ys = [q[1] for q in b]
        if not rng[0] <= min(ys) / H < rng[1]: continue
        t = it['text'].strip()
        if not t: continue
        w = max(xs) - min(xs)
        rows.append((max(xs), min(ys), w, t, it['confidence']))
    if not rows: continue
    wmax = max(r[2] for r in rows)
    rows.sort(key=lambda r: -r[0])
    print(f'# {f.stem}')
    for x, y, w, t, conf in rows:
        small = w < wmax * 0.72
        print(('＊' if small else '') + t + ('' if conf >= 0.5 else '〔?〕'))
