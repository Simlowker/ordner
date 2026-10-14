"""Official corpus for grounded explanations: download the public PDFs listed in SOURCES (work/explain/raw/), extract
the selected pages with pypdfium2, split them into passages of ~80-200 words -> data/corpus/passages.jsonl + SOURCES.md.
python -m ordner.explain.corpus [--download]"""
import argparse
import json
import re
import subprocess
from datetime import date
from pathlib import Path

import pypdfium2

RAW = Path("work/explain/raw")
OUT = Path("data/corpus")
ACCESSED = "2026-10-14"

ESTV_215 = "https://www.estv.admin.ch/dam/{l}/sd-web/vFK3ntWLQ4s4/2-215-D-2025-d.pdf"
BE_WL = "https://www.wegleitung.sv.fin.be.ch/content/dam/sv_fin/dokumente/{l}/wegleitungen/2025/wl_natuerliche-personen_2025_{l}.pdf"
ECH = "https://www.ech.ch/sites/default/files/dosvers/hauptdokument/"
ECH_HDR = r"E-Government-Standards (?:Seite|Page) \d+ (?:von|sur) \d+ Verein eCH www\.ech\.ch / info@ech\.ch eCH-0196 – .{5,40}? / 2\.2\.0 / (?:Genehmigt|Approuvé) / 2022-06-07"
BE_HDR = r"(?:Natürliche Personen|Personnes physiques) 2025 Wegleitung NP 2025 definitiv_(?:de|fr)\.docx (?:Seite|Page) \d+"
GR_HDR = (r"(?:Istruzioni per la dichiarazione d'imposta 2025 Elenco dei titoli e degli averi"
          r"|Elenco dei titoli e degli averi Istruzioni per la dichiarazione d'imposta 2025) \d+")

FED_TERMS = ("Federal publication (admin.ch legal notice: copyright of the federal authorities; reproduction needs prior "
             "written consent). Official circulars may fall under art. 5 para. 1 let. c URG/LDA (reports of public "
             "administrations are not protected).")
BE_TERMS = ("Cantonal publication (Canton of Bern, Tax Administration). Legal notice not found; no reuse licence found.")
TI_TERMS = ("Cantonal publication (Canton of Ticino, Divisione delle contribuzioni). Legal notice not found; no reuse "
            "licence found.")
GR_TERMS = ("Cantonal publication (Canton of Graubünden). gr.ch legal notice: all rights reserved, reproduction needs "
            "prior written consent.")
ECH_TERMS = ("eCH standard, section 5 'Urheberrechte / Droits d'auteur': may be used, redistributed and developed free "
             "of charge and without restriction, naming the eCH authors.")

# id, lang, file, url, pages (1-based; None = all), header regex to strip, title, terms
SOURCES = [
    ("estv-2-215", "de", "estv-2-215-de.pdf", ESTV_215.format(l="de"), [1, 2, 3], None,
     "ESTV, Rundschreiben 2-215-D-2025-d: Ausgleich der Folgen der kalten Progression sowie Zinssätze bei der "
     "direkten Bundessteuer für das Steuerjahr 2026 (11.9.2025)", FED_TERMS),
    ("estv-2-215", "fr", "estv-2-215-fr.pdf", ESTV_215.format(l="fr"), [1, 2, 3], None,
     "AFC, Lettre circulaire 2-215-D-2025-f : Compensation des effets de la progression à froid et taux d'intérêt "
     "pour l'impôt fédéral direct pour l'année fiscale 2026 (11.9.2025)", FED_TERMS),
    ("estv-2-215", "it", "estv-2-215-it.pdf", ESTV_215.format(l="it"), [1, 2, 3], None,
     "AFC, Lettera circolare 2-215-D-2025-i: Compensazione degli effetti della progressione a freddo e tassi di "
     "interesse sull'imposta federale diretta per l'anno fiscale 2026 (11.9.2025)", FED_TERMS),
    ("be-wl-2025", "de", "be-wegleitung-2025-de.pdf", BE_WL.format(l="de"), list(range(129, 151)) + [155], BE_HDR,
     "Kanton Bern, Steuerverwaltung: Wegleitung Natürliche Personen 2025 (Vermögenswerte/Wertschriften, "
     "eSteuerauszug, Verrechnungssteuer)", BE_TERMS),
    ("be-wl-2025", "fr", "be-wegleitung-2025-fr.pdf", BE_WL.format(l="fr"), list(range(130, 152)) + [156], BE_HDR,
     "Canton de Berne, Intendance des impôts : Guide Personnes physiques 2025 (éléments de fortune/titres, relevés "
     "fiscaux numériques, impôt anticipé)", BE_TERMS),
    ("ti-istr-2025", "it", "ti-istruzioni-pf-2025-it.pdf",
     "https://www4.ti.ch/fileadmin/DFE/DC/DOC-IPF/2025/Istruzioni/Istruzioni_PF_2025.pdf", [17, 33] + list(range(39, 46)),
     r"^\d{1,2} ", "Cantone Ticino, Divisione delle contribuzioni: Istruzioni per la compilazione della dichiarazione "
     "d'imposta 2025 delle persone fisiche (redditi e sostanza mobiliare, Elenco dei titoli)", TI_TERMS),
    ("gr-istr-2025", "it", "gr-istruzioni-2025-it.pdf",
     "https://www.gr.ch/IT/istituzioni/amministrazione/dfg/stv/steuererklaerung/einkommens_und_vermoegenssteuer/"
     "Istruzioni_promemoria/Istruzioni%20per%20la%20dichiarazione%20d'imposta%202025.pdf", list(range(37, 43)), GR_HDR,
     "Cantone dei Grigioni, Amministrazione delle imposte: Istruzioni per la dichiarazione d'imposta 2025 (Elenco dei "
     "titoli e degli averi, modulo 2)", GR_TERMS),
    ("ech-0196", "de", "ech-0196-v2.2.0-de.pdf", ECH + "STAN_d_DEF_2022-06-07_eCH-0196_V2.2.0_E-Steuerauszug_.pdf",
     [2, 5, 6, 7, 12, 13, 14, 28, 29], ECH_HDR, "Verein eCH: eCH-0196 E-Steuerauszug, Version 2.2.0 (genehmigt "
     "2022-06-07)", ECH_TERMS),
    ("ech-0196", "fr", "ech-0196-v2.2.0-fr.pdf",
     ECH + "STAN_f_DEF_2022-06-07_eCH-0196_V2.2.0_Relev%C3%A9%20fiscal%20%C3%A9lectroniques_.pdf",
     [2, 5, 6, 7, 11, 12, 13, 27, 28], ECH_HDR, "Association eCH : eCH-0196 Relevé fiscal électronique, version 2.2.0 "
     "(approuvée 2022-06-07)", ECH_TERMS),
]

