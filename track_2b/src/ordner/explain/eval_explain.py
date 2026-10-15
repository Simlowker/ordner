"""Light evaluation of the grounded explanations on dev pages (one language per page, rotating fr/de/it):
citation verbatim rate, share of extracted amounts mentioned, output language -> data/explain_eval.json.
    python -m ordner.explain.eval_explain [--n 30] [--system auto] [--mock]"""
import argparse
import json
import re
import time
from pathlib import Path

from ordner.eval.metrics import norm_number, read_jsonl

from . import explain
from .export_demo import MODEL_NAME, doubt_scores, fmt, pick_system, rnd

STOP = {"de": set("der die das und ist nicht sie ihr ihre ein eine mit von zu den im für auf werden wird dem des".split()),
        "fr": set("le la les et est des une un du pour dans que vous sur pas au aux ce votre être".split()),
        "it": set("il lo la le gli e è dei delle una un per nel che lei sul non della di suo sua".split())}
NUM = re.compile(r"\d[\d'’\u202f\u00a0]*(?:[.,]\d+)?")


def detect_lang(text):
    words = re.findall(r"[a-zàâäçéèêëîïôöùûüß]+", text.lower())
    hits = {lang: sum(w in s for w in words) for lang, s in STOP.items()}
    best = max(hits, key=hits.get)
    return best if hits[best] >= 3 else None


def mentioned(text, value):
    v = norm_number(value)
    return v is not None and any(norm_number(n.strip()) == v for n in NUM.findall(text))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--system", default="auto")
    ap.add_argument("--mock", action="store_true", help="mocked generator (pipeline test, no Apertus)")
    ap.add_argument("--server", action="store_true", help="Apertus through the OpenAI-compatible server (LLM_BASE_URL)")
    ap.add_argument("--out", default="data/explain_eval.json")
    a = ap.parse_args(argv)
    items = read_jsonl(Path(a.data) / "items.jsonl")
    system = pick_system(items, a.system)
    combined, _ = doubt_scores(a.data, system)
    pages = {}
    for i, it in enumerate(items):
        if it["system"] == system and it["split"] == "dev":
            pages.setdefault(it["page_id"], []).append(i)
    pids = sorted(pages)
    pids = pids[:: max(1, len(pids) // a.n)][: a.n]  # evenly spaced, deterministic
    jobs = []
    for j, pid in enumerate(pids):
        fields = [{"field": items[i]["field"], "value": fmt(items[i]["pred"]), "doubt": rnd(combined[i])}
                  for i in pages[pid]]
        jobs.append((pid, explain.LANGS[j % 3], fields))

    from ordner.models import embed
    passages = [explain.retrieve([{**f, "status": explain.status(f["doubt"])} for f in fields], lang)
                for _, lang, fields in jobs]
    embed.unload()
    gen = explain.mock_generate if a.mock else explain.server_generate if a.server else explain.apertus_generate

    rows = []
    for (pid, lang, fields), ps in zip(jobs, passages):
        t = time.perf_counter()
        r = explain.explain_lang(fields, lang, gen, passages=ps)
        secs = time.perf_counter() - t
        amounts = [f for f in fields if f["field"] in explain.NUMERIC and f["value"] is not None]
        n_ok, n_bad = len(r["citations"]), len(r["dropped"])
        rows.append({"page_id": pid, "lang": lang, "detected_lang": detect_lang(r["raw"]), "quotes_verified": n_ok,
                     "quotes_dropped": n_bad, "amounts": len(amounts),
                     "amounts_mentioned": sum(mentioned(r["raw"], f["value"]) for f in amounts),
                     "red_fields": sum(explain.status(f["doubt"]) == "red" for f in fields),
                     "words": len(r["raw"].split()), "seconds": round(secs, 2), "text": r["text"],
                     "dropped": r["dropped"]})
        print(f"{pid} [{lang}] verified {n_ok} dropped {n_bad} lang={rows[-1]['detected_lang']} {secs:.1f}s", flush=True)

    s = lambda k: sum(r[k] for r in rows)  # noqa: E731
    quotes = s("quotes_verified") + s("quotes_dropped")
    res = {"system_extraction": MODEL_NAME.get(system, system),
           "generator": "mock" if a.mock else "Apertus 1.5 8B base (MLX, greedy, thinking disabled)",
           "n_pages": len(rows), "split": "dev",
           "citation_verbatim_rate": s("quotes_verified") / quotes if quotes else None,
           "quotes_total": quotes,
           "outputs_with_verified_quote": sum(r["quotes_verified"] > 0 for r in rows) / len(rows) if rows else None,
           "amounts_mentioned_share": s("amounts_mentioned") / s("amounts") if s("amounts") else None,
           "language_match_rate": sum(r["detected_lang"] == r["lang"] for r in rows) / len(rows) if rows else None,
           "mean_words": s("words") / len(rows) if rows else None,
           "mean_seconds": s("seconds") / len(rows) if rows else None,
           "rows": rows}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    assert detect_lang("Die Verrechnungssteuer wird zurückerstattet, wenn Sie die Erträge in der Steuererklärung "
                       "deklarieren.") == "de"
    assert detect_lang("Vous pouvez récupérer l'impôt anticipé si vous déclarez les rendements dans la déclaration.") == "fr"
    assert detect_lang("Il diritto al rimborso dell'imposta preventiva va riportato nella dichiarazione e nel modulo.") == "it"
    assert mentioned("Valeur fiscale de 23'806 CHF.", "23806") and not mentioned("Total 9.03", "9.30")
    main()
