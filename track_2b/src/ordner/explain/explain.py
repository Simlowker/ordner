"""Grounded explanation of the extracted totals: retrieve official passages (EmbeddingGemma 2), ask Apertus (MLX,
thinking disabled) to explain in fr/de/it with verbatim quotes «…» [passage_id], verify every quote word for word,
drop the unverified ones, and add a fixed warning for every doubtful (red) field.
Self-check with a mocked generator (no model): python -m ordner.explain.explain"""
import re
import unicodedata

LANGS = ("fr", "de", "it")
LANG_NAME = {"fr": "French", "de": "German", "it": "Italian"}
DOUBT_LEVELS = {"orange": 0.25, "red": 0.5}
NUMERIC = ("totalTaxValue", "totalGrossRevenueA", "totalGrossRevenueB", "totalWithHoldingTaxClaim")
LABELS = {
    "fr": {"totalTaxValue": "valeur fiscale totale", "totalGrossRevenueA": "rendement brut A (avec impôt anticipé)",
           "totalGrossRevenueB": "rendement brut B (sans impôt anticipé)",
           "totalWithHoldingTaxClaim": "impôt anticipé à récupérer", "institution": "établissement",
           "canton": "canton", "taxPeriod": "année fiscale", "client_last_name": "nom du client"},
    "de": {"totalTaxValue": "Total Steuerwert", "totalGrossRevenueA": "Bruttoertrag A (mit Verrechnungssteuer)",
           "totalGrossRevenueB": "Bruttoertrag B (ohne Verrechnungssteuer)",
           "totalWithHoldingTaxClaim": "Verrechnungssteueranspruch", "institution": "Finanzinstitut",
           "canton": "Kanton", "taxPeriod": "Steuerjahr", "client_last_name": "Name der Kundin / des Kunden"},
    "it": {"totalTaxValue": "valore fiscale totale", "totalGrossRevenueA": "reddito lordo A (con imposta preventiva)",
           "totalGrossRevenueB": "reddito lordo B (senza imposta preventiva)",
           "totalWithHoldingTaxClaim": "imposta preventiva da recuperare", "institution": "istituto",
           "canton": "cantone", "taxPeriod": "anno fiscale", "client_last_name": "cognome del cliente"},
}
QUERIES = {
    "fr": {"totalTaxValue": "où reporter la valeur fiscale des titres et comptes dans l'état des titres",
           "totalGrossRevenueA": "rendements bruts soumis à l'impôt anticipé à déclarer",
           "totalGrossRevenueB": "rendements bruts non soumis à l'impôt anticipé à déclarer",
           "totalWithHoldingTaxClaim": "remboursement de l'impôt anticipé : où le demander dans la déclaration",
           None: "relevé fiscal électronique de la banque : reporter les totaux dans la déclaration d'impôt"},
    "de": {"totalTaxValue": "wohin gehört der Steuerwert der Wertschriften und Konten im Wertschriftenverzeichnis",
           "totalGrossRevenueA": "Bruttoerträge mit Verrechnungssteuerabzug deklarieren",
           "totalGrossRevenueB": "Bruttoerträge ohne Verrechnungssteuerabzug deklarieren",
           "totalWithHoldingTaxClaim": "Rückerstattung der Verrechnungssteuer in der Steuererklärung beantragen",
           None: "eSteuerauszug der Bank: Totale in die Steuererklärung übernehmen"},
    "it": {"totalTaxValue": "dove riportare il valore fiscale dei titoli e dei conti nell'elenco dei titoli",
           "totalGrossRevenueA": "redditi lordi soggetti all'imposta preventiva da dichiarare",
           "totalGrossRevenueB": "redditi lordi non soggetti all'imposta preventiva da dichiarare",
           "totalWithHoldingTaxClaim": "rimborso dell'imposta preventiva: dove chiederlo nella dichiarazione",
           None: "estratto fiscale della banca: riportare i totali nella dichiarazione d'imposta"},
}
WARN = {
    "fr": "• À vérifier : {label} ({value}). La lecture automatique de ce montant n'est pas sûre ; comparez-le avec "
          "le document avant de le reporter.",
    "de": "• Bitte prüfen: {label} ({value}). Die automatische Erkennung dieses Werts ist unsicher; vergleichen Sie "
          "ihn mit dem Dokument, bevor Sie ihn übertragen.",
    "it": "• Da verificare: {label} ({value}). La lettura automatica di questo valore non è sicura; lo confronti con "
          "il documento prima di riportarlo.",
}
STATUS = {"ok": "read with confidence",
          "orange": "UNCERTAIN: suggest checking it against the document",
          "red": "DOUBTFUL: do NOT present this value as certain; tell the reader to check it against the document",
          None: "no confidence score"}

