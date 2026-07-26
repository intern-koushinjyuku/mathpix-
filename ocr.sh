#!/bin/bash
# $1 = tool-result json path, $2 = short name
set -e
W=/tmp/claude-0/-home-user-mathpix-/f853bc60-e9f9-5cfe-97b9-33b58dabf833/scratchpad/work_india
cd $W
jq -r .content "$1" | base64 -d > f.pdf
pdftoppm -r 200 -png f.pdf pg
: > "$2.txt"
for p in pg-*.png; do tesseract "$p" stdout -l jpn 2>/dev/null >> "$2.txt"; done
rm -f f.pdf pg-*.png "$1"
wc -c "$2.txt"
