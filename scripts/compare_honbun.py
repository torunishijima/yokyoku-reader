#!/usr/bin/env python3
"""大観本文の書き起こし（taikan-honbun/<曲>.txt）と半魚文庫の原文を照合し、食い違い箇所を出す。
比較用に表記（旧字・仮名遣い・踊り字・句読点・役名）をそろえてから差分をとる。表示用テキストは変えない。"""
import sys, re, difflib, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; YK = ROOT/'data'/'yokyoku'
OLD='淸經國戶吳戀櫻實舍榮關與攝蟬禪曾佛會當龜寢覺樂辨卷萬靜蟲瀨顏賴藏繪鹽郞鐵檜歸賴髮黑淚亂聲戰鬪靈臺雜兵遲從將豐兩稱德氣變處數樣續總壽傳圓廣應來祕佛彌陀竝隱澤劍姬譽餘覽讀戲驛醫鄕寬窄邊龍惠圖眞纏淺壞恥祿顯團攝獨單參澁滿舊殘晝狀盡壯專惱擔斷柳'
NEW='清経国戸呉恋桜実舎栄関与摂蝉禅曽仏会当亀寝覚楽弁巻万静虫瀬顔頼蔵絵塩郎鉄桧帰頼髪黒涙乱声戦闘霊台雑兵遅従将豊両称徳気変処数様続総寿伝円広応来秘仏弥陀並隠沢剣姫誉余覧読戯駅医郷寛窄辺竜恵図真纏浅壊恥禄顕団摂独単参渋満旧残昼状尽壮専悩担断柳'
TR=str.maketrans(OLD[:len(NEW)],NEW[:len(OLD)])
def norm(t):
    t=t.translate(TR)
    t=re.sub(r'（[^）]*）','',t)
    t=re.sub(r'(.)／＼|(.)％＼','',t) if False else t
    t=re.sub(r'[\s。、・「」『』〳〵／＼％,]','',t)
    return t
def hangyo_body(f):
    b=(YK/'hangyo'/f).read_text(encoding='utf-8').split('――――',1)[1]
    out=[]
    for l in b.split('\n'):
        m=re.match(r'^[^「」。]{1,14}「(.*)$',l); out.append(m.group(1) if m else l)
    return norm(''.join(out))
def taikan_body(p):
    out=[]
    for l in p.read_text(encoding='utf-8').split('\n'):
        if not l or l.startswith('#') or l.startswith('【'): continue
        out.append(l.split('\t',1)[-1])
    return norm(''.join(out))
title=sys.argv[1]; f=sys.argv[2]
a=hangyo_body(f); b=taikan_body(YK/'taikan-honbun'/f'{title}.txt')
sm=difflib.SequenceMatcher(None,a,b,autojunk=False)
ops=[o for o in sm.get_opcodes() if o[0]!='equal']
print(f'{title}: 半魚{len(a)}字 / 大観{len(b)}字 一致率{sm.ratio():.3f} 差分{len(ops)}か所')
for tag,i1,i2,j1,j2 in ops:
    print(f'  {tag:7} 半魚「{a[i1:i2]}」→ 大観「{b[j1:j2]}」  …{b[max(0,j1-8):j1]}|{b[j2:j2+8]}…')
