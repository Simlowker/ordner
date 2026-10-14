#!/usr/bin/env bash
# macstudio: finish base extraction once all OCR has arrived, then LoRA extraction on dev+test.
set -u
cd "$(dirname "$0")/../../.."
export PYTHONPATH=src TOKENIZERS_PARALLELISM=false
PY=../.venv/bin/python
while pgrep -f "extract_batch --tag apertus-base" >/dev/null; do sleep 30; done
until [ -f work/OCR_ALL_DONE ]; do sleep 30; done
$PY -m ordner.pipeline.extract_batch --tag apertus-base >> work/extract.apertus-base.log 2>&1
$PY -m ordner.pipeline.extract_batch --tag apertus-lora --adapter work/adapters/lora-v1 --splits dev,test > work/extract.apertus-lora.log 2>&1
touch work/EXTRACT_DONE
