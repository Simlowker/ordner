"""Docker entry point (`make run`): replay the evaluation if available, then serve the console."""
import importlib.util
import subprocess
import sys

from ordner.app import server


def has_eval():
    try:
        return importlib.util.find_spec("ordner.eval.run") is not None
    except ImportError:
        return False


if __name__ == "__main__":
    if not has_eval():
        print("[ordner] ordner.eval.run is not available yet: skipping the replay, serving the console only.", flush=True)
    elif rc := subprocess.call([sys.executable, "-m", "ordner.eval.run"]):
        print(f"[ordner] replay failed (exit code {rc}): serving the console anyway; "
              "the triage panel shows whatever is in data/results/.", flush=True)
    else:
        print(f"[ordner] replay done: results in {server.DATA / 'results'}", flush=True)
    server.main()
