# 謡曲リーダー

謡曲352曲の原文と、佐成謙太郎『謡曲大観』の通釈（現代語訳）を段ごとに並べて読む静的Webアプリ。

## 起動

```sh
cd yokyoku-reader
python3 -m http.server 8765
# → http://127.0.0.1:8765/
```

index.html をファイルとして直接開くとデータを読み込めないため、ローカルサーバー経由で開く。

## 通釈を追加したとき

1. `data/yokyoku/taikan/<曲名>.json` を置く（形式は [docs/taikan.md](docs/taikan.md)）
2. `python3 scripts/build_index.py` で一覧データ `data/yokyoku/index.json` を作り直す

## データと権利

| データ | 出典 | 条件 |
|---|---|---|
| 原文 `data/yokyoku/hangyo/` | [半魚文庫「謡曲三百五十番集」](https://hangyo.sakura.ne.jp/utahi/) | フリーデータ。直接の商用利用は不可。著作権は底本校訂者と JALLC が共有 |
| 通釈 `data/yokyoku/taikan/` | 佐成謙太郎『謡曲大観』明治書院 1930–31（[国立国会図書館デジタルコレクション](https://dl.ndl.go.jp/pid/1884285)） | パブリックドメイン（著者1966年没） |

半魚文庫の改変内容と照合結果は [docs/hangyo.md](docs/hangyo.md)。

謡曲の本文には、人権に関わる用語が原本どおり含まれているものがあります（半魚文庫凡例による注記）。資料としての性格から原文のまま収録しています。