SENT = re.compile(r"(?<=[.!?;:])\s+|\s+(?=[•‒–] )")


def clean(text, header=None):
    t = re.sub(r"[￾­]\s*", "", text)  # soft hyphens at line ends: join the word
    t = re.sub(r"\s+", " ", t.replace("‐", "-")).strip()
    return re.sub(header, " ", t).strip() if header else t


def split_passages(text, max_words=180, min_words=80):
    """Greedy packing of sentences into passages of <= max_words; a short tail is merged into the previous one."""
    out, cur = [], []
    for s in (s for s in SENT.split(text) if s.strip()):
        w = s.split()
        while len(w) > max_words:  # tables: hard split
            if cur:
                out.append(cur)
                cur = []
            out.append(w[:max_words])
            w = w[max_words:]
        if cur and len(cur) + len(w) > max_words:
            out.append(cur)
            cur = []
        cur += w
    if cur:
        if out and len(cur) < min_words and len(out[-1]) + len(cur) <= max_words + min_words // 2:
            out[-1] += cur
        else:
            out.append(cur)
    return [" ".join(p) for p in out]


def download():
    RAW.mkdir(parents=True, exist_ok=True)
    for _, _, fname, url, *_ in SOURCES:
        if not (RAW / fname).exists():
            subprocess.run(["curl", "-sSLf", "-A", "Mozilla/5.0", "-o", str(RAW / fname), url], check=True)


def build():
    passages, seen = [], set()
    for sid, lang, fname, url, pages, header, title, _ in SOURCES:
        pdf = pypdfium2.PdfDocument(str(RAW / fname))
        for page in pages or range(1, len(pdf) + 1):
            text = clean(pdf[page - 1].get_textpage().get_text_range(), header)
            for i, chunk in enumerate(split_passages(text), 1):
                if len(chunk.split()) < 12 or chunk in seen:  # junk or duplicated spread (GR two-page layout)
                    continue
                seen.add(chunk)
                passages.append({"passage_id": f"{sid}-{lang}-p{page}-{i}", "source_title": title, "url": url,
                                 "page": page, "lang": lang, "text": chunk})
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "passages.jsonl", "w") as f:
        f.writelines(json.dumps(p, ensure_ascii=False) + "\n" for p in passages)
    return passages


def write_sources_md(passages):
    n = {}
    for p in passages:
        k = (p["source_title"], p["lang"])
        n[k] = n.get(k, 0) + 1
    lines = ["# Official corpus (data/corpus/passages.jsonl)", "",
             f"Built by `python -m ordner.explain.corpus --download` (date accessed: {ACCESSED}). Text only: the PDFs "
             "stay in `work/explain/raw/` (not versioned). Each passage is the pypdfium2 text of one PDF page (soft "
             "hyphens joined, whitespace collapsed, running headers removed), split at sentence boundaries into "
             "~80-200 words. No passage is written by hand.", "",
             "| Source | Lang | Pages | Passages | URL | Terms / licence note |", "|---|---|---|---|---|---|"]
    for sid, lang, fname, url, pages, header, title, terms in SOURCES:
        rng = ", ".join(map(str, pages)) if pages else "all"
        lines.append(f"| {title} | {lang} | {rng} | {n.get((title, lang), 0)} | {url} | {terms} |")
    lines += ["", "**Reuse (to decide before publishing the repo).** All sources are public, freely downloadable official "
              "publications (federal, cantonal) or an eCH standard. Only eCH grants an explicit redistribution licence. "
              "The admin.ch and gr.ch legal notices require prior written consent for any reproduction; art. 5 para. 1 "
              "let. c URG/LDA may exempt the federal circular (report of a public administration) but probably not the "
              "cantonal guides. `passages.jsonl` holds the full text of the selected pages, kept so that every quote "
              "shown to the user can be checked word for word against its source. Safe option for a public repository: "
              "keep only the eCH passages (or none) in git and rebuild the rest locally with the command above (URLs "
              "and page lists are in `src/ordner/explain/corpus.py`).", ""]
    (OUT / "SOURCES.md").write_text("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    if ap.parse_args().download:
        download()
    ps = build()
    write_sources_md(ps)
    words = [len(p["text"].split()) for p in ps]
    by = {}
    for p in ps:
        by[p["lang"]] = by.get(p["lang"], 0) + 1
    print(f"{len(ps)} passages {by}, words min/median/max {min(words)}/{sorted(words)[len(words) // 2]}/{max(words)}, "
          f"{(OUT / 'passages.jsonl').stat().st_size / 1e3:.0f} kB; built {date.today()}")
