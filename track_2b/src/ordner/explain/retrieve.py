"""EmbeddingGemma 2 retrieval over data/corpus/passages.jsonl or any passage list (embeddings cached in work/explain/).
Sanity check: python -m ordner.explain.retrieve"""
import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path

import numpy as np

from ordner.models import embed

PASSAGES = Path("data/corpus/passages.jsonl")
CACHE = Path("work/explain/emb.npy")  # one file per passage set: emb-<sha>.npy


def load_passages(path=PASSAGES):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def doc_text(p):
    return f"title: {p['source_title']} | text: {p['text']}"  # EmbeddingGemma document format


@lru_cache(maxsize=4)
def _embed_docs(docs: tuple):
    path = CACHE.with_name(f"emb-{hashlib.sha256(chr(10).join(docs).encode()).hexdigest()[:16]}.npy")
    if path.exists():
        return np.load(path)
    emb = embed.embed(list(docs))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.npy")
    np.save(tmp, emb)
    os.replace(tmp, path)   # atomic: parallel processes never read a half-written cache
    return emb


def scores(query, ps):
    """Cosine similarity of the query to each passage of ps (any passage list: corpus, card quotes)."""
    return _embed_docs(tuple(map(doc_text, ps))) @ embed.embed([query], prompt_name="SearchQuery")[0]


def top_k(query, lang=None, k=3, ps=None):
    ps = ps or load_passages()
    s = scores(query, ps)
    idx = [i for i in np.argsort(-s) if lang is None or ps[i]["lang"] == lang][:k]
    return [{**ps[i], "score": round(float(s[i]), 4)} for i in idx]


SANITY = {
    "de": ["Wo deklariere ich die Rückerstattung der Verrechnungssteuer?",
           "Wohin gehört der Steuerwert meiner Wertschriften in der Steuererklärung?",
           "Bruttoertrag A mit Verrechnungssteuer und B ohne Verrechnungssteuer"],
    "fr": ["Où déclarer le remboursement de l'impôt anticipé ?",
           "Où reporter la valeur fiscale de mes titres dans la déclaration d'impôt ?",
           "rendement brut A soumis à l'impôt anticipé et rendement B sans impôt anticipé"],
    "it": ["Dove dichiaro il rimborso dell'imposta preventiva?",
           "Dove riporto il valore fiscale dei miei titoli nella dichiarazione d'imposta?",
           "reddito lordo A soggetto all'imposta preventiva e reddito B non soggetto"],
}

if __name__ == "__main__":
    for lang, queries in SANITY.items():
        for q in queries:
            print(f"\n[{lang}] {q}")
            for r in top_k(q, lang, 3):
                print(f"  {r['score']:.3f} {r['passage_id']}: {r['text'][:150]}")
