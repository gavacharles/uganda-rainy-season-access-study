#!/bin/sh
# Republish the public map (https://gavacharles.github.io/uganda-rainy-season-access/)
# after rebuilding it with 10_interactive_map.py. Copies web/index.html into site/
# (a separate git repo holding only the public page) and pushes it; GitHub Pages
# redeploys within a minute or two.
set -e
cd "$(dirname "$0")/.."
cp web/index.html site/index.html
cd site
if git diff --quiet; then echo "site already up to date"; exit 0; fi
git add index.html
git commit -m "Update map"
git push
