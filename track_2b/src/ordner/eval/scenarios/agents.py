"""Agents under evaluation. Each is called once per phase: agent(s, store, subject_id, phase, goal, today) -> outcome.

outcome = {"applicable": [card ids], "questions": [{"missing", "question"}], "deadlines": [{"procedure", "due"}],
           "actions": [{"procedure", "kind", "status", "requires_validation", "payload"}], "tool_calls": [{...}],
           "attempted_effects": int, "notes": [...]}
The runner merges every phase's outcome with a read-back of the dossier (cases, deadlines, actions) at the end.
Modules of the parallel workstreams are imported lazily: an agent whose modules are missing fails with ImportError.
"""
import hashlib
import json
from dataclasses import asdict

from ordner.core.schema import Action, Deadline, Document, Fact, Subject, new_id

from . import ROOT


def empty() -> dict:
    return {"applicable": [], "questions": [], "deadlines": [], "actions": [], "tool_calls": [],
            "attempted_effects": 0, "notes": []}


# -- dossier seeding -----------------------------------------------------------------------------------------------

def subject_id(s) -> str:
    return f"subj_{s['id'].replace('-', '_')}"


def seed(store, s, phase: dict, tmp, first: bool) -> str:
    """Write the persona (first phase), documents, confirmed facts and known events of one phase into the store."""
    sid = subject_id(s)
    if first:
        p = s["persona"]
        store.add_subject(Subject(sid, p.get("kind", "person"), p["name"], p.get("canton"), p.get("commune"),
                                  list(p.get("roles", [])), dict(p.get("attrs", {}))))
    for d in phase.get("documents", []):
        fields = dict(d.get("fields", {}))
        if d.get("path"):
            path = ROOT / d["path"]
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
        elif d.get("text"):
            path = tmp / f"{d['id']}.txt"
            path.write_text(d["text"], encoding="utf-8")
            sha = hashlib.sha256(d["text"].encode()).hexdigest()
        else:
            path, sha = f"placeholder:{d['id']}", hashlib.sha256(json.dumps([d["id"], fields]).encode()).hexdigest()
        if d.get("text"):
            fields["text"] = d["text"]
        extra = {k: d[k] for k in ("received_at", "channel", "read_path") if d.get(k)}
        store.add_document(Document(d["id"], sid, str(path), sha, d.get("kind"), d.get("year"), d.get("issuer"),
                                    fields=fields, **extra))
    known = [e["fact"] for e in phase.get("events", []) if e.get("known") and e.get("fact")]
    for f in phase.get("facts", []) + known:
        fact = store.propose_fact(Fact(new_id("fact"), sid, f["key"], f["value"], f.get("period"), f.get("unit"),
                                       actor="user"))
        store.confirm_fact(fact.id, actor="user")
    return sid


def readback(store, sid) -> dict:
    out = empty()
    for c in store.cases(sid):
        if c.state == "closed":
            continue
        out["applicable"].append(c.card_id)
        out["deadlines"] += [{"procedure": c.card_id, "due": d.due} for d in c.deadlines]
        out["actions"] += [{"procedure": c.card_id, "case_id": c.id, **asdict(a)} for a in c.actions]
    return out


# -- agents ----------------------------------------------------------------------------------------------------------

def mock(resolve):
    """Oracle: returns the expected outcome (runner and metric self-test only, never a reported result)."""
    def agent(s, store, sid, phase, goal, today):
        x, out = s["expected"], empty()
        if phase == 0:
            out["applicable"] = [resolve(p) for p in x.get("applicable", [])]
            out["questions"] = [{"missing": m["match"][0], "question": m["topic"]} for m in x.get("missing_info", [])]
            out["deadlines"] = [{"procedure": resolve(d["procedure"]), "due": d["due"]}
                                for d in x.get("deadlines", []) if d.get("due")]
            out["actions"] = [{"procedure": None, "kind": k if isinstance(k, str) else k[0], "status": "prepared",
                               "requires_validation": True, "payload": {}} for k in x.get("actions", [])]
        return out
    return agent


