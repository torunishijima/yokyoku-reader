#!/usr/bin/env python3
"""曲の一覧データ data/yokyoku/index.json を、data/yokyoku/kyoku/ にある曲データから作る。
曲順は謡曲大観の目次順。曲データを作り直したら（build_kyoku.py）、このスクリプトも実行し直す。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
YK = ROOT / "data" / "yokyoku"
toc = json.loads((YK / "taikan_toc.json").read_text(encoding="utf-8"))

index = []
for x in toc:
    f = YK / "kyoku" / f"{x['title']}.json"
    if not f.exists():
        continue
    d = json.loads(f.read_text(encoding="utf-8"))
    info = d.get("info", {})
    index.append({
        "title": d["title"],
        "yomi": x.get("yomi", ""),
        "volume": d["volume"],
        "pages": d["pages"],
        "nougara": info.get("能柄", ""),
        "toki": info.get("時", ""),
        "check": d["check"]["status"],
    })

missing = [r["title"] for r in index if not r["yomi"]]
if missing:
    print("読み仮名がない曲（taikan_toc.json の yomi に足す）:", " ".join(missing))

out = YK / "index.json"
out.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"{out.relative_to(ROOT)}: {len(index)}曲（大観の目次 {len(toc)}曲中）")
