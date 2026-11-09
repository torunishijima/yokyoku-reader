#!/usr/bin/env python3
"""一括 OCR の結果（work/ndlocr/<pid>/fNNNN[LR].json）を曲ごとに分け、本文（中段）と通釈（下段）を取り出す。
- ページ→コマ: 巻ごとに一定（コマ = 巻の基準 + 頁//2、奇数頁=左 L、偶数頁=右 R）。目次のコマ番号は使わない（錦戸に誤りあり）。
- 曲の範囲: その曲の開始頁 〜 次の曲の開始頁の前。〔考異〕が出たらそこで打ち切る。
- 行の分類（ページ高さ比）: 高さ 0.45 超の長い行は散文（解説・間狂言など）として除外。
  上端 <0.28 頭注 / 0.28–0.6 本文 / 0.6 以上 通釈。
- 小さい字（型付・ト書き）は行幅で判定して行頭に「＊」、確信度 0.5 未満は末尾に「〔?〕」。
出力: work/split/<曲名>.honbun.txt / .tsushaku.txt（ページごとに「# p<頁> <コマ><L|R>」見出し）
  と、各行の画像上の位置 .honbun.lines.json / .tsushaku.lines.json（見出し行は null。x は行の右端、ページ幅比）
使い方: split_taikan.py [曲名 ...]"""
import json, sys, re
KOI = re.compile(r'^[〔「(（]考\s*異[〕」)）]$')
DAN = re.compile(r'^＊?【[一二三四五六七八九十ⅠI1l|]{1,3}】')
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OCR = ROOT / 'work/ndlocr'; OUT = ROOT / 'work/split'; OUT.mkdir(parents=True, exist_ok=True)
toc = json.loads((ROOT / 'data/yokyoku/taikan_toc.json').read_text(encoding='utf-8'))

