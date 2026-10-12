from datetime import date

_WEEKDAYS = {
    "es": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}
_MONTHS = {
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
           "septiembre", "octubre", "noviembre", "diciembre"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"],
}


def money_text(amount: int | float) -> str:
    """Colombian peso format kept in transcripts for audit: 1200000 -> "$1.200.000"."""
    return "$" + f"{int(amount):,}".replace(",", ".")


def date_text(d: date, lang: str = "es") -> str:
    lang = lang if lang in _WEEKDAYS else "es"
    weekday = _WEEKDAYS[lang][d.weekday()]
    month = _MONTHS[lang][d.month - 1]
    if lang == "en":
        return f"{weekday}, {month} {d.day}"
    return f"{weekday} {d.day} de {month}"


def mask_tail(value: str | None, visible: int = 4) -> str:
    if not value:
        return ""
    return f"terminado en {value[-visible:]}"
