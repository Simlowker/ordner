# Ordner: a sovereign Swiss paperwork assistant built on Apertus

**Team Meotis · Hack Apertus 2026 · Track 2B (Own Project)**

**Ordner is a local, sovereign assistant for Swiss paperwork: it knows which administrative procedures concern a person,
what is missing, what to do and why, and prepares everything; it never sends, files, signs or pays.**

Everything runs on the person's own machine: one Apple Silicon Mac with 36 GB, Apertus 1.5 8B in bf16, support models
loaded on demand, no network at runtime. Two claims are measured:

1. **Reading documents without silent errors.** A Swiss e-tax statement (eCH-0196) carries its own data in PDF417
   barcodes, a free and exact answer key. Apertus extracts the fields from the human-readable page (LoRA fine-tune);
   a probe on its hidden states, the d1-3B judge and rule checks flag the values to re-check. Pre-registered, tested on
   1,200 pages including two layouts never seen in training.
2. **Tools and architecture make an 8B model useful as a coordinator.** On 43 dev scenarios, Apertus alone passes
   14.0 % with generic tools and 27.9-30.2 % with process tools, below a deterministic rules engine (46.5 %); rules
   first, then Apertus on the same dossier passes 53.5 %, adding the questions rules cannot ask (dev split; the gain
   over rules alone is within run-to-run noise; test results in the report). No configuration executed anything.

Details, dev results and how to run everything: [`track_2b/README.md`](track_2b/README.md) ·
[technical report](track_2b/technical_report.md) · pre-registration [`track_2b/PREREG.md`](track_2b/PREREG.md).

## Run it

```bash
make run
```

Docker, from a clean checkout, **no GPU, no network, no API key**: replays the document evaluation from the recorded
model outputs and hidden-state features, runs the scenario suite with the rules engine, seeds a fictional demo dossier
and serves the console on http://localhost:8000. The live models (OCR, Apertus, d1-3B, EmbeddingGemma 2) run on Apple
Silicon outside Docker, which cannot use the Mac GPU: see [`track_2b/README.md`](track_2b/README.md).

## Architecture

```
documents ─► READ: barcode first (eCH-0196, QR-bill: exact)
             otherwise LightOnOCR-3 ─► APERTUS 1.5 8B + LoRA ─► fields + rule checks
             doubt (evaluated batch pipeline): probe on Apertus hidden states + d1-3B judge + rule checks
               │ facts enter as "proposed"; only the person confirms them
               ▼
DOSSIER      local SQLite, append-only event log: documents · facts · cases · deadlines · prepared actions
               │
   1. RULES ENGINE (no model)                    2. APERTUS COORDINATOR (same dossier, ≤ 12 steps)
   18 procedure cards, 227 official sources      free text, missing information, questions to the
   quoted verbatim: applicability, deadlines,    person, explanations in fr/de/it; process toolset
   completeness, prepared steps, phishing and    (9 tools) + ask_user + prepare_action; knowledge
   double-payment guards                         search with EmbeddingGemma 2
               └──────────────────┬─────────────────┘
                                  ▼
COCKPIT      what concerns me · what is missing · next step · why (quoted sources) ─► the person validates and acts
```

- **Apertus 1.5 8B** is the only general-purpose language model in the product: field extraction (LoRA), hidden states for the doubt
  probe, coordination over 16 registered tools (11 generic, 5 process tools), explanations.
- **Support models**, loaded on demand: LightOnOCR-3-1B (OCR), d1-3B (judge), EmbeddingGemma 2 (knowledge search;
  BM25 only as fallback).
- **DeepSeek Harness** is integrated as an alternative agent runtime (MCP server + proxy) with measured parity; it is
  not the default.
- **GLM-5.3** was used at development time only, through OpenRouter, as a distillation teacher on fictional synthetic
  scenarios. It is not part of the product and no personal data was sent.

Target architecture: **air-gapped (b)** and **on-premise (a)**. External services at runtime: **none**.

## Repository

| Path                           | What                                                                                      |
| ------------------------------ | ----------------------------------------------------------------------------------------- |
| `track_2b/src/ordner/`         | the application: dossier, procedures, rules, tools, agent, connectors, console, pipelines |
| `track_2b/data/`               | everything the replay needs (< 100 MB): recorded outputs, scenarios, demo dossier         |
| `track_2b/docs/`               | architecture, DeepSeek Harness integration, model revisions                               |
| `track_2b/PREREG.md`           | pre-registered hypotheses, frozen before any test score                                   |
| `track_2b/technical_report.md` | technical report                                                                          |

Not legal or tax advice: Ordner informs and cites, the person decides. Code: Apache-2.0 · documentation: CC-BY-4.0 ·
data: CDLA-Permissive-2.0 (third-party components and licences: technical report).
