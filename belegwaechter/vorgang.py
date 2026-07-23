"""Regeln auf Vorgangsebene: naechste Aktivitaet und fehlende Dokumente.

Die naechste Aktivitaet wird ausschliesslich mit expliziter Evidenz gesetzt:
ein ausdrueckliches Verlaengerungs- oder Abbuchungsdatum ergibt eine
bestaetigte naechste Zahlung; ein expliziter Leistungszeitraum (von-bis)
ergibt hoechstens einen erwarteten naechsten Beleg, nie eine Zahlungszusage.
Ohne solche Evidenz bleibt der Status 'unbekannt' ohne Art und Datum. Es
gibt bewusst keine Wahrscheinlichkeits- oder Rhythmusschaetzung.
"""
from __future__ import annotations

import re

from belegwaechter.modelle import (
    AKTIVITAET_ART_BELEG,
    AKTIVITAET_ART_ZAHLUNG,
    AKTIVITAET_BESTAETIGT,
    AKTIVITAET_ERWARTET,
    AKTIVITAET_UNBEKANNT,
    DOKUMENTART_RECHNUNG,
    DOKUMENTART_ZAHLUNGSBELEG,
    Beleg,
)

_MUSTER_VERLAENGERUNG = re.compile(
    r"(?:verl(?:ae|ä)ngert\s+sich\s+am|verl(?:ae|ä)ngerung\s+am|n(?:ae|ä)chste\s+abbuchung\s+am)"
    r"\s*:?\s*(\d{2}\.\d{2}\.\d{4})",
    re.IGNORECASE,
)
_MUSTER_ZEITRAUM_VON_BIS = re.compile(r"\d{2}\.\d{2}\.\d{4}\s*-\s*(\d{2}\.\d{2}\.\d{4})")

AUFGABE_RECHNUNG_ANFORDERN = "Rechnung oder Originalbeleg anfordern"


def naechste_aktivitaet(texte: list[str]) -> tuple[str | None, str, str | None, str]:
    """Liefert (art, status, datum, begruendung) aus den uebergebenen
    Evidenztexten (Mailtext plus extrahierte Zeitraum-Feldwerte)."""
    gesamt = "\n".join(t for t in texte if t)

    treffer_verlaengerung = _MUSTER_VERLAENGERUNG.search(gesamt)
    if treffer_verlaengerung:
        datum = treffer_verlaengerung.group(1)
        return (
            AKTIVITAET_ART_ZAHLUNG,
            AKTIVITAET_BESTAETIGT,
            datum,
            f"Naechste Zahlung bestaetigt: explizites Verlaengerungsdatum {datum} im Dokument genannt.",
        )

    treffer_zeitraum = _MUSTER_ZEITRAUM_VON_BIS.search(gesamt)
    if treffer_zeitraum:
        bis_datum = treffer_zeitraum.group(1)
        return (
            AKTIVITAET_ART_BELEG,
            AKTIVITAET_ERWARTET,
            bis_datum,
            f"Naechster Beleg erwartet: Leistungszeitraum bis {bis_datum} erkannt. "
            "Das ist keine Aussage ueber eine sichere naechste Zahlung.",
        )

    return (
        None,
        AKTIVITAET_UNBEKANNT,
        None,
        "Naechste Aktivitaet unbekannt: weder Verlaengerungsdatum noch Leistungszeitraum erkannt.",
    )


def rechnung_fehlt(belege: list[Beleg]) -> bool:
    """Ein Vorgang mit Zahlungsbeleg, aber ohne Rechnung, braucht die
    Review-Aufgabe 'Rechnung oder Originalbeleg anfordern'."""
    arten = {b.dokumentart for b in belege}
    return DOKUMENTART_ZAHLUNGSBELEG in arten and DOKUMENTART_RECHNUNG not in arten
