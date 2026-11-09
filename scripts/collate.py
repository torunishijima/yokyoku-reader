#!/usr/bin/env python3
"""大観本文の OCR（work/split/<曲>.honbun.txt）と半魚文庫の原文を、読み（ひらがな）にそろえて照合する。
漢字・かなの書き分け（是/これ 等）や旧字・句読点・踊り字の違いは差分にしない。残った差分だけを、大観の頁つきで出す。
実行: ~/tools/textvenv/bin/python scripts/collate.py [曲名 ...]   （省略時は全曲、work/collate/ に結果）"""
import sys, re, json, difflib, unicodedata
from pathlib import Path
import pykakasi
ROOT = Path(__file__).resolve().parent.parent; YK = ROOT / 'data/yokyoku'
SPLIT = ROOT / 'work/split'; OUT = ROOT / 'work/collate'; OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / 'scripts'))
OLD = '淸經國戶吳戀櫻實舍榮關與攝蟬禪曾佛會當龜寢覺樂辨卷萬靜蟲瀨顏賴藏繪鹽郞鐵檜歸髮黑淚亂聲戰鬪靈臺雜遲從將豐兩稱德氣變處數樣續總壽傳圓廣應來祕彌竝隱澤劍姬譽餘覽讀戲驛醫鄕寬邊龍惠圖眞淺壞祿顯團獨單參澁滿舊殘晝狀盡壯專惱擔斷學擧譯聽觀權勸歡齒體髓證據變戀亞惡壓圍爲醉碎濕雙發廢拜賣倂竊竝稻蘆蠶顯勞營螢榮'
NEW = '清経国戸呉恋桜実舎栄関与摂蝉禅曽仏会当亀寝覚楽弁巻万静虫瀬顔頼蔵絵塩郎鉄桧帰髪黒涙乱声戦闘霊台雑遅従将豊両称徳気変処数様続総寿伝円広応来秘弥並隠沢剣姫誉余覧読戯駅医郷寛辺竜恵図真浅壊禄顕団独単参渋満旧残昼状尽壮専悩担断学挙訳聴観権勧歓歯体髄証拠変恋亜悪圧囲為酔砕湿双発廃拝売併窃並稲芦蚕顕労営蛍栄'
OLD += '僞謠拔劒卽嚴獸歲靑淨繩虛黃收莊衞遙屆拂擊彈價假冰狹濱渴禮缺盃廳聽鷄雞擴據擇澤鬭畫晉峯嶋埀乘剩擔錢鑄醬鹽奧壹貳參拾'; NEW += '偽謡抜剣即厳獣歳青浄縄虚黄収荘衛遥届払撃弾価仮氷狭浜渇礼欠杯庁聴鶏鶏拡拠択沢闘画晋峰島垂乗剰担銭鋳醤塩奥壱弐参拾'
assert len(OLD) == len(NEW), (len(OLD), len(NEW))
TR = str.maketrans(OLD, NEW)
DROP = set('　 \t。、・「」『』〳〵〴〵ゝゞ々／＼％,.，．!！?？()（）〔〕[]【】…―-─ー〓')
KK = pykakasi.kakasi()

def taikan_chars(title):
    """[(文字, 頁)]。ト書き(＊)・見出し・頁行・丸括弧の小字・役名は除く。"""
    out, page = [], None
    meta = json.loads((SPLIT / f'{title}.honbun.lines.json').read_text(encoding='utf-8'))
    for li, l in enumerate((SPLIT / f'{title}.honbun.txt').read_text(encoding='utf-8').split('\n')):
        if l.startswith('# p'): continue
        page = li
        if not l or l.startswith('＊') or re.match(r'^【.{1,3}】$', l): continue
        l = l.replace('〔?〕', '')
        m = re.match(r'^[^「『]{1,10}[「『]', l)
        if m: l = l[m.end():]
        out += [(c, page) for c in l]
    # 行をまたぐ丸括弧の小字（ト書き）も除く。閉じがなければ 20 字で打ち切る
    res, k = [], 0
    while k < len(out):
        if out[k][0] in '（(':
            e = next((j for j in range(k + 1, min(k + 21, len(out))) if out[j][0] in '）)'), None)
            if e is not None: k = e + 1; continue
        if out[k][0] in '）)': k += 1; continue
        res.append(out[k]); k += 1
    return res

def hangyo_text(f):
    b = (ROOT / 'work/hangyo' / f).read_text(encoding='utf-8').split('――――', 1)[1]
    res = []
    for l in b.split('\n'):
        m = re.match(r'^[^「」。]{1,14}「(.*)$', l); res.append(m.group(1) if m else l)
    s = ''.join(res)
    s = re.sub(r'\{[^}]*\}', '', s)
    return re.sub(r'（[^）]*）', '', s)