PID = r"[\w.\-]+-p\d+-\d+"
# «quote» [id] (id optional), or „quote“ / “quote” / "quote" followed by [id]
QUOTE = re.compile(rf"«\s*([^»]+?)\s*»(?:\s*[\[(]\s*({PID})\s*[\])])?"
                   rf"|[„“\"]\s*([^„“”\"\n]+?)\s*[“”\"]\s*[\[(]\s*({PID})\s*[\])]")
BARE_ID = re.compile(rf"\s*[\[(]\s*{PID}\s*[\])]")
MIN_QUOTE_WORDS = 5  # an unreferenced «…» shorter than this is ordinary typography (a term), not a citation


def status(doubt, levels=DOUBT_LEVELS):
    if doubt is None:
        return None
    return "red" if doubt >= levels["red"] else "orange" if doubt >= levels["orange"] else "ok"


def norm(s):
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[’‘`´]", "'", s)
    s = re.sub(r"[“”„]", '"', s)
    return re.sub(r"\s+", " ", s).strip()


def _strip_quote(q):
    return re.sub(r"^(?:\.\.\.|…|\s)+|(?:\.\.\.|…|[\s.,;:])+$", "", q)


def retrieve(fields, lang, k=6):
    from .retrieve import top_k
    queries = [QUERIES[lang][f["field"]] for f in fields if f["field"] in NUMERIC and f.get("value") is not None]
    out, seen = [], set()
    for q in [QUERIES[lang][None]] + queries:
        for p in top_k(q, lang, 2):
            if p["passage_id"] not in seen:
                seen.add(p["passage_id"])
                out.append(p)
    return out[:k]


def messages(fields, lang, passages):
    meta = {f["field"]: f.get("value") for f in fields}
    lines = [f"- {f['field']} ({LABELS[lang][f['field']]}): {f.get('value')} — status: {STATUS[f['status']]}"
             for f in fields if f.get("value") is not None]
    ctx = "\n\n".join(f"[{p['passage_id']}] ({p['source_title']}, p. {p['page']})\n{p['text']}" for p in passages)
    ex = passages[0]["passage_id"] if passages else "source-xx-p1-1"
    about = "".join(f", {k} {meta[k]}" for k in ("taxPeriod", "canton") if meta.get(k) is not None)
    user = (
        f"A bank's electronic tax statement (eCH-0196, Swiss e-tax statement){about.replace('taxPeriod', 'tax year')} "
        "shows these values:\n" + "\n".join(lines) +
        f"\n\nOfficial passages:\n\n{ctx}\n\n"
        f"Write in {LANG_NAME[lang]}, at most 170 words, for a young adult filling in their first tax return:\n"
        "- First sentence: what this statement is.\n"
        "- Then one line per amount, starting with \"• \": what the amount means and where it goes in the tax return.\n"
        "- Support each line with a short quote copied word for word from the passages, between « and », followed by "
        f"the passage id in square brackets, e.g. «exact words from the passage» [{ex}]. Quotes: 5 to 25 words, only "
        "from the passages above. Do not use « » for anything else.\n"
        "- Follow each value's status: never present a DOUBTFUL value as certain.\n"
        "- Form names differ between cantons: say that the exact field names are in the canton's official guide.\n"
        "- No advice, no tax computation.\n"
        "Answer with the explanation only."
    )
    system = (f"You explain Swiss tax documents to young adults in plain {LANG_NAME[lang]}. You rely only on the "
              "official passages you are given and never give financial advice.")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def verify(text, passages, corpus=None, first_n=1, lang=None):
    """Check every «quote» [id] word for word (whitespace, apostrophes and NFKC normalised) against its passage, then
    against the other retrieved passages. Verified quotes become «quote» [n]; unverified ones are removed.
    Returns (text, citations, dropped)."""
    by_id = {p["passage_id"]: p for p in (corpus or [])} | {p["passage_id"]: p for p in passages}
    cited, citations, dropped = {}, [], []

    def find(q, pid):
        nq = norm(q)
        cands = ([by_id[pid]] if pid in by_id else []) + [p for p in passages if p["passage_id"] != pid]
        return next((p for p in cands if nq in norm(p["text"])), None)

    def sub(m):
        raw, pid = m.group(1) or m.group(3), m.group(2) or m.group(4)
        q = _strip_quote(raw)
        if pid is None and len(q.split()) < MIN_QUOTE_WORDS:
            return m.group(0)
        p = find(q, pid) if q else None
        if p is None:
            dropped.append({"quote": raw, "passage_id": pid, "lang": lang, "reason": "not found verbatim"})
            return ""
        key = (p["passage_id"], norm(q))
        if key not in cited:
            cited[key] = first_n + len(citations)
            citations.append({"source": f"[{cited[key]}] {p['source_title']}, p. {p['page']}", "url": p["url"],
                              "quote": q, "verified": True, "passage_id": p["passage_id"], "lang": lang,
                              **({"cited_as": pid} if pid and pid != p["passage_id"] else {})})
        return f"«{q}» [{cited[key]}]"

    out = []
    for line in BARE_ID.sub("", QUOTE.sub(sub, text)).split("\n"):
        line = re.sub(r"\(\s*\)|\[\s*\]", "", line)
        line = re.sub(r"\s+([,.;:!?])", r"\1", re.sub(r"[ \t]+", " ", line)).strip()
        line = re.sub(r"([,;:])(?=[.!?]?$)", "", line).strip()
        if len(line.lstrip("•-* ").split()) >= 3:
            out.append(line)
    return "\n".join(out), citations, dropped


def explain_lang(fields, lang, generate, passages=None, first_n=1, levels=DOUBT_LEVELS):
    fields = [{**f, "status": status(f.get("doubt"), levels)} for f in fields]
    passages = retrieve(fields, lang) if passages is None else passages
    raw = generate(messages(fields, lang, passages))
    text, citations, dropped = verify(raw, passages, first_n=first_n, lang=lang)
    warn = [WARN[lang].format(label=LABELS[lang][f["field"]], value=f.get("value"))
            for f in fields if f["status"] == "red"]
    return {"text": "\n".join([text] + warn).strip(), "citations": citations, "dropped": dropped, "raw": raw,
            "passages": [p["passage_id"] for p in passages]}


def explain_doc(fields, generate, langs=LANGS, levels=DOUBT_LEVELS, passages=None):
    """fields: [{field, value, doubt}] -> demo.json `explanation` ({text: {lang: str}, citations: [...]}) plus the
    dropped quotes and raw outputs for audit. passages: {lang: [...]} to skip retrieval (tests)."""
    out = {"text": {}, "citations": [], "dropped": [], "raw": {}, "passages": {}}
    for lang in langs:
        r = explain_lang(fields, lang, generate, (passages or {}).get(lang), len(out["citations"]) + 1, levels)
        out["text"][lang] = r["text"]
        out["citations"] += r["citations"]
        out["dropped"] += r["dropped"]
        out["raw"][lang], out["passages"][lang] = r["raw"], r["passages"]
    return out


def apertus_generate(msgs, max_tokens=600):
    """Greedy generation with Apertus 1.5 8B on MLX (base weights, no LoRA), chat template with thinking disabled."""
    import mlx.core as mx
    from mlx_lm.generate import generate_step

    from ordner.models import apertus as hf
    from ordner.models import apertus_mlx as am
    if am._model is None:
        am.load()
    ids = hf._tok.apply_chat_template(msgs, add_generation_prompt=True, enable_thinking=False, tokenize=True,
                                      return_dict=False)
    out = []
    for tok, _ in generate_step(mx.array(ids), am._model, max_tokens=max_tokens):
        if tok in am.EOS:
            break
        out.append(tok)
    return hf._tok.decode(out, skip_special_tokens=True).strip()


def mock_generate(msgs):
    """Test double for Apertus: quotes the first 10 words of the first passage of the prompt, plus an invented quote."""
    pid, words = re.search(r"\n\[([\w.\-]+-p\d+-\d+)\] \([^\n]*\)\n(\S+(?: \S+){9})", msgs[-1]["content"]).groups()
    return f"Mock.\n• Real: «{words}» [{pid}].\n• Fake: «this sentence is in no official passage» [{pid}]."


def _selfcheck():
    from .retrieve import load_passages
    corpus = {p["passage_id"]: p for p in load_passages()}
    real = corpus["ti-istr-2025-it-p44-1"]
    assert "dell’imposta preventiva va riportato" in real["text"]
    fields = [{"field": "totalTaxValue", "value": "23806", "doubt": 0.05},
              {"field": "totalWithHoldingTaxClaim", "value": "9.03", "doubt": 0.71},
              {"field": "canton", "value": "TI", "doubt": 0.02}, {"field": "taxPeriod", "value": "2025", "doubt": 0.01}]
    fixed = ("Questo è il suo estratto fiscale.\n"
             "• Imposta preventiva 9.03: «Il diritto al recupero dell'imposta preventiva va riportato in basso a "
             "pagina 1 del Modulo 1» [ti-istr-2025-it-p44-1].\n"
             "• Valore fiscale 23806: «Il valore fiscale va sempre riportato alla cifra 99 del Modulo 7» "
             "[ti-istr-2025-it-p44-1].\n"
             "I nomi esatti sono nella guida del «Cantone».")
    seen = []
    r = explain_doc(fields, lambda m: seen.append(m) or fixed, langs=("it",), passages={"it": [real]})
    text, cites, dropped = r["text"]["it"], r["citations"], r["dropped"]
    assert len(cites) == 1 and cites[0]["verified"] and cites[0]["passage_id"] == real["passage_id"], cites
    assert "[1]" in text and "Modulo 1» [1]" in text, text
    assert len(dropped) == 1 and "cifra 99" in dropped[0]["quote"] and "cifra 99" not in text, (dropped, text)
    assert "«Cantone»" in text  # short unreferenced guillemets = typography, untouched
    assert "Da verificare: imposta preventiva da recuperare (9.03)" in text  # red field warning
    assert "Da verificare: valore fiscale" not in text
    assert "DOUBTFUL" in seen[0][1]["content"] and real["passage_id"] in seen[0][1]["content"]
    # quote cited with a wrong id but present verbatim in another retrieved passage -> kept, id corrected
    other = corpus["be-wl-2025-fr-p156-1"]
    t, c, d = verify("x «Il diritto al recupero dell’imposta preventiva va riportato» [be-wl-2025-fr-p156-1] y",
                     [other, real])
    assert c[0]["passage_id"] == real["passage_id"] and c[0]["cited_as"] == other["passage_id"] and not d
    # German quotation marks with an id are checked too; a bare id without a quote is removed
    t, c, d = verify("Laut „Die Verrechnungssteuer (VSt) ist eine Bundessteuer“ (be-wl-2025-de-p155-1) gilt das. "
                     "Und „Erfundener Satz ohne Quelle hier“ [be-wl-2025-de-p155-1]. Siehe [ti-istr-2025-it-p44-1] dort.",
                     [corpus["be-wl-2025-de-p155-1"]])
    assert len(c) == 1 and len(d) == 1 and "«Die Verrechnungssteuer (VSt) ist eine Bundessteuer» [1]" in t, (t, c, d)
    assert "Erfundener" not in t and "ti-istr" not in t, t
    print("explain self-check ok\n" + text)
    print("dropped:", dropped)


if __name__ == "__main__":
    _selfcheck()
