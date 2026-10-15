#!/usr/bin/env bash
# technical_report.md -> Meotis_Report.pdf (A4, Times 10 pt): pandoc to HTML, headless Chrome to PDF.
# The "## Placeholders" fill table at the end of the report is not part of the PDF.
set -euo pipefail
cd "$(dirname "$0")/.."
tmp=$(mktemp -d)
sed '/^## Placeholders/,$d' technical_report.md > "$tmp/report.md"
cp docs/report.css "$tmp/style.css"
pandoc "$tmp/report.md" -s --css style.css --metadata pagetitle="Meotis — Ordner" -o "$tmp/report.html"
CHROME=${CHROME:-"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"}
(cd "$tmp" && "$CHROME" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="$tmp/out.pdf" report.html 2>/dev/null)
mv "$tmp/out.pdf" Meotis_Report.pdf && rm -rf "$tmp"
grep -o "{{[a-z0-9_]*}}" <(sed '/^## Placeholders/,$d' technical_report.md) | sort -u | sed 's/^/unfilled: /' || true
echo "Meotis_Report.pdf written"
