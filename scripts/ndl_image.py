#!/usr/bin/env python3
"""国立国会図書館デジタルコレクションから、大観の頁の画像を取ってくる（IIIF）。手元に OCR の作業データがなくても原本を確かめられる。
使い方: ndl_image.py <曲名> <頁> [x,y,w,h] [出力.jpg]
  x,y,w,h は頁（見開きの片側）に対する % で、省くと頁全体。小さい字は 5〜10% 四方ほどに絞ると読める。
  例: ndl_image.py 羽衣 2484 62,60,12,12
曲データ（data/yokyoku/kyoku/<曲>.json）の pid・frame_base から、頁 → コマ・左右を出す（build_kyoku.py と同じ計算）。"""
import json, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
def get(u): return urllib.request.urlopen(u, timeout=60).read()

title, page = sys.argv[1], int(sys.argv[2])
box = [float(v) for v in sys.argv[3].split(',')] if len(sys.argv) > 3 else [0, 0, 100, 100]
out = sys.argv[4] if len(sys.argv) > 4 else f'{title}_p{page}.jpg'
d = json.loads((ROOT / 'data/yokyoku/kyoku' / f'{title}.json').read_text(encoding='utf-8'))
man = json.loads(get(f"https://dl.ndl.go.jp/api/iiif/{d['pid']}/manifest.json"))
cv = man['sequences'][0]['canvases'][d['frame_base'] + page // 2 - 1]
svc = cv['images'][0]['resource']['service']['@id']
x0 = 0 if page % 2 else 48   # 奇数頁は見開きの左、偶数頁は右（継ぎ目を少し重ねる）
x, y, w, h = box
region = f'pct:{x0 + x * 0.52:.2f},{y:.2f},{w * 0.52:.2f},{h:.2f}'
Path(out).write_bytes(get(f'{svc}/{region}/1400,/0/default.jpg'))
print(out, f"コマ {d['frame_base'] + page // 2}", 'L' if page % 2 else 'R')
