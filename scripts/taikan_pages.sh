#!/bin/zsh
# 謡曲大観の通釈欄（各ページ下段）を NDL の IIIF から切り出して保存する。ref_frame/ref_page は目次表 data/yokyoku/taikan_toc.json の frame/page。
# usage: pages.sh pid ref_frame ref_page p_start p_end outdir  （通釈欄=下段をページ単位で切り出す）
pid=$1; rf=$2; rp=$3; ps=$4; pe=$5; out=$6; mkdir -p $out
c=$(( rf - rp/2 ))
for p in $(seq $ps $pe); do f=$(( p/2 + c )); n=$(printf %07d $f)
  if (( p % 2 == 0 )); then x=46; else x=9; fi
  curl -sL "https://dl.ndl.go.jp/api/iiif/$pid/R$n/pct:$x,60,44,36/1700,/0/default.jpg" -o $out/$p.jpg
done
