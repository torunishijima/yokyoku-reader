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
6. 解説の頁から曲情報（能柄・人物・所・時・梗概）を取る
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
         '地', '狂言', 'アイ', '同', '二人', '三人', '立衆', '女', '男']
SHODAN = ['次第', '名ノリ', '名宣', '道行', '一聲', '一セイ', '二句', 'サシ', '下歌', '上歌', 'クリ', 'クセ', 'ロンギ', '待謠', '詞',
          '歌', 'ワカ', 'ノリ地', 'キリ', '掛合', '中ノリ', '大ノリ', '問答', '上', '下', 'カカル', '一']
# OCR の読み誤り（画像で確かめたもの）
ROLE_MISREAD = {'ッキ': 'ワキ', 'ット': 'ワキ', 'ッレ': 'ツレ', 'ット': 'ワキ', 'シァ': 'シテ', 'ジテ': 'シテ', 'び': 'シテ', '邦': '地',
                'サン': 'サシ', '土歌': '上歌', 'ウキ': 'ワキ'}
ROLE_RE = '|'.join(sorted(set(ROLES) | {k for k, v in ROLE_MISREAD.items() if v in ROLES}, key=len, reverse=True))
SHODAN_RE = '|'.join(sorted(set(SHODAN) | {k for k, v in ROLE_MISREAD.items() if v in SHODAN}, key=len, reverse=True))
LABEL = re.compile(rf'^((?:(?:{ROLE_RE})(?:・?(?:{ROLE_RE}))*)?)((?:{SHODAN_RE})?)(\([^)）]*[)）])?([「『])')
SHODAN_MID = '|'.join(s for s in SHODAN_RE.split('|') if s not in ('一', '上', '下', '詞', '歌'))
MID = re.compile(rf'(?<=[。、\s])((?:{ROLE_RE})?)((?:{SHODAN_MID})?)(\([^)）]*[)）])?([「『])')
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
    if part == 'honbun':
        boxes = json.loads((SPLIT / f'{title}.honbun.lines.json').read_text(encoding='utf-8'))
        it = iter(boxes)
        for p in pages:
            assert next(it) is None
            for l in p['lines']: l['box'] = next(it)['box']
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
                    l['t'] = l['t'].replace(fx['ocr'], fx['fixed'], 1); hit = True; break
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
    for p in pages:
        ls = p['lines']
        tops = sorted(l['box'][1] for l in ls if l['box'][3] - l['box'][1] > 300)
        body = tops[len(tops) // 4] if tops else 0
        for l in ls:
            t = clean(l['t']); x0, y0, x1, y1 = l['box']
            if not t or re.fullmatch(r'[\d\s\-ー―・.]+', t) or sum(c in '- ー―' for c in l['t']) > len(l['t']) / 2:
                l['kind'] = 'junk'
            elif DAN_LINE.match(l['t']):
                l['kind'] = 'dan'
            elif y1 - y0 < 160 and y0 < body + 60 and re.fullmatch(rf'(?:{ROLE_RE}|ワキヅ|シテツ)(?:・(?:{ROLE_RE}|ワキヅ))*・?', t):
                l['kind'] = 'role'
            elif y0 > body + 80 and not ((m := LABEL.match(t)) and m[2]):
                l['kind'] = 'note'
            else:
                l['kind'] = 'text'
            l['t'] = t

# ---------- 段に分ける ----------
def split_dan(pages, log):
    """[{no, label, page, lines:[(page, line)]}]。最初の印より前は no=0"""
    dans = [dict(no=0, label='', page=pages[0]['page'] if pages else 0, lines=[])]
    n = 0
    for p in pages:
        for l in p['lines']:
            if l.get('kind', 'text') == 'junk': continue
            m = DAN_LINE.match(l['t']) if l.get('kind') in (None, 'dan') else None
            if m:
                s = m[1]
                if s in AI_MARK:
                    dans.append(dict(no=None, label='間', page=p['page'], lines=[], ai=True))
                elif s in ('物着',) or len(s) >= 2 and dan_no(s) is None and s not in ('I', 'II', 'IO', '10', '11'):
                    dans[-1]['lines'].append((p['page'], dict(t=f'【{s}】', kind='heading')))
                else:
                    k = dan_no(s)
                    if k != n + 1:
                        log.append(dict(page=p['page'], kind='段の印', ocr=f'【{s}】', fixed=f'【{kansuji(n + 1)}】'))
                    n += 1
                    dans.append(dict(no=n, label=kansuji(n), page=p['page'], lines=[]))
                rest = clean(m[3] or '')
                if rest: dans[-1]['lines'].append((p['page'], dict(l, t=rest, kind='note' if l.get('kind') else None)))
                continue
            dans[-1]['lines'].append((p['page'], l))
    if not dans[0]['lines']: dans.pop(0)
    return dans

# ---------- 本文 ----------
def roles_of(s, log, page):
    """'ワキワキヅレ' / 'シテ・ツレ' → 'ワキ・ワキヅレ'（読み誤りも直す）"""
    if not s: return ''
    return '・'.join(fix_label(r, log, page) for r in ROLE_SPLIT.findall(s))

def parse_honbun(lines, log, state):
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
            else:
                pending = r
            continue
        if k == 'note':
            if items and items[-1]['type'] == 'note': items[-1]['text'] += t
            else: items.append(dict(type='note', text=t))
            if '中入' in t: ai_from = page
            continue
        # 本文行
        m = LABEL.match(t)
        if m and (m[1] or m[2]):
            role = roles_of(m[1], log, page) or pending
            items.append(dict(type='u', role=role, shodan=fix_label(m[2], log, page) if m[2] else '', paren=m[3] or '', q=m[4], text='', page=page))
            body = t[m.end():]
        else:
            if not items or items[-1]['type'] != 'u':
                items.append(dict(type='u', role='', shodan='', paren='', q='', text='', page=page, _cont=True))
            body = t
        pending = ''
        parts = MID.split(body)   # [text, role, shodan, paren, quote, text, ...]
        items[-1]['text'] += parts[0]
        for i in range(1, len(parts), 5):
            r, sd, paren, q, txt = parts[i:i + 5]
            if not r and not sd:
                items[-1]['text'] += (paren or '') + q + txt; continue
            items.append(dict(type='u', role=roles_of(r, log, page), shodan=fix_label(sd, log, page) if sd else '',
                              paren=paren or '', q=q, text=txt, page=page))
    if ai_from is not None:
        last_page = max(p for p, _ in lines)
        items.append(dict(type='ai', pages=[ai_from, last_page]))
    for it in items: it.pop('_cont', None)
    return items

# ---------- 通釈 ----------
def parse_tsushaku(lines):
    items, buf, depth = [], None, 0
    def flush():
        nonlocal buf
        if buf:
            t = buf['text']
            m = re.match(r'^([^「『(（\s。、]{1,10})「(.*)$', t, re.S)
            if t in ('前段', '後段'): items.append(dict(type='heading', text=t))
            elif m: items.append(dict(type='speech', speaker=m[1], text=m[2].rstrip('」') if m[2].endswith('」') and m[2].count('「') < m[2].count('」') else m[2]))
            elif re.match(r'^[(（].*[)）]$', t, re.S): items.append(dict(type='gloss', text=t))
            else: items.append(dict(type='narration', text=t))
        buf = None
    for page, l in lines:
        t = l['t']
        if l.get('kind') in ('junk',): continue
        if l.get('kind') == 'heading': flush(); items.append(dict(type='heading', text=t)); continue
        starts = bool(re.match(r'^[^「『(（\s。、]{1,10}「', t)) or t[:1] in '(（' or t in ('前段', '後段')
        if buf is None or (depth == 0 and (starts or re.search(r'[。」)）]$', buf['text']))) or t in ('前段', '後段'):
            flush(); buf = dict(text=t, page=page)
        else:
            buf['text'] += t
        depth = max(0, depth + t.count('「') + t.count('(') + t.count('（') - t.count('」') - t.count(')') - t.count('）'))
        if buf['text'] in ('前段', '後段'): flush()
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
    for p in (x['page'], x['page'] + 1):
        f = OCR / pid / f'f{base[pid] + p // 2:04d}{"L" if p % 2 else "R"}.txt'
        if f.exists(): txt += f.read_text(encoding='utf-8') + '\n'
    info = {}
    m = re.search(r'^.*?([觀観寶宝春剛金喜]{1,2}[(（][^)）\n]*[)）]?)', txt, re.M)
    if m: info['流派'] = m[1]
    parts = re.split(r'【([^】]{0,4})】', txt)
    for k, v in zip(parts[1::2], parts[2::2]):
        k = '梗概' if k in ('梗槪', '梗概') else k
        if k in ('能柄', '人物', '所', '時', '梗概') and k not in info:
            v = v.strip()
            info[k] = '\n'.join(re.sub(r'\s+', '', x) for x in v.split('\n')) if k == '人物' else re.sub(r'\s+', '', v)
    return info

# ---------- 組み立て ----------
def build(title):
    x = next(r for r in toc if r['title'] == title)
    fixes = read_fixes(title)
    log = []
    hb = read_split(title, 'honbun'); ts = read_split(title, 'tsushaku')
    if fixes: apply_fixes(hb, fixes, log); apply_fixes(ts, fixes, log)
    dedupe(hb, log); dedupe(ts, log)
    classify(hb)
    for p in ts:
        for l in p['lines']:
            l['t'] = clean(l['t'])
            if not l['t'] or re.fullmatch(r'[\d\s\-ー―・.]+', l['t']): l['kind'] = 'junk'
            elif DAN_LINE.match(l['t']): l['kind'] = None
    hd = split_dan(hb, log); td = split_dan(ts, [])
    warn = []
    hk = [(d['no'], d.get('ai', False)) for d in hd]; tk = [(d['no'], d.get('ai', False)) for d in td]
    if hk != tk: warn.append(f'段の数が本文と通釈で合わない: 本文{hk} 通釈{tk}')
    state = {}
    dan = []
    tmap = {(d['no'], d.get('ai', False)): d for d in td}
    for d in hd:
        t = tmap.get((d['no'], d.get('ai', False)))
        hon = [dict(type='ai', pages=[d['page'], max(p for p, _ in d['lines'])])] if d.get('ai') else parse_honbun(d['lines'], log, state)
        dan.append(dict(no=d['no'], label=d['label'], page=d['page'], ai=d.get('ai', False),
                        honbun=hon,
                        tsushaku=parse_tsushaku(t['lines']) if t else []))
    unapplied = [f for f in (fixes or []) if f['ocr'] and not f.get('applied')]
    for f in unapplied: warn.append(f"訂正を当てられなかった: p{f['page']} {f['ocr']}→{f['fixed']}")
    pages = sorted({p['page'] for p in hb})
    out = dict(
        title=title, volume=x['volume'], pid=x['pid'], start_page=x['page'],
        pages=[pages[0], pages[-1]] if pages else [],
        ndl_url=f"https://dl.ndl.go.jp/pid/{x['pid']}", frame_base=base[x['pid']],
        info=read_info(x),
        check=dict(status='確認済み' if fixes is not None else '未確認', fixes=len(fixes or [])),
        dan=dan, log=log, warn=warn)
    (OUT / f'{title}.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    return out

if __name__ == '__main__':
    titles = sys.argv[1:] or sorted(f.stem for f in FIX.glob('*.tsv'))
    for t in titles:
        o = build(t)
        print(f"{t}\t段{sum(1 for d in o['dan'] if d['no'])}\t記録{len(o['log'])}\t" + ('／'.join(o['warn']) or 'OK'))
