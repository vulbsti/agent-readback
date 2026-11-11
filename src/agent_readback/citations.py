"""Parse and check [E12] / [H3, E4-E7] citations in an explanation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

CITE_RE = re.compile(r"\[((?:[EH]\d+)(?:\s*(?:,|-|–|\.\.)\s*[EH]?\d+)*)\]")
ID_RE = re.compile(r"([EH])(\d+)")


def expand(group: str) -> list[str]:
    """'E3-E5, H2' -> ['E3', 'E4', 'E5', 'H2']"""
    out: list[str] = []
    for part in re.split(r"\s*,\s*", group):
        m = re.match(r"([EH])(\d+)\s*(?:-|–|\.\.)\s*([EH])?(\d+)$", part)
        if m:
            kind, a, b = m.group(1), int(m.group(2)), int(m.group(4))
            if b >= a and b - a <= 200:
                out += [f"{kind}{i}" for i in range(a, b + 1)]
                continue
        out += [k + n for k, n in ID_RE.findall(part)]
    return out


@dataclass
class Check:
    cited: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    uncited_lines: list[str] = field(default_factory=list)
    factual_lines: int = 0

    @property
    def coverage(self) -> float:
        return 1.0 if not self.factual_lines else 1 - len(self.uncited_lines) / self.factual_lines

    @property
    def ok(self) -> bool:
        return not self.unknown and self.coverage >= 0.9


def _is_factual(line: str) -> bool:
    s = line.strip()
    if not s or s.startswith(("```", "#", "|---", "flowchart", "graph ", "%%")):
        return False
    if re.match(r"^(?:[-*+]|\d+[.)])\s", s):  # list items always state something
        return True
    bare = re.sub(r"[*_`]", "", s).strip(" -:")
    # section labels such as "**Changed**" or "Risks:"
    if len(bare.split()) <= 3 and not CITE_RE.search(s):
        return False
    return True


def check(text: str, valid_ids: set[str]) -> Check:
    c = Check()
    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        groups = CITE_RE.findall(line)
        ids = [i for g in groups for i in expand(g)]
        c.cited += ids
        c.unknown += [i for i in ids if i not in valid_ids]
        if _is_factual(line):
            c.factual_lines += 1
            if not any(i in valid_ids for i in ids):  # a line citing only unknown ids is uncited
                c.uncited_lines.append(line.strip())
    c.unknown = sorted(set(c.unknown), key=lambda x: (x[0], int(x[1:])))
    return c


def strip_unknown(text: str, valid_ids: set[str]) -> str:
    """Drop citations to ids that do not exist (keeps valid ones in the same bracket)."""

    def fix(m: re.Match) -> str:
        ids = [i for i in expand(m.group(1)) if i in valid_ids]
        return f"[{', '.join(ids)}]" if ids else ""

    return CITE_RE.sub(fix, text)
