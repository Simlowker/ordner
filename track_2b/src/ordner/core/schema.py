"""Shared contracts for every Ordner module. Change only with the coordinator's agreement: other modules depend on it."""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
import uuid

SubjectKind = Literal["person", "household", "company"]
FactStatus = Literal["proposed", "confirmed", "rejected", "superseded"]
Nature = Literal["obligation", "right", "option", "contract"]
Qualification = Literal["qualified", "draft", "unknown"]
CaseState = Literal[
    "to_qualify", "missing_documents", "ready_to_prepare", "ready_to_validate", "action_engaged",
    "awaiting_response", "complement_requested", "decision_received", "result_verified", "closed",
]
ActionKind = Literal["form_entry", "letter", "email_draft", "payment", "reminder", "document_request"]
ActionStatus = Literal["prepared", "validated", "done_by_user", "verified", "cancelled"]
Actor = Literal["user", "ordner", "connector", "rule", "model"]


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Subject:
    id: str
    kind: SubjectKind
    name: str
    canton: str | None = None          # two-letter code, e.g. "VD"
    commune: str | None = None
    roles: list[str] = field(default_factory=list)   # salaried, apprentice, student, self_employed, employer, ...
    attrs: dict[str, Any] = field(default_factory=dict)  # birth_year, has_pension_fund, children, ...


@dataclass
class Document:
    id: str
    subject_id: str
    path: str
    sha256: str
    kind: str | None = None            # swiss_tax_statement_eCH0196, qr_bill_invoice, health_insurance_premium_letter, ...
    year: int | None = None
    issuer: str | None = None
    received_at: str = field(default_factory=now)
    channel: str = "inbox"             # inbox, share, camt, email, scan, video
    read_path: str | None = None       # "barcode" (exact) or "ai" (OCR + Apertus)
    fields: dict[str, Any] = field(default_factory=dict)
    doubt: dict[str, float] = field(default_factory=dict)   # field -> P(wrong)


@dataclass
class Source:
    title: str
    url: str
    quote: str | None = None           # verbatim passage supporting the rule
    verified: bool = False             # quote found word for word in the fetched source
    accessed: str | None = None


@dataclass
class Fact:
    id: str
    subject_id: str
    key: str                           # dotted, e.g. "tax.securities.total_tax_value"
    value: Any
    period: str | None = None          # "2025"
    unit: str | None = None            # "CHF"
    status: FactStatus = "proposed"
    actor: Actor = "model"
    source_doc: str | None = None
    doubt: float | None = None
    created_at: str = field(default_factory=now)
    supersedes: str | None = None


@dataclass
class DeadlineRule:
    id: str                            # implemented in ordner.rules (e.g. "fixed_date", "days_after_notification")
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcedureCard:
    """The 'fiche indispensable' of docs/vision/ordner-parcours: one per procedure x jurisdiction family."""
    id: str                            # e.g. "tax.return.VD"
    name: dict[str, str]               # {"fr": ..., "de": ..., "it": ...}
    domain: str                        # tax, health_insurance, pension, social, housing, debt, work, business, identity
    nature: Nature
    jurisdiction: str                  # "CH" or canton code
    applicability: dict[str, Any]      # declarative conditions on Subject/facts, evaluated by ordner.rules
    required_facts: list[str] = field(default_factory=list)
    required_documents: list[str] = field(default_factory=list)   # document kinds
    deadline: DeadlineRule | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)     # {"id", "label": {fr,de,it}, "action": ActionKind?, "who": "user"|"ordner"}
    outputs: list[str] = field(default_factory=list)              # what closes the case (receipt, decision, payment)
    sources: list[Source] = field(default_factory=list)
    valid_from: str | None = None
    valid_to: str | None = None
    qualification: Qualification = "draft"
    notes: str | None = None


@dataclass
class Deadline:
    id: str
    case_id: str
    due: str                           # ISO date
    rule_id: str
    computed_from: dict[str, Any] = field(default_factory=dict)
    reminders: list[str] = field(default_factory=list)          # ISO dates


@dataclass
class Action:
    id: str
    case_id: str
    kind: ActionKind
    payload: dict[str, Any]
    requires_validation: bool = True   # anything with an external effect needs the user's validation
    status: ActionStatus = "prepared"
    created_at: str = field(default_factory=now)


@dataclass
class Case:
    id: str
    subject_id: str
    card_id: str
    period: str | None = None
    state: CaseState = "to_qualify"
    missing: list[str] = field(default_factory=list)             # missing fact keys / document kinds
    deadlines: list[Deadline] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    opened_at: str = field(default_factory=now)


@dataclass
class Event:
    id: str
    ts: str
    subject_id: str
    type: str                          # document_received, fact_proposed, fact_confirmed, state_changed, action_prepared, ...
    payload: dict[str, Any]
    actor: Actor
    case_id: str | None = None


@dataclass
class ToolSpec:
    """A bounded operation shown to Apertus: name, description, JSON-schema in/out. Implementations live in ordner.tools."""
    name: str                          # e.g. "document.decode"
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    side_effect: bool = False          # True => only prepares; execution needs user validation


def to_dict(obj) -> dict:
    return asdict(obj)
