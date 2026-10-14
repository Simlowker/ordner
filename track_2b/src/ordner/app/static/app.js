"use strict";

const I18N = {
  fr: {
    skip: "Aller au contenu", tagline: "assistant administratif souverain",
    lead: "Lit un relevé fiscal bancaire, extrait les montants à reporter, signale ce dont il n'est pas sûr et l'explique dans votre langue. Tout tourne en local : aucun appel réseau.",
    h_doc: "Document et champs extraits", pick_doc: "Choisir un document", fields_caption: "Champs extraits avec leur niveau de doute",
    col_field: "Champ", col_value: "Valeur", col_doubt: "Doute", col_why: "Pourquoi", col_oracle: "Corrigé",
    legend: "Doute : score combiné (sonde sur les états internes d'Apertus, validation d1-3B, règles, probabilité des tokens). Corrigé : valeur lue dans les codes-barres du relevé.",
    h_triage: "Tri : que relire ?", thr_label: "Part des champs relus, les plus douteux d'abord :", thr_low: "relire moins", thr_high: "relire plus",
    triage_missing: "Pas encore de résultats : lancez « make eval » (ou « make run ») pour calculer la courbe de tri.",
    h_explain: "Explication", h_ded: "Déductions à vérifier",
    fs_work: "Activité", income_type: "Revenu d'activité", opt_employee: "Salarié·e", opt_self: "Indépendant·e", opt_none: "Sans revenu d'activité",
    net_income: "Revenu net d'activité (CHF/an, facultatif)", pension_fund: "Affilié·e à une caisse de pension (2e pilier)",
    pays_3a: "Je verse sur un pilier 3a", gap_3a_2025: "Je n'ai pas versé le maximum 3a en 2025", lpp_buyin: "J'envisage un rachat dans ma caisse de pension",
    fs_commute: "Trajets, repas, formation", commute_km: "Trajet domicile-travail (km, aller simple)", commute_mode: "Moyen de transport",
    opt_public: "Transports publics", opt_car: "Voiture", opt_moto: "Moto", opt_bike: "Vélo, vélomoteur",
    meals: "Repas de midi", opt_meals_none: "À la maison", opt_meals_out: "À l'extérieur (travail)", opt_meals_canteen: "Cantine subventionnée",
    training: "Je paie moi-même une formation continue professionnelle",
    fs_family: "Famille", married: "Marié·e", both_earn: "Les deux conjoints ont un revenu", children: "Enfants à charge", childcare: "Garde d'enfants payée à des tiers",
    footer_models: "Modèles : Apertus 1.5 8B (extraction, explication), LightOnOCR-3 (lecture), d1-3B (routage, validation), EmbeddingGemma 2 (recherche dans les guides).",
    footer_note: "Documents fictifs générés pour l'évaluation. Information générale, pas un conseil fiscal.",
    fixture_demo: "Fixture : les champs, doutes et explications des documents sont des valeurs de démonstration écrites à la main, en attendant les sorties du pipeline.",
    fixture_results: "Fixture : la courbe de tri vient de chiffres synthétiques, pas de l'évaluation.",
    fields: { totalTaxValue: "Valeur fiscale totale", totalGrossRevenueA: "Revenus bruts A (avec impôt anticipé)", totalGrossRevenueB: "Revenus bruts B (sans impôt anticipé)",
      totalWithHoldingTaxClaim: "Impôt anticipé à récupérer", institution: "Établissement", canton: "Canton", taxPeriod: "Période fiscale", client_last_name: "Nom du client" },
    lv: { low: "faible", medium: "moyen", high: "élevé", na: "n/d" },
    sig_probe: p => `Sonde : risque d'erreur ${p}`, sig_d1: p => `d1-3B : p(juste) ${p}`,
    sig_rule_ok: r => `Règle « ${r} » : OK`, sig_rule_bad: r => `Règle « ${r} » : non respectée`, sig_lp: p => `Prob. min. des tokens : ${p}`,
    rules: { wht_35: "impôt anticipé = 35 % des revenus A", sum_ab: "A + B = total des revenus" },
    no_flag: "aucun signal d'alerte", signals: "signaux", correct: "juste", wrong: "faux, corrigé :",
    route: (m, l, p) => `Type de document (${m}) : ${l}, probabilité ${p}`,
    doc_types: { swiss_tax_statement_eCH0196: "relevé fiscal eCH-0196", qr_bill_invoice: "QR-facture", health_insurance_premium_letter: "prime LAMal", other: "autre" },
    page_meta: (lay, deg, lang) => `Mise en page ${lay} · dégradation ${deg}/3 · document en ${lang}`, unseen: " (jamais vue à l'entraînement)", thumb: (l, lay, deg) => `${l} · mise en page ${lay} · dégradation ${deg}/3`,
    langs: { fr: "français", de: "allemand", it: "italien" },
    triage_out: (x, y) => `Tu relis ${x} % des champs, tu attrapes ${y} % des erreurs.`,
    triage_meta: (n, e, main, others) => `Apertus zéro-shot, jeu de test : ${n} champs, ${e} erreurs. Rouge : ${main}. Gris : ${others}. Pointillé : ordre aléatoire.`,
    axis_x: "part des champs relus", axis_y: "erreurs attrapées", curve_label: "Courbe de tri : part des erreurs attrapées selon la part des champs relus",
    curves: { combined: "score combiné", "probe A": "sonde (états internes)", "probe B": "sonde, position B", "min token prob": "prob. min. des tokens", "mean token prob": "prob. moyenne des tokens",
      "mean entropy": "entropie moyenne", "first-token entropy": "entropie du 1er token", "d1 validation": "validation d1-3B", rules: "règles" },
    sources_cited: "Sources citées", verified: "✓ citation vérifiée mot pour mot", unverified_quote: "citation non vérifiée", missing_quote: "passage à extraire (fixture)",
    ded_scope: y => `Année fiscale ${y}. `, estimate: "Montant indicatif selon vos réponses :", legal: "Base légale :", no_rules: "Aucune règle déclenchée pour ce profil.",
    flag: { secondary: "non vérifié (source secondaire)", unverified: "non vérifié", partial: "en partie non vérifié" },
    mode_replay: "Mode : rejeu des sorties enregistrées.", mode_llm: n => ` Point d'accès modèle configuré : ${n}.`, err: "Erreur de chargement :"
  },
  de: {
    skip: "Zum Inhalt", tagline: "souveräner Verwaltungsassistent",
    lead: "Liest einen Steuerausweis der Bank, extrahiert die zu übertragenden Beträge, meldet, wo er unsicher ist, und erklärt es in Ihrer Sprache. Alles läuft lokal: kein Netzwerkzugriff.",
    h_doc: "Dokument und extrahierte Felder", pick_doc: "Dokument wählen", fields_caption: "Extrahierte Felder mit Zweifelsgrad",
    col_field: "Feld", col_value: "Wert", col_doubt: "Zweifel", col_why: "Warum", col_oracle: "Lösung",
    legend: "Zweifel: kombinierter Wert (Sonde auf den internen Zuständen von Apertus, Prüfung durch d1-3B, Regeln, Token-Wahrscheinlichkeit). Lösung: Wert aus den Barcodes des Ausweises.",
    h_triage: "Triage: was prüfen?", thr_label: "Anteil geprüfter Felder, die zweifelhaftesten zuerst:", thr_low: "weniger prüfen", thr_high: "mehr prüfen",
    triage_missing: "Noch keine Resultate: Starten Sie «make eval» (oder «make run»), um die Triage-Kurve zu berechnen.",
    h_explain: "Erklärung", h_ded: "Abzüge zum Prüfen",
    fs_work: "Erwerbstätigkeit", income_type: "Erwerbseinkommen", opt_employee: "Unselbständig", opt_self: "Selbständig", opt_none: "Kein Erwerbseinkommen",
    net_income: "Nettoerwerbseinkommen (CHF/Jahr, freiwillig)", pension_fund: "Pensionskasse (2. Säule)",
    pays_3a: "Ich zahle in eine Säule 3a ein", gap_3a_2025: "Ich habe 2025 nicht den Maximalbetrag 3a einbezahlt", lpp_buyin: "Ich erwäge einen Einkauf in die Pensionskasse",
    fs_commute: "Arbeitsweg, Verpflegung, Weiterbildung", commute_km: "Arbeitsweg (km, einfach)", commute_mode: "Verkehrsmittel",
    opt_public: "Öffentlicher Verkehr", opt_car: "Auto", opt_moto: "Motorrad", opt_bike: "Velo, Motorfahrrad",
    meals: "Mittagessen", opt_meals_none: "Zu Hause", opt_meals_out: "Auswärts (beruflich)", opt_meals_canteen: "Verbilligte Kantine",
    training: "Ich bezahle selbst eine berufliche Weiterbildung",
    fs_family: "Familie", married: "Verheiratet", both_earn: "Beide Ehegatten haben ein Einkommen", children: "Kinder", childcare: "Kinderbetreuung durch Dritte bezahlt",
    footer_models: "Modelle: Apertus 1.5 8B (Extraktion, Erklärung), LightOnOCR-3 (Lesen), d1-3B (Routing, Prüfung), EmbeddingGemma 2 (Suche in den Wegleitungen).",
    footer_note: "Für die Evaluation generierte fiktive Dokumente. Allgemeine Information, keine Steuerberatung.",
    fixture_demo: "Fixture: Felder, Zweifel und Erklärungen der Dokumente sind von Hand geschriebene Demowerte, bis die Pipeline-Ausgaben vorliegen.",
    fixture_results: "Fixture: Die Triage-Kurve beruht auf synthetischen Zahlen, nicht auf der Evaluation.",
    fields: { totalTaxValue: "Steuerwert total", totalGrossRevenueA: "Bruttoerträge A (mit Verrechnungssteuer)", totalGrossRevenueB: "Bruttoerträge B (ohne Verrechnungssteuer)",
      totalWithHoldingTaxClaim: "Rückforderbare Verrechnungssteuer", institution: "Institut", canton: "Kanton", taxPeriod: "Steuerperiode", client_last_name: "Name Kunde/Kundin" },
    lv: { low: "tief", medium: "mittel", high: "hoch", na: "k. A." },
    sig_probe: p => `Sonde: Fehlerrisiko ${p}`, sig_d1: p => `d1-3B: p(richtig) ${p}`,
    sig_rule_ok: r => `Regel «${r}»: OK`, sig_rule_bad: r => `Regel «${r}»: verletzt`, sig_lp: p => `Min. Token-Wahrscheinlichkeit: ${p}`,
    rules: { wht_35: "Verrechnungssteuer = 35 % der Erträge A", sum_ab: "A + B = Total Erträge" },
    no_flag: "kein Warnsignal", signals: "Signale", correct: "richtig", wrong: "falsch, Lösung:",
    route: (m, l, p) => `Dokumenttyp (${m}): ${l}, Wahrscheinlichkeit ${p}`,
    doc_types: { swiss_tax_statement_eCH0196: "Steuerausweis eCH-0196", qr_bill_invoice: "QR-Rechnung", health_insurance_premium_letter: "KVG-Prämie", other: "anderes" },
    page_meta: (lay, deg, lang) => `Layout ${lay} · Degradation ${deg}/3 · Dokument auf ${lang}`, unseen: " (im Training nie gesehen)", thumb: (l, lay, deg) => `${l} · Layout ${lay} · Degradation ${deg}/3`,
    langs: { fr: "Französisch", de: "Deutsch", it: "Italienisch" },
    triage_out: (x, y) => `Du prüfst ${x} % der Felder und findest ${y} % der Fehler.`,
    triage_meta: (n, e, main, others) => `Apertus Zero-Shot, Testset: ${n} Felder, ${e} Fehler. Rot: ${main}. Grau: ${others}. Gestrichelt: zufällige Reihenfolge.`,
    axis_x: "Anteil geprüfter Felder", axis_y: "gefundene Fehler", curve_label: "Triage-Kurve: Anteil gefundener Fehler nach Anteil geprüfter Felder",
    curves: { combined: "kombinierter Wert", "probe A": "Sonde (interne Zustände)", "probe B": "Sonde, Position B", "min token prob": "min. Token-Wahrscheinlichkeit", "mean token prob": "mittlere Token-Wahrscheinlichkeit",
      "mean entropy": "mittlere Entropie", "first-token entropy": "Entropie des 1. Tokens", "d1 validation": "Prüfung d1-3B", rules: "Regeln" },
    sources_cited: "Zitierte Quellen", verified: "✓ Zitat wörtlich geprüft", unverified_quote: "Zitat nicht geprüft", missing_quote: "Passage noch zu extrahieren (Fixture)",
    ded_scope: y => `Steuerjahr ${y}. `, estimate: "Richtbetrag gemäss Ihren Angaben:", legal: "Rechtsgrundlage:", no_rules: "Für dieses Profil greift keine Regel.",
    flag: { secondary: "nicht geprüft (Sekundärquelle)", unverified: "nicht geprüft", partial: "teilweise nicht geprüft" },
    mode_replay: "Modus: Wiedergabe gespeicherter Ausgaben.", mode_llm: n => ` Modell-Endpunkt konfiguriert: ${n}.`, err: "Ladefehler:"
  },
  it: {
    skip: "Vai al contenuto", tagline: "assistente amministrativo sovrano",
    lead: "Legge un estratto fiscale bancario, estrae gli importi da riportare, segnala ciò di cui non è sicuro e lo spiega nella sua lingua. Tutto gira in locale: nessun accesso alla rete.",
    h_doc: "Documento e campi estratti", pick_doc: "Scegliere un documento", fields_caption: "Campi estratti con il loro livello di dubbio",
    col_field: "Campo", col_value: "Valore", col_doubt: "Dubbio", col_why: "Perché", col_oracle: "Soluzione",
    legend: "Dubbio: punteggio combinato (sonda sugli stati interni di Apertus, verifica d1-3B, regole, probabilità dei token). Soluzione: valore letto nei codici a barre dell'estratto.",
    h_triage: "Triage: cosa rileggere?", thr_label: "Quota di campi riletti, i più dubbi prima:", thr_low: "rileggere di meno", thr_high: "rileggere di più",
    triage_missing: "Ancora nessun risultato: lanci «make eval» (o «make run») per calcolare la curva di triage.",
    h_explain: "Spiegazione", h_ded: "Deduzioni da verificare",
    fs_work: "Attività", income_type: "Reddito da attività", opt_employee: "Dipendente", opt_self: "Indipendente", opt_none: "Senza reddito da attività",
    net_income: "Reddito netto da attività (CHF/anno, facoltativo)", pension_fund: "Affiliato/a a una cassa pensioni (2° pilastro)",
    pays_3a: "Verso in un pilastro 3a", gap_3a_2025: "Nel 2025 non ho versato il massimo 3a", lpp_buyin: "Considero un riscatto nella cassa pensioni",
    fs_commute: "Tragitto, pasti, formazione", commute_km: "Tragitto casa-lavoro (km, sola andata)", commute_mode: "Mezzo di trasporto",
    opt_public: "Mezzi pubblici", opt_car: "Automobile", opt_moto: "Motocicletta", opt_bike: "Bicicletta, ciclomotore",
    meals: "Pranzo", opt_meals_none: "A casa", opt_meals_out: "Fuori casa (lavoro)", opt_meals_canteen: "Mensa sovvenzionata",
    training: "Pago personalmente una formazione continua professionale",
    fs_family: "Famiglia", married: "Coniugato/a", both_earn: "Entrambi i coniugi hanno un reddito", children: "Figli a carico", childcare: "Custodia dei figli pagata a terzi",
    footer_models: "Modelli: Apertus 1.5 8B (estrazione, spiegazione), LightOnOCR-3 (lettura), d1-3B (instradamento, verifica), EmbeddingGemma 2 (ricerca nelle guide).",
    footer_note: "Documenti fittizi generati per la valutazione. Informazione generale, non una consulenza fiscale.",
    fixture_demo: "Fixture: campi, dubbi e spiegazioni dei documenti sono valori dimostrativi scritti a mano, in attesa degli output della pipeline.",
    fixture_results: "Fixture: la curva di triage proviene da cifre sintetiche, non dalla valutazione.",
    fields: { totalTaxValue: "Valore fiscale totale", totalGrossRevenueA: "Redditi lordi A (con imposta preventiva)", totalGrossRevenueB: "Redditi lordi B (senza imposta preventiva)",
      totalWithHoldingTaxClaim: "Imposta preventiva da recuperare", institution: "Istituto", canton: "Cantone", taxPeriod: "Periodo fiscale", client_last_name: "Cognome cliente" },
    lv: { low: "basso", medium: "medio", high: "alto", na: "n.d." },
    sig_probe: p => `Sonda: rischio di errore ${p}`, sig_d1: p => `d1-3B: p(giusto) ${p}`,
    sig_rule_ok: r => `Regola «${r}»: OK`, sig_rule_bad: r => `Regola «${r}»: non rispettata`, sig_lp: p => `Prob. min. dei token: ${p}`,
    rules: { wht_35: "imposta preventiva = 35 % dei redditi A", sum_ab: "A + B = totale redditi" },
    no_flag: "nessun segnale d'allarme", signals: "segnali", correct: "giusto", wrong: "sbagliato, soluzione:",
    route: (m, l, p) => `Tipo di documento (${m}): ${l}, probabilità ${p}`,
    doc_types: { swiss_tax_statement_eCH0196: "estratto fiscale eCH-0196", qr_bill_invoice: "fattura QR", health_insurance_premium_letter: "premio LAMal", other: "altro" },
    page_meta: (lay, deg, lang) => `Impaginazione ${lay} · degrado ${deg}/3 · documento in ${lang}`, unseen: " (mai vista nell'addestramento)", thumb: (l, lay, deg) => `${l} · impaginazione ${lay} · degrado ${deg}/3`,
    langs: { fr: "francese", de: "tedesco", it: "italiano" },
    triage_out: (x, y) => `Rileggi il ${x} % dei campi e trovi il ${y} % degli errori.`,
    triage_meta: (n, e, main, others) => `Apertus zero-shot, set di test: ${n} campi, ${e} errori. Rosso: ${main}. Grigio: ${others}. Tratteggio: ordine casuale.`,
    axis_x: "quota di campi riletti", axis_y: "errori trovati", curve_label: "Curva di triage: quota di errori trovati secondo la quota di campi riletti",
    curves: { combined: "punteggio combinato", "probe A": "sonda (stati interni)", "probe B": "sonda, posizione B", "min token prob": "prob. min. dei token", "mean token prob": "prob. media dei token",
      "mean entropy": "entropia media", "first-token entropy": "entropia del 1° token", "d1 validation": "verifica d1-3B", rules: "regole" },
    sources_cited: "Fonti citate", verified: "✓ citazione verificata alla lettera", unverified_quote: "citazione non verificata", missing_quote: "passaggio da estrarre (fixture)",
    ded_scope: y => `Anno fiscale ${y}. `, estimate: "Importo indicativo secondo le sue risposte:", legal: "Base legale:", no_rules: "Nessuna regola si applica a questo profilo.",
    flag: { secondary: "non verificato (fonte secondaria)", unverified: "non verificato", partial: "in parte non verificato" },
    mode_replay: "Modalità: riproduzione degli output registrati.", mode_llm: n => ` Endpoint del modello configurato: ${n}.`, err: "Errore di caricamento:"
  }
};

