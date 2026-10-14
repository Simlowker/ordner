// Ordner tool views (new file; harness MIT notice in ../../../LICENSE), registered under `tool.call.toolview` (ui-tool
// README, "Registering a business tool view"); reading of the call/result blocks follows ui-skill's SkillRow.
// - PrepareActionCard, key mcp__ordner__prepare_action: what was prepared, nothing sent, link to the cockpit.
// - OrdnerToolRow, every other Ordner tool: a plain-language title, the raw wire name, input and result on expand.
// Display only: the tool text the model sees is unchanged.
import { useState, type CSSProperties } from 'react'
import { DisclosureRow, IconInspectOutlineRegular, IconSparkleRegular } from '@deepseek-ai/dsh-client-ui-primitives'

/** Cockpit page of the prepared action (the cockpit is the only place where an action is validated). */
const COCKPIT = 'http://127.0.0.1:8000/'

/** Wire prefix of the Ordner MCP tools (ordner.harness.proxy PREFIX). */
export const PREFIX = 'mcp__ordner__'

/** The slice of ToolCallViewProps these views read (ui-tool contract/slots.ts). */
type Block = {
  argsRaw?: string
  kind?: string
  content?: { type: string, text?: string }[]
  call?: { argsRaw?: string }
  isError?: boolean
  error?: { code?: string }
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

/** Pretty JSON when the text is JSON, else the text as is. */
function pretty(text: string): string {
  try {
    return JSON.stringify(JSON.parse(text), null, 2)
  } catch {
    return text
  }
}

const firstLine = (s: string): string => s.split('\n', 1)[0] ?? ''

/**
 * The row's view model: tool short name (a call carried by ask_user keeps its own name, see the proxy's CARRIER),
 * state, first string argument other than an id as summary, and the raw input and result for the expanded details.
 * @param props - phase, block and wire name of the keyed toolview.
 * @returns the fields shown.
 */
export function rowModel({ phase, block, toolName }: Pick<Props, 'phase' | 'block'> & { toolName: string }) {
  const settled = phase === 'result'
  const argsRaw = (settled ? block.call?.argsRaw : block.argsRaw) ?? ''
  const args = obj(argsRaw)
  const output = settled ? (block.content ?? []).map(c => c.type === 'text' ? c.text ?? '' : JSON.stringify(c)).join('\n') : ''
  // Ids (subject_id, case_id...) mean nothing to the person: they stay in the expanded input.
  const summary = Object.entries(args).find(([k, v]) => !k.endsWith('_id') && !k.startsWith('__') && str(v) !== undefined)?.[1] as string | undefined
  return {
    name: str(args.__ordner_name__) ?? toolName.replace(PREFIX, ''),
    state: !settled ? 'running' : block.error?.code === 'interrupted' ? 'stopped' : block.isError === true ? 'error' : 'ok',
    summary: summary !== undefined ? firstLine(summary) : '',
    argsRaw,
    output,
  }
}

const IO_CARD: CSSProperties = {
  margin: '4px 0 4px 4px', border: '0.5px solid var(--dsw-alias-border-l1)', borderRadius: 'var(--dsw-radius-lg)',
  background: 'var(--dsw-alias-markdown-code-block)', font: 'var(--dsw-font-markdown-code-block-small)', overflow: 'hidden',
}
const IO_SECTION: CSSProperties = {
  display: 'grid', gridTemplateColumns: 'max-content 1fr', columnGap: 14, alignItems: 'baseline', padding: '10px 16px',
  maxHeight: 180, overflowY: 'auto', borderTop: '0.5px solid var(--dsw-alias-border-l2)',
}
const IO_LABEL: CSSProperties = { color: 'var(--dsw-alias-label-caption)' }
const IO_TEXT: CSSProperties = {
  minWidth: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: 'var(--dsw-alias-label-secondary)',
}
const SEP: CSSProperties = {
  flex: 'none', width: 2, height: 2, borderRadius: 1, margin: '0 8px', background: 'var(--dsw-alias-label-caption)',
}
const SUMMARY: CSSProperties = {
  flex: '1 1 auto', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
  fontSize: 'var(--dsh-content-font-size-secondary, 13px)',
}
const INSPECT: CSSProperties = {
  display: 'inline-flex', alignSelf: 'flex-start', alignItems: 'center', gap: 4, margin: '2px 0 2px 4px', padding: '2px 6px',
  border: 0, borderRadius: 6, background: 'transparent', color: 'var(--dsw-alias-label-tertiary)', font: 'inherit',
  fontSize: 12, cursor: 'pointer',
}

/**
 * One Ordner tool call as a process row: plain-language title and first argument; on expand, the wire tool name,
 * the input and the result as recorded (transparency: nothing hidden, only labelled).
 * @param props - keyed toolview payload plus the `ordner` locale seat.
 * @returns the row.
 */
export function OrdnerToolRow(props: Props & { toolName: string, inspect?: (() => void) | undefined }) {
  const { t, toolName, inspect } = props
  const m = rowModel(props)
  const [open, setOpen] = useState(false)
  const key = `tool.${m.name}`
  const title = t(key) !== key ? t(key) : m.name
  const expandable = props.phase !== 'preparing'
  const summary = m.state === 'error' && m.output !== '' ? firstLine(m.output) : m.summary
  const color = m.state === 'error' ? 'var(--dsw-alias-state-error-primary)'
    : m.state === 'stopped' ? 'var(--dsw-alias-state-warn-label)' : undefined
  const section = (label: string, text: string) => (
    <div style={IO_SECTION}><span style={IO_LABEL}>{label}</span><span style={IO_TEXT}>{text}</span></div>
  )
  return (
    <div data-tool={toolName} data-state={m.state}>
      <DisclosureRow
        icon={<IconSparkleRegular size={14} />}
        title={title}
        running={m.state === 'running'}
        open={open && expandable}
        expandable={expandable}
        expandOnRowClick
        keepContentWhenOpen
        onToggle={() => { setOpen(v => !v) }}
        collapsedContent={summary !== '' ? <><span style={SEP} aria-hidden /><span style={{ ...SUMMARY, color }}>{summary}</span></> : null}
      >
        <div style={IO_CARD}>
          <div style={{ ...IO_SECTION, borderTop: 0 }}><span style={IO_LABEL}>{t('row.tool')}</span><code style={IO_TEXT}>{toolName}</code></div>
          {section(t('row.input'), pretty(m.argsRaw))}
          {m.output !== '' ? section(t('row.output'), pretty(m.output)) : null}
        </div>
        {inspect !== undefined ? (
          <button type="button" style={INSPECT} onClick={inspect}><IconInspectOutlineRegular />{t('row.inspect')}</button>
        ) : null}
      </DisclosureRow>
    </div>
  )
}

/** The `ordner` namespace, per language (en is the required fallback). `tool.<name>` keys also list the tools that get
 * an OrdnerToolRow (index.ts). */
export const CARD_DICTS: Record<string, Record<string, string>> = {
  en: {
    'tool.case_load': 'Reading the dossier', 'tool.knowledge_search': 'Searching the official sources',
    'tool.rules_evaluate': 'Checking the rules', 'tool.case_record': 'Note to the dossier',
    'tool.piece_recevoir': 'Document received', 'tool.document_read': 'Reading a document',
    'tool.document_decode': 'Reading the barcode', 'tool.expert_run': 'Tax statement extraction',
    'tool.impots_preparer_declaration': 'Preparing the tax return',
    'tool.lamal_revoir_franchise': 'Deductible and health insurer',
    'tool.poursuite_repondre': 'Responding to the debt collection',
    'tool.demenagement_annoncer': 'Moving notification', 'tool.ask_user': 'Question for you', 'row.tool': 'Tool',
    'row.input': 'Input', 'row.output': 'Result', 'row.inspect': 'Show in the trajectory',
    'kind.form_entry': 'form entry', 'kind.letter': 'letter', 'kind.email_draft': 'email draft', 'kind.payment': 'payment',
    'kind.reminder': 'reminder', 'kind.document_request': 'document request',
    'action.title': 'Prepared action', 'action.refused': 'Action not prepared', 'action.preparing': 'Preparing the action…',
    'action.notSent': 'Prepared, nothing is sent.', 'action.open': 'Open in Ordner',
  },
  fr: {
    'tool.case_load': 'Lecture du dossier', 'tool.knowledge_search': 'Recherche dans les sources officielles',
    'tool.rules_evaluate': 'Vérification des règles', 'tool.case_record': 'Note au dossier',
    'tool.piece_recevoir': 'Pièce reçue', 'tool.document_read': 'Lecture d’un document',
    'tool.document_decode': 'Lecture du code-barres', 'tool.expert_run': 'Extraction du relevé fiscal',
    'tool.impots_preparer_declaration': 'Préparation de la déclaration',
    'tool.lamal_revoir_franchise': 'Franchise et caisse maladie',
    'tool.poursuite_repondre': 'Réponse à la poursuite', 'tool.demenagement_annoncer': 'Annonce de déménagement',
    'tool.ask_user': 'Question à vous', 'row.tool': 'Outil', 'row.input': 'Entrée', 'row.output': 'Résultat',
    'row.inspect': 'Voir dans la trajectoire',
    'kind.form_entry': 'saisie de formulaire', 'kind.letter': 'lettre', 'kind.email_draft': 'brouillon de courriel',
    'kind.payment': 'paiement', 'kind.reminder': 'rappel', 'kind.document_request': 'demande de document',
    'action.title': 'Action préparée', 'action.refused': 'Action non préparée', 'action.preparing': 'Préparation de l’action…',
    'action.notSent': 'Préparée, rien n’est envoyé.', 'action.open': 'Ouvrir dans Ordner',
  },
  de: {
    'tool.case_load': 'Dossier lesen', 'tool.knowledge_search': 'Suche in den amtlichen Quellen',
    'tool.rules_evaluate': 'Prüfung der Regeln', 'tool.case_record': 'Notiz im Dossier',
    'tool.piece_recevoir': 'Unterlage erhalten', 'tool.document_read': 'Dokument lesen',
    'tool.document_decode': 'Barcode lesen', 'tool.expert_run': 'Auslesen des Steuerausweises',
    'tool.impots_preparer_declaration': 'Vorbereitung der Steuererklärung',
    'tool.lamal_revoir_franchise': 'Franchise und Krankenkasse',
    'tool.poursuite_repondre': 'Antwort auf die Betreibung', 'tool.demenagement_annoncer': 'Umzugsmeldung',
    'tool.ask_user': 'Frage an Sie', 'row.tool': 'Werkzeug', 'row.input': 'Eingabe', 'row.output': 'Ergebnis',
    'row.inspect': 'In der Trajektorie zeigen',
    'kind.form_entry': 'Formulareintrag', 'kind.letter': 'Brief', 'kind.email_draft': 'E-Mail-Entwurf', 'kind.payment': 'Zahlung',
    'kind.reminder': 'Erinnerung', 'kind.document_request': 'Dokumentenanfrage',
    'action.title': 'Vorbereitete Aktion', 'action.refused': 'Aktion nicht vorbereitet', 'action.preparing': 'Aktion wird vorbereitet…',
    'action.notSent': 'Vorbereitet, nichts wird gesendet.', 'action.open': 'In Ordner öffnen',
  },
  it: {
    'tool.case_load': 'Lettura del dossier', 'tool.knowledge_search': 'Ricerca nelle fonti ufficiali',
    'tool.rules_evaluate': 'Verifica delle regole', 'tool.case_record': 'Nota nel dossier',
    'tool.piece_recevoir': 'Documento ricevuto', 'tool.document_read': 'Lettura di un documento',
    'tool.document_decode': 'Lettura del codice a barre', 'tool.expert_run': 'Estrazione dell’estratto fiscale',
    'tool.impots_preparer_declaration': 'Preparazione della dichiarazione',
    'tool.lamal_revoir_franchise': 'Franchigia e cassa malati', 'tool.poursuite_repondre': 'Risposta all’esecuzione',
    'tool.demenagement_annoncer': 'Notifica di trasloco', 'tool.ask_user': 'Domanda per lei',
    'row.tool': 'Strumento', 'row.input': 'Input', 'row.output': 'Risultato',
    'row.inspect': 'Mostra nella traiettoria',
    'kind.form_entry': 'compilazione di modulo', 'kind.letter': 'lettera', 'kind.email_draft': 'bozza di e-mail',
    'kind.payment': 'pagamento', 'kind.reminder': 'promemoria', 'kind.document_request': 'richiesta di documento',
    'action.title': 'Azione preparata', 'action.refused': 'Azione non preparata', 'action.preparing': 'Preparazione dell’azione…',
    'action.notSent': 'Preparata, nulla viene inviato.', 'action.open': 'Aprire in Ordner',
  },
}
