// Forked from deepseek-harness@d743267 packages/client/ui-brand-official/src/client/index.ts (MIT, Copyright (c) 2026
// DeepSeek). Ordner: always active (no `official` build condition), fills the hero mark too, registers fr/de/it, the
// prepare_action card and the labelled rows of the other Ordner tools.
/** Ordner occupants for the generic browser-brand slots, plus Ordner's language packs. */
import type { Context as ClientContext } from '@deepseek-ai/cordis'
import type {} from '@deepseek-ai/dsh-client-ui-renderer/client'
import type {} from '@deepseek-ai/dsh-client-ui-sidebar/client'
import { OrdnerMark, OrdnerName } from './Brand.tsx'
import { LANGUAGES } from './locales.ts'
import { CARD_DICTS, OrdnerToolRow, PREFIX, PrepareActionCard } from './ToolCards.tsx'

/** Required services: the UI slot registry and the locale service. */
export const inject = ['slots', 'locale']

/**
 * Fill the sidebar brand slots as one registration set and the conversation hero mark, then register the
 * language definitions and their dictionaries as owned effects.
 * @param ctx - Client root context.
 */
export function apply(ctx: ClientContext): void {
  ctx.slots.inject('sidebar.brand.mark', () =>
    ctx.slots.inject('sidebar.brand.name', function* () {
      yield ctx.slots.register({ name: 'sidebar.brand.mark' }, OrdnerMark)
      yield ctx.slots.register({ name: 'sidebar.brand.name' }, OrdnerName)
    }))
  ctx.slots.inject('conversation.hero.brand.mark', () =>
    ctx.slots.register({ name: 'conversation.hero.brand.mark' }, OrdnerMark))
  // ponytail: untyped access, ctx.locale's augmentation lives in a package this one does not depend on.
  const locale = (ctx as unknown as { locale: {
    addLanguage(l: { id: string, label: string, fallback: string }): () => void
    register(ns: string, id: string, dict: Record<string, string>): () => void
  } }).locale
  for (const [id, dict] of Object.entries(CARD_DICTS)) ctx.effect(() => locale.register('ordner', id, dict), `ordner: ${id} cards`)
  const tools = Object.keys(CARD_DICTS.en ?? {}).filter(k => k.startsWith('tool.')).map(k => PREFIX + k.slice(5))
  ctx.slots.inject('tool.call.toolview', function* () {
    yield ctx.slots.register(
      { name: 'tool.call.toolview', key: PREFIX + 'prepare_action', locale: 'ordner' } as never, PrepareActionCard as never)
    for (const key of tools) {
      yield ctx.slots.register({ name: 'tool.call.toolview', key, locale: 'ordner' } as never, OrdnerToolRow as never)
    }
  })
  for (const { id, label, dicts } of LANGUAGES) {
    ctx.effect(() => locale.addLanguage({ id, label, fallback: 'en' }), `ordner: ${id}`)
    for (const [ns, dict] of Object.entries(dicts)) ctx.effect(() => locale.register(ns, id, dict), `ordner: ${id} ${ns}`)
  }
}
