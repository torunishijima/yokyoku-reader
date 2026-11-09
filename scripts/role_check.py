#!/usr/bin/env python3
"""曲データ（data/yokyoku/kyoku/<曲>.json）の役名を、半魚文庫の同じ箇所の役名と照らし合わせる。
本文を読み（ひらがな）にそろえて位置を合わせ、各発言の頭が半魚文庫のどの発言に当たるかで比べる。
次のものを「要確認」として、確認用シートを作る（右から左へ 1, 2, 3…。赤枠が発言の頭の行）。
- 役名が読めなかったもの（役名なし・小段名だけ）
- 役名が半魚文庫と食い違うもの（シテ／ツレ／ワキ／地… の区分で比べる）
- 行の途中に崩れた役名が残るもの（行頭の役名が読めず、前の発言につながった）
画像で確かめた訂正記録（work/fixes/<曲>.tsv）がある発言は飛ばす
出力: work/checks/<曲>/roles.txt と roleNN.jpg
実行: ~/tools/textvenv/bin/python scripts/role_check.py <曲名> [...]"""
import sys, re, json, difflib
from pathlib import Path
sys.argv, _args = sys.argv[:1], sys.argv[1:]   # collate.py の引数処理を避ける
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
src = (ROOT / 'scripts/collate.py').read_text(encoding='utf-8').split('\ntoc = json.loads')[0]
exec(src)   # TR, DROP, KK, to_hira など（collate.py の関数定義まで）
from PIL import Image, ImageDraw, ImageFont
mc = (ROOT / 'scripts/make_checks.py').read_text(encoding='utf-8').split('\ndef strip')[0]
exec(mc)    # half（片ページ画像）
TOC = json.loads((ROOT / 'data/yokyoku/taikan_toc.json').read_text(encoding='utf-8'))

SHODAN = r'(詞|サシ|上歌|下歌|歌|上|下|次第|一セイ|一声|一聲|セイ|クリ|クセ|ロンギ|キリ|道行|ワカ|ノリ|待謡|待謠|名ノリ|カカル|呼掛|上ゲ歌|下ゲ歌|二ノ句|二句|中ノリ|大ノリ|掛ケ合|掛合)'
def role_key(label, prev=''):
    """役名 → 区分（シテ・ツレ・ワキ・ワキツレ・地・子方・アイ・同吟）。小段名だけなら直前の区分"""
    if not label: return prev
    if '・' in label or re.search(r'二人|三人|同吟|^同', label): return '同吟'
    if re.match(r'^(後|前)?(シテツレ|ツレ|トモ)', label): return 'ツレ'
    if re.match(r'^(後|前)?[シジ]テ', label): return 'シテ'
    if re.match(r'^ワキ[ヅツ]レ', label): return 'ワキツレ'
    if re.match(r'^ワキ', label): return 'ワキ'
    if re.match(r'^子', label): return '子方'
    if re.match(r'^(地|.*地$)', label): return '地'
    if re.match(r'^(狂言|アイ|間|強力|太刀|オモ|アド)', label): return 'アイ'
    if re.fullmatch(SHODAN + r'.*', label): return prev
    return label

KEYS = {'シテ', 'ツレ', 'ワキ', 'ワキツレ', '地', '子方', 'アイ', '同吟'}

def hangyo_utts(f):
    body = (ROOT / 'work/hangyo' / f).read_text(encoding='utf-8').split('――――', 1)[1]
    utts, prev = [], ''
    for l in body.split('\n'):
        m = re.match(r'^([^「」。、\s]{1,14})「(.*)$', l)
        if m:
            prev = role_key(m[1], prev); utts.append(dict(label=m[1], key=prev, text=m[2]))
        elif utts and l.strip():
            utts[-1]['text'] += l.strip()
    return utts

def reading(chunks):
    """chunks: [(文字列, タグ)] → (ひらがな列, 各字のタグ)"""
    chars = []
    for t, tag in chunks:
        t = re.sub(r'[(（〔][^)）〕]*[)）〕]', '', t)
        chars += [(c, tag) for c in t]
    hira, idx, keep = to_hira(chars)
    return hira, [keep[i][1] for i in idx]

MIDG = re.compile(r'(?<=[。、ぁ-ん一-龥)）])([ァ-ヶヮ〃]{1,4}[一-龥]{0,2})([『「一])')
GARBLE = re.compile(r'^([^「『』。、\s]{1,6})[「『』]')

