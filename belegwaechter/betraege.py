"""Einzige Stelle im Projekt, die Rechnungsbetraege in Zahlen umwandelt.

Deutsche Notation: Punkt als Tausendertrenner, Komma als Dezimaltrenner.
Liefert None statt zu raten, wenn der Text nicht eindeutig als Zahl lesbar
ist -- das treibt sowohl die Checkliste (fail-closed) als auch den
CSV-Export (nie ungeprueften Rohtext als Zahlenzelle).
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_BETRAG_MUSTER = re.compile(r"^-?\d{1,3}(?:\.\d{3})*(?:,\d+)?$|^-?\d+(?:,\d+)?$")


def betrag_zu_decimal(rohtext: str | None) -> Decimal | None:
    if not rohtext:
        return None
    text = rohtext.strip()
    if not _BETRAG_MUSTER.match(text):
        return None
    normalisiert = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(normalisiert)
    except InvalidOperation:
        return None


def decimal_zu_anzeige(wert: Decimal | None) -> str:
    """Kanonische deutsche Anzeige, z.B. Decimal('19.00') -> '19,00'."""
    if wert is None:
        return ""
    text = format(wert, "f")
    if "." in text:
        ganzzahl, nachkomma = text.split(".", 1)
    else:
        ganzzahl, nachkomma = text, ""
    negativ = ganzzahl.startswith("-")
    if negativ:
        ganzzahl = ganzzahl[1:]
    nachkomma = (nachkomma + "00")[:2]
    return f"{'-' if negativ else ''}{ganzzahl},{nachkomma}"


def decimal_zu_csv_zahl(wert: Decimal | None) -> str:
    """Reine Zahlendarstellung fuer den CSV-Export (Punkt als Dezimaltrenner,
    damit Tabellenprogramme den Wert als echte Zahl erkennen)."""
    if wert is None:
        return ""
    return format(wert, "f")
