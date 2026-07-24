"""Einheitliche Datumsdarstellung beim Ausliefern und Exportieren.

Interne Werte bleiben unveraendert gespeichert (keine Migration); diese
Funktionen normalisieren ausschliesslich die sichtbare Darstellung:
UI immer TT.MM.JJJJ bzw. "TT.MM.JJJJ bis TT.MM.JJJJ", CSV immer YYYY-MM-DD
bzw. "YYYY-MM-DD bis YYYY-MM-DD". Erkannt werden die drei Formate der
Extraktion (deutsch numerisch, deutsch ausgeschrieben, englisch). Alles,
was nicht sicher als Datum bzw. Datumsbereich erkennbar ist (z.B.
"monatlich" oder ein defekter Wert), wird unveraendert zurueckgegeben --
es wird nie ein Datum erfunden.
"""
from __future__ import annotations

import re
from datetime import date

_MONATE = {
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5,
    "juni": 6, "juli": 7, "august": 8, "september": 9, "oktober": 10,
    "november": 11, "dezember": 12,
    "january": 1, "february": 2, "march": 3, "may": 5, "june": 6, "july": 7,
    "october": 10, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DE_NUMERISCH = re.compile(r"\b(\d{2})\.(\d{2})\.(\d{4})\b")
_DE_AUSGESCHRIEBEN = re.compile(r"\b(\d{1,2})\.\s*([A-Za-zÄÖÜäöü]+)\s+(\d{4})\b")
_EN = re.compile(r"\b([A-Za-z]+)\.?\s+(\d{1,2}),\s*(\d{4})\b")

# Englischer Bereich mit nur einmal genanntem Jahr, beliebiger
# Gross-/Kleinschreibung und Bindestrich, Halbgeviertstrich oder
# Gedankenstrich als Trenner: "jul 15-aug 15, 2026", "jun 22 – jul 21, 2026".
_EN_BEREICH_EIN_JAHR = re.compile(
    r"\b([A-Za-z]+)\.?\s+(\d{1,2})\s*[-–—]\s*([A-Za-z]+)\.?\s+(\d{1,2}),?\s*(\d{4})\b"
)


def _monat(name: str) -> int | None:
    return _MONATE.get(name.lower())


def _alle_daten(text: str) -> list[date]:
    """Alle sicher erkennbaren Datumswerte im Text, in Textreihenfolge.
    Ungueltige Kalenderdaten werden uebersprungen, nie korrigiert."""
    treffer: list[tuple[int, date]] = []
    for m in _ISO.finditer(text):
        try:
            treffer.append((m.start(), date(int(m.group(1)), int(m.group(2)), int(m.group(3)))))
        except ValueError:
            continue
    for m in _DE_NUMERISCH.finditer(text):
        try:
            treffer.append((m.start(), date(int(m.group(3)), int(m.group(2)), int(m.group(1)))))
        except ValueError:
            continue
    for m in _DE_AUSGESCHRIEBEN.finditer(text):
        monat = _monat(m.group(2))
        if monat is None:
            continue
        try:
            treffer.append((m.start(), date(int(m.group(3)), monat, int(m.group(1)))))
        except ValueError:
            continue
    for m in _EN.finditer(text):
        monat = _monat(m.group(1))
        if monat is None:
            continue
        try:
            treffer.append((m.start(), date(int(m.group(3)), monat, int(m.group(2)))))
        except ValueError:
            continue
    treffer.sort(key=lambda t: t[0])
    return [d for _, d in treffer]


def _einzeldatum(wert: str | None) -> date | None:
    if not wert:
        return None
    daten = _alle_daten(wert)
    return daten[0] if len(daten) == 1 else None


def datum_ui(wert: str | None) -> str | None:
    d = _einzeldatum(wert)
    return f"{d.day:02d}.{d.month:02d}.{d.year:04d}" if d else wert


def datum_csv(wert: str | None) -> str | None:
    d = _einzeldatum(wert)
    return d.isoformat() if d else wert


def _bereich(wert: str) -> tuple[date, date] | None:
    """Sicher erkannter Datumsbereich oder None. Beim Ein-Jahr-Muster gilt
    das genannte Jahr fuer beide Seiten, aber nur wenn der Bereich damit
    aufsteigend ist -- sonst wird nichts geraten und der Originalwert
    bleibt als Review-Fall sichtbar."""
    m = _EN_BEREICH_EIN_JAHR.search(wert)
    if m:
        monat_von, monat_bis = _monat(m.group(1)), _monat(m.group(3))
        if monat_von is not None and monat_bis is not None:
            try:
                jahr = int(m.group(5))
                von = date(jahr, monat_von, int(m.group(2)))
                bis = date(jahr, monat_bis, int(m.group(4)))
            except ValueError:
                von, bis = None, None
            if von is not None and bis is not None and von <= bis:
                return von, bis
    daten = _alle_daten(wert)
    if len(daten) == 2:
        return daten[0], daten[1]
    return None


def zeitraum_ui(wert: str | None) -> str | None:
    if not wert:
        return wert
    bereich = _bereich(wert)
    if bereich is None:
        return wert
    von, bis = bereich
    return (
        f"{von.day:02d}.{von.month:02d}.{von.year:04d} bis "
        f"{bis.day:02d}.{bis.month:02d}.{bis.year:04d}"
    )


def zeitraum_csv(wert: str | None) -> str | None:
    if not wert:
        return wert
    bereich = _bereich(wert)
    if bereich is None:
        return wert
    von, bis = bereich
    return f"{von.isoformat()} bis {bis.isoformat()}"
