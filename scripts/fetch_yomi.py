#!/usr/bin/env python3
"""曲名の読み仮名を、国立国会図書館サーチの書誌データ（書名の読み）から集める。
謡本の版元（檜書店＝観世流、わんや書店＝宝生流）の本のうち、書名が曲名とちょうど一致するものの読みを数え、多数決で決める。
国立国会図書館の読みは「ぢ・づ」を「ジ・ズ」と書く（井筒＝イズツ）。
結果: work/yomi_ndl.json（{曲名: {yomi, count, total, candidates}}）。取り直すときは曲名を指定する。
使い方: fetch_yomi.py [曲名 ...]（省略時は公開中の曲のうち未取得のもの）"""
import json, re, sys, time, unicodedata, collections, urllib.request, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'work/yomi_ndl.json'
src = (ROOT / 'scripts/collate.py').read_text(encoding='utf-8')
ns = {}
exec('\n'.join(l for l in src.split('\n') if l.startswith(('OLD', 'NEW'))), ns)
TR = str.maketrans(ns['OLD'], ns['NEW'])

def query(title, pub):
    u = 'https://ndlsearch.ndl.go.jp/api/opensearch?' + urllib.parse.urlencode(dict(title=title, publisher=pub, cnt=50))
    for k in range(3):
        try:
            x = urllib.request.urlopen(u, timeout=180).read().decode()
            break
        except Exception as e:
            print('  再試行', title, pub, e, flush=True); time.sleep(10)
    else:
        return []
    out = []
    for it in re.findall(r'<item>(.*?)</item>', x, re.S):
        t = re.search(r'<title>([^<]*)</title>', it); tr = re.search(r'<dcndl:titleTranscription>([^<]*)</dcndl:titleTranscription>', it)
        if t and tr: out.append((t[1], tr[1]))
    return out

def hira(s):
    s = unicodedata.normalize('NFKC', s)
    return ''.join(chr(ord(c) - 0x60) if 'ァ' <= c <= 'ヶ' else c for c in s).replace(' ', '')

def fetch(title):
    q = re.sub(r'（別巻）$', '', title).translate(TR)
    names = {q, q.replace('上', 'の上') if q.endswith('上') else q}
    c = collections.Counter(); total = 0
    for pub in ('檜書店', 'わんや書店'):
        for t, tr in query(q, pub):
            base = re.split(r'\s*[:：(（]', t)[0].strip().translate(TR)
            if base in names:
                c[hira(tr)] += 1; total += 1
        time.sleep(2)
        if total >= 3: break
    if not c: return dict(yomi='', count=0, total=0, candidates={})
    y, n = c.most_common(1)[0]
    return dict(yomi=y, count=n, total=total, candidates=dict(c))

if __name__ == '__main__':
    data = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {}
    if sys.argv[1:]:
        titles = sys.argv[1:]
    else:
        idx = json.loads((ROOT / 'data/yokyoku/index.json').read_text(encoding='utf-8'))
        titles = [r['title'] for r in idx if r['title'] not in data]
    for t in titles:
        data[t] = fetch(t)
        print(t, data[t], flush=True)
        OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
