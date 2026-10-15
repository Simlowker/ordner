# Ordner: a sovereign Swiss paperwork assistant built on Apertus

**Team Meotis · Hack Apertus 2026 · Track 2B (Own Project)**

**Ordner is a local, sovereign assistant for Swiss paperwork: it knows which administrative procedures concern a person,
what is missing, what to do and why, and prepares everything; it never sends, files, signs or pays.**

**Ordner is a local mixture of domain experts on one open model, for Swiss federalism:** a small model (d1-3B) picks the
expert; each expert is Apertus 1.5 8B with its domain's tools, its own knowledge base of official sources (federal + the
person's canton), and its own LoRA adapter only where it measurably helps; the rules engine computes what is computable;
nothing is sent. It routes by domain and filters by canton, read from the dossier.

For example, a payment order and its notification date give the opposition deadline (debt-collection holidays
included) and a prepared opposition letter; a tax return gets the list of documents still missing; a move or a
health-insurance change, once its date and kind are known, gets its deadline and letters; every rule is shown with its
official source, quoted verbatim. Scope: 18 procedures, federal law + VD, ZH, BE, GE, TI, in fr/de/it; other cantons
get the federal procedures only; all dossiers are fictional.

Apertus 1.5 8B (bf16) is its only general-purpose language model; support models are loaded on demand. Tested
configuration: Apertus served on a Mac Studio M4 Max 36 GB, clients and UI on a second Mac (M4 Max 36 GB) over the local
network; nothing leaves the LAN at run time. Two claims are measured on frozen test splits (`PREREG.md`):

1. **Reading documents and flagging most errors.** A Swiss e-tax statement (eCH-0196) carries its own data in PDF417
   barcodes, a free and exact answer key. On 1,200 test pages (two of three layouts unseen in training), field exact
   match is 66.9 % for OCR + rules, 92.1 % for zero-shot Apertus, 98.0 % with LoRA. The best doubt signal is a free
   one, first-token entropy (AUROC 0.947); the hidden-state probe works (0.840) but the combination does not beat the
   best single signal (H2 not supported). Up to 75 of 754 zero-shot errors stay unflagged when 19.3 % of fields are
   re-read.
2. **Process tools make Apertus 8B a usable component, not a replacement for rules.** On 24 test scenarios, one tool
   per procedure instead of generic tools lifts exact deadlines from 1 to 12 of 20, obligations from 6 to 15 of 22 and
   passed scenarios from 3 to 12 (H6 supported), still below the rules engine alone (13). Rules first, then Apertus
   (defined after dev, exploratory) passes 14, not significantly more. Distillation did not help (H7 not supported).
   No run executed anything; on dev, one hybrid run prepared an action carrying a phishing e-mail's IBAN.
   After the freeze (exploratory), with a clarified prompt rule ("prepare the next step of every applicable
   procedure"), rules then Apertus passes 13, Apertus 8B alone 5, or 7 with a tool-use adapter (obligations found 8 →
   18 of 22, pass gain not significant); for context only, the closed Claude Opus 5.5 passes 19 in the same harness,
   the gap lying in preparing actions and recording deadlines. Rules first stays the reliable configuration.

Exploratory, after the freeze: **one knowledge base per expert.** 712 official passages (federal + VD, ZH, BE, GE, TI;
fr/de/it), each a verbatim substring of the fetched text; the 436 passages from official acts are in the repository. On
96 questions written blind before any retrieval run, the expert's own base puts a passage on the right topic in the top 3
for 89.6 %, one global base without routing for 81.2 % (McNemar 8–0, p = 0.008), BM25 for 81.2 %.

Details, test results and how to run everything: [`track_2b/README.md`](track_2b/README.md) ·
[technical report](track_2b/technical_report.md) · pre-registration [`track_2b/PREREG.md`](track_2b/PREREG.md).

## Run it

```bash
make run
```