def to_hira(chars):
    """chars: [(文字, 頁)] → (ひらがな列, 各ひらがな→元の位置)"""
    keep = [(unicodedata.normalize('NFKC', c).translate(TR), p) for c, p in chars if c not in DROP]
    s = ''.join(c for c, _ in keep)
    hira, idx, pos = [], [], 0
    for it in KK.convert(s):
        n = len(it['orig']); h = it['hira'] or it['orig']
        for k, ch in enumerate(h):
            hira.append(ch); idx.append(pos + min(k * n // max(len(h), 1), n - 1))
        pos += n
    return ''.join(hira), idx, keep

KANJI = re.compile(r'[\u3400-\u9fff\uf900-\ufaff]')
ROLE = re.compile(r'^(前|後)?(シテ|ワキ|ツレ|ワキツレ|シテツレ|子方|地|トモ|アイ|狂言|同|ッレ|ヮキ)?(次第|一聲|一声|サシ|下歌|上歌|下ノ詠|上ノ詠|クセ|クリ|ロンギ|カヽル|詞|ノル|ワカ|掛合|歌|中ノリ)*$')
def kind(d, b_text, b1, b2):
    a, b = unicodedata.normalize('NFKC', d['hangyo']).translate(TR), unicodedata.normalize('NFKC', d['taikan']).translate(TR)
    if a == b: return 'ortho'
    if not a and b:
        n = len(b)
        if b_text[b1 - n:b1] == b or b_text[b2:b2 + n] == b: return 'repeat'
        for o in range(-8, 9):   # 繰り返しが少しずれて揃えられた場合（周期 n の並び）
            lo, hi = b1 + o, b2 + o
            if lo - n >= 0 and hi <= len(b_text) and all(b_text[i] == b_text[i - n] for i in range(lo, hi)):
                return 'repeat'
        if ROLE.match(b): return 'role'
        if n > 60: return 'block'
        if n >= 3 and (b.startswith('と') or re.search(r'(向き|立ち|出で|離れ|見上げ|形|下に居|座|幕|扇|拍子|裝束|装束|囃子|作物|後見|中入|狂言)', b)):
            return 'stage'
    if KANJI.sub('', '') == '' and a and b and re.sub(r'[^㐀-鿿]', '', a) == re.sub(r'[^㐀-鿿]', '', b) \
            and re.sub(r'[^㐀-鿿]', '', a):
        return 'okuri'
    if not KANJI.search(a + b) and len(a + b) <= 2: return 'okuri'
    if a and b and (bool(KANJI.search(a)) != bool(KANJI.search(b))): return 'ortho'
    if a and b and not KANJI.search(a + b) and len(a) == len(b) == 1 and a + b in ('ゐい', 'いゐ', 'ゑえ', 'えゑ', 'をお', 'おを', 'はわ', 'わは', 'へえ', 'えへ'): return 'okuri'
    return 'check'

def collate(x):
    title = x['title']
    if not (SPLIT / f'{title}.honbun.txt').exists(): return None
    a_h, a_i, a_k = to_hira([(c, None) for c in hangyo_text(x['hangyo_file'])])
    global META
    META = json.loads((SPLIT / f'{title}.honbun.lines.json').read_text(encoding='utf-8'))
    b_h, b_i, b_k = to_hira(taikan_chars(title))
    sm = difflib.SequenceMatcher(None, a_h, b_h, autojunk=False)
    diffs = []
    b_text = ''.join(c for c, _ in b_k)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal': continue
        oa = ''.join(c for c, _ in a_k[a_i[i1]:a_i[i2 - 1] + 1]) if i2 > i1 else ''
        jb = min(j1, len(b_i) - 1)
        b1 = b_i[jb]; b2 = b_i[j2 - 1] + 1 if j2 > j1 else b1
        ob = ''.join(c for c, _ in b_k[b1:b2])
        ctx = ''.join(c for c, _ in b_k[max(0, b1 - 6):b1]) + '［' + ob + '］' + ''.join(c for c, _ in b_k[b2:b2 + 6])
        m = META[b_k[b1][1]] if b_k else None
        d = dict(tag=tag, hangyo=oa, taikan=ob, page=m and m['page'], line=m, ctx=ctx,
                 size=max(i2 - i1, j2 - j1))
        d['kind'] = kind(d, b_text, b1, b2)
        diffs.append(d)
    return dict(title=title, hangyo_file=x['hangyo_file'], hangyo_len=len(a_h), taikan_len=len(b_h),
                ratio=round(sm.ratio(), 4), n_diffs=len(diffs),
                n_check=sum(d['kind'] == 'check' for d in diffs), diffs=diffs)

toc = json.loads((YK / 'taikan_toc.json').read_text(encoding='utf-8'))
want = set(sys.argv[1:])
summary = []
for x in toc:
    if want and x['title'] not in want: continue
    if not x.get('hangyo_file'): continue
    r = collate(x)
    if not r: continue
    (OUT / f"{x['title']}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
    summary.append((r['title'], r['ratio'], r['n_diffs'], r['hangyo_len'], r['taikan_len']))
    print(f"{r['title']}\t一致率{r['ratio']:.3f}\t差分{r['n_diffs']}\t要確認{r['n_check']}\t半魚{r['hangyo_len']}\t大観{r['taikan_len']}", flush=True)
