"""Colombian public holidays (Ley 51 de 1983, "Ley Emiliani")."""

from datetime import date, timedelta
from functools import lru_cache


def _easter(year: int) -> date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _next_monday(d: date) -> date:
    return d + timedelta(days=(7 - d.weekday()) % 7)


@lru_cache
def colombian_holidays(year: int) -> frozenset[date]:
    fixed = [date(year, 1, 1), date(year, 5, 1), date(year, 7, 20),
             date(year, 8, 7), date(year, 12, 8), date(year, 12, 25)]
    moved = [date(year, 1, 6), date(year, 3, 19), date(year, 6, 29), date(year, 8, 15),
             date(year, 10, 12), date(year, 11, 1), date(year, 11, 11)]
    easter = _easter(year)
    easter_fixed = [easter - timedelta(days=3), easter - timedelta(days=2)]
    easter_moved = [easter + timedelta(days=39), easter + timedelta(days=60),
                    easter + timedelta(days=68)]
    return frozenset(fixed + easter_fixed + [_next_monday(d) for d in moved + easter_moved])


def is_holiday(d: date) -> bool:
    return d in colombian_holidays(d.year)


def is_business_day(d: date) -> bool:
    return d.weekday() < 6 and not is_holiday(d)


def next_business_day(d: date) -> date:
    while not is_business_day(d):
        d += timedelta(days=1)
    return d