/* Cockpit strings (home, inbox, cases, coverage, chat). */
const C18N = {
  fr: {
    nav_label: "Sections", nav_home: "Où j'en suis", nav_inbox: "Pièces reçues", nav_cases: "Démarches", nav_coverage: "Couverture", nav_releve: "Relevé fiscal",
    sim_date: d => `date simulée : ${d}`, h_wealth: y => `Votre fortune et vos revenus de titres à déclarer (${y})`,
    wealth_status: { final: "définitif", provisional: "provisoire", incomplete: "incomplet" },
    measures: { total_tax_value: "Valeur fiscale des titres (fortune)", gross_revenue_a: "Rendements bruts A (avec impôt anticipé)",
      gross_revenue_b: "Rendements bruts B (sans impôt anticipé)", withholding_tax_claim: "Impôt anticipé à récupérer" },
    m_status: { confirmed: "confirmé", provisional: "provisoire", missing: "manquant" }, inst_in: "Établissements inclus :", inst_missing: "Établissements sans relevé :",
    wealth_note: "Somme des relevés fiscaux reçus. Une valeur seulement proposée, ou un relevé manquant, rend le total provisoire.",
    eml: "Télécharger le brouillon (.eml) — Ordner ne l'envoie jamais", missing_vars: "À compléter avant envoi :",
    h_check: "Contrôle des pièces", wrong_year: "Mauvaise année :", duplicates: "Doublons probables :", check_why: "Détail du contrôle",
    review_btn: "Revoir le dossier (règles, sans modèle)", review_done: "Revue terminée : démarches, échéances et manques mis à jour.",
    ask_title: "Demander à Ordner", close: "Fermer", ask_examples: "Questions enregistrées", ask_label: "Votre question", ask_send: "Demander",
    ask_demo: r => `Mode démo (${r}) : les réponses sont des transcriptions enregistrées, marquées fixture, pas une sortie du modèle.`,
    ask_reasons: { no_endpoint: "aucun modèle configuré, LLM_BASE_URL", no_agent: "coordinateur pas encore disponible", no_client: "client modèle introuvable" },
    ask_live: n => `Modèle local : ${n}. Ordner prépare, vous validez : rien n'est envoyé.`,
    ask_nearest: "Mode démo : réponse enregistrée la plus proche de votre question.", ask_wait: "Ordner travaille… (modèle local, cela peut prendre une minute)",
    you: "Vous", steps_n: n => `Étapes (${n} appels d'outils)`, recorded: "réponse enregistrée (fixture)", asks_you: "Ordner vous demande :",
    prepared_note: "préparée, à valider dans la démarche ; rien n'est envoyé", warnings: "Avertissements",
    unavailable: m => `Module pas encore disponible : ${m}`, loading: "Chargement…", fictional: "dossier fictif",
    ics: "Exporter le calendrier (.ics)", ics_off: "Export du calendrier : module des règles pas encore disponible", subject_pick: "Dossier",
    h_next: "Prochaine étape", h_urgent: "Urgent : échéances dans les 30 jours", h_missing: "Pièces et informations manquantes", h_review: "Pièces à vérifier (doute élevé)",
    none_urgent: "Aucune échéance dans les 30 prochains jours.", none_missing: "Rien ne manque dans les démarches ouvertes.",
    none_review: "Aucune valeur en rouge : rien à relire.", none_next: "Rien à faire pour l'instant dans les parcours couverts.",
    next_validate: (k, c) => `Valider : ${k} — ${c}`, next_provide: (i, c) => `Fournir ${i} pour « ${c} »`,
    next_qualify: c => `Répondre aux questions qui qualifient « ${c} »`, next_review: (d, f) => `Relire ${d} : ${f}`,
    open_case: "Ouvrir la démarche", open_inbox: "Voir les pièces", due_on: d => `échéance le ${d}`,
    days: n => (n < 0 ? `en retard de ${-n} j` : n === 0 ? "aujourd'hui" : n === 1 ? "demain" : `dans ${n} jours`),
    reminders: "Rappels :", red_fields: "Champs en rouge :",
    cov_banner: (c, v, n, w) => `Parcours examinés (${w}) — couverts : ${c} · à vérifier : ${v} · non applicables : ${n}.`, notes: "Notes de qualification de la fiche",
    cov_where: k => `${k} et fédéral`, cov_nodomain: l => `Domaines sans aucune fiche : ${l}.`,
    cov_claim: "« Aucun problème détecté » ne vaut que pour les parcours couverts ; le reste est à vérifier.",
    cov_norules: "Moteur de règles pas encore disponible : tout reste « à vérifier ».", cov_details: "Détail des parcours examinés", cov_map_link: "Carte de couverture",
    no_cases: "Aucune démarche ouverte pour l'instant. Les démarches sont ouvertes à partir du profil, des pièces et du catalogue.",
    inbox_caption: "Pièces reçues avec type, année, mode de lecture et doute", col_received: "Reçue le", col_type: "Type", col_year: "Année", col_issuer: "Émetteur",
    col_channel: "Canal", col_read: "Lecture", read: { barcode: "code-barres · exact", ai: "IA (OCR + Apertus)" },
    channels: { inbox: "dépôt", share: "partage", camt: "relevé bancaire", email: "e-mail", scan: "scan, photo", video: "vidéo" },
    inbox_legend: "Code-barres : valeur exacte lue dans le code (eCH-0196, QR-facture). IA : lecture OCR puis Apertus avec un score de doute ; seules les valeurs en rouge demandent une relecture.",
    no_docs: "Aucune pièce reçue.", progress: (i, n) => `étape ${i} sur ${n}`, next_due: d => `Prochaine échéance : ${d}`, missing_l: "Manque :",
    nature: { obligation: "obligation", right: "droit à demander", option: "option", contract: "contrat" },
    qual: { qualified: "fiche qualifiée", draft: "fiche en brouillon", unknown: "fiche non qualifiée" }, unknown_card: "fiche absente du catalogue",
    states: { to_qualify: "À qualifier", missing_documents: "Pièces manquantes", ready_to_prepare: "Prêt à préparer", ready_to_validate: "À valider",
      action_engaged: "Action engagée", awaiting_response: "En attente de réponse", complement_requested: "Complément demandé",
      decision_received: "Décision reçue", result_verified: "Résultat vérifié", closed: "Clos" },
    domains: { tax: "Impôts", health_insurance: "Assurance maladie", pension: "Prévoyance", social: "Assurances sociales", housing: "Logement", debt: "Dettes, poursuites",
      work: "Travail", business: "Entreprise", identity: "Identité, domicile" },
    back: "← Toutes les démarches", period: p => `période ${p}`, h_progress: "Avancement", h_case_missing: "Ce qui manque", h_deadlines: "Échéances",
    h_actions: "Actions préparées", h_facts: "Informations du dossier", h_events: "Historique", h_sources: "Sources officielles", h_steps: "Étapes de la procédure",
    who: { user: "vous", ordner: "Ordner" }, validate: "Valider",
    validated_msg: "Validation enregistrée. Ordner n'envoie rien : c'est vous qui envoyez, déposez ou payez.",
    pay_note: "Paiement QR : Ordner ne l'exécute jamais. Payez vous-même depuis votre e-banking.", send_note: "Rien n'est envoyé automatiquement.",
    kinds: { form_entry: "Saisie guidée du formulaire", letter: "Lettre", email_draft: "Brouillon d'e-mail", payment: "Paiement QR", reminder: "Rappel", document_request: "Demande de pièce" },
    astatus: { prepared: "préparée", validated: "validée par vous", done_by_user: "faite par vous", verified: "vérifiée", cancelled: "annulée" },
    fstatus: { proposed: "proposée", confirmed: "confirmée", rejected: "rejetée", superseded: "remplacée" },
    actors: { user: "vous", ordner: "Ordner", connector: "connecteur", rule: "règle", model: "modèle" },
    col_key: "Information", col_period: "Période", col_status: "Statut", col_source: "Source", facts_caption: "Informations liées à cette démarche, avec statut et source",
    rule_l: "Règle :", basis_l: "Bases :", computed_l: "Calcul", send_by: d => `envoi conseillé avant le ${d}`,
    no_deadlines: "Aucune échéance enregistrée.", no_actions: "Aucune action préparée.", no_facts: "Aucune information liée.", no_events: "Aucun événement.",
    no_sources: "Aucune source citée : fiche à qualifier.", releve_link: "Voir les relevés fiscaux lus (champs, doute, explication, déductions)",
    events: { subject_added: "dossier créé", document_received: "pièce reçue", fact_proposed: "information proposée", fact_confirmed: "information confirmée",
      fact_rejected: "information rejetée", fact_superseded: "information remplacée", case_opened: "démarche ouverte", state_changed: "changement d'état",
      missing_updated: "manques mis à jour", action_prepared: "action préparée", action_updated: "action mise à jour", deadline_added: "échéance ajoutée" },
    cov_title: "Couverture du catalogue",
    cov_intro: "Une démarche peut être qualifiée au niveau fédéral, en brouillon dans un canton et non couverte ailleurs. Une case vide ne signifie pas qu'il n'y a rien à faire : le catalogue ne couvre pas encore cette zone.",
    cov_caption: "Fiches de procédure par domaine et par juridiction", cov_domain: "Domaine",
    cov_status: { qualified: "qualifiée", draft: "brouillon", none: "non couverte" }, cov_counts: (q, d) => `${q} cases qualifiées, ${d} en brouillon.`,
    you_here: "vous", cov_yours: "Vos parcours examinés", verdict: { covered: "couvert", to_verify: "à vérifier", not_applicable: "non applicable" },
    app: { applicable: "s'applique", not_applicable: "ne s'applique pas", missing_info: "informations manquantes", unknown: "non évalué", error: "erreur de règle" },
    yes: "oui", no: "non",
    pk: { issuer: "établissement", to: "destinataire", channel: "canal", creditor: "bénéficiaire", amount: "montant", currency: "monnaie", reference: "référence", iban: "IBAN", due: "échéance", recipient: "destinataire" },
    fact_labels: { "subject.tax_at_source": "imposition à la source (oui ou non)", "tax.securities.withholding_tax_total": "total de l'impôt anticipé", "tax.period": "période fiscale", "person.civil_status": "état civil" }
  },
  de: {
    nav_label: "Bereiche", nav_home: "Wo stehe ich", nav_inbox: "Eingang", nav_cases: "Verfahren", nav_coverage: "Abdeckung", nav_releve: "Steuerausweis",
    sim_date: d => `simuliertes Datum: ${d}`, h_wealth: y => `Ihr Vermögen und Ihre Wertschriftenerträge zum Deklarieren (${y})`,
    wealth_status: { final: "definitiv", provisional: "provisorisch", incomplete: "unvollständig" },
    measures: { total_tax_value: "Steuerwert der Wertschriften (Vermögen)", gross_revenue_a: "Bruttoerträge A (mit Verrechnungssteuer)",
      gross_revenue_b: "Bruttoerträge B (ohne Verrechnungssteuer)", withholding_tax_claim: "Rückforderbare Verrechnungssteuer" },
    m_status: { confirmed: "bestätigt", provisional: "provisorisch", missing: "fehlt" }, inst_in: "Einbezogene Institute:", inst_missing: "Institute ohne Ausweis:",
    wealth_note: "Summe der eingegangenen Steuerausweise. Ein nur vorgeschlagener Wert oder ein fehlender Ausweis macht das Total provisorisch.",
    eml: "Entwurf herunterladen (.eml) — Ordner sendet ihn nie", missing_vars: "Vor dem Versand ergänzen:",
    h_check: "Prüfung der Unterlagen", wrong_year: "Falsches Jahr:", duplicates: "Wahrscheinliche Doppel:", check_why: "Details der Prüfung",
    review_btn: "Dossier überprüfen (Regeln, ohne Modell)", review_done: "Überprüfung beendet: Verfahren, Fristen und Fehlendes aktualisiert.",
    ask_title: "Ordner fragen", close: "Schliessen", ask_examples: "Aufgezeichnete Fragen", ask_label: "Ihre Frage", ask_send: "Fragen",
    ask_demo: r => `Demo-Modus (${r}): Die Antworten sind aufgezeichnete Transkripte, als Fixture markiert, keine Modellausgabe.`,
    ask_reasons: { no_endpoint: "kein Modell konfiguriert, LLM_BASE_URL", no_agent: "Koordinator noch nicht verfügbar", no_client: "Modell-Client nicht gefunden" },
    ask_live: n => `Lokales Modell: ${n}. Ordner bereitet vor, Sie bestätigen: Es wird nichts gesendet.`,
    ask_nearest: "Demo-Modus: aufgezeichnete Antwort, die Ihrer Frage am nächsten kommt.", ask_wait: "Ordner arbeitet… (lokales Modell, das kann eine Minute dauern)",
    you: "Sie", steps_n: n => `Schritte (${n} Werkzeugaufrufe)`, recorded: "aufgezeichnete Antwort (Fixture)", asks_you: "Ordner fragt Sie:",
    prepared_note: "vorbereitet, im Verfahren zu bestätigen; es wird nichts gesendet", warnings: "Warnungen",
    unavailable: m => `Modul noch nicht verfügbar: ${m}`, loading: "Wird geladen…", fictional: "fiktives Dossier",
    ics: "Kalender exportieren (.ics)", ics_off: "Kalenderexport: Regelmodul noch nicht verfügbar", subject_pick: "Dossier",
    h_next: "Nächster Schritt", h_urgent: "Dringend: Fristen in den nächsten 30 Tagen", h_missing: "Fehlende Unterlagen und Angaben", h_review: "Zu prüfende Unterlagen (hoher Zweifel)",
    none_urgent: "Keine Frist in den nächsten 30 Tagen.", none_missing: "In den offenen Verfahren fehlt nichts.",
    none_review: "Kein roter Wert: nichts nachzulesen.", none_next: "In den abgedeckten Bereichen ist im Moment nichts zu tun.",
    next_validate: (k, c) => `Bestätigen: ${k} — ${c}`, next_provide: (i, c) => `${i} liefern für «${c}»`,
    next_qualify: c => `Fragen beantworten, um «${c}» abzuklären`, next_review: (d, f) => `${d} nachlesen: ${f}`,
    open_case: "Verfahren öffnen", open_inbox: "Unterlagen ansehen", due_on: d => `Frist am ${d}`,
    days: n => (n < 0 ? `${-n} T überfällig` : n === 0 ? "heute" : n === 1 ? "morgen" : `in ${n} Tagen`),
    reminders: "Erinnerungen:", red_fields: "Rote Felder:",
    cov_banner: (c, v, n, w) => `Geprüfte Verfahren (${w}) — abgedeckt: ${c} · zu prüfen: ${v} · nicht anwendbar: ${n}.`, notes: "Qualifizierungsnotizen der Karte",
    cov_where: k => `${k} und Bund`, cov_nodomain: l => `Bereiche ohne Karte: ${l}.`,
    cov_claim: "«Kein Problem gefunden» gilt nur für die abgedeckten Verfahren; der Rest ist zu prüfen.",
    cov_norules: "Regelwerk noch nicht verfügbar: Alles bleibt «zu prüfen».", cov_details: "Geprüfte Verfahren im Detail", cov_map_link: "Abdeckungskarte",
    no_cases: "Noch kein offenes Verfahren. Verfahren werden aus Profil, Unterlagen und Katalog eröffnet.",
    inbox_caption: "Eingegangene Unterlagen mit Typ, Jahr, Leseart und Zweifel", col_received: "Eingang", col_type: "Typ", col_year: "Jahr", col_issuer: "Aussteller",
    col_channel: "Kanal", col_read: "Lesung", read: { barcode: "Barcode · exakt", ai: "KI (OCR + Apertus)" },
    channels: { inbox: "Ablage", share: "Teilen", camt: "Bankauszug", email: "E-Mail", scan: "Scan, Foto", video: "Video" },
    inbox_legend: "Barcode: exakter Wert aus dem Code (eCH-0196, QR-Rechnung). KI: OCR, dann Apertus mit Zweifelswert; nur rote Werte müssen nachgelesen werden.",
    no_docs: "Keine Unterlagen eingegangen.", progress: (i, n) => `Schritt ${i} von ${n}`, next_due: d => `Nächste Frist: ${d}`, missing_l: "Fehlt:",
    nature: { obligation: "Pflicht", right: "Anspruch (auf Antrag)", option: "Option", contract: "Vertrag" },
    qual: { qualified: "qualifizierte Karte", draft: "Karte im Entwurf", unknown: "nicht qualifizierte Karte" }, unknown_card: "Karte nicht im Katalog",
    states: { to_qualify: "Abzuklären", missing_documents: "Unterlagen fehlen", ready_to_prepare: "Bereit zur Vorbereitung", ready_to_validate: "Zu bestätigen",
      action_engaged: "Schritt eingeleitet", awaiting_response: "Antwort ausstehend", complement_requested: "Ergänzung verlangt",
      decision_received: "Entscheid erhalten", result_verified: "Ergebnis geprüft", closed: "Abgeschlossen" },
    domains: { tax: "Steuern", health_insurance: "Krankenversicherung", pension: "Vorsorge", social: "Sozialversicherungen", housing: "Wohnen", debt: "Schulden, Betreibung",
      work: "Arbeit", business: "Unternehmen", identity: "Identität, Wohnsitz" },
    back: "← Alle Verfahren", period: p => `Periode ${p}`, h_progress: "Fortschritt", h_case_missing: "Was fehlt", h_deadlines: "Fristen",
    h_actions: "Vorbereitete Schritte", h_facts: "Angaben im Dossier", h_events: "Verlauf", h_sources: "Amtliche Quellen", h_steps: "Ablauf des Verfahrens",
    who: { user: "Sie", ordner: "Ordner" }, validate: "Bestätigen",
    validated_msg: "Bestätigung gespeichert. Ordner sendet nichts: Sie selbst senden, reichen ein oder bezahlen.",
    pay_note: "QR-Zahlung: Ordner führt sie nie aus. Bezahlen Sie selbst im E-Banking.", send_note: "Es wird nichts automatisch gesendet.",
    kinds: { form_entry: "Geführte Formulareingabe", letter: "Brief", email_draft: "E-Mail-Entwurf", payment: "QR-Zahlung", reminder: "Erinnerung", document_request: "Unterlagen anfordern" },
    astatus: { prepared: "vorbereitet", validated: "von Ihnen bestätigt", done_by_user: "von Ihnen erledigt", verified: "geprüft", cancelled: "abgebrochen" },
    fstatus: { proposed: "vorgeschlagen", confirmed: "bestätigt", rejected: "abgelehnt", superseded: "ersetzt" },
    actors: { user: "Sie", ordner: "Ordner", connector: "Konnektor", rule: "Regel", model: "Modell" },
    col_key: "Angabe", col_period: "Periode", col_status: "Status", col_source: "Quelle", facts_caption: "Angaben zu diesem Verfahren mit Status und Quelle",
    rule_l: "Regel:", basis_l: "Grundlagen:", computed_l: "Berechnung", send_by: d => `Versand empfohlen vor dem ${d}`,
    no_deadlines: "Keine Frist erfasst.", no_actions: "Kein vorbereiteter Schritt.", no_facts: "Keine verknüpfte Angabe.", no_events: "Kein Ereignis.",
    no_sources: "Keine Quelle zitiert: Karte noch zu qualifizieren.", releve_link: "Gelesene Steuerausweise ansehen (Felder, Zweifel, Erklärung, Abzüge)",
    events: { subject_added: "Dossier erstellt", document_received: "Unterlage eingegangen", fact_proposed: "Angabe vorgeschlagen", fact_confirmed: "Angabe bestätigt",
      fact_rejected: "Angabe abgelehnt", fact_superseded: "Angabe ersetzt", case_opened: "Verfahren eröffnet", state_changed: "Statuswechsel",
      missing_updated: "Fehlendes aktualisiert", action_prepared: "Schritt vorbereitet", action_updated: "Schritt aktualisiert", deadline_added: "Frist hinzugefügt" },
    cov_title: "Abdeckung des Katalogs",
    cov_intro: "Ein Verfahren kann auf Bundesebene qualifiziert, in einem Kanton im Entwurf und anderswo nicht abgedeckt sein. Ein leeres Feld heisst nicht, dass nichts zu tun ist: Der Katalog deckt diesen Bereich noch nicht ab.",
    cov_caption: "Verfahrenskarten nach Bereich und Zuständigkeit", cov_domain: "Bereich",
    cov_status: { qualified: "qualifiziert", draft: "Entwurf", none: "nicht abgedeckt" }, cov_counts: (q, d) => `${q} Felder qualifiziert, ${d} im Entwurf.`,
    you_here: "Sie", cov_yours: "Ihre geprüften Verfahren", verdict: { covered: "abgedeckt", to_verify: "zu prüfen", not_applicable: "nicht anwendbar" },
    app: { applicable: "anwendbar", not_applicable: "nicht anwendbar", missing_info: "Angaben fehlen", unknown: "nicht ausgewertet", error: "Regelfehler" },
    yes: "ja", no: "nein",
    pk: { issuer: "Institut", to: "Empfänger", channel: "Kanal", creditor: "Zahlungsempfänger", amount: "Betrag", currency: "Währung", reference: "Referenz", iban: "IBAN", due: "Fälligkeit", recipient: "Empfänger" },
    fact_labels: { "subject.tax_at_source": "Quellensteuer (ja oder nein)", "tax.securities.withholding_tax_total": "Total Verrechnungssteuer", "tax.period": "Steuerperiode", "person.civil_status": "Zivilstand" }
  },
  it: {
    nav_label: "Sezioni", nav_home: "A che punto sono", nav_inbox: "Documenti ricevuti", nav_cases: "Pratiche", nav_coverage: "Copertura", nav_releve: "Estratto fiscale",
    sim_date: d => `data simulata: ${d}`, h_wealth: y => `La sua sostanza e i redditi da titoli da dichiarare (${y})`,
    wealth_status: { final: "definitivo", provisional: "provvisorio", incomplete: "incompleto" },
    measures: { total_tax_value: "Valore fiscale dei titoli (sostanza)", gross_revenue_a: "Redditi lordi A (con imposta preventiva)",
      gross_revenue_b: "Redditi lordi B (senza imposta preventiva)", withholding_tax_claim: "Imposta preventiva da recuperare" },
    m_status: { confirmed: "confermato", provisional: "provvisorio", missing: "mancante" }, inst_in: "Istituti inclusi:", inst_missing: "Istituti senza estratto:",
    wealth_note: "Somma degli estratti fiscali ricevuti. Un valore solo proposto, o un estratto mancante, rende il totale provvisorio.",
    eml: "Scaricare la bozza (.eml) — Ordner non la invia mai", missing_vars: "Da completare prima dell'invio:",
    h_check: "Controllo dei documenti", wrong_year: "Anno sbagliato:", duplicates: "Probabili doppioni:", check_why: "Dettaglio del controllo",
    review_btn: "Rivedere il dossier (regole, senza modello)", review_done: "Revisione terminata: pratiche, scadenze e mancanze aggiornate.",
    ask_title: "Chiedere a Ordner", close: "Chiudere", ask_examples: "Domande registrate", ask_label: "La sua domanda", ask_send: "Chiedere",
    ask_demo: r => `Modalità demo (${r}): le risposte sono trascrizioni registrate, marcate fixture, non un output del modello.`,
    ask_reasons: { no_endpoint: "nessun modello configurato, LLM_BASE_URL", no_agent: "coordinatore non ancora disponibile", no_client: "client del modello non trovato" },
    ask_live: n => `Modello locale: ${n}. Ordner prepara, lei convalida: non viene inviato nulla.`,
    ask_nearest: "Modalità demo: risposta registrata più vicina alla sua domanda.", ask_wait: "Ordner lavora… (modello locale, può richiedere un minuto)",
    you: "Lei", steps_n: n => `Passi (${n} chiamate di strumenti)`, recorded: "risposta registrata (fixture)", asks_you: "Ordner le chiede:",
    prepared_note: "preparata, da convalidare nella pratica; non viene inviato nulla", warnings: "Avvertenze",
    unavailable: m => `Modulo non ancora disponibile: ${m}`, loading: "Caricamento…", fictional: "dossier fittizio",
    ics: "Esportare il calendario (.ics)", ics_off: "Esportazione del calendario: modulo delle regole non ancora disponibile", subject_pick: "Dossier",
    h_next: "Prossimo passo", h_urgent: "Urgente: scadenze entro 30 giorni", h_missing: "Documenti e informazioni mancanti", h_review: "Documenti da verificare (dubbio alto)",
    none_urgent: "Nessuna scadenza nei prossimi 30 giorni.", none_missing: "Nelle pratiche aperte non manca nulla.",
    none_review: "Nessun valore in rosso: niente da rileggere.", none_next: "Per ora niente da fare nei percorsi coperti.",
    next_validate: (k, c) => `Convalidare: ${k} — ${c}`, next_provide: (i, c) => `Fornire ${i} per «${c}»`,
    next_qualify: c => `Rispondere alle domande che qualificano «${c}»`, next_review: (d, f) => `Rileggere ${d}: ${f}`,
    open_case: "Aprire la pratica", open_inbox: "Vedere i documenti", due_on: d => `scadenza il ${d}`,
    days: n => (n < 0 ? `in ritardo di ${-n} g` : n === 0 ? "oggi" : n === 1 ? "domani" : `tra ${n} giorni`),
    reminders: "Promemoria:", red_fields: "Campi in rosso:",
    cov_banner: (c, v, n, w) => `Percorsi esaminati (${w}) — coperti: ${c} · da verificare: ${v} · non applicabili: ${n}.`, notes: "Note di qualificazione della scheda",
    cov_where: k => `${k} e Confederazione`, cov_nodomain: l => `Ambiti senza alcuna scheda: ${l}.`,
    cov_claim: "«Nessun problema rilevato» vale solo per i percorsi coperti; il resto è da verificare.",
    cov_norules: "Motore delle regole non ancora disponibile: tutto resta «da verificare».", cov_details: "Dettaglio dei percorsi esaminati", cov_map_link: "Carta della copertura",
    no_cases: "Ancora nessuna pratica aperta. Le pratiche vengono aperte a partire dal profilo, dai documenti e dal catalogo.",
    inbox_caption: "Documenti ricevuti con tipo, anno, modalità di lettura e dubbio", col_received: "Ricevuto il", col_type: "Tipo", col_year: "Anno", col_issuer: "Emittente",
    col_channel: "Canale", col_read: "Lettura", read: { barcode: "codice a barre · esatto", ai: "IA (OCR + Apertus)" },
    channels: { inbox: "deposito", share: "condivisione", camt: "estratto bancario", email: "e-mail", scan: "scansione, foto", video: "video" },
    inbox_legend: "Codice a barre: valore esatto letto nel codice (eCH-0196, fattura QR). IA: lettura OCR poi Apertus con un punteggio di dubbio; solo i valori in rosso vanno riletti.",
    no_docs: "Nessun documento ricevuto.", progress: (i, n) => `passo ${i} di ${n}`, next_due: d => `Prossima scadenza: ${d}`, missing_l: "Manca:",
    nature: { obligation: "obbligo", right: "diritto da richiedere", option: "opzione", contract: "contratto" },
    qual: { qualified: "scheda qualificata", draft: "scheda in bozza", unknown: "scheda non qualificata" }, unknown_card: "scheda assente dal catalogo",
    states: { to_qualify: "Da qualificare", missing_documents: "Documenti mancanti", ready_to_prepare: "Pronto da preparare", ready_to_validate: "Da convalidare",
      action_engaged: "Azione avviata", awaiting_response: "In attesa di risposta", complement_requested: "Complemento richiesto",
      decision_received: "Decisione ricevuta", result_verified: "Risultato verificato", closed: "Chiuso" },
    domains: { tax: "Imposte", health_insurance: "Assicurazione malattia", pension: "Previdenza", social: "Assicurazioni sociali", housing: "Alloggio", debt: "Debiti, esecuzioni",
      work: "Lavoro", business: "Impresa", identity: "Identità, domicilio" },
    back: "← Tutte le pratiche", period: p => `periodo ${p}`, h_progress: "Avanzamento", h_case_missing: "Cosa manca", h_deadlines: "Scadenze",
    h_actions: "Azioni preparate", h_facts: "Informazioni del dossier", h_events: "Cronologia", h_sources: "Fonti ufficiali", h_steps: "Passi della procedura",
    who: { user: "lei", ordner: "Ordner" }, validate: "Convalidare",
    validated_msg: "Convalida registrata. Ordner non invia nulla: è lei a inviare, depositare o pagare.",
    pay_note: "Pagamento QR: Ordner non lo esegue mai. Paghi lei stesso dal suo e-banking.", send_note: "Non viene inviato nulla automaticamente.",
    kinds: { form_entry: "Compilazione guidata del modulo", letter: "Lettera", email_draft: "Bozza di e-mail", payment: "Pagamento QR", reminder: "Promemoria", document_request: "Richiesta di documento" },
    astatus: { prepared: "preparata", validated: "convalidata da lei", done_by_user: "fatta da lei", verified: "verificata", cancelled: "annullata" },
    fstatus: { proposed: "proposta", confirmed: "confermata", rejected: "respinta", superseded: "sostituita" },
    actors: { user: "lei", ordner: "Ordner", connector: "connettore", rule: "regola", model: "modello" },
    col_key: "Informazione", col_period: "Periodo", col_status: "Stato", col_source: "Fonte", facts_caption: "Informazioni legate a questa pratica, con stato e fonte",
    rule_l: "Regola:", basis_l: "Basi:", computed_l: "Calcolo", send_by: d => `invio consigliato entro il ${d}`,
    no_deadlines: "Nessuna scadenza registrata.", no_actions: "Nessuna azione preparata.", no_facts: "Nessuna informazione collegata.", no_events: "Nessun evento.",
    no_sources: "Nessuna fonte citata: scheda da qualificare.", releve_link: "Vedere gli estratti fiscali letti (campi, dubbio, spiegazione, deduzioni)",
    events: { subject_added: "dossier creato", document_received: "documento ricevuto", fact_proposed: "informazione proposta", fact_confirmed: "informazione confermata",
      fact_rejected: "informazione respinta", fact_superseded: "informazione sostituita", case_opened: "pratica aperta", state_changed: "cambio di stato",
      missing_updated: "mancanze aggiornate", action_prepared: "azione preparata", action_updated: "azione aggiornata", deadline_added: "scadenza aggiunta" },
    cov_title: "Copertura del catalogo",
    cov_intro: "Una pratica può essere qualificata a livello federale, in bozza in un Cantone e non coperta altrove. Una casella vuota non significa che non ci sia nulla da fare: il catalogo non copre ancora questa zona.",
    cov_caption: "Schede di procedura per ambito e giurisdizione", cov_domain: "Ambito",
    cov_status: { qualified: "qualificata", draft: "bozza", none: "non coperta" }, cov_counts: (q, d) => `${q} caselle qualificate, ${d} in bozza.`,
    you_here: "lei", cov_yours: "I suoi percorsi esaminati", verdict: { covered: "coperto", to_verify: "da verificare", not_applicable: "non applicabile" },
    app: { applicable: "si applica", not_applicable: "non si applica", missing_info: "informazioni mancanti", unknown: "non valutato", error: "errore di regola" },
    yes: "sì", no: "no",
    pk: { issuer: "istituto", to: "destinatario", channel: "canale", creditor: "beneficiario", amount: "importo", currency: "valuta", reference: "riferimento", iban: "IBAN", due: "scadenza", recipient: "destinatario" },
    fact_labels: { "subject.tax_at_source": "imposizione alla fonte (sì o no)", "tax.securities.withholding_tax_total": "totale dell'imposta preventiva", "tax.period": "periodo fiscale", "person.civil_status": "stato civile" }
  }
};
for (const l in C18N) Object.assign(I18N[l], C18N[l]);
Object.assign(I18N.fr.doc_types, { salary_certificate: "certificat de salaire", pillar3a_certificate: "attestation 3a", tax_return_invitation: "formulaire de déclaration (code de contrôle)",
  pension_fund_certificate: "attestation de rachat 2e pilier", health_insurance_tax_certificate: "attestation fiscale d'assurance maladie", securities_list: "état des titres",
  tax_assessment_decision: "décision de taxation", camt053: "relevé bancaire camt.053", identity_document: "pièce d'identité", health_insurance_policy: "police d'assurance maladie",
  study_certificate: "attestation d'études", tax_instalment_bill: "bordereau d'acomptes" });
