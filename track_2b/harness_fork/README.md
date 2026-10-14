# Ordner brand fork of the DeepSeek Harness web UI

Ordner's conversation view runs on the DeepSeek Harness web UI, re-branded. This folder holds the forked files, under
the upstream MIT licence ([LICENSE](LICENSE), Copyright (c) 2026 DeepSeek), separate from the Apache-2.0 code of Ordner.

- Upstream: [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness), version 0.2.1-alpha.2,
  commit `d743267` (npm `@deepseek-ai/dsh@0.2.1-alpha.2`).
- Ordner is not affiliated with DeepSeek. The DeepSeek name and whale are removed from the product UI
  (upstream `BRAND_GUIDELINES.md`); the UI states "construite sur DeepSeek Harness (licence MIT)".

## Changed files

| Fork file                                                               | Upstream file                                             | Change                                                                                                                                                                                  |
| ----------------------------------------------------------------------- | --------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ui-brand-official/src/client/index.ts`                                 | `packages/client/ui-brand-official/src/client/index.ts`   | Always active (no `official` build condition); fills `sidebar.brand.mark`, `sidebar.brand.name` and `conversation.hero.brand.mark`; registers the fr, de and it languages (fallback en) |
| `ui-brand-official/src/client/Brand.tsx`                                | same path                                                 | Ordner mark (white Swiss cross on red, inline SVG) and name instead of the whale and wordmark                                                                                           |
| `ui-brand-official/src/client/locales.ts`                               | (new)                                                     | Partial fr/de/it dictionaries for the main surfaces (sidebar, welcome screen, composer, chat, trajectory) and the preview notice, rewritten as Ordner's prototype notice                |
| `ui-brand-official/src/client/ToolCards.tsx` | (new) | Card for `mcp__ordner__prepare_action` in the `tool.call.toolview` slot: summary, recipient, "Préparée, rien n’est envoyé." and a link to the action's case in the cockpit (`http://127.0.0.1:8000/#/case/<id>`); the tool text sent to the model is unchanged |
| `ui-theme/src/styles/design-platform.css`                               | `packages/client/ui-theme/src/styles/design-platform.css` | Accent scale `--dsw-static-deepseek-*` in Swiss red (500 = #D52B1E), light and dark; brand colour literal; neutral light user bubble and active sidebar row                             |
| `ui-theme/src/styles/base.css`                                          | `packages/client/ui-theme/src/styles/base.css`            | Brand font = system stack (no Montserrat); running whale hidden                                                                                                                         |
| `dist/favicon.svg`, `dist/favicon-dark.svg`                             | `apps/web/public/` (served from `apps/web/dist/`)         | Ordner mark                                                                                                                                                                             |
| `dist/manifest.webmanifest`                                             | same                                                      | Name "Ordner"                                                                                                                                                                           |
| (patched by `apply.sh`)                                                 | `apps/web/dist/index.html`, `preview.html`                | `<title>Ordner</title>`                                                                                                                                                                 |
| (patched by `apply.sh --installed`) | `lib/client.js` of the published `@deepseek-ai/dsh-client-ui-layout` | Window title: the official npm build inlines `"DeepSeek Harness"`, replaced by `"Ordner"` (the checkout build reads `brand.localBuild` instead) |
| `build/ui-brand-official/lib/client.js`, `build/ui-theme/lib/client.js` | `lib/client.js` of both packages                          | Bundles built from the files above with upstream tsdown (committed, for Docker)                                                                                                         |

Each forked source file starts with a line naming its upstream path and the MIT notice.

## Apply

```bash
# Harness checkout (pnpm, built): copy sources, rebuild the two plugin bundles (~1-2 s each), refresh build/,
# patch apps/web/dist. Idempotent.
bash harness_fork/apply.sh work/vendor/deepseek-harness

# npm install (Docker): copy build/ and dist/ over the installed packages, no build tools needed.
bash harness_fork/apply.sh --installed /usr/local/lib/node_modules
```

The UI language is chosen by the web overlay (`locale` `preference: fr`, in `src/ordner/harness/web.patch.yml`); de and
it can be picked in Réglages > Général. Strings not in the packs stay in English.

## Not changed

Static libraries linked into the Vite shell (`ui-primitives`, React, Cordis) and every other plugin. Settings pages
(account, models, plugins) keep upstream wording, including "DeepSeek Account".
