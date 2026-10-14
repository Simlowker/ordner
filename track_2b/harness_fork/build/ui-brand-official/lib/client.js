window.__ModuleLoader__.load({
	id: "@deepseek-ai/dsh-client-ui-brand-official",
	factory: (require) => {
		var module = { exports: {} };
		var exports = module.exports;
		Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
		let react_jsx_runtime = require("react/jsx-runtime");
		//#region src/client/Brand.tsx
		/** Ordner's Swiss red (the cockpit's --accent). */
		const RED$1 = "#D52B1E";
		/**
		* Ordner's mark: a white Swiss cross on a red rounded square, the cockpit's `.mark` drawn in SVG.
		* @param props.size - requested square edge in pixels.
		* @param props.className - host class keeping the surrounding geometry.
		* @returns the mark svg, decorative.
		*/
		function OrdnerMark({ size, className }) {
			return /* @__PURE__ */ (0, react_jsx_runtime.jsxs)("svg", {
				className,
				width: size,
				height: size,
				viewBox: "0 0 32 32",
				"aria-hidden": "true",
				children: [
					/* @__PURE__ */ (0, react_jsx_runtime.jsx)("rect", {
						width: "32",
						height: "32",
						rx: "4",
						fill: RED$1
					}),
					/* @__PURE__ */ (0, react_jsx_runtime.jsx)("rect", {
						x: "13",
						y: "6",
						width: "6",
						height: "20",
						fill: "#fff"
					}),
					/* @__PURE__ */ (0, react_jsx_runtime.jsx)("rect", {
						x: "6",
						y: "13",
						width: "20",
						height: "6",
						fill: "#fff"
					})
				]
			});
		}
		const NAME = {
			font: "700 16px/1 var(--dsh-font-family-text-default)",
			letterSpacing: "-0.02em",
			color: "var(--dsw-alias-label-primary, #111113)"
		};
		/**
		* Ordner's name beside the sidebar mark.
		* @returns the product name.
		*/
		function OrdnerName() {
			return /* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", {
				style: NAME,
				children: "Ordner"
			});
		}
		//#endregion
		//#region src/client/locales.ts
		const NOTICE_FR = "Ordner est un prototype de recherche (Hack Apertus 2026). Il prépare vos démarches administratives à partir de votre dossier et des sources officielles ; vous décidez. Rien n’est envoyé, déposé, signé ni payé.\n\nLe modèle est Apertus 1.5 8B, exécuté en local. Cette interface est construite sur DeepSeek Harness (licence MIT).";
		const NOTICE_DE = "Ordner ist ein Forschungsprototyp (Hack Apertus 2026). Er bereitet Ihre Behördengänge aus Ihrem Dossier und den amtlichen Quellen vor; Sie entscheiden. Nichts wird gesendet, eingereicht, unterschrieben oder bezahlt.\n\nDas Modell ist Apertus 1.5 8B, lokal ausgeführt. Diese Oberfläche basiert auf DeepSeek Harness (MIT-Lizenz).";
		const NOTICE_IT = "Ordner è un prototipo di ricerca (Hack Apertus 2026). Prepara le sue pratiche amministrative a partire dal suo dossier e dalle fonti ufficiali; lei decide. Nulla viene inviato, depositato, firmato o pagato.\n\nIl modello è Apertus 1.5 8B, eseguito in locale. Questa interfaccia è costruita su DeepSeek Harness (licenza MIT).";
		const SESSION_IN_USE_FR = "Cette conversation est déjà ouverte par une autre instance d’Ordner. Fermez-la et réessayez.";
		/** Language definitions, registered in this order (each falls back to English). */
		const LANGUAGES = [
			{
				id: "fr",
				label: "Français",
				dicts: {
					"common": {
						"ok": "OK",
						"cancel": "Annuler",
						"close": "Fermer",
						"copy": "Copier",
						"copied": "Copié",
						"retry": "Réessayer",
						"loading": "Chargement…",
						"load.failed": "Échec du chargement",
						"submit": "Valider",
						"submitting": "Envoi…",
						"next": "Suivant",
						"previous": "Précédent",
						"skip": "Passer",
						"delete": "Supprimer",
						"edit": "Modifier",
						"save": "Enregistrer",
						"search": "Rechercher",
						"more": "Plus",
						"collapse": "Réduire",
						"expand": "Développer",
						"back": "Retour",
						"brand.localBuild": "Ordner",
						"workspace.defaultName": "Mon dossier",
						"unknown": "Inconnu",
						"none": "Aucun",
						"truncated": "Tronqué"
					},
					"conversation": {
						"hero.headline": "Vos démarches, en clair",
						"hero.preview": "Prototype",
						"hero.chooseWorkspace": "Choisir un dossier",
						"placeholder.hero": "Posez votre question sur votre dossier",
						"placeholder.default": "Votre message",
						"placeholder.workspace": "Choisissez un dossier pour commencer",
						"placeholder.unavailable": "Conversation indisponible",
						"shortcut.newline": "Nouvelle ligne",
						"input.commands": "Ajouter des fichiers",
						"input.file": "Fichier",
						"input.stop": "Arrêter",
						"input.send": "Envoyer",
						"input.send.queue": "Mettre en attente",
						"context.aria": "{percent} du contexte utilisé",
						"context.used": "du contexte utilisé",
						"context.system": "Consigne système",
						"context.tools": "Définitions des outils",
						"context.messages": "Messages",
						"tool.title.generic": "Appel d’outil",
						"row.input": "ENTRÉE",
						"row.output": "SORTIE",
						"row.inspect": "Détails",
						"details.running": "En cours…",
						"error.sessionInUse": SESSION_IN_USE_FR
					},
					"sidebar": {
						"session.new": "Nouvelle conversation",
						"session.new.label": "Nouvelle conversation",
						"toggle.open": "Ouvrir le panneau latéral",
						"toggle.collapse": "Réduire le panneau latéral",
						"panels.label": "Panneaux"
					},
					"workspace": {
						"session.new": "Nouvelle conversation",
						"session.untitled": "Sans titre",
						"section.workspaces": "Dossiers",
						"section.sessions": "Conversations",
						"empty.none": "Aucune conversation",
						"workspace.add": "Ajouter un dossier",
						"search.sessions.aria": "Rechercher une conversation",
						"search.placeholder": "Rechercher une conversation",
						"viewOptions.label": "Affichage",
						"draft.workspaceRequired": "Choisissez d’abord un dossier.",
						"time.now": "à l’instant",
						"time.minutes": "{n} min",
						"time.hours": "{n} h",
						"time.days": "{n} j",
						"time.ago": "il y a {t}"
					},
					"chat": {
						"message.stepProcess.thinking": "Analyse de la demande",
						"message.stepProcess.done.thinking": "Analyse terminée",
						"message.stepProcess.tools": "Appel des outils",
						"message.stepProcess.prepare.tools": "Préparation des appels d’outils",
						"message.stepProcess.done.tools": "Outils appelés",
						"message.stepProcess.questions": "En attente de votre réponse",
						"message.stepProcess.prepare.questions": "Préparation des questions",
						"message.stepProcess.done.questions": "Questions posées",
						"message.stepProcess.joinTwo": "{first} et {second}",
						"message.stepProcess.more": "{title}, etc.",
						"message.trigger.request": "Demande reçue",
						"message.turnProcess.worked": "Terminé",
						"message.turnProcess.took": "Terminé en ",
						"message.turnProcess.failed": "Échec",
						"message.turnUsage.consumed": "Utilisation {total}",
						"view.chat": "Conversation",
						"stats.counts": "{turns} tours, {steps} étapes",
						"chat.loadingHistory": "Chargement de l’historique…",
						"chat.toBottom": "Revenir en bas",
						"chat.deepDiving": "Ordner travaille",
						"chat.deepDivingFor": "Ordner travaille depuis {duration} ···"
					},
					"settings": {
						"trigger": "Réglages",
						"shortcut.open": "Ouvrir les réglages"
					},
					"permission.access": {
						"mode": "Mode d’accès, actuel : {name}",
						"close": "Fermer",
						"preset.readOnly": "Lecture seule",
						"preset.workspaceWrite": "Écriture dans le dossier",
						"preset.fullAccess": "Accès complet"
					},
					"model": {
						"command.label": "Modèle",
						"menu.model": "Modèle",
						"trigger.fallback": "Choisir un modèle",
						"error.sessionInUse": SESSION_IN_USE_FR
					},
					"trajectory": {
						"view.trajectory": "Trajectoire",
						"toolbar.duration": "Durée",
						"toolbar.turns": "Tours",
						"toolbar.calls": "Appels",
						"toolbar.searchPlaceholder": "Rechercher",
						"status.completed": "Terminé",
						"kind.system": "SYSTÈME",
						"kind.user": "PERSONNE",
						"kind.context": "CONTEXTE",
						"kind.tool": "OUTIL"
					},
					"pluginManager": {
						"panel": "Extensions",
						"title": "Extensions"
					},
					"schedule.manager": {
						"panel": "Tâches planifiées",
						"title": "Tâches planifiées"
					},
					"settings.models": {
						"welcomeTitle": "Prototype",
						"welcomeBody": NOTICE_FR,
						"welcomeContinue": "Commencer"
					}
				}
			},
			{
				id: "de",
				label: "Deutsch",
				dicts: {
					"common": {
						"brand.localBuild": "Ordner",
						"close": "Schliessen",
						"cancel": "Abbrechen",
						"workspace.defaultName": "Mein Dossier"
					},
					"conversation": {
						"hero.headline": "Ihre Behördengänge, klar",
						"hero.preview": "Prototyp",
						"placeholder.hero": "Stellen Sie eine Frage zu Ihrem Dossier",
						"placeholder.default": "Ihre Nachricht",
						"input.send": "Senden"
					},
					"sidebar": {
						"session.new": "Neues Gespräch",
						"session.new.label": "Neues Gespräch"
					},
					"workspace": {
						"session.new": "Neues Gespräch",
						"section.workspaces": "Dossiers",
						"section.sessions": "Gespräche"
					},
					"settings": { "trigger": "Einstellungen" },
					"settings.models": {
						"welcomeTitle": "Prototyp",
						"welcomeBody": NOTICE_DE,
						"welcomeContinue": "Beginnen"
					}
				}
			},
			{
				id: "it",
				label: "Italiano",
				dicts: {
					"common": {
						"brand.localBuild": "Ordner",
						"close": "Chiudere",
						"cancel": "Annullare",
						"workspace.defaultName": "Il mio dossier"
					},
					"conversation": {
						"hero.headline": "Le sue pratiche, in chiaro",
						"hero.preview": "Prototipo",
						"placeholder.hero": "Faccia una domanda sul suo dossier",
						"placeholder.default": "Il suo messaggio",
						"input.send": "Inviare"
					},
					"sidebar": {
						"session.new": "Nuova conversazione",
						"session.new.label": "Nuova conversazione"
					},
					"workspace": {
						"session.new": "Nuova conversazione",
						"section.workspaces": "Dossier",
						"section.sessions": "Conversazioni"
					},
					"settings": { "trigger": "Impostazioni" },
					"settings.models": {
						"welcomeTitle": "Prototipo",
						"welcomeBody": NOTICE_IT,
						"welcomeContinue": "Iniziare"
					}
				}
			}
		];
		//#endregion
		//#region src/client/ToolCards.tsx
		/** Cockpit page of the prepared action (the cockpit is the only place where an action is validated). */
		const COCKPIT = "http://127.0.0.1:8000/";
		/** Parsed JSON object, or {} when the text is not one (streaming prefix, foreign shape). */
		function obj(text) {
			try {
				const v = JSON.parse(text ?? "");
				return typeof v === "object" && v !== null ? v : {};
			} catch {
				return {};
			}
		}
		const str = (v) => typeof v === "string" && v !== "" ? v : void 0;
		/**
		* The card's view model from the durable call slice: arguments, and the ordner.harness.mcp_server result
		* `{"tool": "prepare_action", "result": {...}}`.
		* @param props - phase and block of the keyed toolview.
		* @returns the fields shown.
		*/
		function actionModel({ phase, block }) {
			const args = obj(phase === "result" ? block.call?.argsRaw : block.argsRaw);
			const parsed = obj((block.content ?? []).map((c) => c.text ?? "").join(""));
			const result = typeof parsed.result === "object" && parsed.result !== null ? parsed.result : parsed;
			const caseId = str(args.case_id);
			const amount = typeof args.amount === "number" ? `CHF ${args.amount.toFixed(2)}` : void 0;
			return {
				state: phase !== "result" ? "running" : str(result.error) !== void 0 ? "refused" : "prepared",
				summary: str(args.summary) ?? "",
				kind: str(args.kind),
				details: [
					str(args.recipient),
					str(args.subject),
					amount
				].filter(Boolean).join(" · "),
				error: str(result.error),
				warning: str(result.warning),
				href: COCKPIT + (caseId !== void 0 ? `#/case/${encodeURIComponent(caseId)}` : "#/cases")
			};
		}
		const CARD = {
			margin: "6px 0",
			padding: "10px 12px",
			border: "1px solid var(--dsw-alias-border-l4, #e3e3e7)",
			borderRadius: 8,
			font: "14px/1.45 var(--dsh-font-family-text-default)",
			color: "var(--dsw-alias-label-primary, #111113)"
		};
		const MUTED = {
			color: "var(--dsw-alias-label-tertiary, #5b5b64)",
			fontSize: 13
		};
		const RED = { color: "var(--dsw-static-deepseek-600, #b8231a)" };
		/**
		* One prepare_action call: what was prepared, that nothing is sent, and the way to the cockpit to validate it.
		* @param props - keyed toolview payload plus the `ordner` locale seat.
		* @returns the card.
		*/
		function PrepareActionCard(props) {
			const { t } = props;
			const m = actionModel(props);
			const kind = m.kind !== void 0 && t(`kind.${m.kind}`) !== `kind.${m.kind}` ? t(`kind.${m.kind}`) : m.kind;
			return /* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
				style: CARD,
				"data-tool": "prepare_action",
				"data-state": m.state,
				children: [
					/* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
						style: {
							...MUTED,
							fontWeight: 600
						},
						children: [t(m.state === "refused" ? "action.refused" : "action.title"), kind !== void 0 ? ` · ${kind}` : ""]
					}),
					m.summary !== "" ? /* @__PURE__ */ (0, react_jsx_runtime.jsx)("div", {
						style: { marginTop: 2 },
						children: m.summary
					}) : null,
					m.details !== "" ? /* @__PURE__ */ (0, react_jsx_runtime.jsx)("div", {
						style: MUTED,
						children: m.details
					}) : null,
					m.error !== void 0 ? /* @__PURE__ */ (0, react_jsx_runtime.jsx)("div", {
						style: {
							...MUTED,
							...RED
						},
						children: m.error
					}) : null,
					m.warning !== void 0 ? /* @__PURE__ */ (0, react_jsx_runtime.jsx)("div", {
						style: {
							...RED,
							fontSize: 13,
							marginTop: 4
						},
						children: m.warning
					}) : null,
					m.state === "prepared" ? /* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
						style: {
							display: "flex",
							gap: 12,
							flexWrap: "wrap",
							marginTop: 6,
							...MUTED
						},
						children: [/* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", { children: t("action.notSent") }), /* @__PURE__ */ (0, react_jsx_runtime.jsx)("a", {
							href: m.href,
							target: "_blank",
							rel: "noreferrer",
							style: {
								...RED,
								fontWeight: 600
							},
							children: t("action.open")
						})]
					}) : m.state === "running" ? /* @__PURE__ */ (0, react_jsx_runtime.jsx)("div", {
						style: MUTED,
						children: t("action.preparing")
					}) : null
				]
			});
		}
		/** The `ordner` namespace, per language (en is the required fallback). */
		const CARD_DICTS = {
			en: {
				"kind.form_entry": "form entry",
				"kind.letter": "letter",
				"kind.email_draft": "email draft",
				"kind.payment": "payment",
				"kind.reminder": "reminder",
				"kind.document_request": "document request",
				"action.title": "Prepared action",
				"action.refused": "Action not prepared",
				"action.preparing": "Preparing the action…",
				"action.notSent": "Prepared, nothing is sent.",
				"action.open": "Open in Ordner"
			},
			fr: {
				"kind.form_entry": "saisie de formulaire",
				"kind.letter": "lettre",
				"kind.email_draft": "brouillon de courriel",
				"kind.payment": "paiement",
				"kind.reminder": "rappel",
				"kind.document_request": "demande de document",
				"action.title": "Action préparée",
				"action.refused": "Action non préparée",
				"action.preparing": "Préparation de l’action…",
				"action.notSent": "Préparée, rien n’est envoyé.",
				"action.open": "Ouvrir dans Ordner"
			},
			de: {
				"kind.form_entry": "Formulareintrag",
				"kind.letter": "Brief",
				"kind.email_draft": "E-Mail-Entwurf",
				"kind.payment": "Zahlung",
				"kind.reminder": "Erinnerung",
				"kind.document_request": "Dokumentenanfrage",
				"action.title": "Vorbereitete Aktion",
				"action.refused": "Aktion nicht vorbereitet",
				"action.preparing": "Aktion wird vorbereitet…",
				"action.notSent": "Vorbereitet, nichts wird gesendet.",
				"action.open": "In Ordner öffnen"
			},
			it: {
				"kind.form_entry": "compilazione di modulo",
				"kind.letter": "lettera",
				"kind.email_draft": "bozza di e-mail",
				"kind.payment": "pagamento",
				"kind.reminder": "promemoria",
				"kind.document_request": "richiesta di documento",
				"action.title": "Azione preparata",
				"action.refused": "Azione non preparata",
				"action.preparing": "Preparazione dell’azione…",
				"action.notSent": "Preparata, nulla viene inviato.",
				"action.open": "Aprire in Ordner"
			}
		};
		//#endregion
		//#region src/client/index.ts
		/** Required services: the UI slot registry and the locale service. */
		const inject = ["slots", "locale"];
		/**
		* Fill the sidebar brand slots as one registration set and the conversation hero mark, then register the
		* language definitions and their dictionaries as owned effects.
		* @param ctx - Client root context.
		*/
		function apply(ctx) {
			ctx.slots.inject("sidebar.brand.mark", () => ctx.slots.inject("sidebar.brand.name", function* () {
				yield ctx.slots.register({ name: "sidebar.brand.mark" }, OrdnerMark);
				yield ctx.slots.register({ name: "sidebar.brand.name" }, OrdnerName);
			}));
			ctx.slots.inject("conversation.hero.brand.mark", () => ctx.slots.register({ name: "conversation.hero.brand.mark" }, OrdnerMark));
			const locale = ctx.locale;
			for (const [id, dict] of Object.entries(CARD_DICTS)) ctx.effect(() => locale.register("ordner", id, dict), `ordner: ${id} cards`);
			ctx.slots.inject("tool.call.toolview", () => ctx.slots.register({
				name: "tool.call.toolview",
				key: "mcp__ordner__prepare_action",
				locale: "ordner"
			}, PrepareActionCard));
			for (const { id, label, dicts } of LANGUAGES) {
				ctx.effect(() => locale.addLanguage({
					id,
					label,
					fallback: "en"
				}), `ordner: ${id}`);
				for (const [ns, dict] of Object.entries(dicts)) ctx.effect(() => locale.register(ns, id, dict), `ordner: ${id} ${ns}`);
			}
		}
		//#endregion
		exports.apply = apply;
		exports.inject = inject;
		return module.exports;
	}
});

//# sourceMappingURL=client.js.map