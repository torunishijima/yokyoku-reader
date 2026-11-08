#!/usr/bin/env python3
"""data/yokyoku/taikan/*.json の形式と、原文（半魚文庫）との段の対応を検査する。"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
YK = ROOT / "data" / "yokyoku"
TYPES = {"speech", "note", "gloss", "narration", "heading"}
KANJI = "一二三四五六七八九十"
def label(n):
    return KANJI[n - 1] if n <= 10 else "十" + KANJI[n - 11]

errors = 0
files = sys.argv[1:] or sorted(str(p) for p in (YK / "taikan").glob("*.json"))
for f in files:
    p = Path(f); d = json.loads(p.read_text(encoding="utf-8")); errs = []
    body = (YK / "hangyo" / d["hangyo_file"]).read_text(encoding="utf-8").split("――――", 1)[1]
    pos = []
    for i, dan in enumerate(d["dan"], 1):
        if dan["no"] != i: errs.append(f"段番号が連番でない: {dan['no']}")
        if dan["label"] != label(i): errs.append(f"段{i}のlabelが{dan['label']}")
        a = dan["hangyo_anchor"]; c = body.count(a)
        if c != 1: errs.append(f"段{i}のanchorが原文に{c}回: {a}")
        pos.append(body.find(a))
        for it in dan["items"]:
            if it["type"] not in TYPES: errs.append(f"段{i}に不明なtype: {it['type']}")
            if it["type"] == "speech" and not it.get("speaker"): errs.append(f"段{i}に話者のない台詞")
            if not it.get("text", "").strip(): errs.append(f"段{i}に空のtext")
            if it.get("continued") and it["type"] != "speech": errs.append(f"段{i}: continuedはspeechのみ")
    if pos != sorted(pos): errs.append(f"anchorの順序が原文と逆転: {pos}")
    pages = [dan["page"] for dan in d["dan"]]
    if pages != sorted(pages): errs.append(f"段のページが逆転: {pages}")
    if "frame_ref" not in d["source"]: errs.append("source.frame_refがない")
    for is_ in d.get("text_issues", []):
        if is_["hangyo"] not in body.replace("\n", ""): errs.append(f"text_issuesの原文が見つからない: {is_['hangyo']}")
    n = sum(len(dan["items"]) for dan in d["dan"])
    print(f"{'NG' if errs else 'OK'} {p.name}: {len(d['dan'])}段 {n}項目")
    for e in errs: print("   -", e)
    errors += len(errs)
sys.exit(1 if errors else 0)
