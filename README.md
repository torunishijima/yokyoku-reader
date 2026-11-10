# 謡曲リーダー

佐成謙太郎『謡曲大観』の本文（謡の詞章）と通釈（現代語訳）を、段ごとに並べて読む静的Webアプリ。
本文・通釈・曲情報は、すべて大観の印刷面を OCR で読み取ったもの。本文の確認が済んだ曲から順に載せる。

## 起動

```sh
cd yokyoku-reader
python3 -m http.server 8765
# → http://127.0.0.1:8765/
```

index.html をファイルとして直接開くとデータを読み込めないため、ローカルサーバー経由で開く。

## 曲を追加したとき

確認作業（[docs/ocr_check.md](docs/ocr_check.md)）で `work/fixes/<曲>.tsv` ができたら：

1. `python3 scripts/build_kyoku.py <曲名>` で `data/yokyoku/kyoku/<曲名>.json` を作る（曲名を省くと確認済みの全曲）
2. `python3 scripts/build_index.py` で一覧データ `data/yokyoku/index.json` を作り直す
3. `python3 scripts/info_check.py <曲名>` で梗概・人物・通釈の誤りの疑いを拾い、原本で確かめる。梗概を原本と全文照合するまで公開しない（[docs/ocr_check.md](docs/ocr_check.md) の「曲情報・通釈の確認」）

## データと権利

| データ | 出典 | 条件 |
|---|---|---|
| 本文・通釈・曲情報 `data/yokyoku/kyoku/` | 佐成謙太郎『謡曲大観』明治書院 1930–31（[国立国会図書館デジタルコレクション](https://dl.ndl.go.jp/pid/1884285)） | パブリックドメイン（著者1966年没） |
| 文字起こし | [NDLOCR-Lite](https://github.com/ndl-lab/ndlocr-lite)（国立国会図書館） | CC BY 4.0 |

本文の作り方（OCR）と確認の方法・範囲は [docs/taikan_ocr.md](docs/taikan_ocr.md)。
OCR の確認には、半魚文庫「謡曲三百五十番集」の本文を照合用に使っている（このリポジトリには収録していない。[docs/hangyo.md](docs/hangyo.md)）。

## ライセンス

- **データと文書**（`data/yokyoku/`・`work/fixes/`・`docs/`）：[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.ja)。自由に複製・改変・再配布できます（商用も可）。その際は「謡曲リーダー（西嶋徹）」と出典を示し、手を加えた場合はその旨を示してください。底本の『謡曲大観』自体はパブリックドメインです。
- **プログラム**（`app.js`・`index.html`・`style.css`・`scripts/`）：MIT License（[LICENSE](LICENSE)）。
- 本文には OCR の誤りが残っている可能性があります。正しさは保証しません。

謡曲の本文には、人権に関わる用語が原本どおり含まれているものがあります。資料としての性格から原文のまま収録しています。
