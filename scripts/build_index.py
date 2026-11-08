#!/usr/bin/env python3
"""謡曲の一覧データ data/yokyoku/index.json を実データから作り直す。

半魚文庫の manifest.json と、data/yokyoku/taikan/ にある通釈データを突き合わせる。
通釈を追加・差し替えしたら、このスクリプトを実行し直すこと。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
YK = ROOT / "data" / "yokyoku"

manifest = json.loads((YK / "hangyo" / "manifest.json").read_text(encoding="utf-8"))

taikan = {}
for p in sorted((YK / "taikan").glob("*.json")):
    d = json.loads(p.read_text(encoding="utf-8"))
    taikan[d["hangyo_file"]] = p.name

index = []
for r in manifest:
    index.append({
        "file": r["file"],
        "title": r["title"],
        "number": r["number"],
        "series": r["series"],
        "season": r["season"],
        "cast": r["cast"],
        "chars": r["chars"],
        "source_text": r.get("source_text"),
        "taikan": taikan.get(r["file"]),
    })

missing = set(taikan) - {r["file"] for r in manifest}
if missing:
    raise SystemExit(f"manifest にない hangyo_file を指す通釈データがあります: {sorted(missing)}")

out = YK / "index.json"
out.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"{out.relative_to(ROOT)}: {len(index)}曲（通釈あり {len(taikan)}曲）")
