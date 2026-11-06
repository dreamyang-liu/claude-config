#!/usr/bin/env bash
# Render a behavior map with headless Chrome: a PNG next to the HTML, and its check report.
# Usage: render.sh <map.html> [<view, e.g. behavior=submit&focus=worker>] [<width>x<height>]
# Exits 0 if the report starts with OK, 1 if it lists problems, 2 if Chrome is missing.
set -euo pipefail

html=$(realpath "$1")
view=${2:-}
size=${3:-2000x2600}
builds=("$HOME"/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell)
chrome=${CHROME:-${builds[-1]}}
if [ ! -x "$chrome" ]; then
  echo "render: no headless Chrome. Set CHROME to a chrome or chrome-headless-shell binary." >&2
  exit 2
fi

url="file://$html${view:+#$view}"
suffix=$(printf '%s' "$view" | tr -c 'A-Za-z0-9_.-' '_')
png="${html%.html}${suffix:+-$suffix}.png"
# AppArmor on Ubuntu 23.10+ blocks the user namespaces of the Chrome sandbox. The page is a
# local file that we write, so it runs without the sandbox.
flags=(--no-sandbox --headless --disable-gpu --hide-scrollbars --no-first-run --window-size="${size/x/,}")

"$chrome" "${flags[@]}" --screenshot="$png" "$url" >/dev/null 2>&1
echo "render: $png"

report=$("$chrome" "${flags[@]}" --dump-dom "$url" 2>/dev/null \
  | awk '/<pre id="check-report"/ { p = 1 } p { print } p && /<\/pre>/ { exit }' \
  | sed -e 's/<[^>]*>//g' -e 's/^[[:space:]]*//' -e 's/&lt;/</g' -e 's/&gt;/>/g' -e 's/&quot;/"/g' -e 's/&amp;/\&/g')
printf '%s\n' "$report"
case "$report" in
  OK*) exit 0 ;;
  *) exit 1 ;;
esac
