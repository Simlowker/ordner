"""Ordner's experts: Apertus 1.5 8B + a domain LoRA adapter + the domain's Ordner tools. One harness agent preset each.

The expert of a request is read from the first line of its system prompt (`[ordner-expert: <id>]`): the harness has no
model per preset, so ordner.harness.proxy routes on this marker (tool subset, adapter). Tool names are the registry's
(ordner.tools.registry.SPECS); the MCP server of each preset exposes only its expert's tools (`--tools`) and writes its
own state file (`--out state-<id>.json`).
"""
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from ordner.agent import coordinator as C
from ordner.tools import processes as P
from ordner.tools.registry import SPECS

ROOT = Path(__file__).resolve().parents[3]   # track_2b/
ADAPTERS = Path(os.environ.get("ORDNER_ADAPTERS", ROOT / "work" / "adapters"))
BASE_TOOLS = ("case.load", "case.record", "piece.recevoir", "knowledge.search", "rules.evaluate", "document.read")
MARK = re.compile(r"^\[ordner-expert: ([a-z_]+)\]")


@dataclass(frozen=True)
class Expert:
    id: str
    name: str
    description: str
    cards: tuple   # procedure card id prefixes covered ("*" = all)
    tools: tuple   # registry tool names
    adapter: str | None   # directory name under ADAPTERS
    order: int
    domain: str = ""


EXPERTS = {e.id: e for e in [
    Expert("coordinateur", "Ordner", "Vue d'ensemble du dossier, toutes les démarches", ("*",),
           tuple(s.name for s in SPECS if P.in_toolset(s.name, "process")), "coordinator-distill-v1", 1,
           "You see the whole dossier and every procedure."),
    Expert("impots", "Impôts", "Déclaration, acomptes, réclamation, impôt anticipé, 3e pilier",
           ("tax.", "pension.pillar3a."),
           BASE_TOOLS + ("impots.preparer_declaration", "document.decode", "expert.run"), "expert-impots-v1", 2,
           "You handle Swiss tax procedures only: tax return, instalments, objections, withholding tax refund, "
           "pillar 3a."),
    Expert("lamal", "Assurance maladie", "Changer de caisse, franchise, subsides", ("health_insurance.",),
           BASE_TOOLS + ("lamal.revoir_franchise",), "expert-lamal-v1", 3,
           "You handle compulsory health insurance only (LAMal/KVG)."),
    Expert("poursuites", "Poursuites", "Commandement de payer, opposition, délais", ("debt.",),
           BASE_TOOLS + ("poursuite.repondre",), "expert-poursuites-v1", 4, "You handle debt collection (LP/SchKG) only."),
    Expert("logement", "Logement et ménage", "Déménagement, annonce à la commune, redevance Serafe",
           ("housing.", "household."), BASE_TOOLS + ("demenagement.annoncer",), "expert-logement-v1", 5,
           "You handle moving (registration at the commune) and the household radio-TV fee (Serafe) only."),
]}


def marker(system_text):
    m = MARK.match(system_text or "")
    return m.group(1) if m and m.group(1) in EXPERTS else None


def system_prompt(expert_id):
    e = EXPERTS[expert_id]
    return f"[ordner-expert: {e.id}]\n{C.SYSTEM}\n\nExpert scope: {e.domain}"


def adapter_path(expert_id):
    """The adapter directory as the MLX server sees it, if it exists locally, else None (base model).
    ORDNER_ADAPTERS_SERVER: the same directory on a remote server (e.g. the Mac Studio behind an SSH tunnel)."""
    e = EXPERTS.get(expert_id)
    p = ADAPTERS / e.adapter if e and e.adapter else None
    if not (p and (p / "adapters.safetensors").exists()):
        return None
    server = os.environ.get("ORDNER_ADAPTERS_SERVER")
    return str(Path(server) / e.adapter) if server else str(p)


def model_label(expert_id, adapters_ok=True):
    path = adapter_path(expert_id) if adapters_ok else None
    return f"Apertus 1.5 8B + adaptateur {Path(path).name}" if path else "Apertus 1.5 8B (adaptateur non disponible)"


def _env(kind, e):
    return f"ORDNER_{kind}_{e.id.upper()}"


def _plugins(e, indent):
    pad = " " * indent
    return "\n".join(pad + line for line in f"""plugins:
  - id: persona
    name: '@deepseek-ai/dsh-persona'
    config:
      prefix: !!js process.env.{_env("SYSTEM", e)} # starts with the [ordner-expert: {e.id}] marker
      complete: true # only the prefix becomes the system prompt
      includeRuntimeContext: false
  - id: mcp-ordner
    name: '@deepseek-ai/dsh-mcp-client'
    config:
      serverName: ordner
      transport: stdio
      command: !!js process.env.ORDNER_PY
      args: !!js JSON.parse(process.env.{_env("MCP_ARGS", e)}) # --tools <expert's tools> --out state-{e.id}.json
      env:
        PYTHONPATH: !!js process.env.ORDNER_SRC
      failOnStartupError: true
      toolCallTimeoutMs: 600000
      reconnect:
        enabled: false""".splitlines())


def _config(e, adapters_ok, indent):
    pad, q = " " * indent, lambda s: json.dumps(s, ensure_ascii=False)
    cid = "standard" if e.id == "coordinateur" else e.id   # Settings > presets expects 'standard' as the default
    desc = f"{e.description} · {model_label(e.id, adapters_ok)}"
    return (f"{pad}id: {cid}\n{pad}name: {q(e.name)}\n{pad}description: {q(desc)}\n{pad}order: {e.order}\n"
            f"{_plugins(e, indent)}")


def presets_yaml(adapters_ok=True):
    """Harness overlay: the default preset becomes the coordinator, one inserted preset per other expert."""
    head = "# Generated by ordner.harness.experts: one agent preset per Ordner expert.\n"
    coord = EXPERTS["coordinateur"]
    out = head + f"- id: preset-standard\n  config:\n{_config(coord, adapters_ok, 4)}\n\n- insert:\n"
    for e in sorted(EXPERTS.values(), key=lambda x: x.order):
        if e is not coord:
            out += (f"    - id: preset-{e.id}\n      name: '@deepseek-ai/dsh-agent-preset'\n      config:\n"
                    f"{_config(e, adapters_ok, 8)}\n")
    return out


def env_for(db, subject, today, state_dir, mode="replay"):
    """Environment read by presets_yaml(): each expert's system prompt and MCP server arguments."""
    env = {}
    for e in EXPERTS.values():
        args = ["-m", "ordner.harness.mcp_server", "--db", str(db), "--subject", subject, "--goal",
                f"conversation ({e.name})", "--out", str(Path(state_dir) / f"state-{e.id}.json"), "--mode", mode,
                "--tools", ",".join(e.tools)]
        env[_env("SYSTEM", e)] = system_prompt(e.id)
        env[_env("MCP_ARGS", e)] = json.dumps(args + (["--today", today] if today else []))
    return env
