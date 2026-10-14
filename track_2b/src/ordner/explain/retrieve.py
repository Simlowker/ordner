"""EmbeddingGemma 2 retrieval over data/corpus/passages.jsonl (embeddings cached in work/explain/emb.npy).
Sanity check: python -m ordner.explain.retrieve"""
import hashlib
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from ordner.models import embed

PASSAGES = Path("data/corpus/passages.jsonl")
CACHE = Path("work/explain/emb.npy")


def load_passages(path=PASSAGES):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


@lru_cache(maxsize=1)
def index():
    ps = load_passages()
    docs = [f"title: {p['source_title']} | text: {p['text']}" for p in ps]  # EmbeddingGemma document format
    key = hashlib.sha256("\n".join(docs).encode()).hexdigest()
    key_file = CACHE.with_suffix(".key")
    if CACHE.exists() and key_file.exists() and key_file.read_text() == key:
        return ps, np.load(CACHE)
    emb = embed.embed(docs)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.save(CACHE, emb)
    key_file.write_text(key)
    return ps, emb


def top_k(query, lang=None, k=3):
    ps, emb = index()
    s = emb @ embed.embed([query], prompt_name="SearchQuery")[0]
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
