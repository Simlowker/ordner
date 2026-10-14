# Replay image for `make run`: no model weights, no GPU, no network at runtime.
# It re-runs the evaluation from the recorded model outputs in data/, runs the scenario baseline (rules only), seeds the
# fictional demo dossier in a throw-away ORDNER_HOME at a simulated date, and serves the console (cockpit first).
# Node for the optional conversation layer (DeepSeek Harness web UI, Node >= 22.19): copied, not installed.
FROM node:22-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392 AS node

FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src MPLBACKEND=Agg HOST=0.0.0.0 PORT=8000 \
    ORDNER_HOME=/tmp/ordner ORDNER_TODAY=2026-02-20

RUN pip install --no-cache-dir numpy==2.4.6 scikit-learn==1.9.1 matplotlib==3.10.9

# Optional conversation layer: the published harness (npm, network at build time only) under Ordner's brand fork
# (harness_fork/, MIT). If any step fails the layer is removed and the image serves the cockpit alone. The LibreOffice
# wasm kit (150 MB, MPL-2.0) is dropped: its only user, the office-to-pdf row, is disabled in web.patch.yml.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
COPY harness_fork/ /opt/harness_fork/
ENV DSH_TELEMETRY_DISABLED=1 ORDNER_HARNESS_BIN=/usr/local/lib/node_modules/@deepseek-ai/dsh/lib/bin.js
RUN ( node /usr/local/lib/node_modules/npm/bin/npm-cli.js i -g --no-audit --no-fund @deepseek-ai/dsh@0.2.1-alpha.2 \
      && bash /opt/harness_fork/apply.sh --installed /usr/local/lib/node_modules \
      && node "$ORDNER_HARNESS_BIN" --version \
      && rm -rf /usr/local/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/libreoffice-kit-wasm ) \
    || { echo "harness layer skipped"; rm -rf /usr/local/lib/node_modules/@deepseek-ai; } ; \
    rm -rf /root/.npm /usr/local/lib/node_modules/npm

WORKDIR /app
RUN useradd --create-home --uid 1000 app
COPY src/ src/
COPY data/ data/
RUN mkdir -p data/results && chown app data/results
USER app

EXPOSE 8000 8790
# Cockpit on 8000 (always). With the harness layer: seed the dossier first (both servers share it), then serve the
# conversation on 8790 in the background; dsh refuses wildcard binds, so it binds the container address and admits the
# host's authority. A failing conversation layer never stops the cockpit.
CMD ["sh", "-c", "if [ -f \"$ORDNER_HARNESS_BIN\" ] && python -c 'from ordner.app import cockpit; cockpit.store()'; then (python -m ordner.harness.web --port 8790 --host \"$(hostname -i | cut -d' ' -f1)\" --trusted-host 127.0.0.1:8790 --trusted-host localhost:8790 --public-url http://127.0.0.1:8790/ || echo '[ordner] conversation layer stopped; the cockpit keeps running') & fi; exec python -m ordner.app"]
