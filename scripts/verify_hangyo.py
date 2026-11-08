#!/usr/bin/env python3
"""半魚文庫の元データ（yo.lzh を展開したもの）と data/yokyoku/hangyo/ の本文が一致するか照合する。

使い方:
  curl -LO http://hangyo.sakura.ne.jp/utahi/yo.lzh && mkdir raw && (cd raw && bsdtar -xf ../yo.lzh)
  python3 scripts/verify_hangyo.py raw data/yokyoku/hangyo

比較は、元データから見出しタグ行（<T> <N> <K> <A> <S> <H> と書式の崩れた変種）と
ページタグ（<P 128b> など）を除き、両方から空白・改行を除いた文字列どうしで行う。
"""
import json, re, sys, collections
from pathlib import Path
RAW = Path(sys.argv[1]); PROC = Path(sys.argv[2])
man = json.loads((PROC/'manifest.json').read_text(encoding='utf-8'))
HEAD = re.compile(r'^<(?:[TNKASk][ >]?|[^<>「」\n]{1,10}>)[^「\n]*$', re.M)
TAG = re.compile(r'<[^<>「」\n]{1,12}>')
tagkinds = collections.Counter()
def orig_body(t):
    for m in re.findall(r'<([A-Z])[ >]', t): tagkinds[m] += 1
    t = HEAD.sub('', t); t = TAG.sub('', t)
    return re.sub(r'\s', '', t)
def proc_body(t):
    return re.sub(r'\s', '', t.split('――――', 1)[1])
groups = collections.defaultdict(list)
for r in man: groups[r['source_file']].append(r)
ok = bad = 0; report = []
for src, rs in sorted(groups.items()):
    o = orig_body((RAW/src).read_bytes().decode('cp932', errors='replace'))
    p = ''.join(proc_body((PROC/r['file']).read_text(encoding='utf-8')) for r in sorted(rs, key=lambda r: r['file']))
    if o == p: ok += 1
    else:
        bad += 1
        i = next((k for k in range(min(len(o), len(p))) if o[k] != p[k]), min(len(o), len(p)))
        report.append(f"{src} ({','.join(r['title'] for r in rs)[:30]}): 元{len(o)}字 / 加工後{len(p)}字, 最初の差 位置{i}: 元『{o[max(0,i-10):i+15]}』 加工後『{p[max(0,i-10):i+15]}』")
print(f"照合: 元ファイル{len(groups)}本（{len(man)}曲） 一致{ok} 不一致{bad}")
print('元データのタグ種別:', dict(tagkinds))
print('\n'.join(report))
