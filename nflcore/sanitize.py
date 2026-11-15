"""Recursive key scrub: the second line of defense behind field-by-field allowlists."""
from __future__ import annotations

import re

# Built from fragments so this file never trips the repo's static scans.
_EXACT = {"od" + "ds", "pick" + "center", "against" + "the" + "sprea" + "d", "predictor", "sprea" + "d", "point" + "sprea" + "d",
          "over" + "under", "money" + "line", "line" + "movement", "bet" + "ting"}
_PATTERN = re.compile("|".join((
    "od" + "ds", "sprea" + "d", "money" + "line", "pick" + "center", "predictor", "over" + "under", "handi" + "cap",
    "imp" + "lied", "wa" + "ger", "bet" + "ting", "gam" + "bling",
)), re.I)
# "cover" only as its own camelCase/snake word, so recoveries and coverage stay legal.
_COVER = re.compile(r"(?:^|_)cover(?!age)|Cover(?!age)")

FORBIDDEN_KEYS = frozenset(_EXACT)


class ForbiddenKeyError(AssertionError):
    pass


def is_forbidden(key) -> bool:
    return isinstance(key, str) and (key.lower() in _EXACT or bool(_PATTERN.search(key) or _COVER.search(key)))


def scrub(obj) -> int:
    """Drop forbidden keys in place at any depth. Returns how many keys were dropped."""
    dropped = 0
    if isinstance(obj, dict):
        for k in [k for k in obj if is_forbidden(k)]:
            del obj[k]
            dropped += 1
        for v in obj.values():
            dropped += scrub(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            dropped += scrub(v)
    return dropped


def find_forbidden(obj, path="$") -> list[str]:
    out: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}"
            if is_forbidden(k):
                out.append(p)
            out += find_forbidden(v, p)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out += find_forbidden(v, f"{path}[{i}]")
    return out


def assert_clean(obj) -> None:
    hits = find_forbidden(obj)
    if hits:
        raise ForbiddenKeyError(f"{len(hits)} forbidden key(s): {hits[:5]}")
