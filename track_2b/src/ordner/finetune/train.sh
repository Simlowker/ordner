#!/usr/bin/env bash
# LoRA fine-tuning of Apertus on macstudio. Extra args override lora_config.yaml (e.g. --iters 10).
set -euo pipefail
cd "$(dirname "$0")/../../.."
export PYTHONPATH=src TOKENIZERS_PARALLELISM=false
PY=${PY:-../.venv/bin/python}
[ -n "${SKIP_PREPARE:-}" ] || $PY -m ordner.finetune.prepare
$PY -m ordner.finetune.train --config src/ordner/finetune/lora_config.yaml "$@"