Object.assign(I18N.de.doc_types, { salary_certificate: "Lohnausweis", pillar3a_certificate: "Bescheinigung Säule 3a", tax_return_invitation: "Steuerformular (Kontrollcode)",
  pension_fund_certificate: "Bescheinigung Einkauf 2. Säule", health_insurance_tax_certificate: "Steuerbescheinigung Krankenkasse", securities_list: "Wertschriftenverzeichnis",
  tax_assessment_decision: "Veranlagungsverfügung", camt053: "Bankauszug camt.053", identity_document: "Ausweis", health_insurance_policy: "Versicherungspolice Krankenkasse",
  study_certificate: "Studienbescheinigung", tax_instalment_bill: "Ratenrechnung" });
Object.assign(I18N.it.doc_types, { salary_certificate: "certificato di salario", pillar3a_certificate: "attestazione 3a", tax_return_invitation: "modulo di dichiarazione (codice di controllo)",
  pension_fund_certificate: "attestazione di riscatto 2° pilastro", health_insurance_tax_certificate: "attestazione fiscale cassa malati", securities_list: "elenco dei titoli",
  tax_assessment_decision: "decisione di tassazione", camt053: "estratto bancario camt.053", identity_document: "documento d'identità", health_insurance_policy: "polizza cassa malati",
  study_certificate: "attestato di studio", tax_instalment_bill: "fattura degli acconti" });

