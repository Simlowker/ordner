// Ordner language packs for the forked brand plugin (new file; harness MIT notice in ../../../LICENSE).
// Partial dictionaries: a missing key falls back to English, key by key (packages/client/locale/README.md).
// Keys are those of the main surfaces: sidebar, welcome screen, composer, chat steps, preview notice.

type Dicts = Record<string, Record<string, string>>

const NOTICE_FR = 'Ordner est un prototype de recherche (Hack Apertus 2026). Il prépare vos démarches administratives '
  + 'à partir de votre dossier et des sources officielles ; vous décidez. Rien n’est envoyé, déposé, signé ni payé.'
  + '\n\nLe modèle est Apertus 1.5 8B, exécuté en local. Cette interface est construite sur DeepSeek Harness (licence MIT).'
const NOTICE_DE = 'Ordner ist ein Forschungsprototyp (Hack Apertus 2026). Er bereitet Ihre Behördengänge aus Ihrem '
  + 'Dossier und den amtlichen Quellen vor; Sie entscheiden. Nichts wird gesendet, eingereicht, unterschrieben oder bezahlt.'
  + '\n\nDas Modell ist Apertus 1.5 8B, lokal ausgeführt. Diese Oberfläche basiert auf DeepSeek Harness (MIT-Lizenz).'
const NOTICE_IT = 'Ordner è un prototipo di ricerca (Hack Apertus 2026). Prepara le sue pratiche amministrative a partire '
  + 'dal suo dossier e dalle fonti ufficiali; lei decide. Nulla viene inviato, depositato, firmato o pagato.'
  + '\n\nIl modello è Apertus 1.5 8B, eseguito in locale. Questa interfaccia è costruita su DeepSeek Harness (licenza MIT).'
const SESSION_IN_USE_FR = 'Cette conversation est déjà ouverte par une autre instance d’Ordner. Fermez-la et réessayez.'

/** French, the product's first language. */
export const fr: Dicts = {
  'common': {
    'ok': 'OK', 'cancel': 'Annuler', 'close': 'Fermer', 'copy': 'Copier', 'copied': 'Copié', 'retry': 'Réessayer',
    'loading': 'Chargement…', 'load.failed': 'Échec du chargement', 'submit': 'Valider', 'submitting': 'Envoi…',
    'next': 'Suivant', 'previous': 'Précédent', 'skip': 'Passer', 'delete': 'Supprimer', 'edit': 'Modifier',
    'save': 'Enregistrer', 'search': 'Rechercher', 'more': 'Plus', 'collapse': 'Réduire', 'expand': 'Développer',
    'back': 'Retour', 'brand.localBuild': 'Ordner', 'workspace.defaultName': 'Mon dossier', 'unknown': 'Inconnu',
    'none': 'Aucun', 'truncated': 'Tronqué',
  },
  'conversation': {
    'hero.headline': 'Vos démarches, en clair',
    'hero.preview': 'Prototype',
    'hero.chooseWorkspace': 'Choisir un dossier',
    'placeholder.hero': 'Posez votre question sur votre dossier',
    'placeholder.default': 'Votre message',
    'placeholder.workspace': 'Choisissez un dossier pour commencer',
    'placeholder.unavailable': 'Conversation indisponible',
    'shortcut.newline': 'Nouvelle ligne',
    'input.commands': 'Ajouter des fichiers',
    'input.file': 'Fichier',
    'input.stop': 'Arrêter',
    'input.send': 'Envoyer',
    'input.send.queue': 'Mettre en attente',
    'context.aria': '{percent} du contexte utilisé',
    'context.used': 'du contexte utilisé',
    'context.system': 'Consigne système',
    'context.tools': 'Définitions des outils',
    'context.messages': 'Messages',
    'tool.title.generic': 'Appel d’outil',
    'row.input': 'ENTRÉE',
    'row.output': 'SORTIE',
    'row.inspect': 'Détails',
    'details.running': 'En cours…',
    'error.sessionInUse': SESSION_IN_USE_FR,
  },
  'sidebar': {
    'session.new': 'Nouvelle conversation', 'session.new.label': 'Nouvelle conversation',
    'toggle.open': 'Ouvrir le panneau latéral', 'toggle.collapse': 'Réduire le panneau latéral', 'panels.label': 'Panneaux',
  },
  'workspace': {
    'session.new': 'Nouvelle conversation', 'session.untitled': 'Sans titre', 'section.workspaces': 'Dossiers',
    'section.sessions': 'Conversations', 'empty.none': 'Aucune conversation', 'workspace.add': 'Ajouter un dossier',
    'search.sessions.aria': 'Rechercher une conversation', 'search.placeholder': 'Rechercher une conversation',
    'viewOptions.label': 'Affichage', 'draft.workspaceRequired': 'Choisissez d’abord un dossier.',
    'time.now': 'à l’instant', 'time.minutes': '{n} min', 'time.hours': '{n} h', 'time.days': '{n} j',
    'time.ago': 'il y a {t}',
  },
  'chat': {
    'message.stepProcess.thinking': 'Analyse de la demande',
    'message.stepProcess.done.thinking': 'Analyse terminée',
    'message.stepProcess.tools': 'Appel des outils',
    'message.stepProcess.prepare.tools': 'Préparation des appels d’outils',
    'message.stepProcess.done.tools': 'Outils appelés',
    'message.stepProcess.questions': 'En attente de votre réponse',
    'message.stepProcess.prepare.questions': 'Préparation des questions',
    'message.stepProcess.done.questions': 'Questions posées',
    'message.stepProcess.joinTwo': '{first} et {second}',
    'message.stepProcess.more': '{title}, etc.',
    'message.trigger.request': 'Demande reçue',
    'message.turnProcess.worked': 'Terminé',
    'message.turnProcess.took': 'Terminé en ',
    'message.turnProcess.failed': 'Échec',
    'message.turnUsage.consumed': 'Utilisation {total}',
    'view.chat': 'Conversation',
    'stats.counts': '{turns} tours, {steps} étapes',
    'chat.loadingHistory': 'Chargement de l’historique…',
    'chat.toBottom': 'Revenir en bas',
    'chat.deepDiving': 'Ordner travaille',
    'chat.deepDivingFor': 'Ordner travaille depuis {duration} ···',
  },
  'settings': { 'trigger': 'Réglages', 'shortcut.open': 'Ouvrir les réglages' },
  'permission.access': {
    'mode': 'Mode d’accès, actuel : {name}', 'close': 'Fermer', 'preset.readOnly': 'Lecture seule',
    'preset.workspaceWrite': 'Écriture dans le dossier', 'preset.fullAccess': 'Accès complet',
  },
  'model': {
    'command.label': 'Modèle', 'menu.model': 'Modèle', 'trigger.fallback': 'Choisir un modèle',
    'error.sessionInUse': SESSION_IN_USE_FR,
  },
  'trajectory': {
    'view.trajectory': 'Trajectoire', 'toolbar.duration': 'Durée', 'toolbar.turns': 'Tours', 'toolbar.calls': 'Appels',
    'toolbar.searchPlaceholder': 'Rechercher', 'status.completed': 'Terminé', 'kind.system': 'SYSTÈME',
    'kind.user': 'PERSONNE', 'kind.context': 'CONTEXTE', 'kind.tool': 'OUTIL',
  },
  'pluginManager': { 'panel': 'Extensions', 'title': 'Extensions' },
  'schedule.manager': { 'panel': 'Tâches planifiées', 'title': 'Tâches planifiées' },
  'settings.models': { 'welcomeTitle': 'Prototype', 'welcomeBody': NOTICE_FR, 'welcomeContinue': 'Commencer' },
}

