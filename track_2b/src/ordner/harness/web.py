"""Ordner's agentic conversation in the DeepSeek Harness web UI: one agent preset per expert (ordner.harness.experts).

    python -m ordner.harness.web [--port 8790] [--llm mock|openai] [--home DIR]

Seeds or opens the dossier ($ORDNER_HOME/ordner.db, same as the cockpit, simulated date ORDNER_TODAY), serves
ordner.harness.proxy in a thread (expert routing: tool subset and LoRA adapter from the marker of the expert's system
prompt) and runs `dsh --profile web` with web.patch.yml + the generated presets. --llm openai reads LLM_BASE_URL,
LLM_NAME, LLM_API_KEY; ORDNER_BACKEND=mlx (default) asks the server for the expert's adapter per request. Each expert
has one MCP process shared by all its sessions: one conversation per expert, restart to start from scratch.
Model requests are logged as JSON lines in $ORDNER_HOME/harness/proxy.log.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

from ordner.agent import coordinator as C
from ordner.agent.llm import OpenAICompat, parse_tool_calls, tool_text
from ordner.tools.registry import SPECS

from . import experts as E
from .proxy import Proxy
from .runtime import HARNESS, ROOT

HERE = Path(__file__).resolve().parent
PATCH = HERE / "web.patch.yml"
BIN = Path(os.environ.get("ORDNER_HARNESS_BIN", HARNESS / "apps/cli/lib/bin.js"))


class DemoLLM:
    """Stateless mock for UI tests: reads the dossier after each question, then answers (marked as simulated)."""

    def chat(self, messages, tools=None, extra=None):
        raw = (tool_text("case_load") if messages[-1]["role"] == "user" else
               "Réponse simulée (modèle factice) : j'ai lu votre dossier. Lancez avec --llm openai pour Apertus.")
        content, calls = parse_tool_calls(raw, {t["function"]["name"] for t in tools or []})
        return {"content": content, "tool_calls": calls, "raw": raw}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--llm", choices=("mock", "openai"), default="openai" if os.environ.get("LLM_BASE_URL") else "mock")
    ap.add_argument("--home", default=os.environ.get("ORDNER_HOME", "~/.ordner"))
    ap.add_argument("--max-steps", type=int, default=12)
    a = ap.parse_args(argv)
    if not BIN.is_file():
        sys.exit(f"DeepSeek Harness not found at {BIN} (set ORDNER_HARNESS_BIN)")
    home = Path(a.home).expanduser().resolve()
    os.environ["ORDNER_HOME"] = str(home)
    from ordner.app import cockpit   # same dossier and seeding (persona + periodic review) as the cockpit
    store = cockpit.store()
    subject = store.subjects()[0].id
    llm = DemoLLM() if a.llm == "mock" else OpenAICompat(os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8080/v1"),
                                                         os.environ.get("LLM_NAME") or "default",
                                                         os.environ.get("LLM_API_KEY") or None)
    order = [s.name.replace(".", "_") for s in SPECS] + [t["function"]["name"] for t in C.AGENT_TOOLS]
    allowed = sorted({t.replace(".", "_") for e in E.EXPERTS.values() for t in e.tools} | {"ask_user", "prepare_action"})
    state = home / "harness"
    (state / "workspace").mkdir(parents=True, exist_ok=True)
    proxy = Proxy(llm, max_steps=a.max_steps, order=order, allowed=allowed, experts=True,
                  log_file=state / "proxy.log")
    presets = state / "experts.patch.yml"
    presets.write_text(E.presets_yaml(proxy.adapters_ok), encoding="utf-8")
    env = {**os.environ, "DSH_HOME": str(state / "dsh-home"), "ORDNER_LOCAL_KEY": "local", "ORDNER_PROXY_URL": proxy.url,
           "ORDNER_PY": sys.executable, "ORDNER_SRC": str(ROOT / "src"), "ORDNER_SYSTEM": C.SYSTEM,
           "DSH_TELEMETRY_DISABLED": "1",
           **E.env_for(store.path, subject, os.environ.get("ORDNER_TODAY"), state)}
    cmd = ["node", str(BIN), "--profile", "web", "--patch", str(PATCH), "--patch", str(presets), "--no-open",
           "--port", str(a.port), "--host", "127.0.0.1"]
    print(f"[ordner] conversation: http://127.0.0.1:{a.port}/  (model: {a.llm} via {proxy.url}, dossier {store.path})\n"
          f"[ordner] Une conversation par expert ; relancer pour repartir de zéro.", flush=True)
    with proxy:
        return subprocess.call(cmd, cwd=state / "workspace", env=env)


if __name__ == "__main__":
    sys.exit(main())
