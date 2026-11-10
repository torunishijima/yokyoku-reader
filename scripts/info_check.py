#!/usr/bin/env python3
"""曲情報（梗概・人物）と通釈の、OCR の誤りの疑いを機械的に拾う（docs/ocr_check.md の「曲情報・通釈の確認」の 1）。
誤りは「実在する字への化け」が多く、辞書では拾えない。そこで同じ曲の本文・通釈・人物欄との食い違いを見る。

使い方: info_check.py [曲名 ...]（省略時は data/yokyoku/kyoku/ の全曲）
出力: 曲ごとに「頁の欄・該当の文字列・理由」。誤りとは限らない。理由を読み、原本の画像で確かめる。

拾うもの
- 近い形: 梗概・人物の漢字 2〜4 字が同じ曲のほかの所に出ず、1 字だけ違う形なら出る（梅若九 ↔ 梅若丸）
- 重なり: 同じ字が続く（萬葉葉）。踊り字で書かない所なので疑わしい
- 紛らわしい字: 読み誤りやすい字（docs/ocr_check.md の「間違えやすい字」）を含み、ほかの所に出ない語
- 互換漢字: 見た目が同じで文字コードが違う字（神 U+FA19 など）。検索や照合で別の字として扱われる
"""
import json, re, sys, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KY = ROOT / 'data/yokyoku/kyoku'
KANJI = r'[㐀-鿿豈-﫿々〆]'
# 読み誤りやすい字の組（OCR の結果 → 正しい字の候補）。見つかった誤りを足していく
CONFUSE = ['鳥烏', '遺遣', '間問', '葉菜集', '荼茶', '憍橋', '九丸', '東束', '益盆', '婆娑', '埵唾', '鷗鴫', '運蓮', '賞貫', '己已巳', '未末', '土士']
CONF = {c: g for g in CONFUSE for c in g}

def texts(d):
    """曲の本文・ト書き・通釈を、頁つきで返す"""
    out = []
    for dan in d['dan']:
        for it in dan['honbun']:
            if it.get('text'): out.append(('本文', it.get('page', dan['page']), it['text']))
            for a in it.get('items', []):
                if a.get('text'): out.append(('間狂言', a.get('page', dan['page']), a['text']))
        for it in dan['tsushaku']:
            t = (it.get('speaker', '') + it.get('text', ''))
            if t: out.append(('通釈', dan['page'], t))
    return out

def runs(s, lo=2, hi=4):
    for m in re.finditer(f'{KANJI}+', s):
        r = m[0]
        for n in range(lo, min(hi, len(r)) + 1):
            for i in range(len(r) - n + 1): yield r[i:i + n]

