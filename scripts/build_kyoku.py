#!/usr/bin/env python3
"""大観の OCR 結果（work/split）と確認作業の訂正（work/fixes）から、サイト用の曲データを作る。
出力: data/yokyoku/kyoku/<曲名>.json
使い方: build_kyoku.py [曲名 ...]（省略時は確認済みの全曲 = work/fixes/<曲>.tsv がある曲）

処理の順:
1. 訂正を当てる（頁ごとに、OCR の字 → 正しい字）
2. 見開きの継ぎ目で二重に出た行を除く（左右の画像を少し重ねて切っているため）
3. 本文とト書きを、行の上端の位置で分ける（ト書きは一段下げて印刷されている）
4. 段の印【一】【二】…で本文・通釈を段に分ける（崩れた印は番号の並びで補う）
5. 役名の読み誤りを直す（ッキ→ワキ など。直したものは記録に残す）
6. 解説の頁から曲情報（能柄・人物・所・時・梗概）を取り、解説の頁の訂正を当てる
"""
import json, re, sys, difflib, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPLIT = ROOT / 'work/split'; FIX = ROOT / 'work/fixes'; OCR = ROOT / 'work/ndlocr'
OUT = ROOT / 'data/yokyoku/kyoku'; OUT.mkdir(parents=True, exist_ok=True)
toc = json.loads((ROOT / 'data/yokyoku/taikan_toc.json').read_text(encoding='utf-8'))
base = {}
for x in toc:
    base.setdefault(x['pid'], x['frame'] - x['page'] // 2)

KANSUJI = '一二三四五六七八九十'
def dan_no(s):
    """'三' → 3, '十一' → 11。読めなければ None"""
    if s in KANSUJI: return KANSUJI.index(s) + 1
    m = re.fullmatch(r'十([一二三四五六七八九])', s)
    return 10 + KANSUJI.index(m[1]) + 1 if m else None
def kansuji(n):
    return KANSUJI[n - 1] if n <= 10 else '十' + KANSUJI[n - 11]

DAN_LINE = re.compile(r'^＊?【([^】]{0,4})】(〔\?〕)?(.*)$')
AI_MARK = {'間', '問'}   # 【間】（間狂言）。「問」は読み誤り

# ---------- 役名 ----------
ROLES = ['後ジテ', '前ジテ', '後シテ', '前シテ', 'シテツレ', 'ワキヅレ', 'ワキツレ', 'シテ', 'ツレ', 'ワキ', 'トモ', '子方', '子',
         '地', '狂言', 'アイ', '同', '二人', '三人', '立衆', '女', '男',
         '強力', '太刀持', '太刀', 'オモ', 'アド', '千歳', '翁', '三番叟', '三番']
SHODAN = ['次第', '名ノリ', '名宣', '道行', '一聲', '一セイ', '二句', 'サシ', '下歌', '上歌', 'クリ', 'クセ', 'ロンギ', '待謠', '詞',
          '歌', 'ワカ', 'ノリ地', 'キリ', '掛合', '中ノリ', '大ノリ', '問答', '上', '下', 'カカル', '一']
# OCR のよくある読み誤り。ここで直した役名も、役名の照合（role_check.py）で半魚文庫と食い違えば画像で確かめる
ROLE_MISREAD = {'ッキ': 'ワキ', 'ット': 'ワキ', 'ッレ': 'ツレ', 'シァ': 'シテ', 'ジテ': 'シテ', 'び': 'シテ', '邦': '地',
                'ヮキ': 'ワキ', 'ンテ': 'シテ', 'シア': 'シテ', 'ワキヅル': 'ワキヅレ', 'ッキヅレ': 'ワキヅレ',
                'サン': 'サシ', '土歌': '上歌', 'ウキ': 'ワキ', '〃七': 'クセ', '〃セ': 'クセ', 'ク七': 'クセ', '"七': 'クセ', 'クヤ': 'クセ'}
ROLE_RE = '|'.join(sorted(set(ROLES) | {k for k, v in ROLE_MISREAD.items() if v in ROLES}, key=len, reverse=True))
SHODAN_RE = '|'.join(sorted(set(SHODAN) | {k for k, v in ROLE_MISREAD.items() if v in SHODAN}, key=len, reverse=True))
LABEL = re.compile(rf'^((?:(?:{ROLE_RE})(?:・?(?:{ROLE_RE}))*)?)((?:{SHODAN_RE})?)(\([^)）]*[)）])?([「『』])')
SHODAN_MID = '|'.join(s for s in SHODAN_RE.split('|') if s not in ('一', '上', '下', '詞', '歌'))
MID = re.compile(rf'(?<=[。、\s])((?:(?:{ROLE_RE})(?:・?(?:{ROLE_RE}))*)?)((?:{SHODAN_MID})?)(\([^)）]*[)）])?([「『])')
ROLE_SPLIT = re.compile(rf'{ROLE_RE}')

def fix_label(s, log, page):
    out = ROLE_MISREAD.get(s, s)
    if out != s: log.append(dict(page=page, kind='役名', ocr=s, fixed=out))
    return out

# ---------- 読み込み ----------
def read_split(title, part):
    pages, cur = [], None
    for ln in (SPLIT / f'{title}.{part}.txt').read_text(encoding='utf-8').splitlines():
        m = re.match(r'^# p(\d+) (\d{4}[LR])$', ln)
        if m: cur = dict(page=int(m[1]), img=m[2], lines=[]); pages.append(cur); continue
        if cur is not None: cur['lines'].append(dict(t=ln))
    it = iter(json.loads((SPLIT / f'{title}.{part}.lines.json').read_text(encoding='utf-8')))
    for p in pages:
        assert next(it) is None
        for l in p['lines']:
            m = next(it); l['box'] = m['box']; l['x'] = m['x']; l['img'] = m['img']
    return pages

def read_fixes(title):
    f = FIX / f'{title}.tsv'
    if not f.exists(): return None
    out = []
    for ln in f.read_text(encoding='utf-8').splitlines():
        if not ln or ln.startswith('#'): continue
        c = ln.split('\t') + ['', '', '', '']
        out.append(dict(page=int(c[0].lstrip('p')), ocr=c[1], fixed=c[2], note=c[3]))
    return out

def apply_fixes(pages, fixes, log):
    for fx in fixes:
        if not fx['ocr']: continue
        hit = False
        for p in pages:
            if p['page'] != fx['page']: continue
            for l in p['lines']:
                if fx['ocr'] in l['t']:
                    l['t'] = l['t'].replace(fx['ocr'], fx['fixed'], 1); l['fixed'] = True; hit = True
                    if fx['note'].startswith('ト書き'): l['force'] = 'note'
                    break
            if not hit:   # 行をまたぐ訂正: 隣り合う 2 行をつないで探し、直した字は前の行に寄せる
                ls = p['lines']
                for i in range(len(ls) - 1):
                    a, b = ls[i]['t'].replace('〔?〕', ''), ls[i + 1]['t'].replace('〔?〕', '')
                    j = (a + b).find(fx['ocr'])
                    if 0 <= j < len(a) < j + len(fx['ocr']):
                        k = j + len(fx['ocr']) - len(a)
                        ls[i]['t'] = a[:j] + fx['fixed']; ls[i + 1]['t'] = b[k:]; hit = True; break
            if hit: break
        if hit:
            log.append(dict(page=fx['page'], kind='訂正', ocr=fx['ocr'], fixed=fx['fixed']))
            fx['applied'] = True

def clean(t):
    t = t.replace('〔?〕', '').lstrip('＊')
    return re.sub(r'(?<=[^\x00-\x7f])\s+(?=[^\x00-\x7f])', '', t).strip()

def similar(a, b):
    a, b = clean(a), clean(b)
    if len(a) < 2 or len(b) < 2: return a == b
    if min(len(a), len(b)) / max(len(a), len(b)) < 0.6: return False
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.7

def dedupe(pages, log):
    """見開きの継ぎ目（右頁の終わりと左頁の始め）で二重に出た行と、続けて同じ行が出たものを除く"""
    for i, p in enumerate(pages):
        if i and p['img'].endswith('L') and pages[i - 1]['img'] == p['img'][:4] + 'R':
            tail = [clean(l['t']) for l in pages[i - 1]['lines'][-5:]]
            # 先頭 5 行のうち、右頁の終わりと同じ行があれば、そこまで（読み崩れた行も含めて）除く
            js = [j for j, l in enumerate(p['lines'][:5]) if any(similar(l['t'], t) for t in tail)]
            for l in p['lines'][:js[-1] + 1] if js else []:
                log.append(dict(page=p['page'], kind='重複', ocr=l['t']))
            if js: del p['lines'][:js[-1] + 1]
        keep = []
        for l in p['lines']:
            if keep and clean(keep[-1]['t']) and similar(keep[-1]['t'], l['t']) and len(clean(l['t'])) >= 6:
                # 続けて同じ行: 訂正済みのほう（＊なし・〔?〕なしのほう）を残す
                log.append(dict(page=p['page'], kind='重複', ocr=l['t'])); continue
            keep.append(l)
        p['lines'] = keep

def classify(pages):
    """本文行: kind=text、ト書き: kind=note、小さい役名: kind=role、ゴミ: kind=junk"""
    # 本文の行頭の高さ: 役名付きの詞の行（「シテ「」など）の上端。頁に役名付きの行がなければ曲全体の中央値
    def labeled(l):
        m = LABEL.match(clean(l['t'])); return bool(m and m[1] and not m[2]) and not l.get('fixed')   # 小段名付きの行は一段下がる
    allt = sorted(l['box'][1] for p in pages for l in p['lines'] if labeled(l))
    song_body = allt[len(allt) // 2] if allt else 0
    prev_kind = None
    for p in pages:
        ls = p['lines']
        tops = sorted(l['box'][1] for l in ls if labeled(l))
        body = tops[len(tops) // 2] if tops else song_body
        for l in ls:
            t = clean(l['t']); x0, y0, x1, y1 = l['box']
            if not t or re.fullmatch(r'[\d\s\-ー―・.I|l]+', t) or sum(c in '- ー―' for c in l['t']) > len(l['t']) / 2:
                l['kind'] = 'junk'
            elif l.get('force'):
                l['kind'] = l['force']
            elif DAN_LINE.match(l['t']):
                l['kind'] = 'dan'
            elif y1 - y0 < 160 and y0 < body + 60 and re.fullmatch(rf'(?:{ROLE_RE}|ワキヅ|シテツ)(?:・(?:{ROLE_RE}|ワキヅ))*・?', t):
                l['kind'] = 'role'
            elif y0 > body + 80 and not ((m := LABEL.match(t)) and m[2]):
                l['kind'] = 'note'
            else:
                l['kind'] = 'text'
                # 段の印の直後に役名なしで始まる行は、冒頭のト書き（一行目だけ本文の高さから組まれる）
                if prev_kind == 'dan' and not ((m := LABEL.match(t)) and (m[1] or m[2])): l['kind'] = 'note'
            if l['kind'] != 'junk': prev_kind = l['kind']
            l['t'] = t

# ---------- 段に分ける ----------
# 段の印は頭注・本文・通釈の 3 段に、ほぼ同じ横位置で印刷されている。
# 同じ頁・同じ位置の印をまとめ、読めた番号の多数決で段を決める（片方の段で印が抜けたり読み誤ったりしても補える）。
MARK_READ = {'I': 1, '1': 1, 'l': 1, '|': 1, 'IO': 10, '10': 10, '因': 4, '回': 4, '凹': 4, '西': 4, '穴': 6, '川': 3}

def raw_lines(pid, page):
    f = OCR / pid / f'f{base[pid] + page // 2:04d}{"L" if page % 2 else "R"}.json'
    if not f.exists(): return []
    d = json.loads(f.read_text(encoding='utf-8'))
    H = d['imginfo']['img_height']; W = d['imginfo']['img_width']
    out = []
    for it in d['contents'][0]:
        b = it['boundingBox']; xs = [q[0] for q in b]; ys = [q[1] for q in b]
        top = min(ys) / H; h = (max(ys) - min(ys)) / H
        band = 'prose' if h > 0.45 else 'head' if top < 0.28 else 'honbun' if top < 0.6 else 'tsushaku'
        out.append(dict(band=band, x=max(xs) / W, top=top, h=h, t=it['text'].strip(), c=it.get('confidence', 1)))
    return out

def mark_value(s):
    if s in AI_MARK: return 'ai'
    return dan_no(s) or MARK_READ.get(s)

def find_bounds(pid, pages, log, extra=()):
    """[{at:{band: (page, x)}, page, no, ai}]（頁順・右から左の順）。extra は訂正記録で補った印"""
    marks = [dict(m, v=mark_value(m['inner'])) for m in extra]
    for page in pages:
        for l in raw_lines(pid, page):
            m = re.match(r'^＊?【([^】]{0,3})】', l['t'])
            if m and m[1] not in ('能柄', '人物', '所', '時', '作者', '異稱', '梗槪', '梗概', '出典', '槪評', '概評', '物着', '序') \
                    and not re.match(r'^[^「『。、\s]{1,6}[「『]', l['t'][m.end():]):   # 〔考異〕の「【四】ワキ「…」は段の印ではない
                marks.append(dict(l, page=page, inner=m[1], v=mark_value(m[1])))
    order = lambda m: (m['page'], -m['x'])
    cs = []
    for m in sorted((m for m in marks if m['band'] in ('honbun', 'tsushaku')), key=order):
        c = cs[-1] if cs else None
        if c and m['band'] in c['at'] and c['at'][m['band']] [0] == m['page'] and abs(c['at'][m['band']][1] - m['x']) < 0.01:
            continue   # 同じ印を二重に読んだもの
        if c and m['band'] in c['at'] and c['at'][m['band']][0] + 1 == m['page'] and m['page'] % 2 and \
                c['at'][m['band']][1] < 0.06 and m['x'] > 0.9 and (m['v'] is None or m['v'] in c['vals'] or None in c['vals']):
            c['at'][m['band']] = (m['page'], m['x']); continue   # 見開きの継ぎ目の印を、重ねて切った左右の頁の両方から読んだもの（蟻通【五】）
        if c and m['band'] not in c['at']:
            pg, x = next(iter(c['at'].values()))
            same_v = m['v'] is None or any(v is None or v == m['v'] for v in c['vals'])
            near = (pg == m['page'] and abs(x - m['x']) < 0.08) or \
                   (m['page'] == pg + 1 and x < 0.3 and m['x'] > 0.7)   # 頁の境目をまたいだ
            same_num = isinstance(m['v'], int) and m['v'] in c['vals']
            if near and same_v or pg == m['page'] and (abs(x - m['x']) < 0.04 or same_num):   # 同じ頁で同じ番号なら位置が離れていても一つ
                c['at'][m['band']] = (m['page'], m['x']); c['votes'].append(m['inner']); c['vals'].append(m['v']); continue
        cs.append(dict(at={m['band']: (m['page'], m['x'])}, votes=[m['inner']], vals=[m['v']]))
    for c in cs:   # 頭注の印は、位置が本文・通釈とそろうときだけ数に入れる
        for m in marks:
            if m['band'] == 'head' and any(pg == m['page'] and abs(x - m['x']) < 0.02 for pg, x in c['at'].values()):
                c['votes'].append(m['inner']); c['vals'].append(m['v'])
    # 本文・通釈のどちらにもない印は、頭注の印で補う（前後の番号の間に入るときだけ）
    def num(c):
        ns = [v for v in c['vals'] if isinstance(v, int)]
        return max(set(ns), key=ns.count) if ns else None
    for m in marks:
        if m['band'] != 'head' or not isinstance(m['v'], int): continue
        if any(pg == m['page'] and abs(x - m['x']) < 0.02 for c in cs for pg, x in c['at'].values()): continue
        prev = [c for c in cs if min(c['at'].values()) < (m['page'], -1) or min(c['at'].values())[0] == m['page'] and min(c['at'].values())[1] > m['x']]
        nxt = [c for c in cs if c not in prev]
        if prev and nxt and num(prev[-1]) == m['v'] - 1 and num(nxt[0]) == m['v'] + 1:
            c = dict(at={'honbun': (m['page'], m['x']), 'tsushaku': (m['page'], m['x'])}, votes=[m['inner']], vals=[m['v']], head_only=True)
            cs.insert(cs.index(nxt[0]), c)
            log.append(dict(page=m['page'], kind='段の印', ocr=f"頭注のみ【{m['inner']}】", fixed=f"【{kansuji(m['v'])}】"))
    bounds, n = [], 0
    for i, c in enumerate(cs):
        page = min(pg for pg, _ in c['at'].values())
        vals = c['vals']
        if 'ai' in vals and not any(isinstance(v, int) for v in vals):
            bounds.append(dict(at=c['at'], page=page, no=None, ai=True)); continue
        nums = [v for v in vals if isinstance(v, int)]
        if n + 1 in nums: k = n + 1
        elif nums and len(set(nums)) == 1 and nums[0] > n + 1 and len(nums) >= 2 and \
                not (i + 1 < len(cs) and num(cs[i + 1]) == nums[0]): k = nums[0]   # どの段でも印が抜けた（次の印が同じ番号なら読み誤り）
        else: k = n + 1
        if any(v != k for v in nums) or not nums:
            log.append(dict(page=page, kind='段の印', ocr='・'.join(f'【{v}】' for v in c['votes']), fixed=f'【{kansuji(k)}】'))
        n = k
        bounds.append(dict(at=c['at'], page=page, no=k, ai=False))
    return bounds

def split_dan(pages, bounds, band, log):
    """行を段に振り分ける: [{no, label, page, ai, lines:[(page, line)]}]。最初の印より前の行は捨てる（記録する）"""
    dans = [dict(no=b['no'], label='間' if b['ai'] else kansuji(b['no']), page=b['page'], ai=b['ai'], lines=[]) for b in bounds]
    def bpos(b):
        return b['at'].get(band) or b['at'].get('honbun') or b['at'].get('tsushaku')
    dropped = []
    for p in pages:
        for l in p['lines']:
            if l.get('kind') == 'junk': continue
            i = sum(1 for b in bounds if bpos(b)[0] < p['page'] or (bpos(b)[0] == p['page'] and l['x'] <= bpos(b)[1] + 0.004)) - 1
            m = DAN_LINE.match(l['t']) if l.get('kind') in (None, 'dan', 'note', 'text') else None
            if m:
                rest = clean(m[3] or '')
                if not rest: continue
                lm = LABEL.match(rest)
                l = dict(l, t=rest, kind=('text' if lm and (lm[1] or lm[2]) else 'note') if band == 'honbun' else None)
            if i < 0: dropped.append((p['page'], l['t'])); continue
            dans[i]['lines'].append((p['page'], l))
    for pg, t in dropped:
        log.append(dict(page=pg, kind=f'段の前（{band}）', ocr=t))
    return dans

# ---------- 本文 ----------
def roles_of(s, log, page):
    """'ワキワキヅレ' / 'シテ・ツレ' → 'ワキ・ワキヅレ'（読み誤りも直す）"""
    if not s: return ''
    return '・'.join(fix_label(r, log, page) for r in ROLE_SPLIT.findall(s))

def parse_honbun(lines, log, state, in_ai=False):
    """行を [{type:'u', role, shodan, paren, q, text} | {type:'note'|'heading'|'ai', ...}] にする。
    役名のない行は直前の謡の続き。小字の役名（kind=role）は、すぐ前かすぐ後の小段名に付ける。"""
    items = []
    pending = ''      # 次の小段に付ける小字の役名
    ai_from = None    # 中入の後（間狂言）
    for page, l in lines:
        k, t = l['kind'], l['t']
        if ai_from is not None:
            continue
        if k == 'heading': items.append(dict(type='heading', text=t)); continue
        if k == 'role':
            r = roles_of(t.replace('ワキヅ', 'ワキヅレ').replace('ワキヅレレ', 'ワキヅレ'), log, page)
            last = items[-1] if items else None
            if last and last['type'] == 'u' and last['shodan'] and not last['role'] and not last.get('_cont'):
                last['role'] = r
            elif last and last['type'] == 'u' and last['shodan'] and last['role']:
                pass   # 訂正記録ですでに役名が付いている
            else:
                pending = r
            continue
        if k == 'note':
            if items and items[-1]['type'] == 'note': items[-1]['text'] += t
            else: items.append(dict(type='note', text=t))
            if '中入' in t and not in_ai: ai_from = (page, l.get('x', 0))
            continue
        # 本文行
        src = [l.get('img'), *l.get('box', [])]
        m = LABEL.match(t)
        if m and (m[1] or m[2]):
            role = roles_of(m[1], log, page) or pending
            items.append(dict(type='u', role=role, shodan=fix_label(m[2], log, page) if m[2] else '', paren=m[3] or '', q=m[4], text='', page=page, src=src))
            body = t[m.end():]
        else:
            if not items or items[-1]['type'] != 'u':
                items.append(dict(type='u', role='', shodan='', paren='', q='', text='', page=page, src=src, _cont=True))
            body = t
        pending = ''
        parts = MID.split(body)   # [text, role, shodan, paren, quote, text, ...]
        items[-1]['text'] += parts[0]
        for i in range(1, len(parts), 5):
            r, sd, paren, q, txt = parts[i:i + 5]
            if not r and not sd:
                items[-1]['text'] += (paren or '') + q + txt; continue
            items.append(dict(type='u', role=roles_of(r, log, page), shodan=fix_label(sd, log, page) if sd else '',
                              paren=paren or '', q=q, text=txt, page=page, src=src))
    prev = state.get('role', '')
    for it in items:
        if it['type'] != 'u': continue
        if it['role']: prev = it['role']
        elif prev: it['role_cont'] = prev   # 役名の印刷がない＝前の役の続き
    state['role'] = prev
    if ai_from is not None:
        last_page = max(p for p, _ in lines)
        items.append(dict(type='ai', pages=[ai_from[0], last_page], start=list(ai_from)))
    for it in items: it.pop('_cont', None)
    return items

# ---------- 間狂言 ----------
# 間狂言は本文・通釈の段をまたぐ長い行で組まれていて、曲ごとの切り出し（split_taikan.py）では散文として除かれている。
# 中入（または【間】の印）から次の段の印までの範囲を、元の OCR からまとめて取り出す。半魚文庫に対応がないので照合はしていない。
def extract_ai(pid, start, end, last_page, log):
    """start/end: (頁, x)。end が None なら曲の終わりまで。発言の並びを返す"""
    pages = []
    for pg in range(start[0], (end[0] if end else last_page) + 1):
        ls, allt = [], []
        for l in raw_lines(pid, pg):
            if l['band'] == 'head' or (l['band'] == 'tsushaku' and l['h'] < 0.45): continue
            allt.append((l['x'], clean(l['t'])))
            if pg == start[0] and l['x'] >= start[1] - 0.003: continue
            if end and pg == end[0] and l['x'] <= end[1] + 0.003: continue
            t = clean(l['t'])
            if not t or re.fullmatch(r'[\d\s\-ー―・.I|l]+', t) or sum(c in '- ー―' for c in l['t']) > len(l['t']) / 2: continue
            if l['c'] < 0.3: log.append(dict(page=pg, kind='間狂言の読み崩れ（除外）', ocr=t)); continue
            ls.append(dict(l, t=t))
        ls.sort(key=lambda l: -l['x'])
        allt.sort(key=lambda a: -a[0])
        pages.append(dict(page=pg, img=f"{base[pid] + pg // 2:04d}{'L' if pg % 2 else 'R'}", lines=ls, allt=[t for _, t in allt]))
    if pages and pages[0]['img'].endswith('L'):   # 最初の頁が左頁なら、その右頁の終わりとも照合する
        prev = sorted(((l['x'], clean(l['t'])) for l in raw_lines(pid, start[0] - 1) if l['band'] != 'head'), key=lambda a: -a[0])
        pages.insert(0, dict(page=start[0] - 1, img=pages[0]['img'][:4] + 'R', lines=[], allt=[t for _, t in prev], dummy=True))
    for i, p in enumerate(pages):   # 見開きの継ぎ目で二重に出た行
        if i and p['img'].endswith('L') and pages[i - 1]['img'] == p['img'][:4] + 'R':
            tail = pages[i - 1]['allt'][-5:]   # 範囲で絞る前の、右頁の終わりの行
            # 長い行は一部が重なるだけで似て見えるので、ほぼ同じ行だけを重複とする
            same = lambda a, b: difflib.SequenceMatcher(None, a, b).ratio() >= 0.85 and min(len(a), len(b)) / max(len(a), len(b)) > 0.8
            js = [j for j, l in enumerate(p['lines'][:5]) if any(same(l['t'], t) for t in tail)]
            if js: del p['lines'][:js[-1] + 1]
    pages = [p for p in pages if not p.get('dummy')]
    lines = []
    for p in pages:
        tops = sorted(l['top'] for l in p['lines'])
        body = tops[len(tops) // 4] if tops else 0
        for l in p['lines']:
            t = l['t']
            m = DAN_LINE.match(t)
            if m:
                t = clean(m[3] or '')
                if not t: continue
            lm = LABEL.match(t)
            kind = 'note' if l['top'] > body + 0.02 and not (lm and (lm[1] or lm[2])) else 'text'
            lines.append((p['page'], dict(t=t, kind=kind, x=l['x'])))
    return parse_honbun(lines, log, {}, in_ai=True) if lines else []

# ---------- 通釈 ----------
SCENE = re.compile(r'(?:前段|後段|第[一二三四五]段)')
def is_scene(t): return bool(SCENE.fullmatch(t))   # 通釈の場面の見出し（夢幻能は前段・後段、劇能は第一段・第二段…）

def parse_tsushaku(lines):
    items, buf, depth = [], None, 0
    def flush():
        nonlocal buf
        if buf:
            t = buf['text']
            m = re.match(r'^([^「『(（\s。、]{1,10})(\([^)）]{1,12}[)）])?[「『](.*)$', t, re.S)
            if is_scene(t): items.append(dict(type='heading', text=t))
            elif re.fullmatch(r'[一二三四五六七八九〇十\d\s\-ー―・.*＊、,]+', t): pass   # 頁番号などのゴミ
            elif m and (re.fullmatch(r'[ぁ-ゖ]+', m[1]) or re.search(r'[-ー―]', m[1])):   # 「と「笠づくし」の…」「英雄--『…」は話し手ではない
                items.append(dict(type='note' if buf['nsmall'] * 2 > buf['n'] else 'narration', text=t))
            elif m:   # 「名前「…」」の形は字の大きさに関係なく台詞
                body = (m[2] or '') + m[3]
                items.append(dict(type='speech', speaker=unicodedata.normalize('NFC', m[1]), text=body[:-1] if body.endswith('」') and body.count('「') < body.count('」') else body))
            elif re.match(r'^[(（].*[)）]$', t, re.S): items.append(dict(type='gloss', text=t))
            else: items.append(dict(type='note' if buf['nsmall'] * 2 > buf['n'] else 'narration', text=t))
        buf = None
    for page, l in lines:
        t = l['t']
        if l.get('kind') in ('junk',): continue
        if l.get('kind') == 'heading': flush(); items.append(dict(type='heading', text=t)); continue
        starts = bool(re.match(r'^[^「『(（\s。、]{1,10}(\([^)）]{1,12}[)）])?「', t)) or t[:1] in '(（' or is_scene(t)
        small = l.get('small', False)
        if buf and len(t) <= 5 and not re.search(r'[。」)）]$', buf['text']): small = buf['small']   # 段落末の短い行（「つた。」）は字の大きさを測れないので前の行に合わせる
        if depth and buf and re.match(r'^[^「『(（\s。、,，-]{1,6}「', t) and re.match(r'^[^「『(（\s。、]{1,10}「', buf['text']): depth = 0   # 閉じ括弧の読み落とし: 行頭に次の話し手が来たら台詞を区切る（敦盛の蓮生→草刈）
        if depth and buf and small and not buf['small'] and re.match(r'^[^「『(（\s。、]{1,10}[「『]', buf['text']) and len(t) >= 8 and not re.search(r'[」』()（）…]', t) \
                and buf['text'].count('(') + buf['text'].count('（') <= buf['text'].count(')') + buf['text'].count('）'): depth = 0   # 台詞の閉じ括弧の読み落とし: 小字の行（説明）に変わったら台詞を区切る
        if buf is None or (depth == 0 and (starts or re.search(r'[。」)）]$', buf['text']) or small != buf['small'])) or is_scene(t):
            flush(); buf = dict(text=t, page=page, small=small, n=0, nsmall=0)
        else:
            buf['text'] += t
        buf['n'] += 1; buf['nsmall'] += small
        depth = max(0, depth + t.count('「') + t.count('(') + t.count('（') - t.count('」') - t.count(')') - t.count('）'))
        if is_scene(buf['text']): flush()
    flush()
    out = []
    for it in items:
        if it['type'] in ('speech', 'narration'):
            src = (it['speaker'] + '「' if it['type'] == 'speech' else '') + it['text']
            pieces = re.split(r'(?<=[」…])(?=[^「」『』(（\s。、]{1,8}「)', src)
            if len(pieces) > 1:
                for pc in pieces:
                    m = re.match(r'^([^「『(（\s。、]{1,10})「(.*?)」?$', pc, re.S)
                    out.append(dict(type='speech', speaker=m[1], text=m[2]) if m else dict(type='narration', text=pc))
                continue
        out.append(it)
    return out

# ---------- 解説 ----------
INFO_KEYS = ['能柄', '人物', '所', '時', '作者', '梗槪', '梗概']
def read_info(x):
    pid = x['pid']; txt = ''
    for p in (x['page'], x['page'] + 1, x['page'] + 2):
        if p == x['page'] + 2 and ('梗' in txt or '別巻' in x['volume']): break   # 解説が 3 頁にわたる曲（翁）だけ 3 頁目も読む
        f = OCR / pid / f'f{base[pid] + p // 2:04d}{"L" if p % 2 else "R"}.txt'
        if f.exists(): txt += f.read_text(encoding='utf-8') + '\n'
    info = {}
    m = re.search(r'^.*?([觀観寶宝春剛金喜]{1,2}[(（][^)）\n]*[)）]?)', txt, re.M)
    if m: info['流派'] = m[1]
    # 読み誤った印をそろえる（「時〕」→【時】、「者】」「[者】」→【作者】）
    txt = re.sub(r'[【\[〔]?時[〕\]】]', '【時】', txt)
    txt = re.sub(r'(?:【作|[\[〔(]|作)?者】', '【作者】', txt)
    txt = re.sub(r'[『【\[〔(]梗[槪概][〕】\])]', '【梗概】', txt)
    # 梗概の 1 行目が見出しより前に読まれることがある（船辨慶・大蛇）。文の途中で切れた行が見出しの直前にあれば梗概の頭へ戻す
    txt = re.sub(r'\n([^\n【】]*[^\n【】。」）)\s])\n(【梗[槪概]】)\n', r'\n\2\n\1', txt)
    parts = re.split(r'【([^】]{0,4})】', txt)
    keys = parts[1::2]
    for i, (k, v) in enumerate(zip(keys, parts[2::2])):
        k = '梗概' if k in ('梗槪', '梗概') else k
        # 見出しを読み誤ったとき（蘆刈の【裸紙】）: 知らない 2 字の見出しで、次が【出典】なら梗概
        if k not in INFO_KEYS + ['出典', '槪評', '概評', '異稱'] and len(k) == 2 and i + 1 < len(keys) and keys[i + 1] == '出典' and '梗概' not in info: k = '梗概'
        if k == '梗概': v = re.sub(r'^\s*(?:梗[槪概])?[】○]', '', v)   # 見出しを二重に読んだ残り（飛鳥川）
        if k in ('能柄', '人物', '所', '時', '梗概') and k not in info:
            v = v.strip()
            info[k] = '\n'.join(re.sub(r'\s+', '', x) for x in v.split('\n')) if k == '人物' else re.sub(r'\s+', '', v)
            if k in ('所', '時'): info[k] = re.split(r'[〔【\[][^〕】\]]{1,3}[〕】\]]', info[k])[0]   # 読み崩れた次の項目の印で切る
    if '能柄' not in info:   # 【能柄】の印を読み落としたとき: 「解説」の次の行
        m = re.search(r'解説\s*\n\s*((?:脇能|初番目|二番目|三番目|四番目|五番目|別曲)\S*)', txt)
        if m: info['能柄'] = m[1]
    return info

SUMMARY_MARK = '（梗概）'   # 訂正記録のこの行が「梗概を原本の画像と全文照合済み」の印（docs/ocr_check.md）
def apply_info_fixes(x, info, fixes, log):
    """解説の頁（曲の最初の 3 頁）の訂正を曲情報に当てる。本文・通釈に当たらなかったものだけ"""
    for fx in fixes:
        if fx.get('applied') or not fx['ocr'] or fx['ocr'].startswith('（') or not (x['page'] <= fx['page'] <= x['page'] + 2): continue
        for k in ('梗概', '人物', '能柄', '所', '時', '流派'):
            if fx['ocr'] in info.get(k, ''):
                info[k] = info[k].replace(fx['ocr'], fx['fixed'], 1); fx['applied'] = True
                log.append(dict(page=fx['page'], kind='曲情報', ocr=fx['ocr'], fixed=fx['fixed']))
                break

def apply_item_patches(title, dan, log, warn):
    """work/fixes/<曲>.items.json の差し替えを、組み立てた段に当てる。
    OCR が行ごと読み落とした・崩れた所など、字の訂正（tsv）では直せないものに使う。
    [{"page": 頁, "dan": 段の番号, "band": "honbun"|"tsushaku", "find": その発言にある文字列（1 か所だけ）,
      "set": {置き換える欄}, "after": [後ろに足す発言], "note": 理由}]"""
    f = FIX / f'{title}.items.json'
    if not f.exists(): return
    for p in json.loads(f.read_text(encoding='utf-8')):
        d = next((x for x in dan if x['no'] == p['dan']), None)
        items = d[p['band']] if d else []
        hits = [i for i, it in enumerate(items) if p['find'] in it.get('text', '')]
        if len(hits) != 1:
            warn.append(f"差し替えを当てられなかった: 【{p['dan']}】{p['band']} {p['find']}（{len(hits)} か所）"); continue
        i = hits[0]
        items[i].update(p.get('set', {}))
        items[i + 1:i + 1] = [dict(x) for x in p.get('after', [])]
        log.append(dict(page=p['page'], kind='差し替え', ocr=p['find'], fixed=p.get('note', '')))

# ---------- 組み立て ----------
def build(title):
    x = next(r for r in toc if r['title'] == title)
    fixes = read_fixes(title)
    log = []
    hb = read_split(title, 'honbun'); ts = read_split(title, 'tsushaku')
    if fixes: apply_fixes(hb, fixes, log); apply_fixes(ts, fixes, log)
    dedupe(hb, log); dedupe(ts, log)
    classify(hb)
    # 普通の字の行幅（曲全体の上側 1/4 の位置。小さい字ばかりの頁もあるので頁ごとには取らない）
    ws_all = sorted(l['box'][2] - l['box'][0] for p in ts for l in p['lines'] if len(clean(l['t'])) >= 12)
    wmed = ws_all[len(ws_all) * 3 // 4] if ws_all else 0
    # 1 字あたりの縦の長さ（行の高さ÷字数）。普通の字は 41〜44px、小さい字は 32〜33px ほどで、行幅よりはっきり分かれる
    def pitch(l):
        n = len(re.sub(r'\s', '', clean(l['t']))); return (l['box'][3] - l['box'][1]) / n if n >= 5 else None
    ps_all = sorted(pv for p in ts for l in p["lines"] if len(clean(l["t"])) >= 12 and (pv := pitch(l)))
    pnorm = ps_all[len(ps_all) * 3 // 4] if ps_all else 0
    for p in ts:
        # 通釈の地の文のうち、所作・場面の説明は小さい字で印刷されている
        tops = sorted(l['box'][1] for l in p['lines'])
        med = tops[len(tops) // 4] if tops else 0   # 小さい字の行が多い頁もあるので下側 1/4 の位置
        for l in p['lines']:
            l['t'] = clean(l['t'])
            w = l['box'][2] - l['box'][0]
            # 字の大きさは 1 字あたりの長さで見る。5 字未満の行だけ行幅で見る（普通の地の文も段落の頭を一字下げるので、字下げは補助）
            pt = pitch(l)
            l['small'] = pt < pnorm * 0.85 if pt else (w < wmed * 0.8 or (w < wmed * 0.9 and l['box'][1] > med + 35))
            if not l['t'] or re.fullmatch(r'[\d\s\-ー―・.]+', l['t']): l['kind'] = 'junk'
    extra = [dict(band=band, page=p['page'], x=l['x'], inner=m[1])
             for band, pages in (('honbun', hb), ('tsushaku', ts)) for p in pages for l in p['lines']
             if l.get('fixed') and (m := re.match(r'^＊?【([^】]{1,3})】', l['t']))]
    bounds = find_bounds(x['pid'], [p['page'] for p in hb], log, extra)
    hd = split_dan(hb, bounds, 'honbun', log); td = split_dan(ts, bounds, 'tsushaku', log)
    warn = []
    nos = [b['no'] for b in bounds if not b['ai']]
    if nos != list(range(1, len(nos) + 1)): warn.append(f'段の番号が飛んでいる: {nos}')
    state = {}
    dan = []
    hpos = lambda b: tuple(b['at'].get('honbun') or b['at'].get('tsushaku'))
    last_page = max(p['page'] for p in hb)
    for i, (d, t) in enumerate(zip(hd, td)):
        if not d['lines'] and not t['lines'] and not d['ai']: continue
        nxt = hpos(bounds[i + 1]) if i + 1 < len(bounds) else None
        if d['ai']:
            start = hpos(bounds[i])
            if dan and dan[-1]['honbun'] and dan[-1]['honbun'][-1]['type'] == 'ai':
                start = tuple(dan[-1]['honbun'].pop()['start'])   # 中入の後と【間】の両方で間狂言になったときは一つに
                d['page'] = start[0]
            hon = [dict(type='ai', start=list(start))]
        else:
            hon = parse_honbun(d['lines'], log, state)
        if hon and hon[-1]['type'] == 'ai' and not (i + 1 < len(bounds) and bounds[i + 1]['ai']):   # 次が【間】の段ならそちらでまとめる
            ai = hon[-1]
            ai['items'] = extract_ai(x['pid'], tuple(ai['start']), nxt, last_page, log)
            ai['pages'] = [ai['start'][0], nxt[0] if nxt else last_page]
            if not ai['items']:
                # 中入の後に散文（間狂言の組み方）が一行もなければ、間狂言のない中入（藍染川の入水など）
                if any(l['band'] == 'prose' for pg in range(ai['pages'][0], ai['pages'][1] + 1) for l in raw_lines(x['pid'], pg)):
                    warn.append(f"【{d['label']}】の間狂言を取り出せなかった")
                else:
                    hon.pop(); log.append(dict(page=ai['start'][0], kind='間狂言', ocr='中入の後に散文なし', fixed='間狂言の欄を出さない'))
        dan.append(dict(no=d['no'], label=d['label'], page=d['page'], ai=d['ai'],
                        honbun=hon, tsushaku=parse_tsushaku(t['lines'])))
    for i, d in enumerate(dan):   # 通釈の場面の見出しが段の末尾に来たら次の段の頭へ。続けて同じ見出しは一つに（藍染川）
        ts_ = d['tsushaku']
        d['tsushaku'] = [t for j, t in enumerate(ts_) if not (t['type'] == 'heading' and j and ts_[j - 1] == t)]
        while i + 1 < len(dan) and d['tsushaku'] and d['tsushaku'][-1]['type'] == 'heading':
            dan[i + 1]['tsushaku'].insert(0, d['tsushaku'].pop())
    apply_item_patches(title, dan, log, warn)
    for d in dan:   # 段の本文と通釈の分量が極端に違うときは、段の区切りがずれている疑い
        h = sum(len(it.get('text', '')) for it in d['honbun'] if it['type'] == 'u')
        t = sum(len(it.get('text', '')) for it in d['tsushaku'])
        if not d['ai'] and h and t and not (0.5 <= t / h <= 6):
            warn.append(f"【{d['label']}】の本文{h}字と通釈{t}字の分量が釣り合わない（段の区切りを確かめる）")
    info = read_info(x)
    if fixes: apply_info_fixes(x, info, fixes, log)
    # 「正」が空（欄外のゴミの削除）や（頁全体）の記録は、当たらなくても処理の中で消えている
    unapplied = [f for f in (fixes or []) if f['ocr'] and f['fixed'] and not f['ocr'].startswith('（') and not f.get('applied')]
    for f in unapplied: warn.append(f"訂正を当てられなかった: p{f['page']} {f['ocr']}→{f['fixed']}")
    pages = sorted({p['page'] for p in hb})
    out = dict(
        title=title, volume=x['volume'], pid=x['pid'], start_page=x['page'],
        pages=[pages[0], pages[-1]] if pages else [],
        ndl_url=f"https://dl.ndl.go.jp/pid/{x['pid']}", frame_base=base[x['pid']],
        info=info,
        check=dict(status='確認済み' if fixes is not None else '未確認', fixes=sum(1 for f in fixes or [] if f['ocr'] != f['fixed']),
                   summary='確認済み' if any(f['ocr'] == SUMMARY_MARK for f in fixes or []) else '未確認'),
        dan=dan, log=log, warn=warn)
    (OUT / f'{title}.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    return out

if __name__ == '__main__':
    titles = sys.argv[1:] or sorted(f.stem for f in FIX.glob('*.tsv'))
    for t in titles:
        o = build(t)
        print(f"{t}\t段{sum(1 for d in o['dan'] if d['no'])}\t記録{len(o['log'])}\t" + ('／'.join(o['warn']) or 'OK'))
