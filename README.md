# Ordner — a sovereign Swiss admin assistant built on Apertus

**Team Meotis · Hack Apertus 2026 · Track 2B (Own Project)**

Nobody teaches young adults how to do their taxes. Ordner reads the papers a person in Switzerland receives — starting
with the bank's electronic tax statement (eCH-0196) — extracts what has to be reported in the tax return, **says which
values it is not sure about**, and explains in German, French or Italian where each amount goes, quoting official
sources word for word. Everything runs **locally**: no document, no amount, no name ever leaves the machine.

- **Apertus 1.5 8B is the core**: it extracts the fields (fine-tuned with LoRA on a laptop), explains them, and its own
  hidden states are read by a probe that predicts when an extracted value is wrong.
- **Free, exact ground truth**: a Swiss e-tax statement carries its own data in PDF417 barcodes. We use them to evaluate
  every field and to fine-tune Apertus — no manual annotation, no closed model anywhere.
- **Doubt you can act on**: probe + calibrated judge (d1-3B) + rule checks → only doubtful fields go to a human.
- **Tested where it matters**: two page layouts never seen in training, phone-photo degradations, three languages,
  pre-registered hypotheses ([`track_2b/PREREG.md`](track_2b/PREREG.md)).

## Run it

```bash
make run
```

Docker, from a clean checkout, **no GPU, no network, no API key**: replays the recorded model outputs and hidden-state
features, re-trains the probe, recomputes every number of the report and serves the console on http://localhost:8000.
The full live pipeline (OCR → Apertus → probe → judge) runs on Apple Silicon with `make -C track_2b live`
(Docker cannot use the Mac GPU). Details: [`track_2b/README.md`](track_2b/README.md) and the
[technical report](track_2b/technical_report.md).

## Architecture

```
document ─► d1-3B router ─► LightOnOCR-3 ─► APERTUS 1.5 8B (LoRA) ─► rule checks
                                              │ hidden states ─► probe ┐
                                              └──────────────► d1-3B judge ┴─► doubt ─► human triage
                                                                                   └─► APERTUS explanation
                                                                                       (EmbeddingGemma 2 retrieval,
                                                                                        verbatim-checked citations)
```

Target architecture: **air-gapped (b)** and **on-premise (a)**. External services at runtime: **none**.

## Repository

| Path                            | What                                                                                   |
| ------------------------------- | -------------------------------------------------------------------------------------- |
| `track_2b/src/ordner/gen/`      | synthetic eCH-0196 statements, 3 layouts, degradations, barcode oracle                 |
| `track_2b/src/ordner/models/`   | local model wrappers (Apertus MLX/transformers, LightOnOCR-3, d1-3B, EmbeddingGemma 2) |
| `track_2b/src/ordner/finetune/` | LoRA data from the barcode oracle, mlx-lm training                                     |
| `track_2b/src/ordner/eval/`     | rules baseline, probe, metrics, replay (`make run`)                                    |
| `track_2b/src/ordner/explain/`  | grounded explanations over official sources                                            |
| `track_2b/src/ordner/app/`      | offline console                                                                        |
| `track_2b/data/`                | everything the replay needs (< 100 MB)                                                 |

Not tax advice: Ordner informs and cites, the person decides. Code: Apache-2.0 · documentation: CC-BY-4.0 ·
data: CDLA-Permissive-2.0 (see the technical report for third-party components and licences).
