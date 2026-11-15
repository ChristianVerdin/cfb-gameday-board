"""ESPN site API client (stdlib only). All I/O goes through _fetch so tests can replace it."""
from __future__ import annotations

import gzip
import json
import re
import time
import urllib.error
import urllib.request

from .cache import TTLCache

HOSTS = ("site.web.api.espn.com", "site.api.espn.com")
SITE = "/apis/site/v2/sports/football/nfl"
LIVE_TIMEOUT = 8
CI_TIMEOUT = 20
CALENDAR_TTL = 6 * 3600
HOST_TRIES = 2
RETRY_PAUSE = 0.4
DEADLINE = 10   # overall budget per get_json call, seconds (Vercel maxDuration must cover a few calls)

PROFILES = {
    "safari": {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
                      "Version/18.0 Safari/605.1.15",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip",
    },
    "default": {"User-Agent": "nfl-board/1.0", "Accept": "application/json"},
}

CACHE = TTLCache()
_sleep = time.sleep


class EspnError(Exception):
    def __init__(self, msg: str, status: int | None = None, url: str | None = None):
        super().__init__(msg)
        self.status = status
        self.url = url


class EspnQueryError(EspnError, ValueError):
    """The caller asked for something this client refuses (ranges, lists, junk ids)."""


def _fetch(url: str, timeout: float, profile: str) -> bytes:
    req = urllib.request.Request(url, headers=PROFILES[profile])
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise EspnError(f"HTTP {e.code}", status=e.code, url=url) from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise EspnError(f"network: {e}", url=url) from None


def _decode(raw: bytes, url: str):
    if raw[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(raw)
        except (OSError, EOFError) as e:
            raise EspnError(f"bad gzip: {e}", url=url) from None
    try:
        return json.loads(raw)
    except ValueError as e:
        raise EspnError(f"bad json: {e}", url=url) from None


def fetch_json(url: str, timeout: float = LIVE_TIMEOUT):
    """GET url as JSON. A 403 on the browser-like profile is retried once with the plain one."""
    last: EspnError | None = None
    for profile in ("safari", "default"):
        try:
            return _decode(_fetch(url, timeout, profile), url)
        except EspnError as e:
            last = e
            if e.status != 403:
                raise
    raise last  # type: ignore[misc]


def _retryable(e: EspnError) -> bool:
    return e.status is None or e.status == 429 or e.status >= 500


def get_json(path: str, timeout: float = LIVE_TIMEOUT):
    """Try each host in order, HOST_TRIES attempts apiece on transient errors, then fall back to the next."""
    last: EspnError | None = None
    end = time.monotonic() + DEADLINE
    for host in HOSTS:
        url = f"https://{host}{SITE}{path}"
        for attempt in range(HOST_TRIES):
            left = end - time.monotonic()
            if left <= 0.5:
                raise EspnError(f"deadline: {last}", status=getattr(last, "status", None))
            try:
                return fetch_json(url, min(timeout, left))
            except EspnError as e:
                last = e
                if not _retryable(e):
                    break
                if attempt + 1 < HOST_TRIES:
                    _sleep(RETRY_PAUSE)
    raise EspnError(f"all hosts failed: {last}", status=getattr(last, "status", None))


def _num(name: str, v, lo: int, hi: int) -> int:
    if isinstance(v, bool) or not (isinstance(v, int) or (isinstance(v, str) and re.fullmatch(r"\d{1,4}", v))):
        raise EspnQueryError(f"{name} must be a single integer, got {v!r}")
    n = int(v)
    if not lo <= n <= hi:
        raise EspnQueryError(f"{name} out of range: {n}")
    return n


def pull_scoreboard(st: int, week: int, year: int | None = None, timeout: float = LIVE_TIMEOUT) -> dict:
    """One week's scoreboard. Ranges and comma lists are refused; postseason and past seasons need year."""
    q = f"?seasontype={_num('seasontype', st, 1, 3)}&week={_num('week', week, 1, 25)}"
    if year is not None:
        q += f"&dates={_num('year', year, 2000, 2100)}"
    return get_json("/scoreboard" + q, timeout)


def pull_summary(event_id: str, timeout: float = LIVE_TIMEOUT) -> dict:
    if not re.fullmatch(r"\d{6,12}", str(event_id)):
        raise EspnQueryError(f"bad event id {event_id!r}")
    return get_json(f"/summary?event={event_id}", timeout)


def pull_calendar(timeout: float = LIVE_TIMEOUT) -> dict:
    """{'calendar': [...], 'season': {...}, 'week': {'number': n}} from the bare scoreboard, cached 6 h."""
    def load():
        d = get_json("/scoreboard", timeout)
        leagues = d.get("leagues") or [{}]
        cal = leagues[0].get("calendar")
        if not cal:
            raise EspnError("scoreboard has no calendar")
        wk = d.get("week") or {}
        return {"calendar": cal, "season": d.get("season") or {}, "week": {"number": wk.get("number")}}
    value, _stale = CACHE.get_or_fetch("calendar", CALENDAR_TTL, load, stale_ok_s=24 * 3600)
    return value
