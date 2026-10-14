.PHONY: run build eval demo live clean

IMAGE ?= ordner
PORT  ?= 8000
TTY   := $(shell [ -t 0 ] && echo -it)
# Optional model endpoint (see .env.example): passed through when set, never required by the replay.
DOCKER_ENV := $(if $(wildcard .env),--env-file .env,) -e LLM_NAME -e LLM_BASE_URL -e LLM_API_KEY
RESULTS    := -v "$(CURDIR)/data/results:/app/data/results"
LIVE_PY    := PYTHONPATH=src .venv/bin/python

# Judges: replay the evaluation from the recorded model outputs in data/ (no GPU, no weights, no network),
# write data/results/ (results.json, table.md, figures), then serve the console on http://localhost:$(PORT)
run: build
	docker run --rm --init $(TTY) -p $(PORT):8000 $(DOCKER_ENV) $(RESULTS) $(IMAGE)

build:
	@mkdir -p data/results && chmod 777 data/results
	docker build -t $(IMAGE) .

# Replay only (no server)
eval: build
	docker run --rm --init $(DOCKER_ENV) $(RESULTS) $(IMAGE) python -m ordner.eval.run

# Console only (no replay; shows whatever is already in data/results/)
demo: build
	docker run --rm --init $(TTY) -p $(PORT):8000 $(DOCKER_ENV) $(RESULTS) $(IMAGE) python -m ordner.app.server

# Host only, macOS on Apple Silicon: run the local models (MPS/MLX) through the project venv.
# Docker cannot use the Mac GPU, hence no container here. Outputs go to work/ (resumable); data/ is not touched.
# Setup and the remaining steps (d1-3B, hidden states, LoRA, export to data/): technical_report.md.
live:
	@[ "$$(uname -sm)" = "Darwin arm64" ] || { echo "make live needs macOS on Apple Silicon (Docker cannot use the Mac GPU). Use make run for the replay."; exit 1; }
	@[ -x .venv/bin/python ] || { echo "make live needs the project venv in .venv (see technical_report.md)."; exit 1; }
	@[ -f work/pages.jsonl ] || $(LIVE_PY) -m ordner.gen.build --out work/
	$(LIVE_PY) -m ordner.pipeline.ocr_batch --work work
	$(LIVE_PY) -m ordner.pipeline.extract_batch --tag apertus-base --work work
	@echo "make live: OCR and Apertus outputs are in work/. Next steps: see technical_report.md."

clean:
	rm -rf data/results
	-docker rmi $(IMAGE)