/** German (Swiss spelling). */
export const de: Dicts = {
  'common': { 'brand.localBuild': 'Ordner', 'close': 'Schliessen', 'cancel': 'Abbrechen', 'workspace.defaultName': 'Mein Dossier' },
  'conversation': {
    'hero.headline': 'Ihre Behördengänge, klar',
    'hero.preview': 'Prototyp',
    'placeholder.hero': 'Stellen Sie eine Frage zu Ihrem Dossier',
    'placeholder.default': 'Ihre Nachricht',
    'input.send': 'Senden',
  },
  'sidebar': { 'session.new': 'Neues Gespräch', 'session.new.label': 'Neues Gespräch' },
  'workspace': { 'session.new': 'Neues Gespräch', 'section.workspaces': 'Dossiers', 'section.sessions': 'Gespräche' },
  'settings': { 'trigger': 'Einstellungen' },
  'settings.models': { 'welcomeTitle': 'Prototyp', 'welcomeBody': NOTICE_DE, 'welcomeContinue': 'Beginnen' },
}

/** Italian (formal "lei", as in the cockpit). */
export const it: Dicts = {
  'common': { 'brand.localBuild': 'Ordner', 'close': 'Chiudere', 'cancel': 'Annullare', 'workspace.defaultName': 'Il mio dossier' },
  'conversation': {
    'hero.headline': 'Le sue pratiche, in chiaro',
    'hero.preview': 'Prototipo',
    'placeholder.hero': 'Faccia una domanda sul suo dossier',
    'placeholder.default': 'Il suo messaggio',
    'input.send': 'Inviare',
  },
  'sidebar': { 'session.new': 'Nuova conversazione', 'session.new.label': 'Nuova conversazione' },
  'workspace': { 'session.new': 'Nuova conversazione', 'section.workspaces': 'Dossier', 'section.sessions': 'Conversazioni' },
  'settings': { 'trigger': 'Impostazioni' },
  'settings.models': { 'welcomeTitle': 'Prototipo', 'welcomeBody': NOTICE_IT, 'welcomeContinue': 'Iniziare' },
}

/** Language definitions, registered in this order (each falls back to English). */
export const LANGUAGES = [
  { id: 'fr', label: 'Français', dicts: fr },
  { id: 'de', label: 'Deutsch', dicts: de },
  { id: 'it', label: 'Italiano', dicts: it },
]