const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = x => Math.round(x * 100);
const num = x => (x == null ? "–" : Number(x).toFixed(2));
const chf = x => Number(x).toLocaleString("de-CH") + " CHF";

const state = { lang: "fr", demo: null, results: null, doc: 0, deductions: null };
try { state.lang = localStorage.getItem("ordner.lang") || "fr"; } catch (e) { /* storage blocked */ }
if (!I18N[state.lang]) state.lang = "fr";
const T = () => I18N[state.lang];

async function getJSON(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r.json();
}

function applyStatic() {
  const t = T();
  document.documentElement.lang = state.lang;
  document.title = `Ordner — ${t.tagline}`;
  document.querySelectorAll("[data-i18n]").forEach(el => { if (typeof t[el.dataset.i18n] === "string") el.textContent = t[el.dataset.i18n]; });
  document.querySelectorAll("[data-i18n-aria]").forEach(el => el.setAttribute("aria-label", t[el.dataset.i18nAria]));
  document.querySelectorAll(".langs button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.lang === state.lang)));
  const notes = [];
  if (state.demo?.fixture) notes.push(t.fixture_demo);
  if (state.results?.fixture) notes.push(t.fixture_results);
  $("#fixture-banner").hidden = !notes.length;
  $("#fixture-banner").textContent = notes.join(" ");
}

function level(doubt) {
  if (doubt == null) return "na";
  const lv = state.demo?.doubt_levels || { orange: 0.25, red: 0.5 };
  return doubt >= lv.red ? "high" : doubt >= lv.orange ? "medium" : "low";
}

function signalLines(s) {
  const t = T(), out = [];
  if (!s) return out;
  if (s.probe != null) out.push({ flag: s.probe >= 0.5, text: t.sig_probe(num(s.probe)) });
  if (s.d1_p_yes != null) out.push({ flag: s.d1_p_yes < 0.5, text: t.sig_d1(num(s.d1_p_yes)) });
  if (s.rule_ok != null) {
    const name = t.rules[s.rule] || s.rule || "?";
    out.push({ flag: s.rule_ok === false, text: s.rule_ok ? t.sig_rule_ok(name) : t.sig_rule_bad(name) });
  }
  if (s.lp_min != null) { const p = Math.exp(s.lp_min); out.push({ flag: p < 0.5, text: t.sig_lp(num(p)) }); }
  return out;
}

function renderThumbs() {
  const t = T();
  $("#thumbs").innerHTML = state.demo.documents.map((d, i) => {
    const inst = d.fields.find(f => f.field === "institution")?.value || d.page_id;
    return `<button type="button" data-i="${i}" aria-pressed="${i === state.doc}">
      <img src="/data/demo/${encodeURIComponent(d.image)}" alt="">
      <span><strong>${esc(inst)}</strong><br>${esc(t.thumb(d.language.toUpperCase(), d.layout, d.degradation))}</span>
    </button>`;
  }).join("");
  $("#thumbs").querySelectorAll("button").forEach(b => b.onclick = () => { state.doc = +b.dataset.i; renderAll(); });
}

function renderDoc() {
  const t = T(), d = state.demo.documents[state.doc];
  const inst = d.fields.find(f => f.field === "institution")?.value || d.page_id;
  $("#page-img").src = `/data/demo/${encodeURIComponent(d.image)}`;
  $("#page-img").alt = `${inst} — ${d.page_id}`;
  $("#page-meta").textContent = t.page_meta(d.layout, d.degradation, t.langs[d.language] || d.language) + (d.layout === "B" ? t.unseen : "");
  $("#route").textContent = d.route ? t.route(d.route.model, t.doc_types[d.route.label] || d.route.label, num(d.route.p)) : "";
  $("#fields tbody").innerHTML = d.fields.map(f => {
    const lv = level(f.doubt), lines = signalLines(f.signals), flagged = lines.filter(l => l.flag);
    const why = flagged.length ? `<ul>${flagged.map(l => `<li class="flag">${esc(l.text)}</li>`).join("")}</ul>` : `<span class="muted">${esc(t.no_flag)}</span>`;
    const all = lines.length ? `<details><summary>${esc(t.signals)}</summary><ul>${lines.map(l => `<li>${esc(l.text)}</li>`).join("")}</ul></details>` : "";
    let oracle = "–";
    if (f.gold != null) oracle = f.correct ? `<span class="ok-mark">✓ ${esc(t.correct)}</span>` : `<span class="bad-mark">✗ ${esc(t.wrong)} <strong>${esc(f.gold)}</strong></span>`;
    return `<tr class="lv-${lv}">
      <th scope="row">${esc(t.fields[f.field] || f.field)}</th>
      <td><span class="value">${esc(f.value ?? "–")}</span><span class="model">${esc(f.model || "")}</span></td>
      <td><span class="chip ${lv}">${esc(t.lv[lv])}${f.doubt != null ? " · " + num(f.doubt) : ""}</span></td>
      <td class="why">${why}${all}</td>
      <td>${oracle}</td>
    </tr>`;
  }).join("");
}

const CURVES_SHOWN = ["min token prob", "d1 validation", "rules", "probe A"];

function caughtAt(curve, x) {
  let prev = curve[0];
  for (const p of curve) {
    if (p[0] >= x) return p[0] === prev[0] ? p[1] : prev[1] + ((p[1] - prev[1]) * (x - prev[0])) / (p[0] - prev[0]);
    prev = p;
  }
  return prev[1];
}

function triageData() {
  const curves = state.results?.curves || {};
  const primary = ["combined", "probe A"].find(n => curves[n]?.length) || Object.keys(curves).find(n => curves[n]?.length);
  if (!primary) return null;
  const sorted = Object.fromEntries(Object.entries(curves).map(([n, c]) => [n, c.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1])]));
  return { curves: sorted, primary, stats: state.results.doubt?.["apertus-base"] || {} };
}

