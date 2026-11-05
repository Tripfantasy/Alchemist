"""Mouse lines: a registry built from a lab's colony lists, and a strict path matcher.

Folder names on a lab collection routinely carry the genotype of the animals
("20230405_SstCre_Ai14_DTA_cortex"). Read against the lab's own colony
list, those tokens say which lines a dataset used, what each line is (a Cre
driver, a reporter, a calcium indicator ...), which gene it targets, and whether
the lab still keeps it.

Two jobs:

  build   colony CSV(s) -> resources/mouse_lines.json (gitignored: a site's
          colony is its own business). Column names are recognised by keyword,
          so most colony spreadsheets work unchanged. Columns naming people
          (responsible member, owner, contact) and free-text notes are never
          read.
  probe   count which lines the paths in an inventory mention, with an example
          path each, so a new registry's precision is checked BEFORE indexing.

Matching is deliberately strict. A colony name is matched only as a whole
allele: separators are optional ("Sst-Cre" = "SstCre" = "sst_cre"), but the
match must start at a token boundary, and names too short to be specific are
refused outright. On a real collection bare "E9"/"E12" are embryonic days far
more often than lines, and a gene symbol alone ("Sox10") is usually an
antibody stain, so neither is ever matched without its allele suffix
("Sox10-CreER", "Pvalb-Cre").

Site additions (extra spellings, extra refusals) go in a JSON passed with
--extra: {"aliases": {"R26R-tdT": ["RtdT"]}, "refuse": ["tet2"]}.

Usage
-----
  python3 scripts/mouse_lines.py build resources/colony/*.csv --extra resources/colony/aliases.json
  python3 scripts/mouse_lines.py probe knowledge/inventory.jsonl [more.jsonl ...]
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb  # noqa: E402

REGISTRY = "mouse_lines.json"

# Display order is also the categorical colour order downstream.
CLASSES = ["Cre/Flp drivers", "Reporters", "Activity tools", "tet system",
           "Ablation & silencing", "Mutants & knock-outs", "Other lines"]

_NAME_RULES = [
    ("Activity tools", r"gcamp|g6[fs](?![a-z])|ccamp|chr2|cop4|catch|(?<![a-z])arch|nphr|hm[34]d|chrm[34]|gqy|giy"),
    ("Ablation & silencing", r"dta\d*|dtr|hbegf|txlc|tetanus|(?<![a-z])kir(?![a-z])"),
    ("tet system", r"tta|(?<![a-z])tet"),
    ("Cre/Flp drivers", r"cre|flp|esrc"),
    ("Reporters", r"gfp|yfp|rfp|tdt|tomato|lacz|mt/?mg|brainbow|citrine|mcherry"),
    ("Mutants & knock-outs", r"(?<![a-z])(ko|cko|cki|mki|flox|loxp|crispr|(?:del|ins|mut)\d+[a-z]?)(?![a-z])"),
]
# A formal strain name ("B6.129-Slc6a3tm1.1(cre)Bkmn/J") always contains "tm"
# or "Tg", so the mutant rule is never applied to it.
_OFFICIAL_RULES = [r for r in _NAME_RULES if r[0] not in ("Mutants & knock-outs", "tet system")]
_OFFICIAL_RULES.insert(4, ("tet system", r"tta|(?<![a-z])teto?(?![a-z])"))
_NAME_RX = [(c, re.compile(p)) for c, p in _NAME_RULES]
_OFFICIAL_RX = [(c, re.compile(p)) for c, p in _OFFICIAL_RULES]
_ALLEN_AI = re.compile(r"^ai\d{1,3}[a-z]?$")
_BACKGROUND = re.compile(r"^(c57bl[/ ]?6?[jn]?|c57bl6/?[jn]|balb/?c[j]?|cba/?caj|cd-?1|fvb(/n)?|129\S*|dba\S*)$", re.I)
# Letter(s)+digits names ("E9", "P7", "B6") collide with embryonic days,
# plate wells and sample labels. Allen "Ai##" reporters are the exception.
_TOO_GENERIC = re.compile(r"^[a-z]{1,2}\d{1,3}[a-z]?$")

STATUS_LABEL = {"active": "In the colony", "cryo": "Cryopreserved only",
                "archived": "No longer kept", "unknown": "Status not recorded"}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def clean(s: str) -> str:
    return re.sub(r"[​-\u200F﻿]", "", (s or "")).strip()


def _gene(official: str) -> str:
    """Target gene from a formal strain name, when it names one."""
    m = re.search(r"\b(Vmn[12]r\d+|Olfr\d+)\b", official)
    if m:
        return m.group(1)
    m = re.search(r"Tg\(([A-Za-z][A-Za-z0-9]+)", official)
    if m and m.group(1).upper() not in ("CAG", "TETO"):
        return m.group(1)
    for m in re.finditer(r"(?<![A-Za-z0-9(])([A-Z][a-z][A-Za-z0-9]{0,8}?)tm\d", official):
        if m.group(1) not in ("Sor", "Gt", "Igs7", "Igs"):
            return m.group(1)
    return ""


def classify(name: str, official: str) -> str:
    low = name.lower()
    for cls, rx in _NAME_RX:
        if rx.search(low):
            return cls
    off = (official or "").lower()
    for cls, rx in _OFFICIAL_RX:
        if rx.search(off):
            return cls
    if _ALLEN_AI.match(norm(name)):
        return "Reporters"
    return "Other lines"


def names_of(raw: str) -> List[str]:
    """'R-CHR2/Ai32' -> ['R-CHR2', 'Ai32']; 'Tnnt2-GFP/LM2' -> ['Tnnt2-GFP'];
    'Ai32 (R26-ChR2/EYFP)' -> ['Ai32']. A '/' suffix is a sub-line or a
    fluorophore, not a second name -- except an Allen 'Ai##' designation."""
    raw = clean(raw)
    raw = re.sub(r"\s*\(.*\)\s*$", "", raw).strip()
    parts = [p.strip() for p in raw.split("/") if p.strip()]
    if len(parts) > 1 and len(norm(parts[0])) < 4:   # 'mT/mG' is one name
        return [raw]
    if len(parts) == 2 and _ALLEN_AI.match(norm(parts[1])):
        return parts
    return parts[:1]


# --------------------------------------------------------------------------
# build


def _col(headers: List[str], *patterns: str, avoid: str = "") -> Optional[str]:
    for pat in patterns:
        for h in headers:
            hl = h.lower()
            if re.search(pat, hl) and not (avoid and re.search(avoid, hl)):
                return h
    return None


_PEOPLE = re.compile(r"member|responsible|owner|contact|person|note")


def _yes(v: str) -> Optional[bool]:
    v = clean(v).lower()
    if v in ("yes", "y", "true", "active"):
        return True
    if v in ("no", "n", "false", "inactive"):
        return False
    return None


def _public_stock(stock: str) -> str:
    """A repository stock number (Jackson digits, MMRRC '-UCD'/'-MU'); never a
    person's or lab's name, which this column often holds instead."""
    s = clean(stock)
    if re.fullmatch(r"0?\d{4,6}(-[A-Za-z]+)*", s) or re.search(r"\d+-(UCD|MU)\b", s, re.I):
        return s
    return ""


def build(csv_paths: List[Path], extra: dict) -> dict:
    entries: Dict[str, dict] = {}
    index: Dict[str, str] = {}

    def lookup(name: str) -> Optional[str]:
        n = norm(name)
        if n in index:
            return index[n]
        if len(n) >= 3:   # 'Pvalb' -> 'Pvalb-Cre'
            # ...but never into a longer number: 'Ai9' is not 'Ai96'.
            hits = {k for a, k in index.items() if a.startswith(n)
                    and not (n[-1].isdigit() and a[len(n):len(n) + 1].isdigit())}
            if len(hits) == 1:
                return hits.pop()
        return None

    def upsert(name: str, alias_names: List[str], official="", vendor="", stock="",
               active=None, cryo=None, source=""):
        key = lookup(name)
        for a in alias_names:
            key = key or lookup(a)
        if key is None:
            key = name
            entries[key] = {"name": name, "aliases": [], "official": "", "vendor": "",
                            "stock": "", "active": None, "cryo": None, "sources": []}
        e = entries[key]
        for a in [name] + alias_names:
            if a not in e["aliases"] and a != e["name"]:
                e["aliases"].append(a)
            index.setdefault(norm(a), key)
        e["official"] = e["official"] or official
        e["vendor"] = e["vendor"] or vendor
        e["stock"] = e["stock"] or stock
        if active is not None:
            e["active"] = bool(e["active"]) or active
        if cryo is not None:
            e["cryo"] = bool(e["cryo"]) or cryo
        if source and source not in e["sources"]:
            e["sources"].append(source)
        return key

    rows_seen = 0
    # Registry-style lists (with a vendor column) first, so their names win.
    tables = []
    for path in csv_paths:
        with path.open(newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        headers = list(rows[0].keys()) if rows else []
        tables.append((path, rows, headers))
    tables.sort(key=lambda t: _col(t[2], r"vendor|supplier") is None)

    for path, rows, headers in tables:
        c_alias = _col(headers, r"alias", avoid=_PEOPLE.pattern)
        c_id = _col(headers, r"strain id|^strain$|^line|line name|^name", avoid=_PEOPLE.pattern)
        c_vendor = _col(headers, r"vendor|supplier", avoid=r"stock")
        c_stock = _col(headers, r"stock")
        c_active = _col(headers, r"active")
        c_cryo = _col(headers, r"cryo")
        c_bg = _col(headers, r"background")
        for row in rows:
            rows_seen += 1
            alias = clean(row.get(c_alias, "")) if c_alias else ""
            sid = clean(row.get(c_id, "")) if c_id else ""
            primary = alias or sid
            if not primary or _BACKGROUND.match(primary) or \
                    (c_bg and clean(row.get(c_bg, "")).lower() == primary.lower()):
                continue
            official = sid if alias else ""
            if not official:
                m = re.search(r"\((.*)\)\s*$", primary)
                official = clean(m.group(1)) if m else ""
            act = _yes(row.get(c_active, "")) if c_active else None
            if c_bg and clean(row.get(c_bg, "")).lower() == "archived":
                act = False
            cryo_v = clean(row.get(c_cryo, "")).lower() if c_cryo else ""
            cryo = None if not cryo_v else ("embryo" in cryo_v or "sperm" in cryo_v)
            vendor = clean(row.get(c_vendor, "")) if c_vendor else ""
            stock = _public_stock(row.get(c_stock, "")) if c_stock else ""

            parts = [p.strip() for p in primary.split(";") if p.strip()]
            if len(parts) > 1:
                # A cross. Its components are the lines; a formal name or stock
                # on the row belongs to the first, unless it names the cross.
                for i, comp in enumerate(parts):
                    ns = names_of(comp)
                    if not ns or _BACKGROUND.match(ns[0]):
                        continue
                    first = i == 0 and ";" not in official
                    upsert(ns[0], ns[1:], official=official if first else "",
                           vendor=vendor if first else "", stock=stock if first else "",
                           active=True if act else None, cryo=cryo if first else None,
                           source=path.name)
                continue
            ns = names_of(primary)
            if ns:
                upsert(ns[0], ns[1:], official=official, vendor=vendor, stock=stock,
                       active=act, cryo=cryo, source=path.name)

    for name, more in (extra.get("aliases") or {}).items():
        key = lookup(name) or upsert(name, [], source="extra")
        for a in more:
            if a not in entries[key]["aliases"]:
                entries[key]["aliases"].append(a)

    lines = []
    for e in entries.values():
        if e["active"]:
            status = "active"
        elif e["cryo"]:
            status = "cryo"
        elif e["active"] is False:
            status = "archived"
        else:
            status = "unknown"
        lines.append({
            "name": e["name"],
            "aliases": sorted(set(e["aliases"]), key=str.lower),
            "class": classify(e["name"], e["official"]),
            "target": _gene(e["official"] or e["name"]),
            "official": e["official"],
            "vendor": e["vendor"],
            "stock": e["stock"],
            "public": bool(e["stock"]),
            "status": status,
        })
    lines.sort(key=lambda x: x["name"].lower())
    return {
        "version": date.today().isoformat(),
        "_comment": [
            "Generated by scripts/mouse_lines.py build from the lab's colony list(s).",
            "Edit freely: add spellings to 'aliases', refusals to 'refuse'. Re-running",
            "build regenerates it, so keep site additions in the --extra file.",
            "'public' = has a repository stock number (e.g. Jackson, MMRRC).",
        ],
        "classes": CLASSES,
        "refuse": sorted({norm(r) for r in (extra.get("refuse") or [])}),
        "rows_read": rows_seen,
        "lines": lines,
    }


# --------------------------------------------------------------------------
# matching

_SEP = r"[^a-z0-9]{0,2}"
_CHUNK = {
    "creer": r"i?creer(?:t2)?", "creert2": r"i?creer(?:t2)?", "icreer": r"i?creer(?:t2)?",
    "icreert2": r"i?creer(?:t2)?", "cre": r"i?cre", "icre": r"i?cre",
    "tdt": r"td(?:t|tomato)", "tdtomato": r"td(?:t|tomato)",
    "r26r": r"r(?:osa)?26r?", "r26": r"r(?:osa)?26r?", "rosa26": r"r(?:osa)?26r?",
}


def alias_pattern(alias: str) -> Optional[str]:
    n = norm(alias)
    if len(n) < 3 or (_TOO_GENERIC.match(n) and not _ALLEN_AI.match(n)):
        return None
    chunks = re.findall(r"[a-z0-9]+", alias.lower())
    if len(chunks) > 1 and chunks[-1] in ("ki", "tg", "line"):
        chunks = chunks[:-1]
    parts, last_run = [], ""
    for ch in chunks:
        if ch in _CHUNK:
            parts.append(_CHUNK[ch])
            last_run = ch
            continue
        # optional separator where digits give way to letters: Thy1Cre = Thy1-cre
        runs = re.findall(r"[a-z]+|\d+", ch)
        last_run = runs[-1]
        out = ""
        for i, r in enumerate(runs):
            if i and r[0].isalpha() and runs[i - 1][0].isdigit():
                out += _SEP
            out += re.escape(r)
        parts.append(out)
    body = _SEP.join(parts)
    if len(n) <= 4 or len(last_run) <= 2:
        tail = r"(?![a-z0-9])"
    elif n[-1].isdigit():
        tail = r"(?![0-9])"
    else:
        tail = ""
    return r"(?<![a-z0-9])" + body + tail


class MouseLines:
    """Strict matcher over a mouse_lines.json registry. Empty if none exists."""

    def __init__(self, data: Optional[dict]):
        data = data or {}
        self.version = str(data.get("version", ""))
        refuse = set(data.get("refuse") or [])
        self.lines = {l["name"]: l for l in data.get("lines", [])}
        groups, self._group_name = [], {}
        for i, (name, line) in enumerate(self.lines.items()):
            pats = []
            for a in [name] + list(line.get("aliases", [])):
                if norm(a) in refuse:
                    continue
                p = alias_pattern(a)
                if p and p not in pats:
                    pats.append(p)
            if pats:
                g = "g{}".format(i)
                self._group_name[g] = name
                groups.append("(?P<{}>{})".format(g, "|".join(pats)))
        # Longest alternatives first, so 'R26R-tdT' wins over a shorter prefix.
        groups.sort(key=len, reverse=True)
        self._rx = re.compile("|".join(groups)) if groups else None
        self._cache: Dict[str, Dict[str, int]] = {}

    @classmethod
    def load(cls) -> "MouseLines":
        path = kb.resource(REGISTRY)
        if not path.exists():
            return cls(None)
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def __bool__(self) -> bool:
        return self._rx is not None

    def _segment(self, seg: str) -> List[str]:
        if seg not in self._cache:
            found = []
            for m in self._rx.finditer(seg.lower()):
                name = self._group_name[m.lastgroup]
                if name not in found:
                    found.append(name)
            if len(self._cache) > 500000:
                self._cache.clear()
            self._cache[seg] = found
        return self._cache[seg]

    def locate(self, path: str) -> Dict[str, int]:
        """line name -> index of the first path segment that names it."""
        if not self._rx:
            return {}
        out: Dict[str, int] = {}
        for i, seg in enumerate(s for s in path.split("/") if s):
            for name in self._segment(seg):
                out.setdefault(name, i)
        return out

    def find(self, path: str) -> List[str]:
        return sorted(self.locate(path))

    def describe(self, name: str) -> str:
        """Search text for one line: 'Pvalb-Cre (Pvalb; Cre/Flp drivers)'."""
        l = self.lines.get(name, {})
        bits = [b for b in (l.get("target"), l.get("class")) if b]
        return "{} ({})".format(name, "; ".join(bits)) if bits else name


# --------------------------------------------------------------------------
# cli


def probe(paths: List[Path]) -> None:
    ml = MouseLines.load()
    if not ml:
        sys.exit("no registry: run `build` first")
    folders: Dict[str, set] = defaultdict(set)
    example: Dict[str, str] = {}
    files = Counter()
    for p in paths:
        for rec in kb.iter_records(p):
            if rec.get("kind") != "file":
                continue
            path = rec.get("path", "")
            segs = [s for s in path.split("/") if s]
            for name, i in ml.locate(path).items():
                # a line in a file's own name counts toward the folder holding it
                folder = "/" + "/".join(segs[: min(i + 1, len(segs) - 1)])
                folders[name].add(folder)
                files[name] += 1
                example.setdefault(name, folder)
    print("{:>8} {:>9}  {:<26} {}".format("folders", "files", "line", "example folder"))
    for name in sorted(folders, key=lambda n: -len(folders[n])):
        print("{:>8} {:>9}  {:<26} ...{}".format(len(folders[name]), files[name], name, example[name][-80:]))
    unseen = [n for n in ml.lines if n not in folders]
    print("\n{} of {} lines named somewhere; never seen: {}".format(
        len(folders), len(ml.lines), ", ".join(sorted(unseen, key=str.lower))))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="colony CSV(s) -> resources/mouse_lines.json")
    b.add_argument("csv", nargs="+")
    b.add_argument("--extra", help="JSON with site 'aliases' and 'refuse' additions")
    b.add_argument("--out", default=str(kb.RESOURCES / REGISTRY))
    p = sub.add_parser("probe", help="which lines an inventory's paths mention")
    p.add_argument("inventory", nargs="+")
    args = ap.parse_args()

    if args.cmd == "build":
        extra = json.loads(Path(args.extra).read_text(encoding="utf-8")) if args.extra else {}
        reg = build([Path(c) for c in args.csv], extra)
        Path(args.out).write_text(json.dumps(reg, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        by = Counter(l["class"] for l in reg["lines"])
        st = Counter(l["status"] for l in reg["lines"])
        print("{} lines from {} rows -> {}".format(len(reg["lines"]), reg["rows_read"], args.out))
        print("classes: " + ", ".join("{} {}".format(c, by[c]) for c in CLASSES if by[c]))
        print("status: " + ", ".join("{} {}".format(k, v) for k, v in st.most_common()))
        print("public (repository stock): {}".format(sum(l["public"] for l in reg["lines"])))
    else:
        probe([Path(x) for x in args.inventory])


if __name__ == "__main__":
    main()
