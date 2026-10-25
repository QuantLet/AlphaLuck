"""Word count of a manuscript's main text, without texcount.

texcount ships with a full TeX distribution and is not present on every
machine, so `make frl-words` used to fail silently depending on where it ran.
This does the same job in Python and makes the exclusions explicit, which
matters because every journal counts something slightly different.

Excluded: the preamble, the title block, the abstract, the highlights, keywords, every float
(so table and figure captions go with them), displayed maths, \\input of
tables, the bibliography, and the data-availability and declaration sections.
Comments are stripped.

Counted: one word per macro that expands to a number, because that is what a
reader sees on the page; otherwise ordinary whitespace-separated tokens with
control sequences removed.

    python paper/code/wordcount.py paper/frl/alphaluck_frl.tex
"""
from __future__ import annotations

import os
import re
import sys

# environments dropped whole, captions included
DROP_ENV = ["abstract", "table", "table*", "figure", "figure*", "tabular",
            "equation", "equation*", "align", "align*", "itemize",
            "thebibliography", "keyword", "highlights"]
# starred sections that are front or back matter rather than main text
DROP_SECTION = ["references", "data availability", "declaration",
                "acknowledg", "appendix", "highlights", "funding",
                "credit authorship"]


def strip(tex: str) -> str:
    tex = re.sub(r"(?<!\\)%.*", "", tex)                       # comments
    # An escaped dollar is a currency sign, not a maths delimiter. Protect it
    # first, or the inline-maths rule below pairs it with a real $ and eats
    # everything between them -- which silently removed a whole section.
    tex = tex.replace(r"\$", "\x00USD\x00")
    tex = tex.split(r"\begin{document}", 1)[-1]                # preamble
    tex = tex.split(r"\end{document}", 1)[0]

    for env in DROP_ENV:
        tex = re.sub(r"\\begin\{" + re.escape(env) + r"\}.*?\\end\{"
                     + re.escape(env) + r"\}", " ", tex, flags=re.S)

    # back-matter sections: from the heading to the next section or the end
    for name in DROP_SECTION:
        tex = re.sub(r"\\section\*?\{[^}]*" + name + r"[^}]*\}"
                     r"(?:(?!\\section).)*", " ", tex, flags=re.S | re.I)

    # title block: names, affiliations, e-mail (one level of nested braces)
    tex = re.sub(r"\\(title|author|address|ead|cortext|tnotetext)\s*"
                 r"(\[[^\]]*\])?\{(?:[^{}]|\{[^{}]*\})*\}", " ", tex)
    tex = re.sub(r"\\input\{[^}]*\}", " ", tex)                # table files
    tex = re.sub(r"\$\$.*?\$\$", " ", tex, flags=re.S)
    tex = re.sub(r"\\\[.*?\\\]", " ", tex, flags=re.S)
    tex = re.sub(r"\\(label|ref|cite[a-z]*|includegraphics|bibliography"
                 r"|bibliographystyle|quantlet)\s*(\[[^\]]*\])?\{[^}]*\}",
                 " x ", tex)                                   # count as 1
    # a number-valued macro is one word on the page
    tex = re.sub(r"\\al[A-Z][A-Za-z]*\s*(\{\})?", " 1 ", tex)
    tex = re.sub(r"\$[^$]*\$", " 1 ", tex)                     # inline maths
    tex = re.sub(r"\\[a-zA-Z@]+\*?", " ", tex)                 # other macros
    tex = re.sub(r"[{}~\\&]", " ", tex)
    return tex.replace("\x00USD\x00", " USD ")


def count(path: str) -> int:
    with open(path) as fh:
        body = strip(fh.read())
    return len([w for w in body.split() if re.search(r"[A-Za-z0-9]", w)])


def main() -> None:
    paths = sys.argv[1:] or [os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "frl", "alphaluck_frl.tex")]
    for p in paths:
        print(f"  {os.path.relpath(p):<34} {count(p):>6,} words "
              f"(main text; abstract, floats, captions, maths, tables and "
              f"back matter excluded)")


if __name__ == "__main__":
    main()