function renderTriage() {
  const t = T(), d = triageData();
  $("#triage").hidden = !d;
  $("#triage-missing").hidden = !!d;
  if (!d) return;
  const x = +$("#thr").value, y = caughtAt(d.curves[d.primary], x);
  const label = n => (t.curves[n] || n) + (d.stats[n]?.auroc != null ? ` (AUROC ${d.stats[n].auroc.toFixed(2)})` : "");
  const others = CURVES_SHOWN.filter(n => n !== d.primary && d.curves[n]?.length);
  $("#thr-val").textContent = `${pct(x)} %`;
  $("#triage-out").textContent = t.triage_out(pct(x), pct(y));
  $("#triage-meta").textContent = t.triage_meta(d.stats._n?.items ?? "?", d.stats._n?.wrong ?? "?", label(d.primary), others.map(label).join(", ") || "–");
  const X = v => 52 + v * 272, Y = v => 190 - v * 175;
  const path = c => c.map((p, i) => `${i ? "L" : "M"}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join("");
  let svg = `<title>${esc(t.curve_label)}</title>`;
  for (const v of [0.25, 0.5, 0.75, 1]) svg += `<line class="grid" x1="${X(0)}" x2="${X(1)}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${X(0) - 6}" y="${Y(v) + 4}" text-anchor="end">${pct(v)}%</text>`;
  for (const v of [0.25, 0.5, 0.75, 1]) svg += `<text x="${X(v)}" y="${Y(0) + 14}" text-anchor="middle">${pct(v)}%</text>`;
  svg += `<line class="axis" x1="${X(0)}" x2="${X(1)}" y1="${Y(0)}" y2="${Y(0)}"/><line class="axis" x1="${X(0)}" x2="${X(0)}" y1="${Y(0)}" y2="${Y(1)}"/>`;
  svg += `<path class="diag" d="M${X(0)},${Y(0)}L${X(1)},${Y(1)}"/>`;
  for (const n of others) svg += `<path class="other" d="${path(d.curves[n])}"><title>${esc(label(n))}</title></path>`;
  svg += `<path class="main" d="${path(d.curves[d.primary])}"><title>${esc(label(d.primary))}</title></path>`;
  svg += `<circle class="dot" cx="${X(x)}" cy="${Y(y)}" r="5"/>`;
  svg += `<text x="${X(0.5)}" y="${Y(0) + 32}" text-anchor="middle">${esc(t.axis_x)}</text>`;
  svg += `<text transform="translate(10 ${Y(0.5)}) rotate(-90)" text-anchor="middle">${esc(t.axis_y)}</text>`;
  $("#curve").setAttribute("aria-label", `${t.curve_label}. ${t.triage_out(pct(x), pct(y))}`);
  $("#curve").innerHTML = svg;
}

function renderExplain() {
  const t = T(), ex = state.demo.documents[state.doc].explanation;
  if (!ex) { $("#explain").innerHTML = ""; return; }
  const text = ex.text?.[state.lang] || "";
  let h = `<div class="explain-text" lang="${state.lang}">${text.split("\n").filter(Boolean).map(l => `<p class="${l.startsWith("•") ? "item" : ""}">${esc(l)}</p>`).join("")}</div>`;
  const cites = (ex.citations || []).filter(c => !c.lang || c.lang === state.lang);
  if (cites.length) {
    h += `<h3 class="small muted">${esc(t.sources_cited)}</h3>`;
    for (const c of cites) {
      const src = c.url ? `<a href="${esc(c.url)}" target="_blank" rel="noopener noreferrer">${esc(c.source)}</a>` : esc(c.source);
      const badge = c.quote == null ? `<span class="badge no">${esc(t.missing_quote)}</span>` : c.verified ? `<span class="badge ok">${esc(t.verified)}</span>` : `<span class="badge no">${esc(t.unverified_quote)}</span>`;
      h += `<div class="cite">${src}${badge}${c.quote ? `<blockquote>${esc(c.quote)}</blockquote>` : ""}</div>`;
    }
  }
  $("#explain").innerHTML = h;
}

function profile() {
  const f = $("#profile"), p = {};
  for (const el of f.elements) {
    if (!el.name) continue;
    p[el.name] = el.type === "checkbox" ? el.checked : el.type === "number" ? Number(el.value) || 0 : el.value;
  }
  return p;
}

let dedTimer;
function refreshDeductions() {
  clearTimeout(dedTimer);
  dedTimer = setTimeout(async () => {
    try {
      state.deductions = await getJSON("/api/deductions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(profile()) });
      renderDeductions();
    } catch (e) { $("#ded-list").innerHTML = `<li>${esc(T().err)} ${esc(e.message)}</li>`; }
  }, 120);
}

function renderDeductions() {
  const t = T(), d = state.deductions, L = state.lang;
  if (!d) return;
  $("#ded-scope").textContent = t.ded_scope(d.tax_year) + (d.scope?.[L] || "");
  $("#ded-disclaimer").textContent = d.disclaimer?.[L] || "";
  if (!d.items.length) { $("#ded-list").innerHTML = `<li class="muted">${esc(t.no_rules)}</li>`; return; }
  $("#ded-list").innerHTML = d.items.map(r => {
    const kind = r.verification !== "primary" ? r.verification : r.unverified_note ? "partial" : null;
    const flag = kind ? `<span class="flag-unverified">${esc(t.flag[kind])}</span>` : "";
    const est = r.estimate != null ? `<p class="estimate">${esc(t.estimate)} <strong>${esc(chf(r.estimate))}</strong></p>` : "";
    const note = r.unverified_note ? `<p class="small muted">${esc(r.unverified_note[L])}</p>` : "";
    const srcs = r.sources.map(s => `<li><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.title)}</a></li>`).join("");
    return `<li><h3><span>${esc(r.title[L])}</span>${flag}</h3>
      <p class="amount">${esc(r.amount[L])}</p>${est}
      <p>${esc(r.condition[L])}</p>
      <p class="small muted">${esc(t.legal)} ${esc(r.legal_basis[L])}</p>${note}
      <ul class="sources">${srcs}</ul></li>`;
  }).join("");
}

function renderMode(h) {
  const t = T();
  $("#mode").textContent = h ? t.mode_replay + (h.llm_configured ? t.mode_llm(h.llm_name || "?") : "") : "";
}

/* ---------- cockpit ---------- */

const VIEWS = ["home", "inbox", "cases", "case", "coverage", "releve"];
const RED = 0.5;
Object.assign(state, { route: { view: "home" }, subjects: null, subject: null, overview: null, caseDetail: null, coverage: null, transcripts: null, ask: null });
let health = null;

async function api(url, opts) {
  const r = await fetch(url, opts);
  const body = await r.json().catch(() => ({}));
  if (r.status === 503 && body.error === "unavailable") return { unavailable: body.module };
  if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
  return { data: body };
}
const post = (url, obj) => api(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(obj) });

const pick = x => (x && typeof x === "object" && !Array.isArray(x) ? x[state.lang] ?? x.fr ?? "" : x ?? "");
const day = iso => (iso ? `${iso.slice(8, 10)}.${iso.slice(5, 7)}.${iso.slice(0, 4)}` : "–");
const stamp = iso => { const d = new Date(iso); return isNaN(d) ? esc(iso) : d.toLocaleString(`${state.lang}-CH`, { dateStyle: "short", timeStyle: "short" }); };
const lbl = (map, k) => esc(T()[map]?.[k] ?? k ?? "–");
const cardName = c => esc(pick(c?.name) || c?.id || "?");
const itemText = k => { const [kind, issuer] = String(k).split(/:(.*)/s); const t = T(); return issuer ? `${t.doc_types[kind] || kind} — ${issuer}` : t.doc_types[k] || t.fact_labels[k] || k; };
const itemLabel = k => esc(itemText(k));
const maxDoubt = d => Math.max(-1, ...Object.values(d?.doubt || {}).filter(v => v != null));
const notice = (html, cls = "notice") => `<p class="${cls}">${html}</p>`;
const unavail = m => notice(esc(T().unavailable(m)));
const announce = msg => { $("#sr-status").textContent = ""; setTimeout(() => { $("#sr-status").textContent = msg; }, 30); };

function value(v, unit) {
  if (typeof v === "boolean") return T()[v ? "yes" : "no"];
  if (typeof v === "number") return v.toLocaleString("de-CH") + (unit ? ` ${unit}` : "");
  if (v && typeof v === "object") return JSON.stringify(v);
  return String(v ?? "–") + (unit ? ` ${unit}` : "");
}

function daysChip(n) {
  const cls = n == null ? "na" : n < 0 || n <= 7 ? "high" : n <= 30 ? "medium" : "low";
  return n == null ? "" : `<span class="chip ${cls}">${esc(T().days(n))}</span>`;
}

function doubtChip(p) {
  if (p < 0) return `<span class="chip na">${esc(T().lv.na)}</span>`;
  const lv = level(p);
  return `<span class="chip ${lv}">${esc(T().lv[lv])} · ${num(p)}</span>`;
}

function parseRoute() {
  const m = location.hash.match(/^#\/(home|inbox|cases|coverage|releve|case)(?:\/([A-Za-z0-9_.:-]{1,80}))?$/);
  return m && (m[1] !== "case" || m[2]) ? { view: m[1], id: m[2] } : { view: "home" };
}

async function loadOverview() {
  if (!state.subject) return;
  try { state.overview = await api(`/api/overview?subject=${encodeURIComponent(state.subject)}`); }
  catch (e) { state.overview = { error: e.message }; }
}

async function loadSubjects() {
  try {
    state.subjects = await api("/api/subjects");
    const list = state.subjects.data?.subjects || [];
    let saved = null;
    try { saved = localStorage.getItem("ordner.subject"); } catch (e) { /* storage blocked */ }
    state.subject = (list.find(s => s.id === saved) || list[0])?.id || null;
  } catch (e) { state.subjects = { error: e.message }; }
  await loadOverview();
}

async function route(focus = true) {
  state.route = parseRoute();
  const v = state.route.view;
  VIEWS.forEach(n => { $(`#v-${n}`).hidden = n !== v; });
  document.querySelectorAll(".tabs a").forEach(a => {
    if (a.dataset.route === (v === "case" ? "cases" : v)) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  if (v === "case") {
    state.caseDetail = null;
    renderView();
    try { state.caseDetail = await api(`/api/case?id=${encodeURIComponent(state.route.id)}`); }
    catch (e) { state.caseDetail = { error: e.message }; }
  }
  if (v === "coverage" && !state.coverage) {
    try { state.coverage = await api("/api/coverage"); } catch (e) { state.coverage = { error: e.message }; }
  }
  renderView();
  if (focus) $(`#v-${v} h2`)?.focus();
}

function renderView() {
  const v = state.route.view, t = T();
  document.title = `Ordner — ${t["nav_" + (v === "case" ? "cases" : v)]}`;
  renderSubjectBar();
  ({ home: renderHome, inbox: renderInbox, cases: renderCases, case: renderCase, coverage: renderCoverage, releve: () => {} })[v]();
}

function renderSubjectBar() {
  const t = T(), s = state.subjects;
  if (!s) { $("#subject-bar").innerHTML = `<span class="muted">${esc(t.loading)}</span>`; return; }
  if (s.unavailable || s.error) { $("#subject-bar").innerHTML = s.unavailable ? unavail(s.unavailable) : notice(esc(`${t.err} ${s.error}`)); return; }
  const list = s.data.subjects, cur = list.find(x => x.id === state.subject);
  if (!cur) { $("#subject-bar").innerHTML = ""; return; }
  const where = [cur.commune, cur.canton].filter(Boolean).join(" ");
  const who = list.length > 1
    ? `<label class="small muted" for="subject-pick">${esc(t.subject_pick)}</label> <select id="subject-pick">${list.map(x => `<option value="${esc(x.id)}"${x.id === cur.id ? " selected" : ""}>${esc(x.name)}</option>`).join("")}</select>`
    : `<strong>${esc(cur.name)}</strong>`;
  const ics = health?.modules?.rules
    ? `<a class="btn" href="/api/calendar.ics?subject=${encodeURIComponent(cur.id)}" download>${esc(t.ics)}</a>`
    : `<span class="small muted">${esc(t.ics_off)}</span>`;
  const sim = health?.simulated ? ` <span class="chip medium">${esc(t.sim_date(day(health.today)))}</span>` : "";
  $("#subject-bar").innerHTML = `<div class="who">${who}${where ? ` <span class="muted">· ${esc(where)}</span>` : ""}${cur.attrs?.fictional ? ` <span class="chip na">${esc(t.fictional)}</span>` : ""}${sim}</div>${ics}`;
  $("#subject-pick")?.addEventListener("change", async e => {
    state.subject = e.target.value;
    try { localStorage.setItem("ordner.subject", state.subject); } catch (err) { /* storage blocked */ }
    state.overview = null; renderView(); await loadOverview(); renderView();
  });
}

/* Shared guard for the views that read the overview. Returns the data or renders a state and returns null. */
function overviewOr(el, title) {
  const t = T(), o = state.overview, head = `<h2 class="view-title" tabindex="-1">${esc(title)}</h2>`;
  const sub = state.subjects;
  if (sub?.unavailable) { el.innerHTML = head + unavail(sub.unavailable); return null; }
  if (sub?.error || o?.error) { el.innerHTML = head + notice(esc(`${t.err} ${sub?.error || o.error}`)); return null; }
  if (o?.unavailable) { el.innerHTML = head + unavail(o.unavailable); return null; }
  if (!o) { el.innerHTML = head + `<p class="muted">${esc(t.loading)}</p>`; return null; }
  return o.data;
}

function coverageBanner(c) {
  const t = T();
  if (!c) return "";
  if (!c.available) return unavail(c.module);
  const k = c.counts, nodom = c.domains_without_card.map(d => t.domains[d] || d).join(", ");
  const items = c.items.map(i => `<li><span class="chip ${i.verdict === "covered" ? "low" : i.verdict === "to_verify" ? "medium" : "na"}">${lbl("verdict", i.verdict)}</span>
      <a href="#/coverage">${cardName(i)}</a> <span class="muted small">· ${lbl("nature", i.nature)} · ${lbl("qual", i.qualification)} · ${lbl("app", i.applicability)}${i.missing.length ? ` (${i.missing.map(esc).join(", ")})` : ""}</span></li>`).join("");
  return `<div class="banner cov" role="note">
    <p><strong>${esc(t.cov_banner(k.covered, k.to_verify, k.not_applicable, t.cov_where(c.canton || "?")))}</strong> ${esc(t.cov_claim)}</p>
    ${!c.rules ? `<p>${esc(t.cov_norules)}</p>` : ""}${nodom ? `<p class="small">${esc(t.cov_nodomain(nodom))}</p>` : ""}
    ${items ? `<details><summary>${esc(t.cov_details)}</summary><ul class="plain">${items}</ul></details>` : ""}
    <p class="small"><a href="#/coverage">${esc(t.cov_map_link)} →</a></p></div>`;
}

function nextStepHtml(n) {
  const t = T();
  if (!n) return `<p class="what">${esc(t.none_next)}</p>`;
  const c = n.card ? (pick(n.card.name) || n.card.id) : "";
  const due = n.due ? ` <span class="muted">· ${esc(t.due_on(day(n.due)))}</span>` : "";
  if (n.kind === "review") {
    const d = n.document, what = [t.doc_types[d.kind] || d.kind, d.issuer, d.year].filter(Boolean).join(" · ");
    return `<p class="what">${esc(t.next_review(what, d.fields.join(", ")))}</p><p><a class="btn primary" href="#/inbox">${esc(t.open_inbox)}</a></p>`;
  }
  const text = n.kind === "validate" ? t.next_validate(pick(n.summary) || t.kinds[n.action_kind] || n.action_kind, c)
    : n.kind === "provide" ? t.next_provide(n.items.map(itemText).join(", "), c) : t.next_qualify(c);
  return `<p class="what">${esc(text)}${due}</p><p><a class="btn primary" href="#/case/${encodeURIComponent(n.case_id)}">${esc(t.open_case)}</a></p>`;
}

function wealthHtml(w) {
  const t = T();
  if (!w) return "";
  if (!w.available) return `<section>${unavail(w.module)}</section>`;
  const chip = st => `<span class="chip ${st === "confirmed" || st === "final" ? "low" : st === "missing" || st === "incomplete" ? "high" : "medium"}">${esc(t.m_status[st] || t.wealth_status[st] || st)}</span>`;
  const rows = Object.entries(w.totals).map(([m, v]) => `<tr><th scope="row">${lbl("measures", m)}</th>
      <td class="value num">${v.total == null ? "–" : esc(chf(v.total))}</td><td>${chip(v.status)}</td></tr>`).join("");
  return `<section aria-labelledby="h-wealth"><h3 id="h-wealth" class="block">${esc(t.h_wealth(w.period))} ${chip(w.status)}</h3>
    <div class="table-wrap"><table class="compact"><tbody>${rows}</tbody></table></div>
    <p class="small"><span class="muted">${esc(t.inst_in)}</span> ${w.institutions_included.map(esc).join(", ") || "–"}</p>
    ${w.institutions_missing?.length ? `<p class="small"><span class="muted">${esc(t.inst_missing)}</span> ${w.institutions_missing.map(i => `<span class="chip high">${esc(i)}</span>`).join(" ")}</p>` : ""}
    <p class="muted small">${esc(t.wealth_note)}</p></section>`;
}

function renderHome() {
  const t = T(), el = $("#v-home"), o = overviewOr(el, t.nav_home);
  if (!o) return;
  const caseLink = (id, card) => `<a href="#/case/${encodeURIComponent(id)}">${cardName(card)}</a>`;
  const urgent = o.urgent.map(u => `<li><span class="due">${esc(day(u.due))}</span> ${daysChip(u.days)} ${caseLink(u.case_id, u.card)}
      ${u.reminders.length ? `<span class="small muted">· ${esc(t.reminders)} ${u.reminders.map(day).join(", ")}</span>` : ""}</li>`).join("");
  const missing = o.missing.map(m => `<li>${caseLink(m.case_id, m.card)}<div class="chips">${m.items.map(i => `<span class="chip medium">${itemLabel(i)}</span>`).join("")}</div></li>`).join("");
  const review = o.review.map(r => `<li><strong>${esc(t.doc_types[r.kind] || r.kind || "?")}</strong> ${esc([r.issuer, r.year].filter(Boolean).join(" · "))}
      <div class="small">${esc(t.red_fields)} ${r.fields.map(f => `<span class="chip high">${esc(t.fields[f] || f)}</span>`).join(" ")}</div></li>`).join("");
  el.innerHTML = `<h2 class="view-title" tabindex="-1">${esc(t.nav_home)}</h2>
    ${coverageBanner(o.coverage)}
    <p><button type="button" class="btn" id="review-btn">${esc(t.review_btn)}</button></p>
    <section class="next" aria-labelledby="h-next"><h3 id="h-next" class="block">${esc(t.h_next)}</h3>${nextStepHtml(o.next_step)}</section>
    ${o.cases.length ? "" : notice(esc(t.no_cases))}
    ${wealthHtml(o.wealth)}
    <div class="two">
      <section aria-labelledby="h-urgent"><h3 id="h-urgent" class="block">${esc(t.h_urgent)}</h3>${urgent ? `<ul class="list">${urgent}</ul>` : `<p class="muted">${esc(t.none_urgent)}</p>`}</section>
      <section aria-labelledby="h-review"><h3 id="h-review" class="block">${esc(t.h_review)}</h3>${review ? `<ul class="list">${review}</ul>` : `<p class="muted">${esc(t.none_review)}</p>`}</section>
    </div>
    <section aria-labelledby="h-missing"><h3 id="h-missing" class="block">${esc(t.h_missing)}</h3>${missing ? `<ul class="list">${missing}</ul>` : `<p class="muted">${esc(t.none_missing)}</p>`}</section>`;
}

function renderInbox() {
  const t = T(), el = $("#v-inbox"), o = overviewOr(el, t.nav_inbox);
  if (!o) return;
  const rows = o.documents.slice().sort((a, b) => (b.received_at || "").localeCompare(a.received_at || "")).map(d => {
    const p = maxDoubt(d), red = Object.entries(d.doubt || {}).filter(([, v]) => v >= RED).map(([f]) => t.fields[f] || f);
    const read = d.read_path ? `<span class="chip ${d.read_path === "barcode" ? "low" : "na"}">${lbl("read", d.read_path)}</span>` : "–";
    return `<tr class="lv-${p < 0 ? "na" : level(p)}">
      <td>${esc(day((d.received_at || "").slice(0, 10)))}</td>
      <th scope="row">${esc(t.doc_types[d.kind] || d.kind || "?")}</th>
      <td>${esc(d.year ?? "–")}</td><td>${esc(d.issuer || "–")}</td><td>${lbl("channels", d.channel)}</td><td>${read}</td>
      <td>${d.read_path === "barcode" && p <= 0 ? "–" : doubtChip(p)}${red.length ? `<div class="small">${esc(t.red_fields)} ${esc(red.join(", "))}</div>` : ""}</td></tr>`;
  }).join("");
  el.innerHTML = `<h2 class="view-title" tabindex="-1">${esc(t.nav_inbox)}</h2>
    <section>${rows ? `<div class="table-wrap"><table><caption class="sr-only">${esc(t.inbox_caption)}</caption>
      <thead><tr><th scope="col">${esc(t.col_received)}</th><th scope="col">${esc(t.col_type)}</th><th scope="col">${esc(t.col_year)}</th><th scope="col">${esc(t.col_issuer)}</th>
      <th scope="col">${esc(t.col_channel)}</th><th scope="col">${esc(t.col_read)}</th><th scope="col">${esc(t.col_doubt)}</th></tr></thead><tbody>${rows}</tbody></table></div>`
      : `<p class="muted">${esc(t.no_docs)}</p>`}
    <p class="muted small">${esc(t.inbox_legend)}</p></section>`;
}

function caseChips(c, card) {
  const t = T();
  return `<div class="chips">${card.nature ? `<span class="chip na">${lbl("nature", card.nature)}</span>` : ""}
    <span class="chip ${c.state === "ready_to_validate" ? "medium" : c.state === "closed" || c.state === "result_verified" ? "low" : "na"}">${lbl("states", c.state)}</span>
    <span class="chip ${card.qualification === "qualified" ? "low" : "medium"}">${card.unknown_card ? esc(t.unknown_card) : lbl("qual", card.qualification)}</span>
    ${card.domain ? `<span class="chip na">${lbl("domains", card.domain)}</span>` : ""}</div>`;
}

function renderCases() {
  const t = T(), el = $("#v-cases"), o = overviewOr(el, t.nav_cases);
  if (!o) return;
  const states = Object.keys(t.states), today = o.today;
  const items = o.cases.map(c => {
    const dues = (c.deadlines || []).map(d => d.due).sort(), next = dues.find(d => d >= today) || dues[dues.length - 1];
    const days = next ? Math.round((Date.parse(next) - Date.parse(today)) / 864e5) : null;
    return `<li><h3><a href="#/case/${encodeURIComponent(c.id)}">${cardName(c.card)}</a>${c.period ? ` <span class="muted small">${esc(t.period(c.period))}</span>` : ""}</h3>
      ${caseChips(c, c.card)}
      <p class="small"><span class="muted">${esc(t.progress(states.indexOf(c.state) + 1, states.length))}</span>
      ${next ? ` · ${esc(t.next_due(day(next)))} ${daysChip(days)}` : ""}</p>
      ${c.missing?.length ? `<p class="small">${esc(t.missing_l)} ${c.missing.map(itemLabel).join(", ")}</p>` : ""}</li>`;
  }).join("");
  el.innerHTML = `<h2 class="view-title" tabindex="-1">${esc(t.nav_cases)}</h2>${items ? `<ul class="case-list">${items}</ul>` : notice(esc(t.no_cases))}`;
}

function payloadHtml(a) {
  const t = T(), p = a.payload || {}, d = { ...p, ...(p.details && typeof p.details === "object" ? p.details : {}) };
  const title = d.summary || d.subject || d.title || d.label;
  const longText = ["body", "text", "letter", "message"].map(k => d[k]).find(v => typeof v === "string");
  const skip = new Set(["summary", "subject", "title", "label", "details", "body", "text", "letter", "message", "goal", "prepared_by", "steps",
    "template", "kind", "vars", "missing_vars"]);
  const kv = Object.entries(d).filter(([k, v]) => !skip.has(k) && v != null && typeof v !== "object")
    .map(([k, v]) => `<dt>${lbl("pk", k)}</dt><dd>${esc(value(v))}</dd>`).join("");
  const steps = Array.isArray(d.steps) ? `<ol class="small">${d.steps.map(s => `<li>${esc(pick(s?.label ?? s))}</li>`).join("")}</ol>` : "";
  return `${title ? `<p><strong>${esc(pick(title))}</strong></p>` : ""}${kv ? `<dl class="kv">${kv}</dl>` : ""}${steps}${longText ? `<pre class="letter">${esc(longText)}</pre>` : ""}`;
}

function renderCase() {
  const t = T(), el = $("#v-case"), r = state.caseDetail;
  const back = `<p><a href="#/cases">${esc(t.back)}</a></p>`;
  if (!r) { el.innerHTML = back + `<h2 class="view-title" tabindex="-1">${esc(t.loading)}</h2>`; return; }
  if (r.unavailable || r.error) { el.innerHTML = back + `<h2 class="view-title" tabindex="-1">${esc(t.nav_cases)}</h2>` + (r.unavailable ? unavail(r.unavailable) : notice(esc(`${t.err} ${r.error}`))); return; }
  const { case: c, card, facts, documents, events, states, rule_sources: rs = {}, completeness: comp } = r.data;
  const check = comp && (comp.wrong_year.length || comp.duplicates.length || comp.why.length)
    ? `${comp.wrong_year.length ? `<p class="small">${esc(t.wrong_year)} ${comp.wrong_year.map(w => `<span class="chip high">${esc(`${T().doc_types[w.kind] || w.kind} ${w.year} ≠ ${w.expected}`)}</span>`).join(" ")}</p>` : ""}
       ${comp.duplicates.length ? `<p class="small">${esc(t.duplicates)} ${comp.duplicates.map(d => `<span class="chip medium">${esc(d.reason)}</span>`).join(" ")}</p>` : ""}
       <details><summary>${esc(t.check_why)}</summary><ul>${comp.why.map(w => `<li>${esc(w)}</li>`).join("")}</ul></details>` : "";
  const cur = states.indexOf(c.state);
  const stepper = states.map((s, i) => `<li class="${i === cur ? "" : s === "complement_requested" ? "branch" : i < cur ? "done" : ""}"${i === cur ? ' aria-current="step"' : ""}>${i < cur && s !== "complement_requested" ? "✓ " : ""}${lbl("states", s)}</li>`).join("");
  const deadlines = (c.deadlines || []).map(d => {
    const cf = d.computed_from || {};
    const basis = (cf.legal_basis || []).map(k => rs[k] ? `<a href="${esc(rs[k].url)}" target="_blank" rel="noopener noreferrer">${esc(rs[k].title)}</a>` : esc(k)).join(", ");
    const steps = [...(cf.steps || []), ...(cf.warnings || []).map(w => `⚠ ${w}`)];
    return `<li><span class="due">${esc(day(d.due))}</span> ${daysChip(d.days)} ${cf.label ? esc(cf.label) : ""}
      <div class="small"><span class="muted">${esc(t.rule_l)}</span> ${esc(cf.rule || d.rule_id)}${cf.version ? ` (v${esc(cf.version)})` : ""}${basis ? ` · <span class="muted">${esc(t.basis_l)}</span> ${basis}` : ""}</div>
      ${d.reminders?.length ? `<div class="small"><span class="muted">${esc(t.reminders)}</span> ${d.reminders.map(day).join(", ")}</div>` : ""}
      ${steps.length ? `<details><summary>${esc(t.computed_l)}</summary><ul>${steps.map(s => `<li>${esc(s)}</li>`).join("")}</ul></details>` : ""}
      ${!cf.steps && Object.keys(cf).length ? `<details><summary>${esc(t.computed_l)}</summary><dl class="kv">${Object.entries(cf).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(value(v))}</dd>`).join("")}</dl></details>` : ""}</li>`;
  }).join("");
  const actions = (c.actions || []).map(a => `<li id="act-${esc(a.id)}" tabindex="-1">
      <h4>${lbl("kinds", a.kind)} <span class="chip ${a.status === "prepared" ? "medium" : a.status === "cancelled" ? "na" : "low"}">${lbl("astatus", a.status)}</span></h4>
      ${payloadHtml(a)}
      ${a.payload?.missing_vars?.length ? `<p class="small">${esc(t.missing_vars)} ${a.payload.missing_vars.map(v => `<code>${esc(v)}</code>`).join(", ")}</p>` : ""}
      <p class="small muted">${esc(a.kind === "payment" ? t.pay_note : t.send_note)}</p>
      ${a.status === "prepared" && a.requires_validation ? `<button type="button" class="btn primary" data-validate="${esc(a.id)}">${esc(t.validate)}</button>` : ""}
      ${a.payload?.template && !["prepared", "cancelled"].includes(a.status) ? `<a class="btn" href="/api/actions/eml?case_id=${encodeURIComponent(c.id)}&action_id=${encodeURIComponent(a.id)}" download>${esc(t.eml)}</a>` : ""}</li>`).join("");
  const order = { confirmed: 0, proposed: 1, superseded: 2, rejected: 3 };
  const factRows = facts.slice().sort((a, b) => a.key.localeCompare(b.key) || order[a.status] - order[b.status]).map(f => {
    const doc = documents[f.source_doc];
    const src = doc ? `${esc(t.doc_types[doc.kind] || doc.kind || "?")}${doc.issuer ? ` · ${esc(doc.issuer)}` : ""}${doc.read_path ? ` <span class="chip ${doc.read_path === "barcode" ? "low" : "na"}">${lbl("read", doc.read_path)}</span>` : ""}` : lbl("actors", f.actor);
    const cls = { confirmed: "low", proposed: "medium", rejected: "high", superseded: "na" }[f.status] || "na";
    return `<tr class="fact-${esc(f.status)}"><th scope="row"><code>${esc(f.key)}</code></th><td class="value">${esc(value(f.value, f.unit))}</td><td>${esc(f.period || "–")}</td>
      <td><span class="chip ${cls}">${lbl("fstatus", f.status)}</span></td><td class="small">${src}</td><td>${f.doubt != null ? doubtChip(f.doubt) : "–"}</td></tr>`;
  }).join("");
  const evs = events.slice().reverse().map(e => `<li><time datetime="${esc(e.ts)}">${stamp(e.ts)}</time><strong>${lbl("events", e.type)}</strong> <span class="muted small">· ${lbl("actors", e.actor)}</span>
      <span class="small">${esc(eventDetail(e))}</span></li>`).join("");
  const srcs = (card.sources || []).map(s => `<div class="cite"><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.title)}</a>
      ${s.verified ? `<span class="badge ok">${esc(t.verified)}</span>` : `<span class="badge no">${esc(t.unverified_quote)}</span>`}${s.quote ? `<blockquote>${esc(s.quote)}</blockquote>` : ""}</div>`).join("");
  const steps = (card.steps || []).map(s => `<li>${esc(pick(s.label) || s.id)} <span class="muted small">· ${lbl("who", s.who)}${s.action ? ` · ${lbl("kinds", s.action)}` : ""}</span></li>`).join("");
  const sec = (id, title, body) => `<section aria-labelledby="h-${id}"><h3 id="h-${id}" class="block">${esc(title)}</h3>${body}</section>`;
  el.innerHTML = back + `<h2 class="view-title" tabindex="-1">${cardName(card)}${c.period ? ` <span class="muted">· ${esc(t.period(c.period))}</span>` : ""}</h2>
    ${caseChips(c, card)}${card.notes ? `<details><summary>${esc(t.notes)}</summary><p>${esc(card.notes)}</p></details>` : ""}
    ${card.domain === "tax" ? `<p class="small"><a href="#/releve">${esc(t.releve_link)} →</a></p>` : ""}
    ${sec("prog", t.h_progress, `<ol class="stepper">${stepper}</ol>`)}
    ${c.missing?.length || check ? sec("miss", c.missing?.length ? t.h_case_missing : t.h_check, `<div class="chips">${(c.missing || []).map(i => `<span class="chip medium">${itemLabel(i)}</span>`).join("")}</div>${check}`) : ""}
    <div class="two">
      ${sec("dl", t.h_deadlines, deadlines ? `<ul class="list">${deadlines}</ul>` : `<p class="muted">${esc(t.no_deadlines)}</p>`)}
      ${sec("act", t.h_actions, actions ? `<ul class="list">${actions}</ul>` : `<p class="muted">${esc(t.no_actions)}</p>`)}
    </div>
    ${sec("facts", t.h_facts, factRows ? `<div class="table-wrap"><table><caption class="sr-only">${esc(t.facts_caption)}</caption><thead><tr>
      <th scope="col">${esc(t.col_key)}</th><th scope="col">${esc(t.col_value)}</th><th scope="col">${esc(t.col_period)}</th><th scope="col">${esc(t.col_status)}</th>
      <th scope="col">${esc(t.col_source)}</th><th scope="col">${esc(t.col_doubt)}</th></tr></thead><tbody>${factRows}</tbody></table></div>` : `<p class="muted">${esc(t.no_facts)}</p>`)}
    <div class="two">
      ${sec("ev", t.h_events, evs ? `<ol class="timeline">${evs}</ol>` : `<p class="muted">${esc(t.no_events)}</p>`)}
      <div>${steps ? sec("steps", t.h_steps, `<ol>${steps}</ol>`) : ""}${sec("src", t.h_sources, srcs || `<p class="muted">${esc(t.no_sources)}</p>`)}</div>
    </div>`;
}

function eventDetail(e) {
  const p = e.payload || {}, t = T();
  if (e.type === "state_changed") return `${t.states[p.from] || p.from} → ${t.states[p.to] || p.to}${p.reason ? ` (${p.reason})` : ""}`;
  if (e.type === "action_updated") return `${t.kinds[p.kind] || p.kind} : ${t.astatus[p.from] || p.from} → ${t.astatus[p.to] || p.to}`;
  if (e.type === "action_prepared") return t.kinds[p.kind] || p.kind || "";
  if (e.type === "deadline_added") return day(p.due);
  if (e.type === "missing_updated") return (p.to || []).map(i => t.doc_types[i] || i).join(", ");
  if (e.type === "case_opened") return [p.card_id, p.period].filter(Boolean).join(" · ");
  if (e.type.startsWith("fact_")) return `${p.key ?? ""} = ${value(p.value ?? p.new_value, p.unit)}`;
  if (e.type === "document_received") return [t.doc_types[p.kind] || p.kind, p.issuer, p.year].filter(Boolean).join(" · ");
  return "";
}

async function validateAction(id) {
  const t = T(), c = state.caseDetail?.data?.case;
  if (!c) return;
  try {
    const r = await post("/api/actions/validate", { case_id: c.id, action_id: id });
    if (r.unavailable) { announce(t.unavailable(r.unavailable)); return; }
    state.caseDetail = r;
    renderCase();
    const li = $(`#act-${CSS.escape(id)}`);
    li?.insertAdjacentHTML("beforeend", `<p class="ok-mark small">✓ ${esc(t.validated_msg)}</p>`);
    li?.focus();
    announce(t.validated_msg);
    loadOverview();
  } catch (e) { announce(`${t.err} ${e.message}`); }
}

