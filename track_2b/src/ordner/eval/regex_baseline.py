"""OCR text -> 8 fields with rules only (no LLM).  python -m ordner.eval.regex_baseline --work work"""

import argparse
import html
import json
import re
import time
import unicodedata
from collections import Counter
from decimal import Decimal
from pathlib import Path

from .metrics import FIELDS, field_correct, gold_fields, read_jsonl

CANTONS = {"AG", "AI", "AR", "BE", "BL", "BS", "FR", "GE", "GL", "GR", "JU", "LU", "NE", "NW", "OW", "SG", "SH", "SO",
           "SZ", "TG", "TI", "UR", "VD", "VS", "ZG", "ZH"}

# Cyrillic/Greek letters that LightOnOCR mixes into Latin words (e.g. "Steuерwert").
HOMOGLYPHS = str.maketrans("аеорсухіјѕԁАВЕКМНОРСТХІЈЅΑΒΕΖΗΙΚΜΝΟΡΤΥΧο",
                           "aeopcyxijsdABEKMHOPCTXIJSABEZHIKMNOPTYXo")

OCR_DIGITS = str.maketrans("10", "IO")
# generic number formats added before the frozen test run (layout-independent): thousands separators
# ' ’ ` ´ space U+00A0 U+202F U+2009 or none, decimal point or comma
SEP = "['’`´ \u00a0\u202f\u2009]"
NUM_RE = re.compile(rf"(?<![\w.,'’`´-])(-?\d{{1,3}}(?:{SEP}\d{{3}})+(?:[.,]\d{{1,2}})?|-?\d+(?:[.,]\d{{1,2}})?)"
                    r"(?![\w'’`´]|[.,]\d)(?!\s*%)")

# Layout B (test only) is unknown here: labels come from layout-A train/dev OCR pages, the rest is generic.
REV = r"bruttoertrag|revenu brut|reddito lordo"
WITH = r"\b(?:mit|avec|con)\b"
WITHOUT = r"\b(?:ohne|sans|senza)\b"
# Per numeric field: (must match all, must match none), tried in order.
LABELS = {
    "totalTaxValue": [
        ([r"total\w*\W+(?:dei\W+)?(?:steu\w*wert|valeur fiscale|valori fiscali)"], []),
        ([r"steu\w*wert|valeur fiscale|valore fiscale"], [r"da-1|usa"]),
    ],
    "totalGrossRevenueA": [
        ([r"total", REV, WITH], [WITHOUT]),
        ([REV, WITH], [WITHOUT, r"da-1"]),
    ],
    "totalGrossRevenueB": [
        ([r"total", REV, WITHOUT], []),
        ([REV, WITHOUT], [r"da-1"]),
    ],
    "totalWithHoldingTaxClaim": [
        ([r"verrechnungs|retenue a la source|ritenuta d\W?imposta"], [r"revenu|ertrag|reddito|abzug|estera|etranger|usa"]),
    ],
}
NAME_STOP = {"kdnr", "ctn", "periode", "periodo", "daten", "donnees", "dati", "kanton", "canton", "cantone", "herr",
             "frau", "m", "mme", "sig", "sig.ra"}
TITLE_WORDS = r"steuerauszug|releve fiscal|dichiarazione fiscale|zusammenfassung|sommaire|sommario|extrait fiscal" \
              r"|estratto fiscale"


def normalize(text):
    return unicodedata.normalize("NFKC", html.unescape(text or "")).translate(HOMOGLYPHS)


def key(s):
    """Lowercase, accents removed, 1:1 in length with s (positions stay valid)."""
    return "".join(unicodedata.normalize("NFKD", ch)[0].lower() if ch.strip() else " " for ch in s)


def to_number(s):
    s = re.sub(SEP, "", s)
    return str(Decimal(s.replace(",", ".")))


def numbers(s):
    """All amounts in s, in order (footnote markers like (1) and <sup> removed)."""
    s = re.sub(r"<sup>.*?</sup>|\(\d\)", " ", s)
    return [to_number(m.group(1)) for m in NUM_RE.finditer(s)]


def first_number(s):
    n = numbers(s)
    return n[0] if n else None


