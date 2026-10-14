"""Fill technical_report.md placeholders from the result files named in its own "Placeholders" table.

    PYTHONPATH=src .venv/bin/python -m ordner.eval.fill_report [--report technical_report.md] [--dry-run]

Each row gives a file, a JSON path (or `derived: <arithmetic over paths>`) and a format. Only rows whose file exists and
whose path resolves are filled; the others stay as {{placeholders}} and are listed."""
import argparse
import json
import re
from pathlib import Path

ROW = re.compile(r"^\| `\{\{(\w+)\}\}` \| `([^`]+)` \| `([^`]+)` \| ([^|]+) \|$")
PATH = re.compile(r'[A-Za-z_][\w ]*(?:\[[^\]]+\]|\.[A-Za-z_]\w*)+')


def to_python(expr):
    """`a["x"].b.c[0]` -> `r["a"]["x"]["b"]["c"][0]`, for every path in an expression."""
    def one(m):
        p = m.group(0)
        head, rest = re.match(r'([A-Za-z_]\w*)(.*)', p).groups()
        return 'r["' + head + '"]' + re.sub(r'\.([A-Za-z_]\w*)', r'["\1"]', rest)
    if re.fullmatch(r"\s*\w+\s*", expr):   # a top-level key
        return f'r["{expr.strip()}"]'
    return PATH.sub(one, expr.replace("×", "*"))


def fmt(v, kind):
    kind = kind.strip()
    if kind.startswith("true"):
        return "supported" if v else "not supported"
    if kind.startswith("%"):
        return f"{100 * v:.1f}"
    if kind.startswith("percentage points"):
        return f"{100 * v:+.1f}"
    if kind == "3 decimals, signed":
        return f"{v:+.3f}"
    if kind == "3 decimals":
        return f"{v:.3f}"
    if kind == "integer, thousands separator":
        return f"{int(round(v)):,}".replace(",", "'")
    if kind == "integer":
        return str(int(round(v)))
    if kind == "seconds, 1 decimal":
        return f"{v:.1f}"
    if kind == "seconds, integer":
        return str(int(round(v)))
    if kind == "text":
        return str(v)
    raise ValueError(f"unknown format {kind!r}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default="technical_report.md")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    text = Path(a.report).read_text(encoding="utf-8")
    cache, filled, left = {}, {}, []
    for line in text.splitlines():
        m = ROW.match(line.strip())
        if not m:
            continue
        name, file, path, kind = m.groups()
        try:
            r = cache.setdefault(file, json.loads(Path(file).read_text(encoding="utf-8")))
            expr = path[len("derived:"):] if path.startswith("derived:") else path
            filled[name] = fmt(eval(to_python(expr), {"r": r}), kind)   # paths come from our own report table
        except (OSError, KeyError, IndexError, TypeError, ValueError, SyntaxError, NameError) as e:
            left.append(f"{name}: {type(e).__name__} {e}")
    body, sep, table = text.partition("## Placeholders")
    for name, v in filled.items():
        body = body.replace("{{" + name + "}}", v)
    print(f"filled {len(filled)}, left {len(left)}")
    for x in left:
        print("  ", x)
    if not a.dry_run:
        Path(a.report).write_text(body + sep + table, encoding="utf-8")


if __name__ == "__main__":
    main()
