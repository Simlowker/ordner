"""python -m ordner.procedures.verify [card_id ...]  (dev/audit tool, needs network on first run)

Fetches every card source (cached in work/procedures_sources/, not versioned), extracts its text and checks that each
quote marked verified=True appears word for word (Unicode NFKC, whitespace collapsed, soft hyphens joined).
Exit 1 if a verified quote is not found. `fetch(url)` returns the text path, for grepping while writing a card.
"""
import hashlib
import html.parser
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import pypdfium2

from .catalog import load_cards

WORK = Path(__file__).resolve().parents[3] / "work" / "procedures_sources"


SKIP = ("script", "style", "noscript", "authorialnote")  # authorialNote = Fedlex XML footnote, would split quotes
BLOCK = ("p", "div", "li", "br", "tr", "h1", "h2", "h3", "h4", "td", "th", "num", "heading", "paragraph", "article")


class _Text(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        self.skip += tag in SKIP
        if tag in BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        self.skip -= tag in SKIP and self.skip > 0

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).replace("\u00ad", "").replace("\ufffe", "")
    t = t.replace("\u2019", "'").replace("\u2018", "'").replace("\u2010", "-").replace("\u2011", "-")
    return " ".join(t.split())


def fetch(url: str) -> Path:
    key = hashlib.sha1(url.encode()).hexdigest()[:12]
    txt = WORK / f"{key}.txt"
    if txt.exists():
        return txt
    WORK.mkdir(parents=True, exist_ok=True)
    raw = WORK / "raw" / key
    raw.parent.mkdir(exist_ok=True)
    if not raw.exists():
        subprocess.run(["curl", "-sSLf", "--max-time", "60", "-A", "Mozilla/5.0", "-o", str(raw), url], check=True)
    data = raw.read_bytes()
    if data[:5] == b"%PDF-":
        pdf = pypdfium2.PdfDocument(str(raw))
        text = "\n\n".join(f"[page {i + 1}]\n" + p.get_textpage().get_text_range() for i, p in enumerate(pdf))
    else:
        doc = data.decode("utf-8", errors="replace")
        if doc.lstrip().startswith("<?xml"):  # Akoma Ntoso <title> is a container, not HTML's RCDATA <title>
            doc = re.sub(r"<(/?)title\b", r"<\1akn-title", doc)
        p = _Text()
        p.feed(doc)
        text = "".join(p.parts)
    txt.write_text(f"URL: {url}\n\n{text}", encoding="utf-8")
    return txt


def check(cards) -> list[str]:
    problems = []
    for card in cards:
        for i, s in enumerate(card.sources):
            if not s.quote:
                continue
            try:
                found = norm(s.quote) in norm(fetch(s.url).read_text(encoding="utf-8"))
            except subprocess.CalledProcessError as e:
                found = None
                problems.append(f"{card.id} sources[{i}] fetch failed ({e.returncode}): {s.url}")
            status = {True: "ok", False: "NOT FOUND", None: "unreachable"}[found]
            print(f"{status:11} {'V' if s.verified else '-'} {card.id} [{i}] {s.url}")
            if s.verified and found is False:
                problems.append(f"{card.id} sources[{i}] verified but quote not found: {s.quote[:60]!r}")
    return problems


if __name__ == "__main__":
    wanted = set(sys.argv[1:])
    problems = check([c for c in load_cards() if not wanted or c.id in wanted])
    print("\n".join(problems) or "all verified quotes found")
    sys.exit(1 if any("not found" in p for p in problems) else 0)
