"""Process teacher: the method of an ideal expert, played deterministically in the same loop as teacher.py and decided
from the tool results only (never from the scenario's expected outcome). Its trajectories are kept only when the
scenario scorer and filter.py pass them, like any teacher's.

Per phase: (1) load the dossier and evaluate every procedure of the expert's scope in the person's canton;
(2) open a case for each applicable procedure and search the official sources; (3) record each computed deadline and
prepare each step with an external effect (no payment when a result flagged injected instructions, rule 6);
(4) ask one question for the missing facts, else answer: what applies, deadlines, what is prepared, sources.

    PYTHONPATH=src .venv/bin/python -m ordner.distill.teacher --teacher process --expert-mode \
        --variants work/distill/variants_all.jsonl --out work/distill/traj.process.jsonl
"""
import json
import re

from ordner.agent.coordinator import REMOVED
from ordner.agent.llm import _call
from ordner.core.labels import label
from ordner.eval.scenarios import agents as A
from ordner.eval.scenarios import run as R
from ordner.procedures import catalog


def results(messages):
    """[(tool name, data)] of the successful tool results, in order."""
    out = []
    for m in messages:
        if m["role"] != "tool":
            continue
        try:
            r = json.loads(m["content"])
        except (json.JSONDecodeError, TypeError):
            continue
        res = r.get("result") or {}
        if res.get("ok") or (res and "ok" not in res and "error" not in res):   # agent tools (prepare_action) answer flat
            out.append((r.get("tool"), res.get("data") or {} if "ok" in res else res))
    return out


def scope(expert, canton):
    from ordner.harness.experts import EXPERTS
    prefixes = EXPERTS[expert].cards if expert in EXPERTS else ("*",)
    return [c for c in catalog.load_cards() if c.jurisdiction in ("CH", canton)
            and ("*" in prefixes or c.id.startswith(tuple(prefixes)))]


KIND = {"housing.moving.announce": {"kind": "arrival"}}   # after a move, the arrival announcement in the new commune


def fmt(iso):
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}"


TXT = {
    "fr": {"applies": "Ce qui vous concerne", "due": "délai", "prepared": "Préparé pour validation (rien n'est envoyé)",
           "none": "Aucune des démarches de mon domaine ne s'applique à votre dossier pour l'instant.",
           "next": "À vous : vérifier et valider dans l'app.", "src": "Sources", "ask": "Pour avancer, il me manque : {}. Pouvez-vous me l'indiquer ?"},
    "de": {"applies": "Was Sie betrifft", "due": "Frist", "prepared": "Zur Freigabe vorbereitet (nichts wird gesendet)",
           "none": "Keines der Verfahren meines Bereichs betrifft Ihr Dossier im Moment.",
           "next": "Ihr nächster Schritt: in der App prüfen und freigeben.", "src": "Quellen", "ask": "Um weiterzumachen, fehlt mir: {}. Können Sie mir das angeben?"},
    "it": {"applies": "Cosa la riguarda", "due": "termine", "prepared": "Preparato da convalidare (nulla viene inviato)",
           "none": "Nessuna procedura del mio ambito riguarda il suo dossier per ora.",
           "next": "Prossimo passo: verificare e convalidare nell'app.", "src": "Fonti", "ask": "Per andare avanti mi manca: {}. Può indicarmelo?"},
}


