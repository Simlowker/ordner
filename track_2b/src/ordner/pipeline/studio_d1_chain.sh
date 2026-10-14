#!/usr/bin/env bash
# macstudio, alongside studio_chain.sh: d1-3B routing of every page, then validation of extractions as they arrive.
set -u
cd "$(dirname "$0")/../../.."
export PYTHONPATH=src TOKENIZERS_PARALLELISM=false
PY=../.venv/bin/python
$PY -m ordner.pipeline.d1_batch --tag route
while :; do
  for t in apertus-base apertus-lora; do [ -f work/extract.$t.jsonl ] && $PY -m ordner.pipeline.d1_batch --tag $t; done
  [ -f work/EXTRACT_DONE ] && break
  sleep 300
done
for t in apertus-base apertus-lora; do $PY -m ordner.pipeline.d1_batch --tag $t; done
touch work/D1_DONE