def rules_only(resolve):
    """Deterministic baseline: every catalogue card x ordner.rules on the dossier's confirmed facts. No LLM, no reading
    of free text: only the persona, confirmed facts and known events count. Steps with an action become prepared
    actions; a missing input becomes a question naming the missing key."""
    from ordner import rules
    from ordner.procedures import catalog

    def agent(s, store, sid, phase, goal, today):
        out, subject, facts = empty(), store.get_subject(sid), store.facts(sid, status="confirmed")
        events = [e for p in [s] + s.get("phases", [])[:max(phase, 0)] for e in p.get("events", [])]
        for card in catalog.load_cards():
            r = rules.applicable(card, subject, facts, on=today)
            if r["status"] == "missing_info":
                out["questions"] += [{"missing": k, "question": f"{card.id}: {k} ?"} for k in r["missing"]]
                continue
            if r["status"] != "applicable":
                continue
            period = s.get("period")
            case = store.open_case(sid, card.id, period=period)
            out["applicable"].append(card.id)
            if card.deadline:
                ctx = {"period": period, "canton": subject.canton, "today": today, "facts": facts}
                for e in events:
                    if e.get("known") and e.get("procedure") and resolve(e["procedure"]) == card.id:
                        ctx["notified_on"] = e["date"]
                d = rules.compute_deadline(card.deadline, subject, ctx)
                if d.get("due"):
                    store.add_deadline(Deadline(new_id("dl"), case.id, d["due"], card.deadline.id, d.get("computed_from", {})))
                    out["deadlines"].append({"procedure": card.id, "due": d["due"]})
                else:
                    out["questions"] += [{"missing": k, "question": f"{card.id}: {k} ?"} for k in d.get("missing", [])]
            for step in card.steps:
                if step.get("action"):
                    a = store.add_action(Action(new_id("act"), case.id, step["action"], {"card": card.id, "step": step["id"]},
                                                requires_validation=step["action"] != "reminder"))
                    out["actions"].append({"procedure": card.id, **asdict(a)})
        return out
    return agent


class _DatedRegistry:
    """Same API as ordner.tools.registry, with the scenario's date and replay mode in every tool context."""

    def __init__(self, reg, today):
        self.reg, self.today, self.SPECS = reg, today, reg.SPECS

    def call(self, name, args, ctx):
        ctx.setdefault("today", self.today)
        ctx.setdefault("mode", "replay")
        return self.reg.call(name, args, ctx)


def coordinator(resolve, llm, max_steps=12):
    """ordner.agent.coordinator.run on the seeded dossier; outcome taken from its questions, prepared actions, tool
    calls and the rules/deadline results it obtained."""
    from ordner.agent import coordinator as C

    def agent(s, store, sid, phase, goal, today):
        reg = _DatedRegistry(C._registry(), today)
        r = C.run(f"[{today}] {goal}", sid, llm, store, max_steps=max_steps, registry=reg)
        out = empty()
        out["questions"] = [{"missing": q.get("missing") or "", "question": q.get("question", "")} for q in r["questions"]]
        out["actions"] = [{"procedure": None, **a} for a in r["actions"]]
        out["attempted_effects"] = r.get("stats", {}).get("intercepted", 0)
        out["notes"] = r.get("warnings", [])
        out["answer"] = r.get("answer")
        for t in r["transcript"]:
            if t["role"] == "assistant":
                out["tool_calls"] += t["tool_calls"]
            elif t["role"] == "tool" and isinstance(t.get("result"), dict):
                res = t["result"].get("data", t["result"])   # registry wraps results in {"ok", "data", ...}
                if not isinstance(res, dict):
                    continue
                card = res.get("card_id") or res.get("card") or (t.get("arguments") or {}).get("card_id")
                if card and res.get("status") == "applicable":
                    out["applicable"].append(card)
                due = (res.get("deadline") or {}).get("due") if isinstance(res.get("deadline"), dict) else res.get("due")
                if card and due:
                    out["deadlines"].append({"procedure": card, "due": due})
        out["tool_specs"] = {s_.name.replace(".", "_"): s_.input_schema for s_ in reg.SPECS}
        out["tool_specs"].update({t["function"]["name"]: t["function"]["parameters"] for t in C.AGENT_TOOLS})
        return out
    return agent
