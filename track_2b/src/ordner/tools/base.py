"""Shared bits of the tool families: error type, paths, lazy access to the parallel workstreams.

ctx keys read by the tools (all optional):
    mode          "replay" (default: cached model outputs, no model loaded) | "live" (loads local models)
    work          work directory with the replay caches (default track_2b/work)
    store         an ordner.case Store (default: Store() created once and kept in ctx)
    actor         "model" (default) | "user": who is calling; some writes are reserved to the user
    llm_url       OpenAI-compatible base URL for expert.run in live mode (e.g. http://127.0.0.1:8080/v1)
    llm_model     model name sent to that endpoint (default "apertus")
    apertus_mlx   True or an adapter path: run expert.run in-process with models/apertus_mlx.py
    expert_tags   replay tags for expert.run (default ["apertus-lora", "apertus-base"])
    today         ISO reference date of the scenario: ages, card validity, deadlines, reminders (default: today)
"""
import importlib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # track_2b/


class ToolError(Exception):
    """Expected failure, returned to the model as {"ok": false, "error": message}."""


def mode(ctx) -> str:
    return ctx.get("mode", "replay")


def today(ctx) -> date:
    try:
        return date.fromisoformat(ctx.get("today") or date.today().isoformat())
    except ValueError as e:
        raise ToolError(f"ctx today must be YYYY-MM-DD ({e})") from None


def work(ctx) -> Path:
    return Path(ctx.get("work") or ROOT / "work")


def need(module: str, owner: str):
    try:
        return importlib.import_module(module)
    except ImportError as e:
        raise ToolError(f"{module} ({owner}) is not available: {e}") from e


def store(ctx):
    if ctx.get("store") is None:
        case = need("ordner.case", "W1 case store")
        ctx["store"] = (getattr(case, "Store", None) or need("ordner.case.store", "W1 case store").Store)()
    return ctx["store"]
