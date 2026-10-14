"""Docker entry point (`make run`): replay the evaluation, run the scenario baseline (rules only, no model), seed the
demo dossier (ORDNER_HOME, simulated date ORDNER_TODAY), then serve the console with the cockpit as home page.
Every step is best effort: a failing step is reported and the console is served anyway."""
import importlib.util
import subprocess
import sys

from ordner.app import cockpit, server

STEPS = [("replay of the evaluation from the recorded model outputs", ["ordner.eval.run"]),
         ("scenario baseline, rules only (CPU, no LLM)",
          ["ordner.eval.scenarios.run", "--agent", "rules_only", "--split", "all"])]


def has(module):
    try:
        return importlib.util.find_spec(module) is not None
    except ImportError:
        return False


def step(name, argv):
    if not has(argv[0]):
        return print(f"[ordner] {argv[0]} is not available: skipping the {name}.", flush=True)
    print(f"[ordner] {name}: python -m {' '.join(argv)}", flush=True)
    rc = subprocess.call([sys.executable, "-m", *argv])
    print(f"[ordner] {name}: " + (f"done, results in {server.DATA / 'results'}" if rc == 0 else
                                 f"failed (exit code {rc}), serving the console anyway"), flush=True)


def seed():
    try:
        s = cockpit.store()  # seeds the fictional persona into an empty dossier and reviews it (no model)
        cases = sum(len(s.cases(subject_id=x.id)) for x in s.subjects())
        print(f"[ordner] dossier {s.path}: {len(s.subjects())} subject(s), {cases} case(s), "
              f"date {cockpit.today_().isoformat()}{' (simulated)' if cockpit.SIMULATED else ''}", flush=True)
    except Exception as e:  # the console still serves the replay panels
        print(f"[ordner] demo dossier not seeded: {e!r}", flush=True)


if __name__ == "__main__":
    for name, argv in STEPS:
        step(name, argv)
    seed()
    server.main()
