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
  const lv = state.demo.doubt_levels || { orange: 0.25, red: 0.5 };
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

let health = null;
function renderAll() {
  applyStatic();
  if (state.demo) { renderThumbs(); renderDoc(); renderExplain(); }
  renderTriage();
  renderDeductions();
  renderMode(health);
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

  const [demo, results, h] = await Promise.allSettled([getJSON("/data/demo/demo.json"), getJSON("/data/results/results.json"), getJSON("/api/health")]);
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
