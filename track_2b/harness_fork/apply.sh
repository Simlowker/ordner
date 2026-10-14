#!/usr/bin/env bash
# Apply the Ordner brand fork onto DeepSeek Harness 0.2.1-alpha.2. Idempotent.
#
#   apply.sh <harness checkout>            copy the forked sources, rebuild the two plugin bundles, refresh build/,
#                                          patch the web shell (apps/web/dist)
#   apply.sh --installed <node_modules>    copy the committed build/ bundles and shell files onto an npm install,
#                                          and set the window title inlined in the published ui-layout bundle
#                                          (e.g. /usr/local/lib/node_modules after `npm i -g @deepseek-ai/dsh`)
set -euo pipefail
FORK="$(cd "$(dirname "$0")" && pwd)"
BRAND=@deepseek-ai/dsh-client-ui-brand-official
THEME=@deepseek-ai/dsh-client-ui-theme
SHELL_FILES=(favicon.svg favicon-dark.svg manifest.webmanifest)

# Shell files and the static <title> (the live title comes from the fr pack: brand.localBuild = Ordner).
patch_dist() {
  local dist="$1" f
  for f in "${SHELL_FILES[@]}"; do cp "$FORK/dist/$f" "$dist/$f"; done
  for f in "$dist/index.html" "$dist/preview.html"; do
    [ -f "$f" ] && sed -i.bak 's#<title>[^<]*</title>#<title>Ordner</title>#' "$f" && rm -f "$f.bak"
  done
  echo "patched $dist"
}

if [ "${1:-}" = "--installed" ]; then
  root="${2:?usage: apply.sh --installed <node_modules root>}"
  n=0
  # npm may nest the plugins under @deepseek-ai/dsh/node_modules: patch every copy found.
  while IFS= read -r pkg; do
    dir="$(dirname "$pkg")"
    case "$dir" in
      */@deepseek-ai/dsh-client-ui-brand-official) cp "$FORK/build/ui-brand-official/lib/client.js" "$dir/lib/client.js" ;;
      */@deepseek-ai/dsh-client-ui-theme) cp "$FORK/build/ui-theme/lib/client.js" "$dir/lib/client.js" ;;
      */@deepseek-ai/dsh-web-frontend) patch_dist "$dir/dist" ;;
      # The published (official) build inlines the window title; the checkout build reads brand.localBuild instead.
      */@deepseek-ai/dsh-client-ui-layout)
        sed -i.bak 's/const productTitle = "DeepSeek Harness";/const productTitle = "Ordner";/' "$dir/lib/client.js"
        rm -f "$dir/lib/client.js.bak"; grep -q 'productTitle = "Ordner"' "$dir/lib/client.js" ;;
      *) continue ;;
    esac
    echo "applied to $dir"; n=$((n + 1))
  done < <(find "$root" -path '*/@deepseek-ai/dsh-client-ui-brand-official/package.json' \
                     -o -path '*/@deepseek-ai/dsh-client-ui-theme/package.json' \
                     -o -path '*/@deepseek-ai/dsh-web-frontend/package.json' \
                     -o -path '*/@deepseek-ai/dsh-client-ui-layout/package.json')
  [ "$n" -ge 4 ] || { echo "apply.sh: expected brand, theme, layout and web-frontend packages under $root, found $n" >&2; exit 1; }
  exit 0
fi

H="$(cd "${1:?usage: apply.sh <harness checkout> | --installed <node_modules root>}" && pwd)"
cp "$FORK"/ui-brand-official/src/client/*.ts* "$H/packages/client/ui-brand-official/src/client/"
cp "$FORK"/ui-theme/src/styles/*.css "$H/packages/client/ui-theme/src/styles/"
for pkg in "$BRAND" "$THEME"; do
  t0=$(date +%s)
  (cd "$H" && pnpm --filter "$pkg" bundle >/dev/null)
  echo "bundled $pkg in $(( $(date +%s) - t0 )) s"
done
cp "$H/packages/client/ui-brand-official/lib/client.js" "$FORK/build/ui-brand-official/lib/client.js"
cp "$H/packages/client/ui-theme/lib/client.js" "$FORK/build/ui-theme/lib/client.js"
patch_dist "$H/apps/web/dist"