def is_label(cell):
    return len(re.findall(r"[^\W\d_]", re.sub(r"\(\d\)", "", cell))) >= 4


def grid(text):
    """Table rows as lists of cell strings, from HTML <tr>/<td>/<th> and markdown |a|b| tables."""
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S):
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)
        rows.append([re.sub(r"\s+", " ", re.sub(r"<(?!/?sup)[^>]+>", " ", c)).strip() for c in cells])
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("|") and not re.fullmatch(r"[|:\-\s]+", line):
            rows.append([c.strip(" *") for c in line.strip("|").split("|")])
    return rows


def label_match(cell, must, never):
    k = key(cell)
    return is_label(cell) and all(re.search(p, k) for p in must) and not any(re.search(p, k) for p in never)


def grid_value(rows, must, never=()):
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            if not label_match(cell, must, never):
                continue
            for nxt in row[c + 1:]:  # same row, before the next label
                if is_label(nxt):
                    break
                if (v := first_number(nxt)) is not None:
                    return v
            if (v := value_below(rows, r, c)) is not None:
                return v
    return None


def value_below(rows, r, c):
    """Header row -> first row below that holds numbers, same column (A/B marker cells and blanks ignored if the
    OCR table is misaligned)."""
    row = rows[r]
    for below in rows[r + 1:r + 3]:
        if not any(numbers(x) for x in below if not is_label(x)):
            if any(is_label(x) for x in below):
                return None
            continue
        if len(below) == len(row):
            cand = below[c]
        else:
            keep = [i for i, x in enumerate(row) if not re.fullmatch(r"\s*[AB]?\s*", x)]
            vals = [x for x in below if not re.fullmatch(r"\s*[AB]?\s*", x)]
            if len(keep) != len(vals) or c not in keep:
                return None
            cand = vals[keep.index(c)]
        return None if is_label(cand) else first_number(cand)
    return None


def flat_lines(text):
    t = re.sub(r"<tr[^>]*>.*?</tr>", lambda m: m.group(0).replace("\n", " "), text, flags=re.S)
    t = re.sub(r"</tr>", "\n", t)
    t = re.sub(r"<t[hd][^>]*>", " | ", t)
    t = re.sub(r"<[^>]+>|[*#_]", " ", t)
    return [re.sub(r"[ \t]+", " ", line).strip() for line in t.splitlines()]


def text_value(lines, must, never=()):
    """Plain-text fallback: last amount on the label's line, else first amount on the next non-empty line."""
    for i, line in enumerate(lines):
        if not label_match(line, must, never):
            continue
        end = max(re.search(p, key(line)).end() for p in must)
        n = numbers(line[end:])
        if n:
            return n[-1]
        for nxt in lines[i + 1:i + 3]:
            if nxt.strip():
                if (v := first_number(nxt)) is not None and not is_label(nxt):
                    return v
                break
    return None


def amount(rows, lines, field):
    for must, never in LABELS[field]:
        if (v := grid_value(rows, must, never)) is not None:
            return v
    for must, never in LABELS[field]:
        if (v := text_value(lines, must, never)) is not None:
            return v
    return None


def canton(flat):
    k = key(flat)
    for m in re.finditer(r"\b(?:kanton|cantone|canton)\b"
                         r"[\s:|]*(?:\d{1,2}\.\d{1,2}\.\d{4}[\s:|]*)?([a-z][a-z01])\b", k):
        if (c := m.group(1).upper().translate(OCR_DIGITS)) in CANTONS:
            return c
    for m in re.finditer(r"^[\s|]*([A-Z]{2})[\s|]*$", flat, re.M):
        if m.group(1) in CANTONS:
            return m.group(1)
    return None


def tax_period(flat):
    k = key(flat)
    date = r"\d{1,2}\.\d{1,2}\.(\d{4})"
    for p in (rf"\b(?:periode|periodo)\b\W*(?:du\W*)?{date}\s*[-–—]+\s*{date}", rf"{date}\s*[-–—]+\s*{date}"):
        if m := re.search(p, k):
            return m.group(2)
    if m := re.search(rf"(?:{TITLE_WORDS})\D{{0,12}}(?:\d{{1,2}}\.\d{{1,2}}\.)?(20\d\d)\b", k):
        return m.group(1)
    years = Counter(re.findall(r"\b(20[0-3]\d)\b", flat))
    return years.most_common(1)[0][0] if years else None