def check(d):
    nfc = lambda t: unicodedata.normalize('NFC', t)
    info = {k: nfc(v) for k, v in d.get('info', {}).items()}
    body = [(a, b, nfc(t)) for a, b, t in texts(d)]
    flags = []
    fields = [('梗概', info.get('梗概', '')), ('人物', info.get('人物', ''))]
    for name, s in fields:
        others = '\n'.join(t for _, _, t in body) + '\n' + '\n'.join(v for k, v in fields if k != name)
        seen = set()
        for w in runs(s):
            if w in seen or w in others: continue
            seen.add(w)
            # 1 字だけ違う形がほかの所に出るか。語の中ほどの字なら 1 回でも、端の字なら「残りの字の後（前）にはほぼいつもその字が来る」ときだけ
            for i, c in enumerate(w):
                pat = re.escape(w[:i]) + f'({KANJI})' + re.escape(w[i + 1:])
                alts = [a for a in re.findall(pat, others) if a != c]
                if not alts or len(w) < 3: continue
                a = max(set(alts), key=alts.count)
                if 0 < i < len(w) - 1: ok = True
                else:
                    core = w[1:] if i == 0 else w[:-1]
                    ok = alts.count(a) >= 2 and alts.count(a) >= 0.6 * others.count(core)
                if ok:
                    flags.append((name, w, f'近い形「{w[:i]}{a}{w[i + 1:]}」がほかの所に出る（{c}→{a}? {alts.count(a)}回）')); break
            else:
                if any(c in CONF for c in w) and len(w) == 2:
                    alt = [w.replace(c, a) for c in w if c in CONF for a in CONF[c] if a != c]
                    hit = [a for a in alt if a in others]
                    if hit: flags.append((name, w, f'紛らわしい字。ほかの所には「{"・".join(hit)}」'))
        # 重なった窓（播磨國・播磨國高…）は最初の 1 件だけ残す
        mine = [f for f in flags if f[0] == name]; keep = []
        for f in sorted(mine, key=lambda f: (not f[2].startswith('近い形'), len(f[1]))):
            if not any(k[1] in f[1] or f[1] in k[1] for k in keep): keep.append(f)
        flags = [f for f in flags if f[0] != name] + keep
        for m in re.finditer(rf'({KANJI})\1', s):
            if m[1] not in '々〆':
                flags.append((name, s[max(0, m.start() - 2):m.end() + 1], f'同じ字「{m[1]}」が続く'))
    raw = json.dumps(d, ensure_ascii=False)
    cs = sorted({c for c in raw if unicodedata.normalize('NFC', c) != c})
    if cs: flags.append(('全体', ''.join(cs), f'互換漢字 {len(cs)} 種（見た目は同じで文字コードが違う。データ統一のときに NFC でそろえる）'))
    # 通釈の話し手名: 曲の中で 1 回しか出ない名前は読み誤りを疑う（運生→蓮生）
    sp = {}
    for dan in d['dan']:
        for it in dan['tsushaku']:
            if it.get('speaker'): sp.setdefault(it['speaker'], []).append(dan['page'])
    for k, v in sp.items():
        if len(v) == 1 and len(sp) > 1:
            near = [o for o in sp if o != k and len(o) == len(k) and sum(a != b for a, b in zip(o, k)) == 1]
            if near: flags.append(('通釈の話し手', k, f'1 回だけの話し手名。近い名前「{"・".join(near)}」がある（p{v[0]}）'))
    # 読み取りの崩れ: 半角の括弧・数字・記号が続く（罫やルビを読んだもの。隅田川 p1525）
    for dan in d['dan']:
        for band, name in (('honbun', '本文'), ('tsushaku', '通釈')):
            for it in dan[band]:
                for m in re.finditer(r'(?:[()\-\d|]\s*){4,}', it.get('text', '')):
                    flags.append((name, m[0].strip()[:30], f'読み取りの崩れ（半角の記号・数字が続く。【{dan["label"]}】p{dan["page"]}〜）'))
            # 役名が前の発言に混ざっている: ト書きの閉じ括弧・句点の直後に役名（鉤括弧の読み落とし。隅田川 p1532）
            if band == 'honbun':
                for it in (x for x in dan[band] if x['type'] == 'u'):
                    for m in re.finditer(r'[)）。](?:(?:シテ|ワキ|ツレ|ワキヅレ|子方|狂言)(?![「『ノ])|地(?=上歌|下歌|クセ|クリ|サシ|ロンギ|次第|一セイ|キリ|ノリ地)(?:上歌|下歌|クセ|クリ|サシ|ロンギ|次第|一セイ|キリ|ノリ地)(?![「『]))(.{0,6})', it.get('text', '')):
                        flags.append(('本文', m[0], f'役名が発言の途中にある（鉤括弧の読み落とし、またはト書きの混入。p{it.get("page", dan["page"])}）'))
    return flags

if __name__ == '__main__':
    titles = sys.argv[1:] or sorted(f.stem for f in KY.glob('*.json'))
    total = 0
    for t in titles:
        d = json.loads((KY / f'{t}.json').read_text(encoding='utf-8'))
        fl = check(d)
        st = d['check'].get('summary', '未確認')
        print(f'■ {t}（梗概の照合: {st}、解説 p{d["start_page"]}）' + ('' if fl else '　疑いなし'))
        for name, w, why in fl: print(f'  {name}\t{w}\t{why}')
        total += len(fl)
    print(f'計 {total} 件（誤りとは限らない。理由を読み、原本の画像で確かめる）')
