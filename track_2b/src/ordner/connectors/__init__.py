"""Local-first connectors: files in, `Document` + proposed `Fact`s out (ordner.core.schema). Nothing is ever sent.

Every parser returns a `Parsed`. `persist(parsed, store)` writes it through `ordner.case.Store` when one is given;
without a store the plain objects are the result. Money facts are JSON floats in the document currency; the exact
source strings stay in `Document.fields`.
"""
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ordner.core.schema import Document, Fact, new_id


@dataclass
class Parsed:
    document: Document
    facts: list[Fact] = field(default_factory=list)
    status: str = "ok"            # ok | needs_ai_read | duplicate | unsupported | skipped
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)   # parser payload (transactions, bill, pages, ...)


def sha256(path) -> str:
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def new_document(path, subject_id, channel="inbox", digest=None, **kw) -> Document:
    p = Path(path)
    return Document(id=new_id("doc"), subject_id=subject_id, path=str(p.resolve()), sha256=digest or sha256(p),
                    channel=channel, **kw)


def fact(doc: Document, key: str, value, unit=None, period=None, doubt=None) -> Fact:
    return Fact(id=new_id("fact"), subject_id=doc.subject_id, key=key, value=value, unit=unit,
                period=period or (str(doc.year) if doc.year else None), actor="connector", source_doc=doc.id,
                doubt=doubt)


def persist(parsed: Parsed, store=None) -> Parsed:
    if store is not None and parsed.status != "duplicate":
        store.add_document(parsed.document)
        for f in parsed.facts:
            store.propose_fact(f)
    return parsed
