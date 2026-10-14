"""Tool registry shown to Apertus: SPECS, call(name, args, ctx), openai_tools(). ctx keys: see ordner.tools.base.

Every call returns {"ok", "data", "warnings", "provenance"} (+ "error" when ok is false), as plain JSON. No tool sends,
files, signs or pays anything: writes go to the local dossier only, actions are prepared by the coordinator.
"""
import json
import time
from dataclasses import asdict, is_dataclass

from ordner.core.schema import now

from . import case, decision, document, expert, knowledge, rules
from .base import ToolError, mode

_TOOLS = {spec.name: (spec, fn) for family in (document, knowledge, decision, expert, rules, case)
          for spec, fn in family.TOOLS}
SPECS = [spec for spec, _ in _TOOLS.values()]
_ALIASES = {name.replace(".", "_"): name for name in _TOOLS}  # OpenAI function names allow no dots
_TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list, "object": dict}


def _type_ok(value, t):
    if isinstance(t, list):
        return any(_type_ok(value, x) for x in t)
    if t == "null":
        return value is None
    return t not in _TYPES or (isinstance(value, _TYPES[t]) and not (t in ("integer", "number") and isinstance(value, bool)))


def check_args(schema, args, where="") -> list[str]:
    """Errors of args against the subset of JSON schema used in SPECS (type, enum, required, properties, items)."""
    if not isinstance(args, dict):
        return [f"{where or 'arguments'} must be an object"]
    errors = [f"missing {where}{k}" for k in schema.get("required", []) if args.get(k) in (None, "")]
    for k, v in args.items():
        p = schema.get("properties", {}).get(k)
        if p is None:
            errors.append(f"unknown argument {where}{k}; allowed: {', '.join(schema.get('properties', {}))}")
        elif "type" in p and not _type_ok(v, p["type"]):
            errors.append(f"{where}{k} must be {p['type']}")
        elif "enum" in p and v not in p["enum"]:
            errors.append(f"{where}{k} must be one of {p['enum']}")
        elif p.get("type") == "array" and "items" in p:
            for i, item in enumerate(v):
                if not _type_ok(item, p["items"].get("type")):
                    errors.append(f"{where}{k}[{i}] must be {p['items']['type']}")
                elif p["items"].get("type") == "object":
                    errors += check_args(p["items"], item, f"{where}{k}[{i}].")
    return errors


def _plain(o):
    return asdict(o) if is_dataclass(o) else str(o)


def call(name: str, args: dict, ctx: dict | None = None) -> dict:
    ctx = {} if ctx is None else ctx
    name = _ALIASES.get(name, name)
    prov = {"tool": name, "mode": mode(ctx), "at": now()}
    t = time.perf_counter()
    try:
        if name not in _TOOLS:
            raise ToolError(f"unknown tool {name}; available: {', '.join(_TOOLS)}")
        spec, fn = _TOOLS[name]
        args = dict(args or {})
        if ctx.get("subject_id") and "subject_id" in spec.input_schema["properties"]:
            args["subject_id"] = ctx["subject_id"]  # one session = one dossier, whatever the model wrote
        if errors := check_args(spec.input_schema, args):
            raise ToolError("invalid arguments: " + "; ".join(errors))
        data, warnings, extra = fn(args, ctx)
        out = {"ok": True, "data": data, "warnings": list(warnings), "provenance": {**prov, **extra}}
    except ToolError as e:
        out = {"ok": False, "data": None, "error": str(e), "warnings": [], "provenance": prov}
    except Exception as e:  # a tool failure is an answer for the model, never a crash of the loop
        out = {"ok": False, "data": None, "error": f"{type(e).__name__}: {e}", "warnings": [], "provenance": prov}
    out["provenance"]["ms"] = round((time.perf_counter() - t) * 1000)
    return json.loads(json.dumps(out, ensure_ascii=False, default=_plain))


def openai_tools() -> list[dict]:
    return [{"type": "function", "function": {"name": s.name.replace(".", "_"), "description": s.description,
                                              "parameters": s.input_schema}} for s in SPECS]
