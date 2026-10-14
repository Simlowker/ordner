"""Synthetic scenario variants for distillation, from the DEV split only (PREREG Addendum 2, H7). Seeded.

    PYTHONPATH=src .venv/bin/python -m ordner.distill.variants [--n 400] [--seed 7] [--out work/distill/variants.jsonl]

Grounding: each scored dev scenario is replayed through the deterministic engine (ordner.rules + catalogue) on every
fact it states (dossier, events incl. text-only ones, all phases). A scenario is engine-grounded when the engine
reproduces every expected (not_)applicable status and, for every expected due date, some rules.evaluate context built
from the scenario's own dates and the card's variants/kinds reproduces it (the "recipe").

Perturbations:
  neutral, any scored scenario: fictional name (never a scenario persona), goal language fr/de/it, duplicate of a
    non-payment document. Expectations are invariant, so the human-grounded ones are kept.
  engine, engine-grounded scenarios only: canton among VD/ZH/BE/GE/TI/FR (texts without place names; cantonal cards
    remapped), birth year, uniform date shift inside the same month (LP feries, weekends, cantonal holidays), missing or
    wrong-year salary certificate / tax statement for a tax return (rules.completeness must confirm it). Statuses and
    due dates are recomputed with the engine and the variant is dropped as soon as one is not computable.
"""
import argparse
import copy
import functools
import itertools
import json
import random
import re
from collections import Counter
from datetime import date, timedelta

from ordner import rules
from ordner.eval.scenarios import load, split_of, validate
from ordner.procedures import catalog

from . import OUT, write_jsonl

CANTONS = ["VD", "ZH", "BE", "GE", "TI", "FR"]
LANG_OF = {"VD": "fr", "GE": "fr", "FR": "fr", "ZH": "de", "BE": "de", "TI": "it"}
COMMUNES = {"VD": ["Lausanne", "Morges", "Nyon", "Vevey", "Renens", "Yverdon-les-Bains", "Pully", "Montreux"],
            "ZH": ["Zürich", "Winterthur", "Uster", "Dübendorf", "Wädenswil"],
            "BE": ["Bern", "Thun", "Köniz", "Burgdorf", "Langenthal"],
            "GE": ["Genève", "Carouge", "Meyrin", "Vernier", "Onex"],
            "TI": ["Lugano", "Bellinzona", "Locarno", "Mendrisio", "Chiasso"],
            "FR": ["Fribourg", "Bulle", "Villars-sur-Glâne", "Morat", "Marly"]}
CANTON_WORDS = r"vaud|vaudois\w*|waadt\w*|vodese|zurich|zürich|zurigo|zürcher|bern|berne|berna|bernese|berner\w*|" \
               r"genève|geneve|genf|ginevra|genevois\w*|tessin|ticino|ticinese|fribourg|freiburg|friburgo"
FIRST = {"fr": "Amélie Bastien Chloé Damien Élise Fabien Gaëlle Hélène Ismaël Jeanne Loïc Manon Nathan Océane Pauline "
               "Quentin Romane Simon Tania Valentin Yasmine Mathis Céline Arnaud".split(),
         "de": "Andrea Beat Corinne Dominik Esther Fabian Gabriela Hans Iris Jürg Katrin Lukas Mirjam Nils Olivia "
               "Patrick Regula Stefan Tanja Urs".split(),
         "it": "Alessia Bruno Chiara Davide Elena Fabio Gianna Ivo Laura Matteo Nadia Paolo Rita Sandro Tiziana "
               "Valerio".split()}
LAST = {"fr": "Aubert Blanc Chappuis Delacrétaz Ecoffey Favrod Girardet Hostettler Jaccard Kohler Monnier Nicod "
              "Perrin Rapin Savary Tinguely Vuilleumier Zufferey Mottier Cuche".split(),
        "de": "Ammann Brunner Christen Egli Frei Graf Hofer Kunz Lehmann Moser Nussbaum Roth Schneider Tanner Vogel "
              "Wyss Zbinden Bachmann Huber Gasser".split(),
        "it": "Bianchi Cattaneo Ferrari Fontana Lepori Monti Pedrazzini Quadri Rusconi Soldati Togni Valsecchi "
              "Zanetti Cavadini".split()}
DUP_KINDS = {"salary_certificate", "swiss_tax_statement_eCH0196", "health_insurance_premium_letter",
             "tax_assessment_decision", "employment_termination_letter", "premium_reduction_form"}