base = {}
for x in toc:
    base.setdefault(x['pid'], x['frame'] - x['page'] // 2)

def page_file(pid, p):
    return OCR / pid / f'f{base[pid] + p // 2:04d}{"L" if p % 2 else "R"}.json'

def lines(path):
    d = json.loads(path.read_text(encoding='utf-8'))
    H = d['imginfo']['img_height']; W = d['imginfo']['img_width']
    out = []
    for it in d['contents'][0]:
        t = it['text'].strip()
        if not t or re.fullmatch(r'[-─―ー－‐・.\s]+', t): continue   # 罫線だけの行は無視
        b = it['boundingBox']; xs = [q[0] for q in b]; ys = [q[1] for q in b]
        top = min(ys) / H; h = (max(ys) - min(ys)) / H
        if h > 0.45: band = 'prose'
        elif top < 0.28: band = 'head'
        elif top < 0.6: band = 'honbun'
        else: band = 'tsushaku'
        out.append(dict(band=band, x=max(xs) / W, w=(max(xs) - min(xs)) / W, t=t, c=it['confidence'],
                        box=[min(xs), min(ys), max(xs), max(ys)]))
    return out

def render(rows):
    """[(表示行, 元の行)]"""
    if not rows: return []
    wmax = max(r['w'] for r in rows)
    return [(('＊' if r['w'] < wmax * 0.72 else '') + r['t'] + ('' if r['c'] >= 0.5 else '〔?〕'), r)
            for r in sorted(rows, key=lambda r: -r['x'])]

def pos(pid, f, p, rows):
    return [dict(page=p, pid=pid, img=f.stem, box=r['box'], x=round(r['x'], 4)) for _, r in rows]

def split(i):
    x = toc[i]; pid = x['pid']
    nxt = toc[i + 1] if i + 1 < len(toc) and toc[i + 1]['pid'] == pid else None
    last = nxt['page'] - 1 if nxt else (x['frame_end'] - base[pid]) * 2 + 1
    started = False
    hl, tl = [], []
    hb, ts, stats = [], [], dict(pages=0, text_pages=0, prose_pages=0, missing=[])
    for p in range(x['page'], last + 1):
        f = page_file(pid, p)
        if not f.exists(): stats['missing'].append(p); continue
        ls = lines(f); stats['pages'] += 1
        ko = [l['x'] for l in ls if KOI.match(l['t'].replace(' ', ''))]
        if ko: ls = [l for l in ls if l['x'] > max(ko) + 0.01]
        h = [l for l in ls if l['band'] == 'honbun']; t = [l for l in ls if l['band'] == 'tsushaku']
        if sum(l['band'] == 'prose' for l in ls) >= 3 and len(h) < 5:
            stats['prose_pages'] += 1; continue
        if not h and not t: continue
        stats['text_pages'] += 1
        rh, rt = render(h), render(t)
        if ko and not (rh or rt): break
        if not started:
            # 頭注・本文・通釈の 3 段がそろった最初の頁から始める。段見出しがあればそこから
            nh = sum(l['band'] == 'head' for l in ls)
            if nh < 3 or len(h) < 3: continue
            k = next((j for j, (l, _) in enumerate(rh) if DAN.match(l)), 0)
            started = True; rh = rh[k:]
            # 前の頁の左端に【一】と冒頭のト書きが載っていることがある
            pf = page_file(pid, p - 1)
            if p - 1 >= x['page'] and pf.exists():
                pl = lines(pf)
                dx = [l['x'] for l in pl if DAN.match(l['t']) or re.match(r'^[I1l|]{1,3}$', l['t'])]
                if dx:
                    ph = [l for l in pl if l['x'] <= max(dx) + 0.005 and l['band'] in ('honbun', 'prose')]
                    pt = [l for l in pl if l['x'] <= max(dx) + 0.005 and l['band'] == 'tsushaku']
                    if ph:
                        hb += [f'# p{p - 1} {pf.stem[1:]}'] + [l for l, _ in render(ph)]
                        ts += [f'# p{p - 1} {pf.stem[1:]}'] + [l for l, _ in render(pt)]
                        hl += [None] + pos(pid, pf, p - 1, render(ph))
                        tl += [None] + pos(pid, pf, p - 1, render(pt))
            k = next((j for j, (l, _) in enumerate(rt) if DAN.match(l)), 0); rt = rt[k:]
        tag = f'# p{p} {f.stem[1:]}'
        hb += [tag] + [l for l, _ in rh]; ts += [tag] + [l for l, _ in rt]
        hl += [None] + pos(pid, f, p, rh); tl += [None] + pos(pid, f, p, rt)
        if ko: break
    name = x['title']
    (OUT / f'{name}.honbun.txt').write_text('\n'.join(hb) + '\n', encoding='utf-8')
    (OUT / f'{name}.honbun.lines.json').write_text(json.dumps(hl), encoding='utf-8')
    (OUT / f'{name}.tsushaku.lines.json').write_text(json.dumps(tl), encoding='utf-8')
    (OUT / f'{name}.tsushaku.txt').write_text('\n'.join(ts) + '\n', encoding='utf-8')
    return name, x['page'], last, stats

BEKKAN = '1884352'
TR = str.maketrans('徑橫國經當隱實瀨碎戶龜俱勸濱', '径横国経当隠実瀬砕戸亀倶勧浜')

def title_x(ls, title):
    """頁の中で曲名（大きい字の見出し）の行の x を返す。なければ None"""
    import unicodedata
    want = unicodedata.normalize('NFKC', re.sub(r'（別巻）$', '', title)).translate(TR)
    best = None
    for l in ls:
        if l['band'] not in ('honbun', 'prose'): continue
        t = unicodedata.normalize('NFKC', re.sub(r'\s', '', l['t'])).translate(TR)
        t = re.sub(r'[觀観]?[\(（].*$', '', t)   # 見出しの後ろの流派の印
        if abs(len(t) - len(want)) > 1: continue
        common = sum(1 for c in want if c in t)
        if common >= max(1, len(want) * 0.6) and (best is None or common > best[0]):
            best = (common, l['x'])
    if best: return best[1]
    # 見出しが読めないときは、その下の流派の印（「觀(寶・喜)」など）の位置で代える
    marks = [l['x'] for l in ls if len(l['t']) <= 10 and
             (re.match(r'^[觀観]{1,2}$', l['t'].strip()) or re.search(r'[觀観]?\s*[\(（][寶宝喜春剛金・\s]+[\)）]?$', l['t']))]
    return max(marks) if marks else None

def split_bekkan(i):
    """別巻（闌曲・曲舞集）: 1 頁に 2 曲がまたがるので、曲名の見出しの位置と〔考異〕で区切る"""
    x = toc[i]; pid = x['pid']
    nxt = toc[i + 1] if i + 1 < len(toc) and toc[i + 1]['pid'] == pid else None
    last = nxt['page'] if nxt else (x['frame_end'] - base[pid]) * 2 + 1
    hb, ts, hl, tl, stats = [], [], [], [], dict(pages=0, text_pages=0, prose_pages=0, missing=[])
    for p in range(x['page'], last + 1):
        f = page_file(pid, p)
        if not f.exists(): stats['missing'].append(p); continue
        ls = [l for l in lines(f) if l['band'] in ('honbun', 'tsushaku', 'prose')]; stats['pages'] += 1
        stop = False
        if p == x['page']:
            tx = title_x(ls, x['title'])
            if tx is None: stats['missing'].append(f'見出し{p}')
            else: ls = [l for l in ls if l['x'] < tx - 0.003]
        ko = [l['x'] for l in ls if KOI.match(l['t'].replace(' ', ''))]
        if ko: ls = [l for l in ls if l['x'] > max(ko) + 0.01]; stop = True
        elif nxt and p == nxt['page']:
            nx = title_x(ls, nxt['title'])
            ls = [l for l in ls if nx is not None and l['x'] > nx + 0.003]; stop = True
        h = [l for l in ls if l['band'] == 'honbun']; t = [l for l in ls if l['band'] == 'tsushaku']   # 散文（曲の紹介文）は除く
        if h or t:
            stats['text_pages'] += 1
            rh, rt = render(h), render(t)
            if p == x['page']:   # 曲の紹介文の末尾（「諸本に見ゆ」「…に收む」など）までを捨てる
                ks = [j for j, (l, _) in enumerate(rh[:4]) if re.search(r'諸本|收む|収む|見ゆ|省略|一節|完曲|曲舞以下|題す|作者|傳はらない', l)]
                if ks: rh = rh[max(ks) + 1:]
            tag = f'# p{p} {f.stem[1:]}'
            hb += [tag] + [l for l, _ in rh]; ts += [tag] + [l for l, _ in rt]
            hl += [None] + pos(pid, f, p, rh); tl += [None] + pos(pid, f, p, rt)
        if stop: break
    name = x['title']
    (OUT / f'{name}.honbun.txt').write_text('\n'.join(hb) + '\n', encoding='utf-8')
    (OUT / f'{name}.honbun.lines.json').write_text(json.dumps(hl), encoding='utf-8')
    (OUT / f'{name}.tsushaku.lines.json').write_text(json.dumps(tl), encoding='utf-8')
    (OUT / f'{name}.tsushaku.txt').write_text('\n'.join(ts) + '\n', encoding='utf-8')
    return name, x['page'], last, stats

want = set(sys.argv[1:])
rep = []
for i, x in enumerate(toc):
    if want and x['title'] not in want: continue
    rep.append(split_bekkan(i) if x["pid"] == BEKKAN else split(i))
for name, a, b, s in rep:
    print(f"{name}\tp{a}-{b}\t本文頁{s['text_pages']}\t散文頁{s['prose_pages']}" + (f"\t欠{s['missing']}" if s['missing'] else ''))
