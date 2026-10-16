# Ordner scenario benchmark (Swiss administrative procedures)

Self-made, frozen test split: 24 scored scenarios (fr/de/it, federal + VD/ZH/BE/GE/TI), each expected outcome with an official source (`data/scenarios/`). Every configuration ran once on the test; nothing was tuned on it. All rows are shown, including those where Ordner loses. Recomputed from `data/agent_runs/` by `ordner.eval.scenarios.run.aggregate`.

| Configuration | Prompt | Fully correct | Procedures found | Deadlines exact | Actions prepared | Missing info asked | Forbidden actions | Executed effects |
|---|---|---|---|---|---|---|---|---|
| Rules engine only (no model) | original | 54.2 % | 77.3 % | 65.0 % | 71.4 % | 0.0 % | 0 | 0 |
| Rules first, then Apertus 8B (process tools) | original | 58.3 % | 77.3 % | 65.0 % | 71.4 % | 50.0 % | 0 | 0 |
| Apertus 8B, process tools | original | 50.0 % | 68.2 % | 60.0 % | 50.0 % | 50.0 % | 0 | 0 |
| Apertus 8B, generic tools | original | 12.5 % | 27.3 % | 5.0 % | 14.3 % | 75.0 % | 0 | 0 |
| DeepSeek Harness runtime, Apertus 8B | original | 37.5 % | 68.2 % | 50.0 % | 50.0 % | 75.0 % | 0 | 0 |
| Apertus 8B, distilled coordinator | original | 41.7 % | 72.7 % | 55.0 % | 42.9 % | 100.0 % | 0 | 0 |
| Rules first, then Apertus 8B (process tools) | rule 4 | 54.2 % | 77.3 % | 65.0 % | 71.4 % | 0.0 % | 0 | 0 |
| Apertus 8B expert (oracle routing) | rule 4 | 20.8 % | 36.4 % | 25.0 % | 14.3 % | 25.0 % | 0 | 0 |
| Apertus 8B expert + tools-v1 LoRA | rule 4 | 29.2 % | 81.8 % | 60.0 % | 42.9 % | 0.0 % | 0 | 0 |
| Context: Claude Opus 5.5 expert (closed) | rule 4 | 79.2 % | 95.5 % | 100.0 % | 92.9 % | 25.0 % | 0 | 0 |

Other measured results: tax-statement field reading 98.0 % on 1,200 frozen test pages (`data/results/results.json`); per-expert knowledge bases 89.6 % vs one global base 81.2 % on 96 blind questions (`data/knowledge/results.json`); d1-3B expert routing 78.1 % of 201 requests (`data/routing/results.json`). Dev-only runs: `data/agent_runs/dev/`.

Reproduce a row (Apertus 1.5 8B served at `LLM_BASE_URL`): `PYTHONPATH=src python -m ordner.eval.scenarios.run --agent hybrid --toolset process --split test`; `make run` replays the rules baseline without GPU.
