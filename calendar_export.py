"""
calendar_export.py
-------------------
Builds a standards-compliant .ics calendar file from an itinerary dict, with
one VEVENT per activity (morning/afternoon/evening) per day. No third-party
calendar library is required - the ICS format is simple enough to build
directly with the standard library, which keeps this module dependency-free
and easy to read for beginners.

Each event uses a fixed, clearly-labeled default time slot (since the AI
itinerary only gives a duration estimate, not an exact clock time):
    Morning   -> starts 09:00
    Afternoon -> starts 13:30
    Evening   -> starts 18:00
Durations are parsed from the activity's "duration" text when possible
(e.g. "1.5 hours"), otherwise a sensible default is used.
"""

import re
import uuid
from datetime import date, datetime, timedelta
from typing import Dict, List

_SLOT_START_TIMES = {
    "morning": (9, 0),
    "afternoon": (13, 30),
    "evening": (18, 0),
}
_SLOT_DEFAULT_DURATION_HOURS = {
    "morning": 2.0,
    "afternoon": 2.5,
    "evening": 1.5,
}


def _parse_duration_hours(duration_text: str, fallback_hours: float) -> float:
    """Extract a number of hours from a free-text duration like '~1.5 hours (estimate)'."""
    if not duration_text:
        return fallback_hours
    match = re.search(r"(\d+(?:\.\d+)?)\s*h", duration_text.lower())
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return fallback_hours
    # Handle "90 minutes" style text as a bonus.
    match_min = re.search(r"(\d+)\s*min", duration_text.lower())
    if match_min:
        try:
            return float(match_min.group(1)) / 60.0
        except ValueError:
            return fallback_hours
    return fallback_hours


def _fold_line(line: str) -> str:
    """
    ICS lines longer than 75 octets should be folded per RFC 5545. This is a
    simple, safe implementation for ASCII-heavy text (adds a space-prefixed
    continuation line).
    """
    if len(line) <= 75:
        return line
    parts = [line[:75]]
    rest = line[75:]
    while rest:
        parts.append(" " + rest[:74])
        rest = rest[74:]
    return "\r\n".join(parts)


def _escape_text(text: str) -> str:
    """Escape characters that have special meaning in ICS TEXT values."""
    if not text:
        return ""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _build_event(summary: str, start_dt: datetime, end_dt: datetime, location: str, description: str) -> List[str]:
    uid = f"{uuid.uuid4()}@travel-itinerary-planner"
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return [
        "BEGIN:VEVENT",
        _fold_line(f"UID:{uid}"),
        f"DTSTAMP:{dtstamp}",
        _fold_line(f"SUMMARY:{_escape_text(summary)}"),
        f"DTSTART:{start_dt.strftime('%Y%m%dT%H%M%S')}",
        f"DTEND:{end_dt.strftime('%Y%m%dT%H%M%S')}",
        _fold_line(f"LOCATION:{_escape_text(location)}"),
        _fold_line(f"DESCRIPTION:{_escape_text(description)}"),
        "END:VEVENT",
    ]


def build_ics(itinerary: Dict, start_date: date) -> str:
    """
    Build the full .ics file content as a string.

    Args:
        itinerary: the itinerary dict (see itinerary_generator.py for shape).
        start_date: a datetime.date representing Day 1 of the trip. Each
            subsequent day is offset by (day_number - 1) days from this date.

    Returns:
        The complete .ics file content, ready to write to disk or hand to a
        Streamlit download_button.

    Raises:
        ValueError if the itinerary has no days to export.
    """
    days = itinerary.get("days", []) or []
    if not days:
        raise ValueError("This itinerary has no days to export to a calendar.")

    destination = itinerary.get("trip_summary", {}).get("destination", "Trip")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Generative AI Travel Itinerary Planner//EN",
        "CALSCALE:GREGORIAN",
    ]

    for day in days:
        day_number = day.get("day_number", 1)
        day_date = start_date + timedelta(days=int(day_number) - 1)

        for slot_key in ("morning", "afternoon", "evening"):
            slot = day.get(slot_key, {}) or {}
            activity = slot.get("activity")
            if not activity:
                continue

            start_hour, start_minute = _SLOT_START_TIMES[slot_key]
            start_dt = datetime(day_date.year, day_date.month, day_date.day, start_hour, start_minute)
            duration_hours = _parse_duration_hours(slot.get("duration", ""), _SLOT_DEFAULT_DURATION_HOURS[slot_key])
            end_dt = start_dt + timedelta(hours=duration_hours)

            description = (
                f"{slot_key.capitalize()} activity in {destination} (Day {day_number}). "
                f"Estimated cost: {slot.get('cost', 'N/A')}. "
                f"Times and costs are estimates."
            )
            lines.extend(
                _build_event(
                    summary=activity,
                    start_dt=start_dt,
                    end_dt=end_dt,
                    location=slot.get("location", destination),
                    description=description,
                )
            )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def safe_filename(destination: str) -> str:
    """Turn a destination string into a safe .ics filename."""
    slug = "".join(c.lower() if c.isalnum() else "_" for c in (destination or "trip"))
    slug = "_".join(filter(None, slug.split("_")))[:40] or "trip"
    return f"travel_itinerary_{slug}.ics"
