# Replay image for `make run`: no model weights, no GPU, no network at runtime.
# It re-runs the evaluation from the recorded model outputs in data/ and serves the demo console.
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src MPLBACKEND=Agg HOST=0.0.0.0 PORT=8000

RUN pip install --no-cache-dir numpy==2.4.6 scikit-learn==1.9.1 matplotlib==3.10.9

WORKDIR /app
RUN useradd --create-home --uid 1000 app
COPY src/ src/
COPY data/ data/
RUN mkdir -p data/results && chown app data/results
USER app

EXPOSE 8000
CMD ["python", "-m", "ordner.app"]
