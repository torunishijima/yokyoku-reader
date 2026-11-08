#!/usr/bin/env python3
"""謡曲大観 第一〜五巻の謡曲ページを NDLOCR-Lite で一括 OCR する。
コマ（見開き）を IIIF から取得し、左半分=奇数頁(L)、右半分=偶数頁(R)に分けて OCR。
結果（json/txt/xml）だけを work/ndlocr/<pid>/ に残し、画像は消す。途中で止めても再開できる。
使い方: ndlocr_all.py [pid ...]"""
import json, subprocess, sys, time, urllib.request, shutil
from pathlib import Path
from PIL import Image
ROOT = Path(__file__).resolve().parent.parent
OCR = Path.home() / 'tools/ndlocr-lite'
toc = json.loads((ROOT / 'data/yokyoku/taikan_toc.json').read_text(encoding='utf-8'))
vols = {}
for x in toc:
    v = vols.setdefault(x['pid'], [10**9, 0]); v[0] = min(v[0], x['frame']); v[1] = max(v[1], x['frame_end'])
pids = sys.argv[1:] or list(vols)
BATCH = 20
for pid in pids:
    first, last = vols[pid]
    out = ROOT / 'work/ndlocr' / pid; out.mkdir(parents=True, exist_ok=True)
    frames = [f for f in range(first, last + 1) if not (out / f'f{f:04d}R.json').exists()]
    print(f'{pid}: frames {first}-{last}, todo {len(frames)}', flush=True)
    for i in range(0, len(frames), BATCH):
        tmp = ROOT / 'work/tmp'; shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir(parents=True)
        for f in frames[i:i + BATCH]:
            url = f'https://dl.ndl.go.jp/api/iiif/{pid}/R{f:07d}/full/full/0/default.jpg'
            for attempt in range(3):
                try:
                    data = urllib.request.urlopen(url, timeout=60).read(); break
                except Exception as e:
                    print('retry', f, e, flush=True); time.sleep(5)
            else:
                raise SystemExit(f'download failed: {url}')
            p = tmp / 'spread.jpg'; p.write_bytes(data)
            im = Image.open(p); w, h = im.size
            im.crop((0, 0, w // 2 + w // 50, h)).save(tmp / f'f{f:04d}L.jpg', quality=92)
            im.crop((w // 2 - w // 50, 0, w, h)).save(tmp / f'f{f:04d}R.jpg', quality=92)
            p.unlink(); time.sleep(0.5)
        subprocess.run([str(OCR / '.venv/bin/python'), 'ocr.py', '--sourcedir', str(tmp), '--output', str(out)],
                       cwd=OCR / 'src', check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f'{pid}: done through frame {frames[min(i + BATCH, len(frames)) - 1]}', flush=True)
    shutil.rmtree(ROOT / 'work/tmp', ignore_errors=True)
print('ALL DONE', flush=True)