def last_name(lines):
    for line in lines:
        k = key(line)
        for m in re.finditer(r"\b(?:kunde|client|cliente)\b[\s:|]*", k):
            toks = []
            for t in re.findall(r"[^\s|:]+", line[m.end():]):
                if key(t).strip(".:") in NAME_STOP or not t[0].isupper() or not re.match(r"[^\W\d_]", t):
                    break
                toks.append(t.strip(",;"))
                if len(toks) == 3:
                    break
            if toks:
                return toks[-1]
    return None


def institution(text, lines):
    for m in re.finditer(r"^#{1,3}\s+(.+?)\s*$", text, re.M):
        name = re.sub(r"[*_]", "", m.group(1)).strip()
        if is_label(name) and not re.search(TITLE_WORDS, key(name)):
            return name
    for line in lines:
        if m := re.search(r"^(.+?)\s+(?:konvertiert mit|converti avec|convertito con|erstellt mit|cree avec|creato con)",
                          key(line)):
            return line[:m.end(1)].strip()
    for line in lines:
        if re.search(r"(?:bank|banque|banca)\b", key(line)) and len(line) < 60:
            return line.strip(" |")
    return None


def extract(text):
    t = normalize(text)
    rows, lines = grid(t), flat_lines(t)
    flat = "\n".join(lines)
    out = {f: amount(rows, lines, f) for f in LABELS}
    out.update(institution=institution(t, lines), canton=canton(flat), taxPeriod=tax_period(flat),
               client_last_name=last_name(lines))
    return {f: out[f] for f in FIELDS}


def load_ocr(work):
    rows = {}
    for p in sorted(Path(work).glob("ocr.*.jsonl")):
        for r in read_jsonl(p):
            rows[r["page_id"]] = r
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="work")
    args = ap.parse_args(argv)
    work = Path(args.work)
    ocr = load_ocr(work)
    pages = {p["page_id"]: p for p in read_jsonl(work / "pages.jsonl")}
    docs = {d["doc_id"]: d for d in read_jsonl(work / "docs.jsonl")}
    out = []
    for pid in sorted(ocr):
        t = time.perf_counter()
        fields = extract(ocr[pid]["text"])
        out.append({"page_id": pid, "model": "regex", "fields": fields, "raw": None, "doubt": None,
                    "seconds": round(time.perf_counter() - t, 5)})
    with open(work / "extract.regex.jsonl", "w") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in out)
    print(f"wrote {len(out)} rows to {work / 'extract.regex.jsonl'}")
    # Report on train/dev only: test pages are never scored here.
    for split in ("train", "dev"):
        rows = [r for r in out if pages[r["page_id"]]["split"] == split]
        if not rows:
            print(f"{split}: no OCR rows yet")
            continue
        ok = {r["page_id"]: {f: field_correct(f, r["fields"][f], gold_fields(docs[pages[r["page_id"]]["doc_id"]])[f])
                             for f in FIELDS} for r in rows}
        levels = sorted({pages[p]["degradation"] for p in ok})
        by = {lv: [p for p in ok if pages[p]["degradation"] == lv] for lv in levels}
        mean = lambda ps, f: sum(ok[p][f] for p in ps) / len(ps)  # noqa: E731
        print(f"{split}: n_pages={len(ok)} mean={sum(map(sum, (o.values() for o in ok.values()))) / (8 * len(ok)):.3f} "
              f"page_all_ok={sum(all(o.values()) for o in ok.values()) / len(ok):.3f}")
        print(f"  {'field':26s} {'all':>6s} " + " ".join(f"{'d' + str(lv) + ' n=' + str(len(by[lv])):>9s}" for lv in levels))
        for f in FIELDS:
            print(f"  {f:26s} {mean(list(ok), f):6.3f} " + " ".join(f"{mean(by[lv], f):9.3f}" for lv in levels))


if __name__ == "__main__":
    main()
