"""Audit paper/references.bib against Crossref and arXiv.

The IJF repository's scripts/audit_bib.py is not present on this machine, so
this is a standalone equivalent. For each entry:

  * DOI entries are looked up at api.crossref.org and the title, year,
    container (journal), volume, pages and first author surname are compared
    with what the .bib claims;
  * arXiv entries are looked up at export.arxiv.org and the title and author
    list are compared;
  * URL-only entries (@misc with howpublished) are reachability-checked.

Comparison is deliberately lenient about formatting -- case, LaTeX braces,
accents and punctuation are normalised away -- and strict about substance: a
different year, volume, page range or surname is reported as a mismatch.

Requests are anonymous and rate-limited to one per second.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BIB = os.path.join(ROOT, "paper", "references.bib")
OUT = os.path.join(ROOT, "paper", "BIB_AUDIT.md")
UA = "AlphaLuck-bib-audit/1.0 (academic reference verification)"
# Crossref and arXiv are happy with the descriptive agent above; the two
# URL-only entries sit behind a CDN that rejects non-browser agents with 429,
# so reachability checks use a browser agent instead.
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
PAUSE = 1.0


def norm(s: str) -> str:
    """Normalise for comparison: strip HTML, LaTeX, accents, punctuation, case."""
    s = re.sub(r"<[^>]+>", " ", s or "")          # Crossref embeds <i> tags
    # alphabetic accent commands bind to the next letter: drop them without
    # inserting a space, or Gen\c{c}ay normalises to "gen cay"
    s = re.sub(r"\\[cvuHtdbkr](?=[{\s])", "", s)
    s = re.sub(r"\\[a-zA-Z]+", " ", s)            # \emph, \textbf, ...
    s = re.sub(r"\\[^a-zA-Z]", "", s)             # \" \' \`
    s = s.replace("{", "").replace("}", "").replace("$", "")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s.lower())
    return " ".join(s.split())


def parse_bib(path: str) -> list[dict]:
    """Brace-counting parser: robust to entries that close on the same line."""
    text = open(path).read()
    entries = []
    i = 0
    while True:
        at = text.find("@", i)
        if at < 0:
            break
        brace = text.find("{", at)
        if brace < 0:
            break
        kind = text[at + 1:brace].strip().lower()
        depth, j = 1, brace + 1
        while j < len(text) and depth:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        body = text[brace + 1:j - 1]
        i = j
        if kind in ("comment", "preamble", "string"):
            continue
        key, _, rest = body.partition(",")
        fields = {}
        for fm in re.finditer(r"(\w+)\s*=\s*\{", rest):
            name = fm.group(1).lower()
            d, k = 1, fm.end()
            while k < len(rest) and d:
                if rest[k] == "{":
                    d += 1
                elif rest[k] == "}":
                    d -= 1
                k += 1
            fields[name] = " ".join(rest[fm.end():k - 1].split())
        entries.append({"kind": kind, "key": key.strip(), **fields})
    return entries


def check_crossref(e: dict) -> list[str]:
    url = f"https://api.crossref.org/works/{e['doi']}"
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    if r.status_code == 404:
        return ["DOI not found at Crossref"]
    r.raise_for_status()
    msg = r.json()["message"]
    bad = []

    got_title = norm(" ".join(msg.get("title") or []))
    want_title = norm(e.get("title", ""))
    if want_title and got_title and want_title not in got_title and got_title not in want_title:
        bad.append(f"title: bib {e['title']!r} vs Crossref {' '.join(msg.get('title') or [])!r}")

    yr = (msg.get("issued", {}).get("date-parts") or [[None]])[0][0]
    if e.get("year") and yr and str(yr) != str(e["year"]):
        bad.append(f"year: bib {e['year']} vs Crossref {yr}")

    cont = norm(" ".join(msg.get("container-title") or []))
    if e.get("journal") and cont and norm(e["journal"]) not in cont and cont not in norm(e["journal"]):
        bad.append(f"journal: bib {e['journal']!r} vs Crossref "
                   f"{' '.join(msg.get('container-title') or [])!r}")

    for f, k in [("volume", "volume"), ("number", "issue")]:
        if e.get(f) and msg.get(k) and str(msg[k]) != str(e[f]):
            bad.append(f"{f}: bib {e[f]} vs Crossref {msg[k]}")

    if e.get("pages") and msg.get("page"):
        want = e["pages"].replace("--", "-")
        got = str(msg["page"])
        # Crossref frequently records only the first page; accept that when it
        # matches our start page, and compare in full otherwise
        if norm(want) != norm(got) and got.strip() != want.split("-")[0].strip():
            bad.append(f"pages: bib {e['pages']} vs Crossref {msg['page']}")

    authors = msg.get("author") or []
    if authors and e.get("author"):
        first_bib = norm(e["author"].split(" and ")[0].split(",")[0])
        surnames = [norm(a.get("family", "")) for a in authors]
        if first_bib and first_bib not in surnames:
            bad.append(f"first author: bib {first_bib!r} not among {surnames}")
    return bad


def check_arxiv(e: dict) -> list[str]:
    url = f"http://export.arxiv.org/api/query?id_list={e['eprint']}"
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(r.text)
    entry = root.find("a:entry", ns)
    if entry is None or entry.find("a:title", ns) is None:
        return [f"arXiv id {e['eprint']} returned no entry"]
    got_title = norm(entry.findtext("a:title", "", ns))
    want_title = norm(e.get("title", ""))
    bad = []
    if want_title and want_title not in got_title and got_title not in want_title:
        bad.append(f"title: bib {e['title']!r} vs arXiv "
                   f"{' '.join(entry.findtext('a:title', '', ns).split())!r}")
    pub = entry.findtext("a:published", "", ns)[:4]
    if e.get("year") and pub and pub != str(e["year"]):
        bad.append(f"year: bib {e['year']} vs arXiv {pub}")
    if e.get("author"):
        first_bib = norm(e["author"].split(" and ")[0].split(",")[0])
        names = [norm(a.findtext("a:name", "", ns).split()[-1])
                 for a in entry.findall("a:author", ns)]
        if first_bib and first_bib not in names:
            bad.append(f"first author: bib {first_bib!r} not among {names}")
    return bad


def check_url(e: dict) -> list[str]:
    m = re.search(r"\\url\{([^}]+)\}", e.get("howpublished", ""))
    if not m:
        # a book or report with no DOI, eprint or URL: nothing to verify
        # automatically, which is not the same as a mismatch
        return []
    delay = 2.0
    for attempt in range(4):
        try:
            r = requests.get(m.group(1), headers={"User-Agent": BROWSER_UA},
                             timeout=30, allow_redirects=True)
            if r.status_code < 400:
                return []
            if r.status_code in (429, 503):      # rate limited, back off
                time.sleep(delay)
                delay *= 2
                continue
            return [f"URL returned HTTP {r.status_code}"]
        except Exception as exc:
            time.sleep(delay)
            delay *= 2
            last = repr(exc)[:80]
    return ["UNCONFIRMED: no response after 4 attempts (rate limited or "
            "temporarily unreachable); this is not a claim that the reference "
            "is wrong"]


def main() -> None:
    entries = parse_bib(BIB)
    print(f"auditing {len(entries)} entries in paper/references.bib\n")
    rows = []
    for e in entries:
        if "doi" in e:
            src, probs = "Crossref", check_crossref(e)
        elif "eprint" in e:
            src, probs = "arXiv", check_arxiv(e)
        elif re.search(r"\\url\{", e.get("howpublished", "")):
            src, probs = "URL", check_url(e)
        else:
            src, probs = "not checkable", []
        time.sleep(PAUSE)
        status = ("OK" if not probs else "MISMATCH")
        if src == "not checkable":
            status = "MANUAL"
        rows.append({"key": e["key"], "source": src, "status": status,
                     "problems": probs})
        mark = "  " if status == "OK" else "!!"
        print(f"{mark} {e['key']:<24} {src:<9} {status}")
        for p in probs:
            print(f"       - {p}")

    nbad = sum(1 for r in rows if r["status"] == "MISMATCH")
    nman = sum(1 for r in rows if r["status"] == "MANUAL")
    lines = [
        "# Bibliography audit",
        "",
        f"`paper/references.bib`, {len(entries)} entries, checked against "
        "Crossref (DOI entries) and arXiv (eprint entries); URL-only entries "
        "are reachability-checked.",
        "",
        "The IJF repository's `scripts/audit_bib.py` is not present on this "
        "machine, so `paper/code/audit_bib.py` performs the equivalent check. "
        "Re-run it with `make bib`.",
        "",
        f"**Result: {len(entries) - nbad - nman} of {len(entries)} verified "
        f"automatically, {nbad} mismatch{'es' if nbad != 1 else ''}, {nman} "
        f"with no DOI, eprint or URL to check against (verify by hand).**",
        "",
        "| key | checked against | status | notes |",
        "|---|---|---|---|",
    ]
    for r in rows:
        note = "; ".join(r["problems"]).replace("|", "\\|") if r["problems"] else "--"
        lines.append(f"| `{r['key']}` | {r['source']} | {r['status']} | {note} |")
    with open(OUT, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"\n{len(entries) - nbad - nman}/{len(entries)} verified, {nman} manual; wrote "
          f"{os.path.relpath(OUT, ROOT)}")
    sys.exit(1 if nbad else 0)


if __name__ == "__main__":
    main()
