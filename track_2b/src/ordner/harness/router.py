"""Expert routing for the general preset « Ordner (général) » (web UI): which expert answers a conversation, read from
its first user message.

d1-3B (LiquidAI, ordner.models.d1) answers a native `choice` question over ROUTES; it runs as a small HTTP service on
the GPU host next to Apertus (bf16, ~6.5 GB; fp32 is 13 GB and exhausted the 36 GB once with Apertus bf16). The proxy
calls it at ORDNER_ROUTER_URL with a TIMEOUT; without it, or on any error, EmbeddingGemma 2 in process: cosine of the
message to the same descriptions, softmax at TEMP. Same rule for both: the top option, if it is an expert and p >= MIN_P;
otherwise None (stay general: coordinator, all process tools). TEMP and MIN_P were fixed by hand before any measurement
(ordner.eval.routing), not tuned on the scenarios.

    python -m ordner.harness.router --serve [--port 8091]       # POST /route {"text"} -> {"expert", "p", "by", "seconds"}
    python -m ordner.harness.router "J'ai reçu un commandement de payer"   # one query, d1 in process
"""
import argparse
import json
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

ROUTES = {   # keys = ordner.harness.experts.EXPERTS; English, with the official terms in fr/de/it
    "impots": "Swiss taxes: tax return, provisional tax instalments, objection to a tax assessment, withholding tax "
              "refund, pillar 3a contributions (impôts, déclaration d'impôt, acomptes, taxation, réclamation, impôt "
              "anticipé, 3e pilier / Steuern, Steuererklärung, Steuerrechnung, Einsprache, Verrechnungssteuer, Säule 3a / "
              "imposte, dichiarazione d'imposta, acconti, reclamo, imposta preventiva, terzo pilastro)",
    "lamal": "Compulsory health insurance: change of health insurer, deductible, premiums, premium reduction subsidy "
             "(assurance maladie, LAMal, caisse maladie, franchise, prime, subside / Krankenkasse, KVG, Franchise, "
             "Prämie, Prämienverbilligung / cassa malati, LAMal, franchigia, premio, riduzione dei premi)",
    "poursuites": "Debt collection: payment order received, opposition, debt enforcement office, deadlines "
                  "(poursuite, commandement de payer, opposition, office des poursuites / Betreibung, Zahlungsbefehl, "
                  "Rechtsvorschlag, Betreibungsamt / esecuzione, precetto esecutivo, opposizione, ufficio esecuzioni)",
    "logement": "Moving home and household: announce a move to the commune, change of address, household radio-TV fee "
                "Serafe (déménagement, annonce d'arrivée, contrôle des habitants, redevance radio-TV / Umzug, "
                "Anmeldung, Einwohnerkontrolle, Serafe, Haushaltabgabe / trasloco, notifica d'arrivo, canone radio-TV)",
    "coordinateur": "Any other administrative matter, several matters at once, or an overview of the whole dossier: "
                    "AVS/AHV contributions, unemployment, self-employment, deadlines across procedures",
}
QUESTION = "Which expert of a Swiss personal-administration assistant should answer this person's message?"
MIN_P = 0.5
TEMP = 0.03   # ponytail: fixed softmax temperature for cosines; calibrate on held-out questions if fallback matters
TIMEOUT = 15   # s; the first d1 call after start, or one sharing the GPU with Apertus, can take several seconds


def decide(p, by):
    best = max(p, key=p.get)
    return {"expert": best if best != "coordinateur" and p[best] >= MIN_P else None, "p": p, "by": by}


def d1_scores(text):
    """{route: probability} from d1-3B (loaded once, bfloat16)."""
    import torch

    from ordner.models import d1
    if d1._model is None:
        d1.load(dtype=torch.bfloat16)
    q = {"type": "choice", "instructions": QUESTION, "criteria": ROUTES}
    p = d1._model.system_one(text, {"expert": q})["answers"]["expert"]["probabilities"]
    return {k: round(float(v), 4) for k, v in p.items()}


def embed_scores(text):
    """{route: probability}: softmax(cosine / TEMP) with EmbeddingGemma 2 (route embeddings cached by explain.retrieve)."""
    import numpy as np

    from ordner.explain import retrieve
    s = retrieve.scores(text, [{"source_title": k, "text": v} for k, v in ROUTES.items()])
    e = np.exp((s - s.max()) / TEMP)
    return {k: round(float(v), 4) for k, v in zip(ROUTES, e / e.sum())}


def ask(text, url=None, fallback=True):
    """{"expert": id | None, "p", "by"}: the d1 service at url, else EmbeddingGemma in process (fallback), else general
    (by None)."""
    errors = []
    if url:
        try:
            req = urllib.request.Request(url.rstrip("/") + "/route", json.dumps({"text": text}).encode(),
                                         {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as f:
                return json.load(f)
        except Exception as e:
            errors.append(f"router: {type(e).__name__}: {e}")
    if not fallback:
        return {"expert": None, "p": {}, "by": None, "errors": errors}
    try:
        return decide(embed_scores(text), "EmbeddingGemma") | ({"errors": errors} if errors else {})
    except Exception as e:
        return {"expert": None, "p": {}, "by": None, "errors": errors + [f"EmbeddingGemma: {type(e).__name__}: {e}"]}


def serve(port):
    d1_scores("warm-up")

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                text = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))["text"]
                t = time.time()
                code, out = 200, decide(d1_scores(text), "d1-3B") | {"seconds": round(time.time() - t, 3)}
            except Exception as e:
                code, out = 500, {"error": f"{type(e).__name__}: {e}"}
            data = json.dumps(out, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt, *args):
            pass
    srv = HTTPServer(("127.0.0.1", port), H)   # single-threaded: one model, one MPS stream
    print(f"ordner router (d1-3B bf16) on http://127.0.0.1:{port}/route", flush=True)
    srv.serve_forever()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text", nargs="?")
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--port", type=int, default=8091)
    a = ap.parse_args(argv)
    if a.serve:
        return serve(a.port)
    print(json.dumps(decide(d1_scores(a.text), "d1-3B"), ensure_ascii=False))


if __name__ == "__main__":
    main()