def check(title):
    k = json.loads((ROOT / 'data/yokyoku/kyoku' / f'{title}.json').read_text(encoding='utf-8'))
    x = next(r for r in TOC if r['title'] == title)
    hu = hangyo_utts(x['hangyo_file'])
    H, Htag = reading([(u['text'], i) for i, u in enumerate(hu)])
    items = [it for d in k['dan'] for it in d['honbun'] if it['type'] == 'u']
    def body(it):
        g = GARBLE.match(it['text']) if not it['role'] else None
        return it['text'][g.end():] if g else it['text']
    T, Ttag = reading([(body(it), i) for i, it in enumerate(items)])
    sm = difflib.SequenceMatcher(None, T, H, autojunk=False)
    t2h = {}
    for a, b, n in sm.get_matching_blocks():
        for j in range(n): t2h[a + j] = b + j
    first = {}
    for i, tag in enumerate(Ttag): first.setdefault(tag, []).append(i)
    ok = []   # 画像で確かめた記録（直したもの・「役名確認」として直さないとしたもの）
    ff = ROOT / 'work/fixes' / f'{title}.tsv'
    for ln in ff.read_text(encoding='utf-8').splitlines() if ff.exists() else []:
        c = ln.split('\t')
        if len(c) >= 4 and ('役名' in c[3] or '画像で確認' in c[3]) and c[2]: ok.append((int(c[0][1:]), c[2]))
    out, prev = [], ''
    for i, it in enumerate(items):
        def verified(t):
            tail = re.split(r'[「『]', t)[-1]
            return it['text'][:3] in t or (tail and it['text'].startswith(tail))
        if any(pg == it['page'] and verified(t) for pg, t in ok):
            if it['role']: prev = role_key(it['role'], prev)
            continue
        ks = [Htag[t2h[p]] for p in first.get(i, [])[:8] if p in t2h]
        hl = hu[max(set(ks), key=ks.count)] if ks else None
        g = GARBLE.match(it['text']) if not it['role'] else None
        mine = role_key(it['role'], prev) if it['role'] else ''
        reason = None
        if g: reason = f'役名が読めない「{g[1]}」'
        elif not it['role'] and not it['shodan'] and re.match(r'^([ァ-ヶヮー〃]{2,5}|地|強力|太刀)(?![ぁ-ん])', it['text']):
            reason = '役名が崩れている？'
        elif not it['role'] and it['shodan']: reason = '役名なし（小段名だけ）'
        elif it['role'] and hl and hl['key'] in KEYS and mine != hl['key'] and not (mine == '同吟' and hl['key'] in ('シテ', 'ツレ', 'ワキ', 'ワキツレ')):
            reason = f'半魚文庫と違う（{hl["key"]}）'
        if not reason:   # 行頭の役名が崩れて前の発言につながったもの（行の途中に崩れた役名が残る）
            m = MIDG.search(it['text'])
            if m and m[1] not in ('ワキ', 'シテ', 'ツレ', '地'): reason = f'行の途中に崩れた役名「{m[1]}」'
        if it['role']: prev = mine
        if reason:
            out.append(dict(it=it, reason=reason, hangyo=hl['label'] if hl else '（対応なし）'))
    return k, out

FONT = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 30)
def strip(k, it):
    img, x0, y0, x1, y1 = it['src']
    im = half(k['pid'], img); W, H = im.size
    lw = max(x1 - x0, 40)
    c = im.crop((max(0, x0 - lw * 2), max(0, y0 - int(H * 0.06)), min(W, x1 + lw * 2), min(H, y0 + int(H * 0.2)))).convert('RGB')
    ox, oy = max(0, x0 - lw * 2), max(0, y0 - int(H * 0.06))
    ImageDraw.Draw(c).rectangle((x0 - ox - 3, y0 - oy - 3, x1 - ox + 3, min(y1, y0 + int(H * 0.2)) - oy + 3), outline=(220, 0, 0), width=3)
    s = 700 / c.height
    return c.resize((max(1, int(c.width * s)), 700))

for title in _args:
    k, out = check(title)
    od = ROOT / 'work/checks' / title; od.mkdir(parents=True, exist_ok=True)
    for old in od.glob('role*.jpg'): old.unlink()
    lines = []
    for s0 in range(0, len(out), 10):
        group = out[s0:s0 + 10]
        strips = [strip(k, o['it']) for o in group]
        W = sum(s.width for s in strips) + 8 * (len(strips) + 1)
        sheet = Image.new('RGB', (W, 750), 'white'); dr = ImageDraw.Draw(sheet); xx = W - 8
        for n, s in enumerate(strips, s0 + 1):
            xx -= s.width; sheet.paste(s, (xx, 50)); dr.text((xx + 4, 8), str(n), fill=(220, 0, 0), font=FONT); xx -= 8
        sheet.save(od / f'role{s0 // 10 + 1:02d}.jpg', quality=85)
    for n, o in enumerate(out, 1):
        it = o['it']
        lines.append(f"{n}\tp{it['page']}\t{o['reason']}\t大観OCR「{it['role']}|{it['shodan']}{it['q']}{it['text'][:14]}」\t半魚「{o['hangyo']}」")
    (od / 'roles.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'{title}\t要確認 {len(out)}')