# question matchers, copied from the dev scenarios that ask for these documents (tax-ti-03, tax-vd-02)
DOC_ASK = {"salary_certificate": ("certificat de salaire {p}", ["salary", "salaire", "salario", "lohnausweis", "certificato"]),
           "swiss_tax_statement_eCH0196": ("relevé fiscal bancaire {p}", ["relev", "statement", "steuerauszug", "eCH0196",
                                                                          "swiss_tax_statement", "bank", "banque", "estratto"])}
DOC_WORDS = {"salary_certificate": r"salaire|lohnausweis|salario|salary",
             "swiss_tax_statement_eCH0196": r"relev|steuerauszug|estratto|statement|bancaire|bank"}

MONTHS = {"fr": "janvier février mars avril mai juin juillet août septembre octobre novembre décembre".split(),
          "de": "Januar Februar März April Mai Juni Juli August September Oktober November Dezember".split(),
          "it": "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()}
WEEKDAYS = r"lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|montag|dienstag|mittwoch|donnerstag|freitag|" \
           r"samstag|sonntag|lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica"
_M = "|".join(m for ms in MONTHS.values() for m in ms)
DATE_MENTION = re.compile(rf"\b\d{{4}}-\d{{2}}-\d{{2}}\b|(?<!\d)\d{{1,2}}\.\d{{1,2}}\.(?:\d{{4}})?|"
                          rf"(?<!\d)\d{{1,2}}(?:er|°)?\.? (?:{_M})(?: \d{{4}})?", re.I)
ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
AGE = re.compile(r"\b\d{1,3} ?(?:ans|jahre|jährig|anni)\b", re.I)


# -- engine oracle ---------------------------------------------------------------------------------------------------

def _sid(s):
    return f"subj_{s['id'].replace('-', '_')}"


def subject(s):
    p = s["persona"]
    return {"id": _sid(s), "kind": p.get("kind", "person"), "name": p["name"], "canton": p.get("canton"),
            "commune": p.get("commune"), "roles": list(p.get("roles", [])), "attrs": dict(p.get("attrs", {}))}


def facts(s):
    """Every fact the scenario states (dossier, events known or only written in the text, all phases), confirmed."""
    out = []
    for ph in [s] + s.get("phases", []):
        for f in ph.get("facts", []) + [e["fact"] for e in ph.get("events", []) if e.get("fact")]:
            out.append({"id": f"f{len(out)}", "subject_id": _sid(s), "key": f["key"], "value": f["value"],
                        "period": f.get("period"), "status": "confirmed", "created_at": f"{len(out):06d}"})
    return out


def status(s, pid):
    return rules.applicable(catalog.get(pid), subject(s), facts(s), on=s["today"], period=s.get("period"))["status"]


def deadline(s, pid, ctx):
    card = catalog.get(pid)
    return rules.compute_deadline(card.deadline, subject(s), {"period": s.get("period"), "today": s["today"],
                                                              "facts": facts(s), **ctx})


def recipe(s, pid, want):
    """Smallest rules.evaluate context (from the scenario's dates and the card's variants/kinds) giving due == want."""
    card = catalog.get(pid)
    if not card.deadline:
        return None
    pr, dates = card.deadline.params, sorted(scenario_dates(s))
    kinds = set(pr.get("kinds", {})) | {k for c in pr.get("cantonal", {}).values() for k in c.get("kinds", {})}
    opts = {"notified_on": dates, "chosen_date": dates if card.deadline.id == "chosen_date" else [],
            "variant": [v["case"] for v in pr.get("variants", [])] + pr.get("applies_to", []), "kind": sorted(kinds),
            "to_canton": CANTONS if kinds else []}
    keys = [k for k, v in opts.items() if v]
    for r in range(len(keys) + 1):
        for combo in itertools.combinations(keys, r):
            for vals in itertools.product(*(opts[k] for k in combo)):
                ctx = dict(zip(combo, vals))
                if deadline(s, pid, ctx).get("due") == want:
                    return ctx
    return None


def ground(s):
    """(engine_grounded, reasons, recipes {procedure: ctx})."""
    x, why, recipes = s["expected"], [], {}
    for p in x.get("applicable", []):
        if (st := status(s, p)) != "applicable":
            why.append(f"{p}: engine says {st}")
    for p in x.get("not_applicable", []):
        if (st := status(s, p)) != "not_applicable":
            why.append(f"trap {p}: engine says {st}")
    for d in x.get("deadlines", []):
        p = d["procedure"]
        if d.get("due") is None:
            if status(s, p) == "applicable" and deadline(s, p, {}).get("due"):
                why.append(f"{p}: engine gives a date where none is provable")
        elif (ctx := recipe(s, p, d["due"])) is None:
            why.append(f"{p} {d['due']}: no engine context reproduces it")
        else:
            recipes[p] = ctx
    return not why, why, recipes


# -- dates -----------------------------------------------------------------------------------------------------------

def _walk(o, fn, skip=("expected", "basis", "persona", "id", "split", "_file")):
    """Rebuild o with fn(key, str) applied to every string outside the skipped top-level keys."""
    def rec(v, key):
        if isinstance(v, dict):
            return {k: rec(x, k) for k, x in v.items()}
        if isinstance(v, list):
            return [rec(x, key) for x in v]
        return fn(key, v) if isinstance(v, str) else v
    return {k: (v if k in skip else rec(v, k)) for k, v in o.items()}


def scenario_dates(s):
    """Dates held as exact ISO values (or ISO datetimes) in the scenario's dossier data, plus today."""
    found = {s["today"]}

    def grab(_, v):
        if ISO.fullmatch(v[:10]) and (len(v) == 10 or v[10] == "T"):
            found.add(v[:10])
        return v
    _walk(s, grab)
    return found


def _texts(s):
    """Free texts the agent reads: goals (every language, every phase) and document bodies."""
    out = []
    for ph in [s] + s.get("phases", []):
        out += list((ph.get("goal") or {}).values()) + [d.get("text") or "" for d in ph.get("documents", [])]
    return out


def forms(d):
    d0 = date.fromisoformat(d)
    day = d0.day
    out = {"iso": d, "dmy0": f"{d0:%d.%m.%Y}", "dmy": f"{day}.{d0.month}.{d0.year}", "dm0": f"{d0:%d.%m.}",
           "dm": f"{day}.{d0.month}."}
    for lang, ms in MONTHS.items():
        m = ms[d0.month - 1]
        days = {"fr": [str(day)] + (["1er"] if day == 1 else []), "it": [str(day)] + (["1°"] if day == 1 else []),
                "de": [f"{day}."]}[lang]
        for i, dd in enumerate(days):
            out[f"{lang}{i}y"], out[f"{lang}{i}"] = f"{dd} {m} {d0.year}", f"{dd} {m}"
    return out


def date_shift_ok(s):
    """Every date written in the texts is one of the scenario's dates (so it can be shifted) and no weekday is named."""
    known = {f.casefold() for d in scenario_dates(s) for f in forms(d).values()}
    for t in _texts(s):
        if re.search(rf"\b({WEEKDAYS})\b", t, re.I):
            return False
        if any(m.group(0).casefold() not in known for m in DATE_MENTION.finditer(t)):
            return False
    return True


def deltas(s):
    """Uniform shifts keeping every scenario date in its month (so month names and periods in the texts stay true)."""
    ds = [date.fromisoformat(d) for d in scenario_dates(s)]
    return [k for k in range(-30, 31) if k and all((d + timedelta(k)).month == d.month
                                                    and (d + timedelta(k)).year == d.year for d in ds)]


def shift(s, k):
    dmap = {d: (date.fromisoformat(d) + timedelta(k)).isoformat() for d in scenario_dates(s)}
    table = {}
    for d, n in dmap.items():
        fo, fn = forms(d), forms(n)
        table.update({fo[f]: fn.get(f) or fn[f.replace("1", "0")] for f in fo})   # "1er"/"1°" only exist on day 1
    rx = re.compile(r"(?<!\d)(" + "|".join(map(re.escape, sorted(table, key=len, reverse=True))) + r")(?!\d)")

    def fn(_, v):
        if v[:10] in dmap and (len(v) == 10 or v[10] == "T"):
            return dmap[v[:10]] + v[10:]
        return rx.sub(lambda m: table[m.group(1)], v)
    v = _walk(s, fn)
    v["today"] = dmap[s["today"]]
    return v, dmap


# -- perturbations ---------------------------------------------------------------------------------------------------

@functools.cache
def _places():
    places = {c for cs in COMMUNES.values() for c in cs} | {x["persona"].get("commune") or "" for x in load("all")}
    return re.compile(rf"(?<!\w)({'|'.join([CANTON_WORDS] + [re.escape(p) for p in places if p])})(?!\w)", re.I)


def place_free(s):
    blob = " ".join(_texts(s) + [str(d.get("issuer") or "") + " " + json.dumps(d.get("fields", {}), ensure_ascii=False)
                                 for ph in [s] + s.get("phases", []) for d in ph.get("documents", [])])
    return not _places().search(blob)


def cmap(pid, old, new):
    """Cantonal card of the old canton -> same card of the new canton (None if the catalogue has none)."""
    if catalog.get(pid).jurisdiction != old:
        return pid
    cand = pid[: -len(old)] + new
    try:
        catalog.get(cand)
        return cand
    except KeyError:
        return None


def rename(v, rng, taken, lang):
    old = v["persona"]["name"]
    while (new := f"{rng.choice(FIRST[lang])} {rng.choice(LAST[lang])}") in taken:
        pass
    of, ol = old.split(" ", 1)
    nf, nl = new.split(" ", 1)
    rx = re.compile(rf"(?<!\w)({re.escape(old)}|{re.escape(ol)}|{re.escape(of)})(?!\w)")
    v = _walk(v, lambda _, t: rx.sub(lambda m: {old: new, ol: nl, of: nf}[m.group(1)], t))
    v["persona"]["name"] = new
    return v


def recompute(v, src, recipes, dmap, old_canton):
    """Expected outcome of an engine-perturbed variant, or (None, reason)."""
    x, new = copy.deepcopy(src["expected"]), v["persona"].get("canton")
    m = {p: cmap(p, old_canton, new) for p in x.get("applicable", []) + [d["procedure"] for d in x.get("deadlines", [])]}
    if None in m.values():
        return None, f"no {new} card for {[p for p, q in m.items() if q is None]}"
    app = [m[p] for p in x.get("applicable", [])]
    for p in app:
        if (st := status(v, p)) != "applicable":
            return None, f"{p}: engine says {st}"
    traps = []
    for p in x.get("not_applicable", []):
        st = "applicable" if p in app else status(v, p)
        if st == "missing_info":
            return None, f"trap {p}: missing_info"
        if st == "not_applicable":
            traps.append(p)
    dls = []
    for d in x.get("deadlines", []):
        p = m[d["procedure"]]
        if d.get("due") is None:
            if deadline(v, p, {}).get("due"):
                return None, f"{p}: a date became computable"
            dls.append({**d, "procedure": p})
            continue
        r = deadline(v, p, {k: new if k == "to_canton" and val == old_canton else dmap.get(val, val) for k, val in recipes[d["procedure"]].items()})
        if r.get("status") != "computed":
            return None, f"{p}: engine {r.get('status')} {r.get('missing')}"
        if (r["due"] >= v["today"]) != (d["due"] >= src["today"]):
            return None, f"{p}: shift crosses today"
        card = catalog.get(p)
        srcs = [card.sources[i] for i in r["computed_from"].get("card_sources") or [0] if i < len(card.sources)]
        source = {"title": srcs[0].title, "url": srcs[0].url, "quote": srcs[0].quote} if srcs else d.get("source")
        dls.append({"procedure": p, "due": r["due"], "rule": card.deadline.id, "source": source,
                    "computed_from": {k: r["computed_from"].get(k) for k in ("rule", "inputs", "steps", "warnings")}})
    x["applicable"], x["not_applicable"], x["deadlines"] = app, traps, dls
    for f in x.get("forbidden", []):
        if f.get("procedure"):
            f["procedure"] = cmap(f["procedure"], old_canton, new) or f["procedure"]
    return x, None


def doc_perturb(v, rng, kind_op):
    """Remove or age by one year the salary certificate / tax statement of a tax-return scenario; engine-confirmed."""
    kind, op = kind_op
    p = int(v["period"])
    docs = [d for d in v["documents"] if d.get("kind") == kind and d.get("year") == p]
    if not docs:
        return None, "no such document"
    d = rng.choice(docs)
    if op == "missing":
        v["documents"] = [x for x in v["documents"] if x is not d]
    else:
        d["year"], d["id"] = p - 1, d["id"] + "_wy"
        d.pop("path", None)  # a real PDF would still decode to its own year
        d["fields"] = {k: (str(p - 1) if k == "taxPeriod" else val.replace(str(p), str(p - 1)) if isinstance(val, str)
                           else val) for k, val in d.get("fields", {}).items()}
    card_id = next(q for q in v["expected"]["applicable"] if q.startswith("tax.return."))
    docs_ = [{**x, "subject_id": _sid(v)} for x in v["documents"]]
    c = rules.completeness(catalog.get(card_id), subject(v), facts(v), docs_, v["period"])
    hit = (kind in [x["kind"] for x in c["missing_documents"]]) if op == "missing" else \
        (d["id"] in [x["document"] for x in c["wrong_year"]])
    if not hit:
        return None, f"completeness does not confirm {op} {kind}"
    topic, match = DOC_ASK[kind]
    topic = topic.format(p=p) + ("" if op == "missing" else f" (la pièce reçue est de {p - 1})")
    v["expected"]["missing_info"] = [{"topic": topic, "match": match}]
    v["expected"]["actions"] = ["document_request"]
    v["hard_cases"] = sorted(set(v.get("hard_cases", [])) | {"missing_document" if op == "missing" else "wrong_year_document"})
    return v, None


def make_variant(src, g, rng, taken, k):
    ok, _, recipes, ks, moved = g
    v = copy.deepcopy(src)
    v.pop("_file", None)
    v["id"], v["split"], v["source_id"] = f"syn-{src['id']}-{k:02d}", "synthetic", src["id"]
    v["needs_review"], v["basis"] = False, src.get("basis", [])
    pert, dmap, old_canton = [], {}, src["persona"].get("canton")
    if ok and src["persona"].get("canton") and rng.random() < 0.5 and place_free(src):
        new = rng.choice([c for c in CANTONS if c != old_canton])
        v["persona"]["canton"], v["persona"]["commune"] = new, rng.choice(COMMUNES[new])
        pert.append(f"canton:{old_canton}->{new}")
    lang = rng.choices(["fr", "de", "it"], [3 if lang == src["lang"] else 2 for lang in ("fr", "de", "it")])[0]
    if pert and rng.random() < 0.5:
        lang = LANG_OF[v["persona"]["canton"]]
    if lang != src["lang"]:
        pert.append(f"lang:{src['lang']}->{lang}")
    v["lang"] = lang
    v = rename(v, rng, taken, lang)
    if ok and ks and rng.random() < 0.6:
        kk = rng.choice(moved if moved and rng.random() < 0.6 else ks)
        v, dmap = shift(v, kk)
        pert.append(f"dates:{kk:+d}d")
    by = v["persona"].get("attrs", {}).get("birth_year")
    if ok and by and rng.random() < 0.3 and not any(AGE.search(t) or str(by) in t for t in _texts(src)):
        dy = rng.choice([d for d in range(-15, 16) if d])
        a = v["persona"]["attrs"]
        a["birth_year"] = by + dy
        if a.get("birth_date"):
            a["birth_date"] = f"{by + dy}{a['birth_date'][4:]}"
        pert.append(f"birth_year:{dy:+d}")
    if ok and pert and any(p.split(":")[0] in ("canton", "dates", "birth_year") for p in pert):
        x, why = recompute(v, src, recipes, dmap, old_canton)
        if x is None:
            return None, why
        v["expected"] = x
        if any(p.startswith("birth_year") for p in pert) and len(x["not_applicable"]) != len(src["expected"]["not_applicable"]):
            return None, "birth year changes a trap"
    r = rng.random()
    docs_ok = (ok and v.get("period") and not v.get("phases") and not src["expected"].get("missing_info")
               and any(q.startswith("tax.return.") for q in v["expected"]["applicable"]))
    if r < 0.25 and docs_ok:
        kind_op = rng.choice([(kd, op) for kd in DOC_ASK for op in ("missing", "wrong_year")])
        if not any(re.search(DOC_WORDS[kind_op[0]], t, re.I) for t in _texts(src)):
            v, why = doc_perturb(v, rng, kind_op)
            if v is None:
                return None, why
            pert.append(f"doc:{kind_op[1]}:{kind_op[0]}")
    elif r < 0.5:
        dups = [d for d in v.get("documents", []) if d.get("kind") in DUP_KINDS and not d.get("path")]
        if dups:
            d = copy.deepcopy(rng.choice(dups))
            d["id"] += "_dup"
            d["channel"] = "email"
            v["documents"].append(d)
            v["hard_cases"] = sorted(set(v.get("hard_cases", [])) | {"duplicate_document"})
            pert.append(f"doc:duplicate:{d['kind']}")
    v["perturbations"] = pert
    return v, None


def _interesting(s, recipes, k):
    """A shift that does not move the due dates by exactly k days (weekend, holiday, feries or fixed date)."""
    if not recipes:
        return False
    v, dmap = shift(s, k)
    for p, ctx in recipes.items():
        r = deadline(v, p, {kk: dmap.get(val, val) for kk, val in ctx.items()})
        d0 = next(d["due"] for d in s["expected"]["deadlines"] if d["procedure"] == p)
        if r.get("due") and (date.fromisoformat(r["due"]) - date.fromisoformat(d0)).days != k:
            return True
    return False


def leakage(variants, test):
    """Assert no test scenario, persona, document or goal reaches the training variants."""
    ids = {s["id"] for s in load("all")}
    names = {s["persona"]["name"].casefold() for s in test}
    paths = {d.get("path") for s in test for ph in [s] + s.get("phases", []) for d in ph.get("documents", []) if d.get("path")}
    doc_ids = {d["id"] for s in test for ph in [s] + s.get("phases", []) for d in ph.get("documents", [])}
    goals = {g for s in test for ph in [s] + s.get("phases", []) for g in (ph.get("goal") or {}).values()}
    dev = {s["id"] for s in load("dev")}
    for v in variants:
        blob = json.dumps({k: val for k, val in v.items() if k != "basis"}, ensure_ascii=False).casefold()
        assert v["source_id"] in dev and split_of(v["source_id"]) == "dev", v["id"]
        assert v["id"] not in ids, v["id"]
        assert v["persona"]["name"].casefold() not in names and not any(n in blob for n in names), v["id"]
        vd = [d for ph in [v] + v.get("phases", []) for d in ph.get("documents", [])]
        assert not {d.get("path") for d in vd} & paths, (v["id"], "test document file")
        assert not {d["id"] for d in vd} & doc_ids, (v["id"], "test document id")
        assert not {g for ph in [v] + v.get("phases", []) for g in (ph.get("goal") or {}).values()} & goals, v["id"]


def strip_test_files(v, test):
    """A dev document file that a test scenario also uses becomes a placeholder (fields only) in the variant."""
    paths = {d.get("path") for s in test for ph in [s] + s.get("phases", []) for d in ph.get("documents", []) if d.get("path")}
    for ph in [v] + v.get("phases", []):
        for d in ph.get("documents", []):
            if d.get("path") in paths:
                d.pop("path")
    return v


def generate(n=450, seed=7):
    rng = random.Random(seed)
    dev = [s for s in load("dev") if not s.get("needs_review")]
    test = load("test")
    taken = {s["persona"]["name"] for s in load("all")}
    grounds = {}
    for s in dev:
        ok, why, recipes = ground(s)
        ks = deltas(s) if ok and date_shift_ok(s) else []
        grounds[s["id"]] = (ok, why, recipes, ks, [k for k in ks if _interesting(s, recipes, k)])
    per = -(-n // len(dev))
    out, rejected, seen = [], Counter(), set()
    for s in dev:
        made, tries = 0, 0
        while made < per and tries < per * 6:
            tries += 1
            v, why = make_variant(s, grounds[s["id"]], rng, taken, made)
            if v is None:
                rejected[why.split(":")[0][:60]] += 1
                continue
            sig = (s["id"], v["lang"], v["persona"].get("canton"), tuple(p for p in v["perturbations"] if not p.startswith("lang")))
            if sig in seen:
                continue
            seen.add(sig)
            v = strip_test_files(v, test)
            errors = [e for e in validate(v) if not e.startswith("split ")]
            assert not errors, (v["id"], errors)
            taken.add(v["persona"]["name"])
            out.append(v)
            made += 1
    leakage(out, test)
    return out, grounds, rejected


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=450, help="target; neutral-only scenarios give fewer distinct variants")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(OUT / "variants.jsonl"))
    a = ap.parse_args(argv)
    out, grounds, rejected = generate(a.n, a.seed)
    write_jsonl(a.out, out)
    g = [k for k, gr in grounds.items() if gr[0]]
    print(f"{len(out)} variants from {len(grounds)} scored dev scenarios ({len(g)} engine-grounded) -> {a.out}")
    for k, (ok, why, *_) in sorted(grounds.items()):
        if not ok:
            print(f"  neutral only {k}: {'; '.join(why)}")
    kinds = Counter(p.split(":")[0] + (":" + p.split(":")[1] if p.startswith("doc") else "") for v in out for p in v["perturbations"])
    print("perturbations:", dict(kinds))
    print("languages:", dict(Counter(v["lang"] for v in out)), "cantons:", dict(Counter(v["persona"].get("canton") for v in out)))
    print("dropped while generating:", dict(rejected))


if __name__ == "__main__":
    main()
