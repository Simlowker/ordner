"""python -m ordner.procedures.selfcheck  (validator asserts, then every card in cards/ loads and validates)"""
import json
import sys
from collections import Counter

from .catalog import CARDS_DIR, get, load_cards, validate

GOOD = {
    "id": "x.demo.VD", "name": {"fr": "a", "de": "b", "it": "c"}, "domain": "tax", "nature": "obligation",
    "jurisdiction": "VD", "applicability": {"all": [{"attr": "canton", "eq": "VD"}, {"role": "taxpayer"}]},
    "deadline": {"id": "fixed_date", "params": {"month": 3, "day": 15, "year_offset": 1, "sources": [0]}},
    "steps": [{"id": "s1", "label": {"fr": "a", "de": "b", "it": "c"}, "who": "user", "sources": [0]}],
    "outputs": ["filing_receipt"],
    "sources": [{"title": "t", "url": "https://www.vd.ch", "quote": "q", "verified": True, "accessed": "2026-10-14"}],
    "qualification": "qualified",
}


def bad(**patch):
    return {**GOOD, **patch}


def main():
    assert validate(GOOD) == [], validate(GOOD)
    assert validate(bad(name={"fr": "a", "de": "b"}))
    assert validate(bad(typo=1))
    assert validate(bad(deadline={"id": "nope", "params": {}}))
    assert validate(bad(applicability={"attr": "canton"}))
    assert validate(bad(applicability={"any": [{"role": "x", "attr": "y"}]}))
    assert validate(bad(sources=[]))
    assert validate(bad(sources=[{"title": "t", "url": "https://x.ch", "verified": True}]))
    assert validate(bad(sources=[{"title": "t", "url": "https://x.ch", "quote": "q", "verified": False}]))  # qualified
    assert validate(bad(qualification="draft"))  # draft without notes
    assert validate(bad(qualification="draft", notes="why")) == []
    assert validate(bad(steps=[{"id": "s1", "label": {"fr": "a", "de": "b", "it": "c"}, "who": "user", "sources": [3]}]))
    assert validate(bad(deadline={"id": "fixed_date", "params": {"month": 3}}))
    assert validate(bad(deadline={"id": "cantonal_table", "params": {"table": {"VD": {"month": 1, "day": 31, "sources": [5]}}}}))
    assert validate(bad(deadline={"id": "cantonal_table", "params": {"table": {"VD": {"month": 1, "day": 31}}}})) == []

    failures, ids = {}, set()
    for path in sorted(CARDS_DIR.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        errs = validate(raw)
        if raw.get("id") != path.stem:
            errs.append(f"id {raw.get('id')!r} != file name")
        if errs:
            failures[path.name] = errs
        ids.add(raw.get("id"))
    for name, errs in failures.items():
        print(f"INVALID {name}:\n  " + "\n  ".join(errs))
    if failures:
        sys.exit(1)

    cards = load_cards()
    assert {c.id for c in cards} == ids and all(get(c.id) is c for c in cards)
    assert all(c.jurisdiction in ("VD", "CH") for c in load_cards("VD"))
    by_q = Counter(c.qualification for c in cards)
    by_domain = Counter(c.domain for c in cards)
    unverified = sum(not s.verified for c in cards for s in c.sources)
    print(f"{len(cards)} cards valid | by qualification: {dict(by_q)} | by domain: {dict(by_domain)}"
          f" | sources: {sum(len(c.sources) for c in cards)} ({unverified} unverified)")
    for c in cards:
        print(f"  {c.qualification:9} {c.id}")


if __name__ == "__main__":
    main()
