"""Calendar and event planning tools.

Adapted from v2 — wrapped with LangChain @tool decorator.
"""

from datetime import datetime, timedelta

from langchain_core.tools import tool


def _get_nth_weekday(year: int, month: int, weekday: int, n: int) -> datetime:
    """Get nth occurrence of weekday in month. weekday: 0=Mon..6=Sun."""
    if n > 0:
        first_day = datetime(year, month, 1)
        days_until = (weekday - first_day.weekday()) % 7
        return first_day + timedelta(days=days_until + 7 * (n - 1))
    else:
        if month == 12:
            last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = datetime(year, month + 1, 1) - timedelta(days=1)
        days_since = (last_day.weekday() - weekday) % 7
        return last_day - timedelta(days=days_since)


def _get_easter(year: int) -> datetime:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return datetime(year, month, day)


_EVENTS_DB = {
    1: [
        {"date": "01", "name": "New Year's Day", "type": "holiday", "region": "global", "themes": ["new beginnings", "goals", "fresh start"]},
        {"date": "14", "name": "Makar Sankranti", "type": "festival", "region": "India", "themes": ["harvest", "kites", "celebration"]},
        {"date": "26", "name": "Republic Day", "type": "national", "region": "India", "themes": ["patriotism", "pride", "unity"]},
    ],
    2: [
        {"date": "14", "name": "Valentine's Day", "type": "observance", "region": "global", "themes": ["love", "relationships", "gifts", "romance"]},
    ],
    3: [
        {"date": "08", "name": "International Women's Day", "type": "awareness", "region": "global", "themes": ["empowerment", "equality", "women"]},
        {"date": "17", "name": "St. Patrick's Day", "type": "observance", "region": "global", "themes": ["luck", "green", "celebration"]},
    ],
    4: [
        {"date": "01", "name": "April Fools' Day", "type": "observance", "region": "global", "themes": ["humor", "pranks", "fun"]},
        {"date": "22", "name": "Earth Day", "type": "awareness", "region": "global", "themes": ["environment", "sustainability", "nature"]},
    ],
    5: [
        {"date": "01", "name": "May Day / Labor Day", "type": "holiday", "region": "global", "themes": ["workers", "rights"]},
    ],
    6: [
        {"date": "21", "name": "International Yoga Day", "type": "awareness", "region": "global", "themes": ["wellness", "health", "mindfulness"]},
    ],
    7: [
        {"date": "04", "name": "Independence Day", "type": "national", "region": "US", "themes": ["freedom", "patriotism", "celebration"]},
    ],
    8: [
        {"date": "15", "name": "Independence Day", "type": "national", "region": "India", "themes": ["freedom", "patriotism", "pride"]},
    ],
    9: [
        {"date": "05", "name": "Teachers' Day", "type": "observance", "region": "India", "themes": ["education", "gratitude"]},
    ],
    10: [
        {"date": "02", "name": "Gandhi Jayanti", "type": "national", "region": "India", "themes": ["peace", "non-violence"]},
        {"date": "31", "name": "Halloween", "type": "observance", "region": "global", "themes": ["costumes", "fun", "spooky"]},
    ],
    11: [
        {"date": "11", "name": "Veterans Day", "type": "national", "region": "US", "themes": ["honor", "gratitude"]},
    ],
    12: [
        {"date": "25", "name": "Christmas", "type": "holiday", "region": "global", "themes": ["gifts", "joy", "celebration", "family"]},
        {"date": "31", "name": "New Year's Eve", "type": "holiday", "region": "global", "themes": ["celebration", "reflection", "countdown"]},
    ],
}


@tool
def get_upcoming_events(
    days_ahead: int = 30,
    region: str = "global",
    industry: str = "",
) -> dict:
    """Get upcoming events and festivals within a date range.

    Args:
        days_ahead: Number of days to look ahead (default 30).
        region: Geographic region filter (global, US, India, etc.).
        industry: Brand industry for relevant event filtering.
    """
    year = datetime.now().year
    start = datetime.now()
    end = start + timedelta(days=days_ahead)

    var_dates = {
        "mothers_day": _get_nth_weekday(year, 5, 6, 2),
        "fathers_day": _get_nth_weekday(year, 6, 6, 3),
        "thanksgiving": _get_nth_weekday(year, 11, 3, 4),
        "easter": _get_easter(year),
    }

    events = []

    current = start
    checked_months = set()
    while current <= end:
        month_num = current.month
        if month_num not in checked_months:
            checked_months.add(month_num)
            for event in _EVENTS_DB.get(month_num, []):
                try:
                    event_date = datetime(current.year, month_num, int(event["date"]))
                    if start <= event_date <= end:
                        if region == "global" or event.get("region") in [region, "global"]:
                            events.append({**event, "full_date": event_date.strftime("%Y-%m-%d")})
                except ValueError:
                    pass

            for name, date in var_dates.items():
                if date.month == month_num and start <= date <= end:
                    display_name = name.replace("_", " ").title()
                    if not any(e["name"] == display_name for e in events):
                        events.append({
                            "date": date.strftime("%d"),
                            "full_date": date.strftime("%Y-%m-%d"),
                            "name": display_name,
                            "type": "observance",
                            "region": "global",
                            "themes": [],
                        })

        current += timedelta(days=28)

    events.sort(key=lambda x: x.get("full_date", ""))
    all_themes = []
    for e in events:
        all_themes.extend(e.get("themes", []))

    return {
        "status": "success",
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
        "events": events,
        "count": len(events),
        "content_themes": list(set(all_themes)),
    }
