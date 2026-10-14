// Ordner tool card for prepare_action (new file; harness MIT notice in ../../../LICENSE). Registered under
// `tool.call.toolview`, key mcp__ordner__prepare_action (ui-tool README, "Registering a business tool view"); reading
// of the call/result blocks follows ui-skill's SkillRow. Display only: the tool text the model sees is unchanged.
import type { CSSProperties } from 'react'

/** Cockpit page of the prepared action (the cockpit is the only place where an action is validated). */
const COCKPIT = 'http://127.0.0.1:8000/'

/** The slice of ToolCallViewProps this card reads (ui-tool contract/slots.ts). */
type Block = {
  argsRaw?: string
  kind?: string
  content?: { type: string, text?: string }[]
  call?: { argsRaw?: string }
}
type Props = { phase: 'preparing' | 'start' | 'result', block: Block, t: (key: string) => string }

/** Parsed JSON object, or {} when the text is not one (streaming prefix, foreign shape). */
function obj(text: string | undefined): Record<string, unknown> {
  try {
    const v: unknown = JSON.parse(text ?? '')
    return typeof v === 'object' && v !== null ? v as Record<string, unknown> : {}
  } catch {
    return {}
  }
}

const str = (v: unknown): string | undefined => typeof v === 'string' && v !== '' ? v : undefined

/**
 * The card's view model from the durable call slice: arguments, and the ordner.harness.mcp_server result
 * `{"tool": "prepare_action", "result": {...}}`.
 * @param props - phase and block of the keyed toolview.
 * @returns the fields shown.
 */
export function actionModel({ phase, block }: Pick<Props, 'phase' | 'block'>) {
  const args = obj(phase === 'result' ? block.call?.argsRaw : block.argsRaw)
  const text = (block.content ?? []).map(c => c.text ?? '').join('')
  const parsed = obj(text)
  const result = typeof parsed.result === 'object' && parsed.result !== null ? parsed.result as Record<string, unknown> : parsed
  const caseId = str(args.case_id)
  const amount = typeof args.amount === 'number' ? `CHF ${args.amount.toFixed(2)}` : undefined
  return {
    state: phase !== 'result' ? 'running' : str(result.error) !== undefined ? 'refused' : 'prepared',
    summary: str(args.summary) ?? '',
    kind: str(args.kind),
    details: [str(args.recipient), str(args.subject), amount].filter(Boolean).join(' · '),
    error: str(result.error),
    warning: str(result.warning),
    href: COCKPIT + (caseId !== undefined ? `#/case/${encodeURIComponent(caseId)}` : '#/cases'),
  }
}

const CARD: CSSProperties = {
  margin: '6px 0', padding: '10px 12px', border: '1px solid var(--dsw-alias-border-l4, #e3e3e7)', borderRadius: 8,
  font: '14px/1.45 var(--dsh-font-family-text-default)', color: 'var(--dsw-alias-label-primary, #111113)',
}
const MUTED: CSSProperties = { color: 'var(--dsw-alias-label-tertiary, #5b5b64)', fontSize: 13 }
const RED: CSSProperties = { color: 'var(--dsw-static-deepseek-600, #b8231a)' }

/**
 * One prepare_action call: what was prepared, that nothing is sent, and the way to the cockpit to validate it.
 * @param props - keyed toolview payload plus the `ordner` locale seat.
 * @returns the card.
 */
export function PrepareActionCard(props: Props) {
  const { t } = props
  const m = actionModel(props)
  const kind = m.kind !== undefined && t(`kind.${m.kind}`) !== `kind.${m.kind}` ? t(`kind.${m.kind}`) : m.kind
  return (
    <div style={CARD} data-tool="prepare_action" data-state={m.state}>
      <div style={{ ...MUTED, fontWeight: 600 }}>
        {t(m.state === 'refused' ? 'action.refused' : 'action.title')}{kind !== undefined ? ` · ${kind}` : ''}
      </div>
      {m.summary !== '' ? <div style={{ marginTop: 2 }}>{m.summary}</div> : null}
      {m.details !== '' ? <div style={MUTED}>{m.details}</div> : null}
      {m.error !== undefined ? <div style={{ ...MUTED, ...RED }}>{m.error}</div> : null}
      {m.warning !== undefined ? <div style={{ ...RED, fontSize: 13, marginTop: 4 }}>{m.warning}</div> : null}
      {m.state === 'prepared' ? (
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 6, ...MUTED }}>
          <span>{t('action.notSent')}</span>
          <a href={m.href} target="_blank" rel="noreferrer" style={{ ...RED, fontWeight: 600 }}>{t('action.open')}</a>
        </div>
      ) : m.state === 'running' ? <div style={MUTED}>{t('action.preparing')}</div> : null}
    </div>
  )
}

/** The `ordner` namespace, per language (en is the required fallback). */
export const CARD_DICTS: Record<string, Record<string, string>> = {
  en: {
    'kind.form_entry': 'form entry', 'kind.letter': 'letter', 'kind.email_draft': 'email draft', 'kind.payment': 'payment',
    'kind.reminder': 'reminder', 'kind.document_request': 'document request',
    'action.title': 'Prepared action', 'action.refused': 'Action not prepared', 'action.preparing': 'Preparing the action…',
    'action.notSent': 'Prepared, nothing is sent.', 'action.open': 'Open in Ordner',
  },
  fr: {
    'kind.form_entry': 'saisie de formulaire', 'kind.letter': 'lettre', 'kind.email_draft': 'brouillon de courriel',
    'kind.payment': 'paiement', 'kind.reminder': 'rappel', 'kind.document_request': 'demande de document',
    'action.title': 'Action préparée', 'action.refused': 'Action non préparée', 'action.preparing': 'Préparation de l’action…',
    'action.notSent': 'Préparée, rien n’est envoyé.', 'action.open': 'Ouvrir dans Ordner',
  },
  de: {
    'kind.form_entry': 'Formulareintrag', 'kind.letter': 'Brief', 'kind.email_draft': 'E-Mail-Entwurf', 'kind.payment': 'Zahlung',
    'kind.reminder': 'Erinnerung', 'kind.document_request': 'Dokumentenanfrage',
    'action.title': 'Vorbereitete Aktion', 'action.refused': 'Aktion nicht vorbereitet', 'action.preparing': 'Aktion wird vorbereitet…',
    'action.notSent': 'Vorbereitet, nichts wird gesendet.', 'action.open': 'In Ordner öffnen',
  },
  it: {
    'kind.form_entry': 'compilazione di modulo', 'kind.letter': 'lettera', 'kind.email_draft': 'bozza di e-mail',
    'kind.payment': 'pagamento', 'kind.reminder': 'promemoria', 'kind.document_request': 'richiesta di documento',
    'action.title': 'Azione preparata', 'action.refused': 'Azione non preparata', 'action.preparing': 'Preparazione dell’azione…',
    'action.notSent': 'Preparata, nulla viene inviato.', 'action.open': 'Aprire in Ordner',
  },
}
