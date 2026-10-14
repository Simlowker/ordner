"""Fictional demo dossier « Noa Keller » for the cockpit and the scenarios. All data is invented.

python -m ordner.case.demo_seed          # seeds $ORDNER_HOME/ordner.db (default ~/.ordner), idempotent

Noa Keller, 23, Lausanne (VD): apprentice until July 2025, then first salaried job with a pension fund; two banks and
one broker; LAMal deductible CHF 300; no pillar 3a; planned move to Fribourg in January 2027. No case is opened here:
cases come from the rules engine (or pass `cases=[(card_id, period), ...]` to open them in `to_qualify`).
Tax statements point to real generated PDFs/PNGs in work/ when present (their printed client name is another
fictional person); otherwise the path is `placeholder:<name>`.
"""
import hashlib
import json
from pathlib import Path

from ordner.core.schema import Document, Fact, Subject, new_id

from .store import Store

SUBJECT_ID = "subj_noa_keller"
ROOT = Path(__file__).resolve().parents[3]  # track_2b/
TAX = "swiss_tax_statement_eCH0196"

DOCS = {  # name -> (path relative to track_2b or placeholder name, Document fields)
    "salary_alpinea": ("certificat_salaire_alpinea_2025.pdf", dict(
        kind="salary_certificate", year=2025, issuer="Alpinea Garage Sàrl", channel="scan", read_path="ai",
        received_at="2026-01-28T17:40:00+00:00",
        fields={"employer": "Alpinea Garage Sàrl", "period": "2025-01-01/2025-07-31", "role": "apprentice",
                "gross": 9450}, doubt={"gross": 0.06})),
    "salary_logivia": ("certificat_salaire_logivia_2025.pdf", dict(
        kind="salary_certificate", year=2025, issuer="Logivia SA", channel="email", read_path="ai",
        received_at="2026-01-30T09:05:00+00:00",
        fields={"employer": "Logivia SA", "period": "2025-08-01/2025-12-31", "gross": 26000,
                "lpp_employee": 900, "activity_rate": "60%"}, doubt={"activity_rate": 0.4, "gross": 0.04})),
    "tax_sellin": ("work/pdf/s0421-A.pdf", dict(
        kind=TAX, year=2025, issuer="Sellin Banque Privée SA", channel="inbox", read_path="barcode",
        received_at="2026-02-02T07:30:00+00:00",
        fields={"totalTaxValue": "4222.36", "totalGrossRevenueA": "33.3", "totalGrossRevenueB": "2.78",
                "totalWithHoldingTaxClaim": "11.655", "taxPeriod": "2025"})),
    "tax_tallin_photo": ("work/png/s0327-A-p1-d1.png", dict(
        kind=TAX, year=2025, issuer="Tallin Banque Privée SA", channel="scan", read_path="ai",
        received_at="2026-02-09T19:12:00+00:00",
        fields={"totalTaxValue": "28037.28", "taxPeriod": "2025"}, doubt={"totalTaxValue": 0.31})),
    "tax_tallin_pdf": ("work/pdf/s0327-A.pdf", dict(
        kind=TAX, year=2025, issuer="Tallin Banque Privée SA", channel="email", read_path="barcode",
        received_at="2026-02-16T08:00:00+00:00",
        fields={"totalTaxValue": "28087.28", "totalGrossRevenueA": "0", "totalGrossRevenueB": "91.213",
                "totalWithHoldingTaxClaim": "0", "taxPeriod": "2025"})),
    "tax_velaro": ("work/pdf/s0498-A.pdf", dict(
        kind=TAX, year=2025, issuer="Velaro Banque de Gestion SA", channel="inbox", read_path="barcode",
        received_at="2026-02-23T07:45:00+00:00",
        fields={"totalTaxValue": "46953", "totalGrossRevenueA": "290.84", "totalGrossRevenueB": "176.46",
                "totalWithHoldingTaxClaim": "101.79", "taxPeriod": "2025"})),
    "lamal_2027": ("avis_primes_lamal_2027.pdf", dict(
        kind="health_insurance_premium_letter", year=2027, issuer="Helvia Assurance-maladie (fictive)",
        channel="inbox", read_path="ai", received_at="2026-10-06T10:20:00+00:00",
        fields={"insurer": "Helvia Assurance-maladie (fictive)", "deductible": 300, "monthly_premium": "412.60",
                "model": "standard", "accident_cover": True, "age_class": "19-25"},
        doubt={"monthly_premium": 0.12})),
}

