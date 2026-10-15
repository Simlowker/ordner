window.__ModuleLoader__.load({
	id: "@deepseek-ai/dsh-client-ui-brand-official",
	factory: (require) => {
		var module = { exports: {} };
		var exports = module.exports;
		Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
		let react_jsx_runtime = require("react/jsx-runtime");
		let react = require("react");
		let _deepseek_ai_dsh_client_ui_primitives = require("@deepseek-ai/dsh-client-ui-primitives");
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
					},
					"settings.agentPreset": {
						"seatHint": "Expert : qui répond à cette conversation (Ordner (général) le choisit pour vous)",
						"headerHint": "L’expert choisi au début de cette conversation",
						"nav": "Experts",
						"builtInGroup": "Experts",
						"sectionIntro": "Chaque expert est Apertus 1.5 8B avec les outils de son domaine.",
						"inUse": "Expert par défaut",
						"setDefault": "Choisir comme expert par défaut",
						"view": "Voir la configuration",
						"noDescription": "Pas de description."
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
					},
					"settings.agentPreset": {
						"seatHint": "Experte: wer dieses Gespräch beantwortet (Ordner (général) wählt für Sie)",
						"headerHint": "Die zu Beginn dieses Gesprächs gewählte Expertin",
						"nav": "Experten",
						"builtInGroup": "Experten"
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
					},
					"settings.agentPreset": {
						"seatHint": "Esperto: chi risponde a questa conversazione (Ordner (général) lo sceglie per lei)",
						"headerHint": "L’esperto scelto all’inizio di questa conversazione",
						"nav": "Esperti",
						"builtInGroup": "Esperti"
					}
				}
			}
		];
		//#endregion
		//#region src/client/cards.ts
		const CARD_NAMES = {
			"business.self_employed.start": {
				"fr": "Démarrer une activité indépendante (entreprise individuelle)",
				"de": "Selbständige Erwerbstätigkeit aufnehmen (Einzelunternehmen)",
				"it": "Avviare un'attività indipendente (ditta individuale)",
				"en": "Démarrer une activité indépendante (entreprise individuelle)"
			},
			"debt.payment_order.opposition": {
				"fr": "Former opposition à un commandement de payer",
				"de": "Rechtsvorschlag gegen einen Zahlungsbefehl erheben",
				"it": "Fare opposizione a un precetto esecutivo",
				"en": "Former opposition à un commandement de payer"
			},
			"health_insurance.change_insurer_or_deductible": {
				"fr": "Changer de caisse-maladie, de franchise ou de modèle (assurance de base)",
				"de": "Krankenkasse, Franchise oder Modell wechseln (Grundversicherung)",
				"it": "Cambiare cassa malati, franchigia o modello (assicurazione di base)",
				"en": "Changer de caisse-maladie, de franchise ou de modèle (assurance de base)"
			},
			"health_insurance.premium_reduction.VD": {
				"fr": "Demander un subside à l'assurance-maladie (Vaud)",
				"de": "Prämienverbilligung der Krankenversicherung beantragen (Waadt)",
				"it": "Chiedere un sussidio per l'assicurazione malattie (Vaud)",
				"en": "Demander un subside à l'assurance-maladie (Vaud)"
			},
			"health_insurance.premium_reduction.ZH": {
				"fr": "Demander la réduction individuelle de primes (Zurich)",
				"de": "Individuelle Prämienverbilligung beantragen (Zürich)",
				"it": "Chiedere la riduzione individuale dei premi (Zurigo)",
				"en": "Demander la réduction individuelle de primes (Zurich)"
			},
			"household.serafe_fee": {
				"fr": "Redevance radio-télévision des ménages (Serafe)",
				"de": "Haushaltabgabe für Radio und Fernsehen (Serafe)",
				"it": "Canone radiotelevisivo per le economie domestiche (Serafe)",
				"en": "Redevance radio-télévision des ménages (Serafe)"
			},
			"housing.moving.announce": {
				"fr": "Annoncer un déménagement (départ et arrivée) au contrôle des habitants",
				"de": "Umzug bei der Einwohnerkontrolle melden (Wegzug und Zuzug)",
				"it": "Annunciare un trasloco (partenza e arrivo) al controllo abitanti",
				"en": "Annoncer un déménagement (départ et arrivée) au contrôle des habitants"
			},
			"pension.pillar3a.contribution": {
				"fr": "Pilier 3a : cotisation annuelle et rachat",
				"de": "Säule 3a: Jahresbeitrag und Einkauf",
				"it": "Pilastro 3a: contributo annuo e riscatto",
				"en": "Pilier 3a : cotisation annuelle et rachat"
			},
			"social.ahv.non_employed_contributions": {
				"fr": "Cotisations AVS/AI/APG des personnes sans activité lucrative (dont étudiants)",
				"de": "AHV/IV/EO-Beiträge für Nichterwerbstätige (inkl. Studierende)",
				"it": "Contributi AVS/AI/IPG delle persone senza attività lucrativa (compresi gli studenti)",
				"en": "Cotisations AVS/AI/APG des personnes sans activité lucrative (dont étudiants)"
			},
			"tax.assessment.objection": {
				"fr": "Réclamation contre la décision de taxation",
				"de": "Einsprache gegen die Veranlagungsverfügung",
				"it": "Reclamo contro la decisione di tassazione",
				"en": "Réclamation contre la décision de taxation"
			},
			"tax.instalments": {
				"fr": "Acomptes et tranches d'impôt",
				"de": "Steuerraten und Vorauszahlungen",
				"it": "Acconti e rate d'imposta",
				"en": "Acomptes et tranches d'impôt"
			},
			"tax.return.BE": {
				"fr": "Déclaration d'impôt (Berne)",
				"de": "Steuererklärung (Bern)",
				"it": "Dichiarazione d'imposta (Berna)",
				"en": "Déclaration d'impôt (Berne)"
			},
			"tax.return.GE": {
				"fr": "Déclaration d'impôt (Genève)",
				"de": "Steuererklärung (Genf)",
				"it": "Dichiarazione d'imposta (Ginevra)",
				"en": "Déclaration d'impôt (Genève)"
			},
			"tax.return.TI": {
				"fr": "Déclaration d'impôt (Tessin)",
				"de": "Steuererklärung (Tessin)",
				"it": "Dichiarazione d'imposta (Ticino)",
				"en": "Déclaration d'impôt (Tessin)"
			},
			"tax.return.VD": {
				"fr": "Déclaration d'impôt (Vaud)",
				"de": "Steuererklärung (Waadt)",
				"it": "Dichiarazione d'imposta (Vaud)",
				"en": "Déclaration d'impôt (Vaud)"
			},
			"tax.return.ZH": {
				"fr": "Déclaration d'impôt (Zurich)",
				"de": "Steuererklärung (Zürich)",
				"it": "Dichiarazione d'imposta (Zurigo)",
				"en": "Déclaration d'impôt (Zurich)"
			},
			"tax.withholding.refund": {
				"fr": "Remboursement de l'impôt anticipé (état des titres)",
				"de": "Rückerstattung der Verrechnungssteuer (Wertschriftenverzeichnis)",
				"it": "Rimborso dell'imposta preventiva (elenco dei titoli)",
				"en": "Remboursement de l'impôt anticipé (état des titres)"
			},
			"work.unemployment.register": {
				"fr": "S'inscrire au chômage (ORP) puis faire valoir l'indemnité auprès d'une caisse",
				"de": "Sich beim RAV zur Arbeitsvermittlung anmelden und Arbeitslosenentschädigung bei einer Kasse geltend machen",
				"it": "Iscriversi presso l'URC e far valere l'indennità di disoccupazione presso una cassa",
				"en": "S'inscrire au chômage (ORP) puis faire valoir l'indemnité auprès d'une caisse"
			}
		};
		//#endregion
		//#region src/client/ToolCards.tsx
		/** Cockpit page of the prepared action (the cockpit is the only place where an action is validated). */
		const COCKPIT = "http://127.0.0.1:8000/";
		/** Wire prefix of the Ordner MCP tools (ordner.harness.proxy PREFIX). */
		const PREFIX = "mcp__ordner__";
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
		/** Pretty JSON when the text is JSON, else the text as is. */
		function pretty(text) {
			try {
				return JSON.stringify(JSON.parse(text), null, 2);
			} catch {
				return text;
			}
		}
		const firstLine = (s) => s.split("\n", 1)[0] ?? "";
		/** ISO date as the Swiss dd.mm.yyyy. */
		function date(iso) {
			const m = str(iso)?.match(/^(\d{4})-(\d{2})-(\d{2})/);
			return m ? `${m[3]}.${m[2]}.${m[1]}` : void 0;
		}
		const field = (o, k) => typeof o === "object" && o !== null ? o[k] : void 0;
		/**
		* What a settled call found, in the person's words, from its recorded result: the procedure and whether it applies
		* with its deadline, how many official sources and from where, what was written to the dossier.
		* @returns the row summary, or undefined to keep the first argument.
		*/
		function outcome(name, args, output, t) {
			const env = obj(output);
			const res = field(env, "result") ?? env;
			const data = field(res, "data") ?? res;
			const lang = t("lang") === "lang" ? "en" : t("lang");
			const card = (id) => {
				const s = str(id);
				return s !== void 0 ? CARD_NAMES[s]?.[lang] ?? s : void 0;
			};
			const parts = (...p) => p.filter(Boolean).join(" · ") || void 0;
			switch (name) {
				case "rules_evaluate": {
					const status = str(data.status), due = date(field(data.deadline, "due"));
					return parts(card(data.card_id ?? args.card_id), status !== void 0 ? t(`status.${status}`) : void 0, due !== void 0 ? `${t("due")} ${due}` : void 0);
				}
				case "knowledge_search": {
					const ps = Array.isArray(data.passages) ? data.passages : [];
					const hosts = [...new Set(ps.map((p) => {
						try {
							return new URL(String(p.url)).hostname.replace(/^www\./, "");
						} catch {
							return "";
						}
					}))];
					return ps.length > 0 ? parts(`${ps.length} ${t("sources")}`, hosts.filter(Boolean).slice(0, 3).join(", ")) : void 0;
				}
				case "case_record": {
					const op = str(args.op);
					return op === "open_case" ? parts(t("case.opened"), card(args.card_id)) : op === "add_deadline" ? parts(t("case.deadline"), date(args.due)) : op === "propose_fact" ? t("case.fact") : void 0;
				}
				case "case_load": {
					const cases = field(data, "open_cases") ?? field(data, "cases");
					return Array.isArray(cases) ? `${cases.length} ${t("dossier.cases")}` : void 0;
				}
				case "piece_recevoir": {
					const u = field(data, "understood"), warn = field(res, "warnings");
					return parts(str(field(u, "kind_label")), str(field(u, "issuer")), Array.isArray(warn) ? str(warn[0]) : void 0);
				}
				default: return str(data.summary);
			}
		}
		/**
		* The row's view model: tool short name (a call carried by ask_user keeps its own name, see the proxy's CARRIER),
		* state, first string argument other than an id as summary, and the raw input and result for the expanded details.
		* @param props - phase, block and wire name of the keyed toolview.
		* @returns the fields shown.
		*/
		function rowModel({ phase, block, toolName }) {
			const settled = phase === "result";
			const argsRaw = (settled ? block.call?.argsRaw : block.argsRaw) ?? "";
			const args = obj(argsRaw);
			const output = settled ? (block.content ?? []).map((c) => c.type === "text" ? c.text ?? "" : JSON.stringify(c)).join("\n") : "";
			const summary = Object.entries(args).find(([k, v]) => !k.endsWith("_id") && !k.startsWith("__") && str(v) !== void 0)?.[1];
			return {
				name: str(args.__ordner_name__) ?? toolName.replace("mcp__ordner__", ""),
				state: !settled ? "running" : block.error?.code === "interrupted" ? "stopped" : block.isError === true ? "error" : "ok",
				summary: summary !== void 0 ? firstLine(summary) : "",
				argsRaw,
				output
			};
		}
		const IO_CARD = {
			margin: "4px 0 4px 4px",
			border: "0.5px solid var(--dsw-alias-border-l1)",
			borderRadius: "var(--dsw-radius-lg)",
			background: "var(--dsw-alias-markdown-code-block)",
			font: "var(--dsw-font-markdown-code-block-small)",
			overflow: "hidden"
		};
		const IO_SECTION = {
			display: "grid",
			gridTemplateColumns: "max-content 1fr",
			columnGap: 14,
			alignItems: "baseline",
			padding: "10px 16px",
			maxHeight: 180,
			overflowY: "auto",
			borderTop: "0.5px solid var(--dsw-alias-border-l2)"
		};
		const IO_LABEL = { color: "var(--dsw-alias-label-caption)" };
		const IO_TEXT = {
			minWidth: 0,
			whiteSpace: "pre-wrap",
			wordBreak: "break-word",
			color: "var(--dsw-alias-label-secondary)"
		};
		const SEP = {
			flex: "none",
			width: 2,
			height: 2,
			borderRadius: 1,
			margin: "0 8px",
			background: "var(--dsw-alias-label-caption)"
		};
		const SUMMARY = {
			flex: "1 1 auto",
			minWidth: 0,
			overflow: "hidden",
			textOverflow: "ellipsis",
			whiteSpace: "nowrap",
			fontSize: "var(--dsh-content-font-size-secondary, 13px)"
		};
		const INSPECT = {
			display: "inline-flex",
			alignSelf: "flex-start",
			alignItems: "center",
			gap: 4,
			margin: "2px 0 2px 4px",
			padding: "2px 6px",
			border: 0,
			borderRadius: 6,
			background: "transparent",
			color: "var(--dsw-alias-label-tertiary)",
			font: "inherit",
			fontSize: 12,
			cursor: "pointer"
		};
		/**
		* One Ordner tool call as a process row: plain-language title and first argument; on expand, the wire tool name,
		* the input and the result as recorded (transparency: nothing hidden, only labelled).
		* @param props - keyed toolview payload plus the `ordner` locale seat.
		* @returns the row.
		*/
		function OrdnerToolRow(props) {
			const { t, toolName, inspect } = props;
			const m = rowModel(props);
			const [open, setOpen] = (0, react.useState)(false);
			const key = `tool.${m.name}`;
			const title = t(key) !== key ? t(key) : m.name;
			const expandable = props.phase !== "preparing";
			const summary = m.state === "error" && m.output !== "" ? firstLine(m.output) : (m.state === "ok" ? outcome(m.name, obj(m.argsRaw), m.output, t) : void 0) ?? m.summary;
			const color = m.state === "error" ? "var(--dsw-alias-state-error-primary)" : m.state === "stopped" ? "var(--dsw-alias-state-warn-label)" : void 0;
			const section = (label, text) => /* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
				style: IO_SECTION,
				children: [/* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", {
					style: IO_LABEL,
					children: label
				}), /* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", {
					style: IO_TEXT,
					children: text
				})]
			});
			return /* @__PURE__ */ (0, react_jsx_runtime.jsx)("div", {
				"data-tool": toolName,
				"data-state": m.state,
				children: /* @__PURE__ */ (0, react_jsx_runtime.jsxs)(_deepseek_ai_dsh_client_ui_primitives.DisclosureRow, {
					icon: /* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.IconSparkleRegular, { size: 14 }),
					title,
					running: m.state === "running",
					open: open && expandable,
					expandable,
					expandOnRowClick: true,
					keepContentWhenOpen: true,
					onToggle: () => {
						setOpen((v) => !v);
					},
					collapsedContent: summary !== "" ? /* @__PURE__ */ (0, react_jsx_runtime.jsxs)(react_jsx_runtime.Fragment, { children: [/* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", {
						style: SEP,
						"aria-hidden": true
					}), /* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", {
						style: {
							...SUMMARY,
							color
						},
						children: summary
					})] }) : null,
					children: [/* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
						style: IO_CARD,
						children: [
							/* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
								style: {
									...IO_SECTION,
									borderTop: 0
								},
								children: [/* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", {
									style: IO_LABEL,
									children: t("row.tool")
								}), /* @__PURE__ */ (0, react_jsx_runtime.jsx)("code", {
									style: IO_TEXT,
									children: toolName
								})]
							}),
							section(t("row.input"), pretty(m.argsRaw)),
							m.output !== "" ? section(t("row.output"), pretty(m.output)) : null
						]
					}), inspect !== void 0 ? /* @__PURE__ */ (0, react_jsx_runtime.jsxs)("button", {
						type: "button",
						style: INSPECT,
						onClick: inspect,
						children: [/* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.IconInspectOutlineRegular, {}), t("row.inspect")]
					}) : null]
				})
			});
		}
		/** The `ordner` namespace, per language (en is the required fallback). `tool.<name>` keys also list the tools that get
		* an OrdnerToolRow (index.ts). */
		const CARD_DICTS = {
			en: {
				"lang": "en",
				"status.applicable": "applies",
				"status.not_applicable": "does not apply",
				"status.missing_info": "information missing",
				"due": "deadline",
				"sources": "official sources",
				"case.opened": "Procedure opened",
				"case.deadline": "Deadline recorded",
				"case.fact": "Noted, for you to confirm",
				"dossier.cases": "procedures in the dossier",
				"tool.case_load": "Reading the dossier",
				"tool.knowledge_search": "Searching the official sources",
				"tool.rules_evaluate": "Checking the rules",
				"tool.case_record": "Note to the dossier",
				"tool.piece_recevoir": "Document received",
				"tool.document_read": "Reading a document",
				"tool.document_decode": "Reading the barcode",
				"tool.expert_run": "Tax statement extraction",
				"tool.impots_preparer_declaration": "Preparing the tax return",
				"tool.lamal_revoir_franchise": "Deductible and health insurer",
				"tool.poursuite_repondre": "Responding to the debt collection",
				"tool.demenagement_annoncer": "Moving notification",
				"tool.ask_user": "Question for you",
				"row.tool": "Tool",
				"row.input": "Input",
				"row.output": "Result",
				"row.inspect": "Show in the trajectory",
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
				"lang": "fr",
				"status.applicable": "s’applique",
				"status.not_applicable": "ne s’applique pas",
				"status.missing_info": "informations manquantes",
				"due": "délai",
				"sources": "sources officielles",
				"case.opened": "Démarche ouverte",
				"case.deadline": "Délai enregistré",
				"case.fact": "Noté, à confirmer par vous",
				"dossier.cases": "démarches au dossier",
				"tool.case_load": "Lecture du dossier",
				"tool.knowledge_search": "Recherche dans les sources officielles",
				"tool.rules_evaluate": "Vérification des règles",
				"tool.case_record": "Note au dossier",
				"tool.piece_recevoir": "Pièce reçue",
				"tool.document_read": "Lecture d’un document",
				"tool.document_decode": "Lecture du code-barres",
				"tool.expert_run": "Extraction du relevé fiscal",
				"tool.impots_preparer_declaration": "Préparation de la déclaration",
				"tool.lamal_revoir_franchise": "Franchise et caisse maladie",
				"tool.poursuite_repondre": "Réponse à la poursuite",
				"tool.demenagement_annoncer": "Annonce de déménagement",
				"tool.ask_user": "Question à vous",
				"row.tool": "Outil",
				"row.input": "Entrée",
				"row.output": "Résultat",
				"row.inspect": "Voir dans la trajectoire",
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
				"lang": "de",
				"status.applicable": "trifft zu",
				"status.not_applicable": "trifft nicht zu",
				"status.missing_info": "Angaben fehlen",
				"due": "Frist",
				"sources": "amtliche Quellen",
				"case.opened": "Verfahren eröffnet",
				"case.deadline": "Frist eingetragen",
				"case.fact": "Notiert, von Ihnen zu bestätigen",
				"dossier.cases": "Verfahren im Dossier",
				"tool.case_load": "Dossier lesen",
				"tool.knowledge_search": "Suche in den amtlichen Quellen",
				"tool.rules_evaluate": "Prüfung der Regeln",
				"tool.case_record": "Notiz im Dossier",
				"tool.piece_recevoir": "Unterlage erhalten",
				"tool.document_read": "Dokument lesen",
				"tool.document_decode": "Barcode lesen",
				"tool.expert_run": "Auslesen des Steuerausweises",
				"tool.impots_preparer_declaration": "Vorbereitung der Steuererklärung",
				"tool.lamal_revoir_franchise": "Franchise und Krankenkasse",
				"tool.poursuite_repondre": "Antwort auf die Betreibung",
				"tool.demenagement_annoncer": "Umzugsmeldung",
				"tool.ask_user": "Frage an Sie",
				"row.tool": "Werkzeug",
				"row.input": "Eingabe",
				"row.output": "Ergebnis",
				"row.inspect": "In der Trajektorie zeigen",
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
				"lang": "it",
				"status.applicable": "si applica",
				"status.not_applicable": "non si applica",
				"status.missing_info": "informazioni mancanti",
				"due": "termine",
				"sources": "fonti ufficiali",
				"case.opened": "Procedura aperta",
				"case.deadline": "Termine registrato",
				"case.fact": "Annotato, da confermare",
				"dossier.cases": "procedure nel dossier",
				"tool.case_load": "Lettura del dossier",
				"tool.knowledge_search": "Ricerca nelle fonti ufficiali",
				"tool.rules_evaluate": "Verifica delle regole",
				"tool.case_record": "Nota nel dossier",
				"tool.piece_recevoir": "Documento ricevuto",
				"tool.document_read": "Lettura di un documento",
				"tool.document_decode": "Lettura del codice a barre",
				"tool.expert_run": "Estrazione dell’estratto fiscale",
				"tool.impots_preparer_declaration": "Preparazione della dichiarazione",
				"tool.lamal_revoir_franchise": "Franchigia e cassa malati",
				"tool.poursuite_repondre": "Risposta all’esecuzione",
				"tool.demenagement_annoncer": "Notifica di trasloco",
				"tool.ask_user": "Domanda per lei",
				"row.tool": "Strumento",
				"row.input": "Input",
				"row.output": "Risultato",
				"row.inspect": "Mostra nella traiettoria",
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
			const tools = Object.keys(CARD_DICTS.en ?? {}).filter((k) => k.startsWith("tool.")).map((k) => PREFIX + k.slice(5));
			ctx.slots.inject("tool.call.toolview", function* () {
				yield ctx.slots.register({
					name: "tool.call.toolview",
					key: "mcp__ordner__prepare_action",
					locale: "ordner"
				}, PrepareActionCard);
				for (const key of tools) yield ctx.slots.register({
					name: "tool.call.toolview",
					key,
					locale: "ordner"
				}, OrdnerToolRow);
			});
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