class ProcessTeacher:
    model = "process (deterministic)"

    def __init__(self):
        self.v = None

    def begin(self, v):
        self.v = v

    def chat(self, messages, tools=None):
        goal = self.goal(messages)
        self.phase = next((i + 1 for i, p in enumerate(self.v.get("phases", []))
                           if (p.get("goal") or {}).get(self.v["lang"], "\0")[:60] in goal), 0)
        content, calls = self.policy(messages)
        return {"content": content, "tool_calls": [_call(i, n, a) for i, (n, a) in enumerate(calls)],
                "raw": json.dumps({"content": content, "calls": calls}, ensure_ascii=False)}

    def policy(self, messages):
        v, sid = self.v, A.subject_id(self.v)
        lg, canton = v["lang"], v["persona"]["canton"]
        expert = (re.search(r"\[ordner-expert: (\w+)\]", messages[0]["content"]) or [None, "coordinateur"])[1]
        period = v.get("period")
        res = results(messages)
        evals = {d["card_id"]: d for n, d in res if n == "rules_evaluate" and d.get("card_id")}
        if not evals:
            notified = {R.resolve(e["procedure"]): e["date"] for p in [v] + v.get("phases", [])[:max(self.phase, 0)]
                        for e in p.get("events", []) if e.get("known") and e.get("procedure")}   # never a later phase
            said = [e for e in (v.get("events", []) if not self.phase else v["phases"][self.phase - 1].get("events", []))
                    if e.get("procedure") and e.get("fact")]   # what the person states in this message
            notified.update({R.resolve(e["procedure"]): e["date"] for e in said})
            return "", [("case_load", {"subject_id": sid})] + [
                ("case_record", {"subject_id": sid, "op": "propose_fact", "key": e["fact"]["key"], "value": e["fact"]["value"]})
                for e in said if not e.get("known")] + [
                ("rules_evaluate", {"card_id": c.id, "subject_id": sid, **({"period": period} if period else {}),
                                    **({"context": {"notified_on": notified[c.id], **KIND.get(c.id, {})}, "include_proposed": True}
                                       if c.id in notified else {})})
                for c in scope(expert, canton)] + [
                ("piece_recevoir", {"subject_id": sid, "doc": d["id"], **({"period": period} if period else {})})
                for d in v.get("documents", [])]
        known = {c.get("card_id"): c.get("id") for n, d in res if n == "case_load" for c in d.get("cases") or []}
        opened = {d["recorded"]["card_id"]: d["recorded"]["id"] for n, d in res
                  if n == "case_record" and d.get("op") == "open_case" and isinstance(d.get("recorded"), dict)}
        cases = {**known, **opened}
        pieces = [d for n, d in res if n == "piece_recevoir"]
        in_scope = {c.id for c in scope(expert, canton)}
        applicable = [c for c, d in evals.items() if d.get("status") == "applicable"]
        applicable += [c for p in pieces for c in p.get("applicable") or [] if c in in_scope and c not in applicable]
        piece_due = {d["card_id"]: d for p in pieces for d in p.get("deadlines") or [] if d.get("card_id") and d.get("due")}
        piece_acts = {c for p in pieces if p.get("prepared_actions") for c in [p.get("card_id") or (p.get("belongs_to") or {}).get("card_id")] if c}
        if any(c not in cases for c in applicable):
            main = applicable[0]
            return "", [("case_record", {"subject_id": sid, "op": "open_case", "card_id": c,
                                         **({"period": period} if period else {})}) for c in applicable if c not in cases] + [
                ("knowledge_search", {"query": self.goal(messages), "card_id": main, "canton": canton, "lang": lg})] + [
                ("impots_preparer_declaration", {"subject_id": sid, **({"period": period} if period else {})})
                for c in applicable[:1] if any(x.startswith("tax.return.") for x in applicable)]
        done = {n for n, _ in res}
        if applicable and "prepare_action" not in done and not any(n == "case_record" and d.get("op") == "add_deadline" for n, d in res):
            injected = any(REMOVED in (m.get("content") or "") for m in messages if m["role"] == "tool")
            calls = []
            for c in applicable:
                dl = (evals.get(c) or {}).get("deadline") or {}
                if not dl.get("due") and c in piece_due:
                    dl = {"due": piece_due[c]["due"], "computed_from": {"document": "piece_recevoir", "rule": piece_due[c].get("rule")}}
                if dl.get("due"):
                    calls.append(("case_record", {"subject_id": sid, "op": "add_deadline", "case_id": cases[c], "due": dl["due"],
                                                  "rule_id": catalog.get(c).deadline.id,
                                                  **({"computed_from": dl["computed_from"]} if dl.get("computed_from") else {})}))
                for step in [] if c in piece_acts else catalog.get(c).steps:
                    if step.get("action") and not (injected and step["action"] == "payment"):
                        calls.append(("prepare_action", {"kind": step["action"], "case_id": cases[c],
                                                         "summary": (step.get("label") or {}).get(lg) or step["id"]}))
            if calls:
                return "", calls
        missing = list(dict.fromkeys(k for d in evals.values() if d.get("status") == "missing_info" for k in d.get("missing") or []))
        missing += [k for c in applicable if c not in piece_due for k in ((evals.get(c) or {}).get("deadline") or {}).get("missing") or [] if k not in missing]
        tools_out = pieces + [d for n, d in res if n == "impots_preparer_declaration"]
        missing += [q["missing"] for p in tools_out for q in p.get("questions") or [] if q.get("missing") and q["missing"] not in missing]
        linked = {p.get("card_id") for p in pieces if p.get("card_id") in in_scope}
        missing += [k for c in linked if c not in applicable and c in evals for w in evals[c].get("why") or []
                    for k in re.findall(r"« ([\w.]+) » absent", w) if k not in missing]   # a received document needs it
        if missing and "ask_user" not in done:
            q = TXT[lg]["ask"].format(", ".join(label(k, lg) for k in missing[:3]))
            return "", [("ask_user", {"question": q, "missing": missing[0]})]
        return self.answer(evals, applicable, res, lg, piece_due), []

    def goal(self, messages):
        first = next((m["content"] for m in messages if m["role"] == "user"), "")
        g = re.search(r"Goal: (.+)", first)
        return (g.group(1) if g else first)[:300]

    def answer(self, evals, applicable, res, lg, piece_due):
        t = TXT[lg]
        if not applicable:
            return t["none"]
        lines = [f"{t['applies']} :"]
        for c in applicable:
            name = catalog.get(c).name
            name = name.get(lg) if isinstance(name, dict) else name
            dl = ((evals.get(c) or {}).get("deadline") or {}).get("due") or (piece_due.get(c) or {}).get("due")
            lines.append(f"- {name}" + (f" ({t['due']} : {fmt(dl)})" if dl else ""))
        prepared = [d for n, d in res if n == "prepare_action"]
        if prepared:
            lines.append(f"{t['prepared']} : {len(prepared)}.")
        lines.append(t["next"])
        urls = list(dict.fromkeys(s["url"] for c in applicable for s in (evals.get(c) or {}).get("sources") or [] if s.get("url")))[:2]
        if urls:
            lines.append(f"{t['src']} : " + " ; ".join(urls))
        return "\n".join(lines)
