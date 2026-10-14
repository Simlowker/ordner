"""Durable local dossier: SQLite at $ORDNER_HOME/ordner.db (default ~/.ordner), JSON columns, append-only event log."""
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path
from typing import get_args

from ordner.core.schema import (
    Action, ActionKind, ActionStatus, Actor, Case, CaseState, Deadline, Document, Event, Fact, FactStatus,
    Subject, SubjectKind, new_id, now,
)

STATES = list(get_args(CaseState))  # declaration order = forward path; a lower index is a back-transition
NEXT = {
    "to_qualify": {"missing_documents", "ready_to_prepare"},  # ready_to_prepare: nothing missing
    "missing_documents": {"ready_to_prepare"},
    "ready_to_prepare": {"ready_to_validate"},
    "ready_to_validate": {"action_engaged"},
    "action_engaged": {"awaiting_response", "result_verified"},  # result_verified: no response expected (payment receipt)
    "awaiting_response": {"complement_requested", "decision_received"},
    "complement_requested": {"missing_documents", "ready_to_prepare", "awaiting_response"},
    "decision_received": {"result_verified"},
    "result_verified": {"closed"},
    "closed": set(),
}
ACTION_NEXT = {
    "prepared": {"validated", "cancelled"},
    "validated": {"done_by_user", "cancelled"},
    "done_by_user": {"verified"},
    "verified": set(),
    "cancelled": set(),
}
PENDING = {"prepared", "validated", "done_by_user"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS subjects (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, subject_id TEXT NOT NULL REFERENCES subjects(id),
  sha256 TEXT NOT NULL, kind TEXT, year INTEGER, data TEXT NOT NULL, UNIQUE (subject_id, sha256));
CREATE TABLE IF NOT EXISTS facts (id TEXT PRIMARY KEY, subject_id TEXT NOT NULL REFERENCES subjects(id),
  key TEXT NOT NULL, period TEXT, status TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, subject_id TEXT NOT NULL REFERENCES subjects(id),
  card_id TEXT NOT NULL, period TEXT, state TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS actions (id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
  status TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS deadlines (id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
  due TEXT NOT NULL, rule_id TEXT, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, ts TEXT NOT NULL,
  subject_id TEXT NOT NULL, case_id TEXT, type TEXT NOT NULL, actor TEXT NOT NULL, payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS events_subject ON events (subject_id, seq);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
"""


def _check(value, literal):
    if value not in get_args(literal):
        raise ValueError(f"{value!r} not in {get_args(literal)}")


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _case_data(c: Case) -> dict:
    return {**asdict(c), "deadlines": [], "actions": []}  # deadlines/actions live in their own tables


def _fact_payload(f: Fact) -> dict:
    return {"fact_id": f.id, "key": f.key, "value": f.value, "period": f.period, "unit": f.unit,
            "source_doc": f.source_doc, "proposed_by": f.actor}


class Store:
    def __init__(self, path=None):
        path = Path(path) if path else Path(os.environ.get("ORDNER_HOME", "~/.ordner")).expanduser() / "ordner.db"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=10)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        self._lock = threading.RLock()  # ponytail: one lock per Store, enough for a single-user local dossier

    def close(self):
        self.db.close()

    # -- plumbing -------------------------------------------------------------------------------------------
    @contextmanager
    def _tx(self):
        with self._lock, self.db:
            yield

    def _insert(self, table, data: dict, **cols):
        cols = {"id": data["id"], **cols, "data": _dumps(data)}
        self.db.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                        list(cols.values()))

    def _update(self, table, data: dict, **cols):
        cols = {**cols, "data": _dumps(data)}
        self.db.execute(f"UPDATE {table} SET {', '.join(f'{k}=?' for k in cols)} WHERE id=?",
                        [*cols.values(), data["id"]])

    def _get(self, table, cls, id):
        row = self.db.execute(f"SELECT data FROM {table} WHERE id=?", (id,)).fetchone()
        if not row:
            raise KeyError(f"{table}: {id} not found")
        return cls(**json.loads(row[0]))

    def _select(self, table, cls, order="rowid", **where):
        where = {k: v for k, v in where.items() if v is not None}
        sql = f"SELECT data FROM {table}" + (" WHERE " + " AND ".join(f"{k}=?" for k in where) if where else "")
        return [cls(**json.loads(r[0])) for r in self.db.execute(f"{sql} ORDER BY {order}", list(where.values()))]

    def _event(self, subject_id, type, payload, actor, case_id=None):
        _check(actor, Actor)
        self.db.execute("INSERT INTO events (id, ts, subject_id, case_id, type, actor, payload) VALUES (?,?,?,?,?,?,?)",
                        (new_id("evt"), now(), subject_id, case_id, type, actor, _dumps(payload)))

    def _case(self, c: Case) -> Case:
        c.deadlines = self._select("deadlines", Deadline, order="due", case_id=c.id)
        c.actions = self._select("actions", Action, case_id=c.id)
        return c

    # -- subjects -------------------------------------------------------------------------------------------
    def add_subject(self, s: Subject, actor="user") -> Subject:
        _check(s.kind, SubjectKind)
        with self._tx():
            if self.db.execute("SELECT 1 FROM subjects WHERE id=?", (s.id,)).fetchone():
                raise ValueError(f"subject {s.id} already exists")
            self._insert("subjects", asdict(s))
            self._event(s.id, "subject_added", {"kind": s.kind, "name": s.name}, actor)
        return s

    def get_subject(self, id) -> Subject:
        return self._get("subjects", Subject, id)

    def subjects(self) -> list[Subject]:
        return self._select("subjects", Subject)

    # -- documents ------------------------------------------------------------------------------------------
    def add_document(self, d: Document, actor="connector") -> Document:
        """Idempotent on (subject, sha256): the same file received twice returns the stored document."""
        self.get_subject(d.subject_id)
        with self._tx():
            row = self.db.execute("SELECT data FROM documents WHERE subject_id=? AND sha256=?",
                                  (d.subject_id, d.sha256)).fetchone()
            if row:
                return Document(**json.loads(row[0]))
            self._insert("documents", asdict(d), subject_id=d.subject_id, sha256=d.sha256, kind=d.kind, year=d.year)
            self._event(d.subject_id, "document_received", {"document_id": d.id, "kind": d.kind, "year": d.year,
                        "issuer": d.issuer, "channel": d.channel, "sha256": d.sha256}, actor)
        return d

    def get_document(self, id) -> Document:
        return self._get("documents", Document, id)

    def documents(self, subject_id, kind=None, year=None) -> list[Document]:
        self.get_subject(subject_id)  # never fall back to "all subjects"
        return self._select("documents", Document, subject_id=subject_id, kind=kind, year=year)

    # -- facts ----------------------------------------------------------------------------------------------
    def propose_fact(self, f: Fact) -> Fact:
        self.get_subject(f.subject_id)
        _check(f.actor, Actor)
        if f.status != "proposed":
            raise ValueError("facts enter the dossier as proposed; use confirm_fact")
        if f.source_doc and self.get_document(f.source_doc).subject_id != f.subject_id:
            raise ValueError(f"source document {f.source_doc} belongs to another subject")
        f = replace(f, supersedes=None)
        with self._tx():
            self._insert("facts", asdict(f), subject_id=f.subject_id, key=f.key, period=f.period, status=f.status)
            self._event(f.subject_id, "fact_proposed", _fact_payload(f), f.actor)
        return f

    def confirm_fact(self, fact_id, actor="user") -> Fact:
        """A confirmed fact supersedes the confirmed fact with the same subject + key + period (kept as history)."""
        _check(actor, Actor)
        if actor == "model":
            raise ValueError("a model proposes facts, it cannot confirm them")
        with self._tx():
            f = self._get("facts", Fact, fact_id)
            if f.status != "proposed":
                raise ValueError(f"fact {fact_id} is {f.status}; only proposed facts can be confirmed")
            for old in self._select("facts", Fact, subject_id=f.subject_id, key=f.key, status="confirmed"):
                if old.period != f.period:
                    continue
                old.status, f.supersedes = "superseded", old.id
                self._update("facts", asdict(old), status=old.status)
                self._event(f.subject_id, "fact_superseded", {"fact_id": old.id, "by": f.id, "key": f.key,
                            "period": f.period, "old_value": old.value, "new_value": f.value}, actor)
            f.status = "confirmed"
            self._update("facts", asdict(f), status=f.status)
            self._event(f.subject_id, "fact_confirmed", {**_fact_payload(f), "supersedes": f.supersedes}, actor)
        return f

    def reject_fact(self, fact_id, actor="user") -> Fact:
        """Proposed or confirmed -> rejected (a confirmed fact it superseded is not restored)."""
        _check(actor, Actor)
        with self._tx():
            f = self._get("facts", Fact, fact_id)
            if f.status not in ("proposed", "confirmed"):
                raise ValueError(f"fact {fact_id} is {f.status}; cannot reject")
            prev, f.status = f.status, "rejected"
            self._update("facts", asdict(f), status=f.status)
            self._event(f.subject_id, "fact_rejected", {**_fact_payload(f), "was": prev}, actor)
        return f

    def facts(self, subject_id, key_prefix=None, status=None) -> list[Fact]:
        self.get_subject(subject_id)
        if status:
            _check(status, FactStatus)
        out = self._select("facts", Fact, subject_id=subject_id, status=status)
        return [f for f in out if not key_prefix or f.key.startswith(key_prefix)]

    # -- cases ----------------------------------------------------------------------------------------------
    def open_case(self, subject_id, card_id, period=None, actor="rule") -> Case:
        """Idempotent: an open (not closed) case for the same subject + card + period is returned as is."""
        self.get_subject(subject_id)
        with self._tx():
            for c in self._select("cases", Case, subject_id=subject_id, card_id=card_id):
                if c.period == period and c.state != "closed":
                    return self._case(c)
            c = Case(new_id("case"), subject_id, card_id, period)
            self._insert("cases", _case_data(c), subject_id=subject_id, card_id=card_id, period=period, state=c.state)
            self._event(subject_id, "case_opened", {"card_id": card_id, "period": period}, actor, c.id)
        return c

    def get_case(self, id) -> Case:
        return self._case(self._get("cases", Case, id))

    def cases(self, subject_id=None, state=None) -> list[Case]:
        if state:
            _check(state, CaseState)
        return [self._case(c) for c in self._select("cases", Case, subject_id=subject_id, state=state)]

    def set_state(self, case_id, state, reason="", actor="ordner") -> Case:
        """Forward moves follow NEXT; going back (or closing early) is allowed only with an explicit reason."""
        _check(state, CaseState)
        with self._tx():
            c = self.get_case(case_id)
            if state == c.state:
                return c
            if state not in NEXT[c.state]:
                back = state == "closed" or STATES.index(state) < STATES.index(c.state)
                if not back:
                    raise ValueError(f"transition {c.state} -> {state} not allowed")
                if not reason.strip():
                    raise ValueError(f"transition {c.state} -> {state} needs a reason")
            payload = {"from": c.state, "to": state, "reason": reason}
            c.state = state
            self._update("cases", _case_data(c), state=state)
            self._event(c.subject_id, "state_changed", payload, actor, c.id)
        return c

    def set_missing(self, case_id, missing: list[str], actor="rule") -> Case:
        with self._tx():
            c = self.get_case(case_id)
            if c.missing == list(missing):
                return c
            payload = {"from": c.missing, "to": list(missing)}
            c.missing = list(missing)
            self._update("cases", _case_data(c))
            self._event(c.subject_id, "missing_updated", payload, actor, c.id)
        return c

    # -- actions & deadlines --------------------------------------------------------------------------------
    def add_action(self, a: Action, actor="ordner") -> Action:
        """Idempotent: an identical pending action (same case, kind, payload) is returned instead of duplicated."""
        _check(a.kind, ActionKind)
        if a.status != "prepared":
            raise ValueError("actions enter the dossier as prepared")
        if a.kind != "reminder" and not a.requires_validation:
            raise ValueError(f"{a.kind} has an external effect and requires the user's validation")
        with self._tx():
            c = self.get_case(a.case_id)
            for old in c.actions:
                if old.status in PENDING and old.kind == a.kind and old.payload == a.payload:
                    return old
            self._insert("actions", asdict(a), case_id=a.case_id, status=a.status)
            self._event(c.subject_id, "action_prepared", {"action_id": a.id, "kind": a.kind,
                        "requires_validation": a.requires_validation}, actor, c.id)
        return a

    def update_action(self, action_id, status, actor="user") -> Action:
        _check(status, ActionStatus)
        with self._tx():
            a = self._get("actions", Action, action_id)
            allowed = set(ACTION_NEXT[a.status])
            if a.status == "prepared" and not a.requires_validation:
                allowed.add("done_by_user")
            if status not in allowed:
                raise ValueError(f"action {a.status} -> {status} not allowed"
                                 + (" (needs the user's validation first)" if status == "done_by_user" else ""))
            if status == "validated" and actor != "user":
                raise ValueError("only the user can validate an action")
            payload = {"action_id": a.id, "kind": a.kind, "from": a.status, "to": status}
            a.status = status
            self._update("actions", asdict(a), status=status)
            self._event(self._get("cases", Case, a.case_id).subject_id, "action_updated", payload, actor, a.case_id)
        return a

    def add_deadline(self, d: Deadline, actor="rule") -> Deadline:
        """Idempotent on (case, rule_id, due)."""
        date.fromisoformat(d.due)
        with self._tx():
            c = self.get_case(d.case_id)
            for old in c.deadlines:
                if old.rule_id == d.rule_id and old.due == d.due:
                    return old
            self._insert("deadlines", asdict(d), case_id=d.case_id, due=d.due, rule_id=d.rule_id)
            self._event(c.subject_id, "deadline_added", {"deadline_id": d.id, "due": d.due, "rule_id": d.rule_id},
                        actor, c.id)
        return d

    # -- reading back ---------------------------------------------------------------------------------------
    def events(self, subject_id=None, case_id=None) -> list[Event]:
        where = {k: v for k, v in {"subject_id": subject_id, "case_id": case_id}.items() if v is not None}
        sql = "SELECT id, ts, subject_id, type, payload, actor, case_id FROM events"
        sql += (" WHERE " + " AND ".join(f"{k}=?" for k in where) if where else "") + " ORDER BY seq"
        return [Event(r[0], r[1], r[2], r[3], json.loads(r[4]), r[5], r[6])
                for r in self.db.execute(sql, list(where.values()))]

    def snapshot(self, subject_id, today=None, last_events=20) -> dict:
        """Everything needed to resume a conversation about one subject, as plain JSON."""
        today = today or date.today().isoformat()
        subject = self.get_subject(subject_id)
        facts = {s: [] for s in get_args(FactStatus)}
        for f in self.facts(subject_id):
            facts[f.status].append(asdict(f))
        cases = self.cases(subject_id)
        open_cases = [c for c in cases if c.state != "closed"]
        return {
            "as_of": today,
            "subject": asdict(subject),
            "documents": [asdict(d) for d in self.documents(subject_id)],
            "facts": facts,
            "open_cases": [asdict(c) for c in open_cases],
            "closed_cases": [{"id": c.id, "card_id": c.card_id, "period": c.period} for c in cases if c.state == "closed"],
            "upcoming_deadlines": sorted(({**asdict(d), "card_id": c.card_id, "overdue": d.due < today}
                                          for c in open_cases for d in c.deadlines), key=lambda d: d["due"]),
            "pending_actions": [{**asdict(a), "card_id": c.card_id}
                                for c in open_cases for a in c.actions if a.status in PENDING],
            "last_events": [asdict(e) for e in self.events(subject_id)[-last_events:]],
        }