# (key, value, period, unit, proposed_by, source doc, doubt, outcome)  outcome: confirm | reject | None (left proposed)
FACTS = [
    ("person.birth_year", 2003, None, None, "user", None, None, "confirm"),
    ("residence.canton", "VD", None, None, "user", None, None, "confirm"),
    ("residence.commune", "Lausanne", None, None, "user", None, None, "confirm"),
    ("household.marital_status", "single", None, None, "user", None, None, "confirm"),
    ("household.children", 0, None, None, "user", None, None, "confirm"),
    ("work.apprenticeship.end_date", "2025-07-31", None, None, "user", None, None, "confirm"),
    ("work.employment.start_date", "2025-08-01", None, None, "user", None, None, "confirm"),
    ("work.employment.employer", "Logivia SA", None, None, "user", None, None, "confirm"),
    ("finance.institutions", [{"name": "Sellin Banque Privée SA", "type": "bank"},
                              {"name": "Tallin Banque Privée SA", "type": "bank"},
                              {"name": "Velaro Banque de Gestion SA", "type": "broker"}],
     "2025", None, "user", None, None, "confirm"),
    ("pension.pillar3a.has", False, None, None, "user", None, None, "confirm"),
    ("move.planned.date", "2027-01-15", None, None, "user", None, None, "confirm"),
    ("move.planned.canton", "FR", None, None, "user", None, None, "confirm"),
    ("move.planned.commune", "Fribourg", None, None, "user", None, None, "confirm"),
    # salary certificates (AI read): the 60 % rate is a misread, rejected and replaced by the user's 100 %
    ("income.employment.alpinea.gross", 9450, "2025", "CHF", "model", "salary_alpinea", 0.06, None),
    ("income.employment.logivia.gross", 26000, "2025", "CHF", "model", "salary_logivia", 0.04, None),
    ("work.employment.rate", 0.6, "2025", None, "model", "salary_logivia", 0.4, "reject"),
    ("work.employment.rate", 1.0, "2025", None, "user", None, None, "confirm"),
    ("pension.lpp.affiliated", True, "2025", None, "model", "salary_logivia", 0.02, "confirm"),
    ("pension.lpp.employee_contributions", 900, "2025", "CHF", "model", "salary_logivia", 0.05, None),
    # tax statements 2025: barcode = exact; the Tallin photo was misread, then superseded by the PDF barcode
    ("tax.securities.sellin.total_tax_value", 4222.36, "2025", "CHF", "ordner", "tax_sellin", 0.0, "confirm"),
    ("tax.securities.sellin.withholding_tax_claim", 11.655, "2025", "CHF", "ordner", "tax_sellin", 0.0, "confirm"),
    ("tax.securities.tallin.total_tax_value", 28037.28, "2025", "CHF", "model", "tax_tallin_photo", 0.31, "confirm"),
    ("tax.securities.tallin.total_tax_value", 28087.28, "2025", "CHF", "ordner", "tax_tallin_pdf", 0.0, "confirm"),
    ("tax.securities.velaro.total_tax_value", 46953.0, "2025", "CHF", "ordner", "tax_velaro", 0.0, None),
    ("tax.securities.velaro.withholding_tax_claim", 101.79, "2025", "CHF", "ordner", "tax_velaro", 0.0, None),
    # LAMal premium notice 2027 (AI read)
    ("health.lamal.insurer", "Helvia Assurance-maladie (fictive)", "2027", None, "model", "lamal_2027", 0.03, "confirm"),
    ("health.lamal.deductible", 300, "2027", "CHF", "model", "lamal_2027", 0.02, "confirm"),
    ("health.lamal.monthly_premium", 412.60, "2027", "CHF", "model", "lamal_2027", 0.12, None),
    ("health.lamal.accident_cover", True, "2027", None, "model", "lamal_2027", 0.2, None),
]


def _document(rel, fields) -> Document:
    p = ROOT / rel
    if p.is_file():
        path, sha = str(p), hashlib.sha256(p.read_bytes()).hexdigest()
    else:
        path = f"placeholder:{Path(rel).name}"
        sha = hashlib.sha256(path.encode()).hexdigest()
    return Document(new_id("doc"), SUBJECT_ID, path, sha, **fields)


def seed(store: Store | None = None, cases=()) -> str:
    """Create the persona once (idempotent), optionally open cases [(card_id, period)], return the subject id."""
    store = store or Store()
    try:
        store.get_subject(SUBJECT_ID)
    except KeyError:
        store.add_subject(Subject(
            SUBJECT_ID, "person", "Noa Keller", canton="VD", commune="Lausanne", roles=["salaried"],
            attrs={"birth_year": 2003, "has_pension_fund": True, "children": 0, "fictional": True}))
        docs = {name: store.add_document(_document(rel, fields), actor="user" if fields["channel"] == "scan"
                                         else "connector") for name, (rel, fields) in DOCS.items()}
        for key, value, period, unit, actor, doc, doubt, outcome in FACTS:
            f = store.propose_fact(Fact(new_id("fact"), SUBJECT_ID, key, value, period=period, unit=unit, actor=actor,
                                        source_doc=docs[doc].id if doc else None, doubt=doubt))
            if outcome == "confirm":
                store.confirm_fact(f.id)
            elif outcome == "reject":
                store.reject_fact(f.id)
    for card_id, period in cases:
        store.open_case(SUBJECT_ID, card_id, period)
    return SUBJECT_ID


if __name__ == "__main__":
    store = Store()
    snap = store.snapshot(seed(store))
    print(json.dumps({"db": str(store.path), "subject": SUBJECT_ID, "documents": len(snap["documents"]),
                      "facts": {k: len(v) for k, v in snap["facts"].items()},
                      "open_cases": len(snap["open_cases"])}, indent=2))
