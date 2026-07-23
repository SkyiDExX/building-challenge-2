"""Schritt 4 des Agent-Zyklus: Bewerten der Vollstaendigkeit (fail-closed).

Fehlende oder widerspruechliche Angaben fuehren zu einem nicht erfuellten
Checkpunkt, nie zu einer Annahme oder einem geratenen Wert.
"""
from __future__ import annotations

from belegwaechter.betraege import betrag_zu_decimal
from belegwaechter.modelle import Beleg, Checkpunkt


def checkliste_pruefen(beleg: Beleg, text_lesbar: bool) -> list[Checkpunkt]:
    def hat(feld: str) -> bool:
        return beleg.feldwert(feld) not in (None, "")

    betrag_lesbar = betrag_zu_decimal(beleg.feldwert("betrag")) is not None

    return [
        Checkpunkt("Anbieter erkannt", hat("anbieter")),
        Checkpunkt("Datum erkannt", hat("datum")),
        Checkpunkt("Betrag und Waehrung erkannt", betrag_lesbar and hat("waehrung")),
        Checkpunkt("Rechnungsnummer vorhanden", hat("referenz")),
        Checkpunkt("Zeitraum eindeutig", hat("zeitraum")),
        Checkpunkt("Dokument vollstaendig lesbar", text_lesbar),
    ]


def vollstaendig(checkliste: list[Checkpunkt]) -> bool:
    return all(punkt.erfuellt for punkt in checkliste)


def fehlende_punkte(checkliste: list[Checkpunkt]) -> list[str]:
    return [punkt.name for punkt in checkliste if not punkt.erfuellt]
