#!/usr/bin/env bash
# Réf : consigne formateur, version figée d'un livrable = Markdown -> HTML -> CSS de pagination -> PDF.
# Usage : md2pdf.sh "fichier.md" [sortie.pdf]. Sans sortie, le PDF est écrit à côté du .md.
set -euo pipefail

src="$1"
out="${2:-${src%.md}.pdf}"
here="$(cd "$(dirname "$0")" && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

title="$(grep -m1 '^# ' "$src" | sed 's/^# //; s/&/\&amp;/g; s/</\&lt;/g')"
css_title="$(grep -m1 '^# ' "$src" | sed 's/^# //; s/\\/\\\\/g; s/"/\\"/g')"
logo="$(base64 -w0 "$here/logo-icon.png")"

npx --yes marked@18 --gfm -i "$src" -o "$work/body.html"
sed -i 's/ \([:;?!»]\)/\xc2\xa0\1/g; s/« /«\xc2\xa0/g' "$work/body.html"
# Les marqueurs de preuve du rapport EC04 deviennent des pastilles, comme les badges d'état de l'application.
sed -i -E 's#\[Prouvé\]#<span class="badge ok">Prouvé</span>#g; s#\[Constaté\]#<span class="badge warn">Constaté</span>#g; s#\[Absent\]#<span class="badge no">Absent</span>#g; s#<strong>((<span class="badge[^"]*">[^<]*</span> ?)+)</strong>#\1#g' "$work/body.html"

{
  printf '<!doctype html>\n<html lang="fr"><head><meta charset="utf-8"><title>%s</title><style>\n' "$title"
  cat "$here/md2pdf.css"
  # Piège : Chromium ignore `string-set`, le titre du pied de page est donc écrit en dur ici.
  printf '\n@page { @bottom-left { content: "%s"; } }\n' "$css_title"
  printf '\n</style></head><body>\n'
  printf '<div class="brand"><div class="lockup"><img src="data:image/png;base64,%s" alt=""><span class="name">EnerVision</span></div><div class="meta">EADL 2026 · Groupe 3</div></div>\n' "$logo"
  cat "$work/body.html"
  printf '\n</body></html>\n'
} > "$work/doc.html"

chromium --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$out" "file://$work/doc.html" 2>/dev/null

echo "PDF écrit : $out"