function renderCoverage() {
  const t = T(), el = $("#v-coverage"), g = state.coverage;
  const head = `<h2 class="view-title" tabindex="-1">${esc(t.cov_title)}</h2><p class="lead">${esc(t.cov_intro)}</p>`;
  const mine = state.overview?.data?.coverage;
  if (!g) { el.innerHTML = head + `<p class="muted">${esc(t.loading)}</p>`; return; }
  if (g.unavailable || g.error) { el.innerHTML = head + (g.unavailable ? unavail(g.unavailable) : notice(esc(`${t.err} ${g.error}`))); return; }
  const { domains, jurisdictions, cells, counts } = g.data, here = mine?.canton;
  const sym = { qualified: "✓", draft: "◐", none: "·" };
  const cell = (dom, j) => {
    const c = cells[dom]?.[j], s = c?.status || "none";
    const names = c ? c.cards.map(x => pick(x.name) || x.id).join(", ") : "";
    return `<td class="cov ${s[0]}${j === here ? " here" : ""}"${names ? ` title="${esc(names)}"` : ""}><span aria-hidden="true">${sym[s]}</span><span class="sr-only">${lbl("cov_status", s)}${names ? ` : ${esc(names)}` : ""}</span></td>`;
  };
  const rows = domains.map(d => `<tr><th scope="row">${lbl("domains", d)}</th>${jurisdictions.map(j => cell(d, j)).join("")}</tr>`).join("");
  el.innerHTML = head + `<section><p class="small">${esc(t.cov_counts(counts.qualified, counts.draft))}</p>
    <div class="table-wrap"><table class="cov-table"><caption class="sr-only">${esc(t.cov_caption)}</caption>
      <thead><tr><th scope="col">${esc(t.cov_domain)}</th>${jurisdictions.map(j => `<th scope="col"${j === here ? ' class="here"' : ""}>${esc(j)}${j === here ? `<span class="sr-only"> (${esc(t.you_here)})</span>` : ""}</th>`).join("")}</tr></thead>
      <tbody>${rows}</tbody></table></div>
    <p class="legend small"><span class="cov q">✓</span> ${lbl("cov_status", "qualified")} &nbsp; <span class="cov d">◐</span> ${lbl("cov_status", "draft")} &nbsp; <span class="cov n">·</span> ${lbl("cov_status", "none")}</p></section>
    ${mine ? `<section aria-labelledby="h-yours"><h3 id="h-yours" class="block">${esc(t.cov_yours)}</h3>${coverageBanner(mine)}</section>` : ""}`;
}

