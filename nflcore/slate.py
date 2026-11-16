"""Which NFL week is it? Calendar-driven, never hardcoded (Super Bowl is week 5 in 2025, 4 in 2026)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
UTC = timezone.utc
_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def parse_utc(s: str) -> datetime:
    """'2026-11-18T08:00Z' (or with seconds / offset) -> aware UTC datetime."""
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d.replace(tzinfo=UTC) if d.tzinfo is None else d.astimezone(UTC)


def chicago(dt) -> datetime:
    if isinstance(dt, str):
        dt = parse_utc(dt)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(CT)


def kick_ct(iso_utc: str) -> str:
    d = chicago(iso_utc)
    h = d.hour % 12 or 12
    return f"{_DAYS[d.weekday()]} {h}:{d.minute:02d} {'PM' if d.hour >= 12 else 'AM'} CT"


def chicago_date(iso_utc: str) -> str:
    return chicago(iso_utc).strftime("%Y-%m-%d")


def parse_calendar(calendar) -> list[dict]:
    """Flatten ESPN's calendar into ordered week entries: {st, week, label, start, end} (start/end aware UTC).

    Accepts pull_calendar()'s dict or the bare list. Only season types 1-3 count; Off Season (4) and entry-less types are skipped.
    """
    items = calendar.get("calendar") if isinstance(calendar, dict) else calendar
    out = []
    for typ in items or []:
        if not isinstance(typ, dict):
            continue
        try:
            st = int(typ.get("value"))
        except (TypeError, ValueError):
            continue
        if st not in (1, 2, 3):   # Off Season (4) and anything new are not slates
            continue
        for e in typ.get("entries") or []:
            try:
                out.append({"st": st, "week": int(e["value"]), "label": e.get("label") or f"Week {e['value']}",
                            "start": parse_utc(e["startDate"]), "end": parse_utc(e["endDate"])})
            except (KeyError, TypeError, ValueError):
                continue
    out.sort(key=lambda r: r["start"])
    return out


_HELD = ("STATUS_SUSPENDED", "STATUS_DELAYED", "STATUS_RAIN_DELAY")   # keep in step with normalize.HELD


def event_settled(ev: dict) -> bool:
    """True when a raw ESPN event is final enough to advance the week: state post, and not a suspended or
    delayed game that ESPN left uncompleted. ESPN repeats the status on the event and its competition."""
    for status in (ev.get("status"), (ev.get("competitions") or [{}])[0].get("status")):
        t = (status or {}).get("type") or {}
        if t.get("state") == "post" and (t.get("completed") or t.get("name") not in _HELD):
            return True
    return False


def _season_year(calendar, entries) -> int | None:
    if isinstance(calendar, dict):
        y = (calendar.get("season") or {}).get("year")
        if y:
            return int(y)
    return entries[0]["start"].year if entries else None


def _shape(e: dict, year) -> dict:
    return {"year": year, "st": e["st"], "week": e["week"], "label": e["label"],
            "start": e["start"].strftime("%Y-%m-%dT%H:%MZ"), "end": e["end"].strftime("%Y-%m-%dT%H:%MZ")}


def resolve_week(calendar, now_utc: datetime, events_all_post: bool | None = None) -> dict | None:
    """The calendar entry containing now_utc; the next entry once every event of that week is final.

    Entry windows end at HH:59Z, so the window is [start, next start). Returns None in the offseason
    (before the first entry, after the last, or when advancing past the final entry).
    """
    entries = parse_calendar(calendar)
    if not entries:
        return None
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=UTC)
    year = _season_year(calendar, entries)
    for i, e in enumerate(entries):
        nxt = entries[i + 1]["start"] if i + 1 < len(entries) else e["end"] + timedelta(minutes=1)
        if e["start"] <= now_utc < nxt:
            if events_all_post:
                return _shape(entries[i + 1], year) if i + 1 < len(entries) else None
            return _shape(e, year)
    return None