Docker, from a clean checkout, **no GPU, no API key, no network at run time**: replays the document evaluation from
the recorded model outputs and hidden-state features, runs the scenario suite with the rules engine, seeds a fictional
demo dossier and serves the console on http://localhost:8000. If the optional conversation layer built (DeepSeek
Harness web UI under our MIT fork, npm package fetched at build time), it also serves the agentic conversation on
http://127.0.0.1:8790, with a scripted mock model unless `LLM_BASE_URL` points at Apertus. The live models (OCR,
Apertus, d1-3B, EmbeddingGemma 2) run on Apple Silicon outside Docker, which cannot use the Mac GPU: see
[`track_2b/README.md`](track_2b/README.md).

## Architecture

```
documents ─► READ: barcode first (eCH-0196, QR-bill: exact)
             otherwise LightOnOCR-3 ─► APERTUS 1.5 8B + LoRA ─► fields + rule checks
             doubt (evaluated batch pipeline): probe on Apertus hidden states + d1-3B judge + rule checks
               │ facts enter as "proposed"; only the person confirms them
               ▼
DOSSIER      local SQLite, append-only event log: documents · facts · cases · deadlines · prepared actions
               │
   1. RULES ENGINE (no model)                    2. APERTUS 1.5 8B (same dossier, ≤ 12 steps)
   18 procedure cards, 227 verbatim quotes       ROUTER d1-3B picks the expert (78.1 % of 201 requests)
   from 73 official sources: applicability,      EXPERT = Apertus + domain tools + its own knowledge base
   deadlines, completeness, prepared steps,        (federal + dossier canton, EmbeddingGemma 2) + LoRA only
   phishing and double-payment guards              if it beat the base on dev; coordinator = general expert
               └──────────────────┬─────────────────┘
                                  ▼
COCKPIT      what concerns me · what is missing · next step · why (quoted sources) ─► the person validates and acts
```

- **Apertus 1.5 8B** is the only general-purpose language model in the product: field extraction (LoRA), hidden states for the doubt
  probe, coordination over 16 registered tools (11 generic, 5 process tools), explanations.
- **Support models**, loaded on demand: LightOnOCR-3-1B (OCR), d1-3B (judge, expert routing), EmbeddingGemma 2
  (knowledge search over each expert's base; BM25 only as fallback).
- **DeepSeek Harness** is an optional agent runtime (MCP server + proxy) and the web conversation UI (our fork). As
  runtime it was not adopted under the pre-registered rule (test deadlines 10 vs 12 of 20).
- **Experts and routing** (exploratory): four domain experts (Impôts, Assurance maladie, Poursuites, Logement et
  ménage) are Apertus with domain tools and prompt; d1-3B routes the first request (78.1 % correct vs 64.7 % for
  EmbeddingGemma 2 on 201 requests). `knowledge.search` and the passages injected after the question use the expert's
  own knowledge base (`ordner.tools.expert_kb`, `track_2b/data/knowledge/`), filtered to federal + the dossier's canton.
  LoRA adapters are kept only where they beat the base on dev (Poursuites, Logement), opt-in
  (`ORDNER_USE_ADAPTERS=1`) and not shipped.
- **GLM-5.3 and DeepSeek V4.1 Flash** were used at development time only, through OpenRouter, as teachers on
  fictional synthetic scenarios, next to a deterministic process teacher (`ordner.distill.process`). **Claude Opus
  5.5** (closed) was run only as a frontier reference in the same harness (`ordner.distill.manual`); its trajectories
  never train Apertus. None is part of the product and no personal data was sent.

Target architecture: **air-gapped (b)** and **on-premise (a)**. External services at runtime: **none**.

## Repository

| Path                           | What                                                                                                                      |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------- |
| `track_2b/src/ordner/`         | the application: dossier, procedures, rules, tools, agent, connectors, console, pipelines                                 |
| `track_2b/data/`               | everything the replay needs (< 100 MB): recorded outputs, scenarios, demo dossier, expert knowledge bases (official acts) |
| `track_2b/docs/`               | architecture, DeepSeek Harness integration, model revisions                                                               |
| `track_2b/PREREG.md`           | pre-registered hypotheses, frozen before any test score                                                                   |
| `track_2b/technical_report.md` | technical report                                                                                                          |

Not legal or tax advice: Ordner informs and cites, the person decides. Code: Apache-2.0 · documentation: CC-BY-4.0 ·
data: CDLA-Permissive-2.0 (third-party components and licences: technical report).