/* ---------- chat panel ---------- */

function askMode() {
  const t = T();
  return health?.agent_live ? t.ask_live(health.llm_name || "?") : t.ask_demo(t.ask_reasons[health?.agent_reason] || health?.agent_reason || "?");
}

function renderAskPanel() {
  const t = T(), list = state.transcripts?.transcripts || [];
  $("#ask-mode").textContent = askMode();
  $("#ask-examples").innerHTML = list.map((x, i) => `<button type="button" class="btn" data-example="${i}">${esc(pick(x.question))}</button>`).join("");
  $("#ask-out").innerHTML = state.ask ? askResultHtml(state.ask) : "";
}

function askResultHtml(a) {
  const t = T(), r = a.result || {};
  if (a.wait) return `<p class="muted">${esc(t.ask_wait)}</p>`;
  if (a.error) return notice(esc(`${t.err} ${a.error}`));
  const tr = r.transcript || [], calls = tr.filter(x => x.role === "tool");
  const steps = tr.map(x => x.role === "tool"
    ? `<li>← <code>${esc(x.name)}</code> ${esc(JSON.stringify(x.result ?? {}).slice(0, 300))}</li>`
    : `${(x.tool_calls || []).map(c => `<li>→ <code>${esc(c.name)}</code>(${esc(JSON.stringify(c.arguments ?? {}).slice(0, 200))})${c.error ? ` ⚠ ${esc(c.error)}` : ""}</li>`).join("")}${x.content ? `<li>${esc(pick(x.content))}</li>` : ""}`).join("");
  const qs = (r.questions || []).map(q => `<li>${esc(pick(q.question))}</li>`).join("");
  const acts = (r.actions || []).map(x => `<li>${lbl("kinds", x.kind)} : ${esc(pick(x.payload?.summary) || "")} <span class="muted small">· ${esc(t.prepared_note)}</span></li>`).join("");
  const warns = (r.warnings || []).map(w => `<li>${esc(w)}</li>`).join("");
  return `<div class="qa"><p class="q"><strong>${esc(t.you)} :</strong> ${esc(a.question)}</p>
    <p class="small muted">${esc(a.mode === "live" ? t.ask_live(a.model || "?") : (a.nearest ? t.ask_nearest + " " : "") + t.recorded)}</p>
    ${steps ? `<details><summary>${esc(t.steps_n(calls.length))}</summary><ol class="steps">${steps}</ol></details>` : ""}
    ${r.answer ? `<div class="answer">${pick(r.answer).split("\n").filter(Boolean).map(p => `<p>${esc(p)}</p>`).join("")}</div>` : ""}
    ${qs ? `<p><strong>${esc(t.asks_you)}</strong></p><ul>${qs}</ul>` : ""}
    ${acts ? `<p><strong>${esc(t.h_actions)}</strong></p><ul>${acts}</ul>` : ""}
    ${warns ? `<details><summary>${esc(t.warnings)}</summary><ul>${warns}</ul></details>` : ""}</div>`;
}

