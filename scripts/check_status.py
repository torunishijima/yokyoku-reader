#!/usr/bin/env python3
"""OCR 確認作業の進み具合を出す。work/fixes/<曲>.tsv があれば確認済み（訂正 0 件でも見出し行だけのファイルを置く）。
使い方: check_status.py [次に出す曲数（既定 10）]"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / 'work/fixes'; COL = ROOT / 'work/collate'
FIRST = ['高砂', '松風', '隅田川', '安宅', '船辨慶', '葵上']   # 有名曲を先に
toc = json.loads((ROOT / 'data/yokyoku/taikan_toc.json').read_text(encoding='utf-8'))
titles = [x['title'] for x in toc if (COL / f"{x['title']}.json").exists()]
order = [t for t in FIRST if t in titles] + [t for t in titles if t not in FIRST]
done = [t for t in order if (FIX / f'{t}.tsv').exists()]
todo = [t for t in order if t not in done]
n_fix = sum(len([l for l in (FIX / f'{t}.tsv').read_text(encoding='utf-8').splitlines() if l and not l.startswith('#')]) for t in done)
recheck = [(t, l) for t in done for l in (FIX / f'{t}.tsv').read_text(encoding='utf-8').splitlines() if '要再確認' in l]
check = lambda t: json.loads((COL / f'{t}.json').read_text(encoding='utf-8'))['n_check']
print(f'確認済み {len(done)} / {len(order)} 曲、訂正 {n_fix} 件、残りの要確認 {sum(check(t) for t in todo)} か所')
k = int(sys.argv[1]) if len(sys.argv) > 1 else 10
print('次の曲:', ' '.join(f'{t}({check(t)})' for t in todo[:k]))
if recheck:
    print('要再確認（高解像度で見直す）:')
    for t, l in recheck: print(f'  {t}\t{l}')