function nearestExample(q) {
  const words = s => new Set(String(s).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").match(/[a-z0-9]{3,}/g) || []);
  const w = words(q), list = state.transcripts?.transcripts || [];
  let best = 0, score = -1;
  list.forEach((x, i) => {
    const s = [...words(Object.values(x.question || {}).join(" "))].filter(v => w.has(v)).length;
    if (s > score) { best = i; score = s; }
  });
  return best;
}

function showExample(i, question, nearest = false) {
  const x = state.transcripts?.transcripts?.[i];
  if (!x) return;
  state.ask = { mode: "demo", question: question ?? pick(x.question), nearest, result: x };
  renderAskPanel();
}

async function openAsk() {
  if (!state.transcripts) {
    try { state.transcripts = await getJSON("/data/demo/transcripts.json"); } catch (e) { state.transcripts = { transcripts: [] }; }
  }
  renderAskPanel();
  $("#ask").showModal();
  $("#ask-q").focus();
}

async function submitAsk(e) {
  e.preventDefault();
  const q = $("#ask-q").value.trim();
  if (!q) return;
  if (!health?.agent_live || !state.subject) { showExample(nearestExample(q), q, true); return; }
  state.ask = { wait: true, question: q };
  renderAskPanel();
  try {
    const r = await post("/api/ask", { subject: state.subject, question: q });
    state.ask = r.unavailable ? { error: T().unavailable(r.unavailable), question: q } : { ...r.data, question: q };
  } catch (err) { state.ask = { error: err.message, question: q }; }
  renderAskPanel();
  loadOverview().then(() => { if (state.route.view !== "case") renderView(); });
}

/* ---------- boot ---------- */

function renderAll() {
  applyStatic();
  if (state.demo) { renderThumbs(); renderDoc(); renderExplain(); }
  renderTriage();
  renderDeductions();
  renderMode(health);
  renderView();
  if ($("#ask").open) renderAskPanel();
}

async function init() {
  document.querySelectorAll(".langs button").forEach(b => b.onclick = () => {
    state.lang = b.dataset.lang;
    try { localStorage.setItem("ordner.lang", state.lang); } catch (e) { /* storage blocked */ }
    renderAll();
  });
  $("#thr").oninput = renderTriage;
  $("#profile").addEventListener("input", refreshDeductions);
  $("#profile").addEventListener("submit", e => e.preventDefault());
  $("#v-home").addEventListener("click", async e => {
    if (!e.target.closest("#review-btn") || !state.subject) return;
    e.target.disabled = true;
    try {
      const r = await post("/api/review", { subject: state.subject });
      state.overview = r;
      renderView();
      announce(r.unavailable ? T().unavailable(r.unavailable) : T().review_done);
      $("#review-btn")?.focus();
    } catch (err) { announce(`${T().err} ${err.message}`); e.target.disabled = false; }
  });
  $("#v-case").addEventListener("click", e => { const b = e.target.closest("button[data-validate]"); if (b) { b.disabled = true; validateAction(b.dataset.validate); } });
  $("#ask-open").onclick = openAsk;
  $("#ask-close").onclick = () => $("#ask").close();
  $("#ask-form").addEventListener("submit", submitAsk);
  $("#ask-examples").addEventListener("click", e => {
    const b = e.target.closest("button[data-example]");
    if (!b) return;
    if (health?.agent_live) { $("#ask-q").value = b.textContent; $("#ask-q").focus(); } else showExample(+b.dataset.example);
  });
  window.addEventListener("hashchange", () => route());

  applyStatic();
  route(false);
  const [demo, results, h] = await Promise.allSettled([getJSON("/data/demo/demo.json"), getJSON("/data/results/results.json"), getJSON("/api/health"), loadSubjects()]);
  if (demo.status === "fulfilled") state.demo = demo.value;
  else $("#fields tbody").innerHTML = `<tr><td colspan="5">${esc(T().err)} ${esc(demo.reason.message)}</td></tr>`;
  if (results.status === "fulfilled") {
    state.results = results.value;
    const d = triageData();
    if (d) $("#thr").value = d.curves[d.primary].find(p => p[1] >= 0.9)?.[0] ?? 0.2;
  }
  if (h.status === "fulfilled") health = h.value;
  renderAll();
  refreshDeductions();
}

init();
