"""Werkzeug 'dokumentart_bestimmen': regelbasierte, deterministische
Einordnung eines Dokuments in genau eine Dokumentart.

Feste Prioritaetsreihenfolge (spezifisch vor generisch): Zahlungsbeleg-
Woerter vor Abo-Woertern vor Rechnungs-Woertern. Wird kein Schluesselwort
gefunden, aber ein Betrag, ist es ein sonstiger Kostennachweis; sonst endet
die Einordnung fail-closed bei 'unbestimmt'. Es wird nie geraten und nie
ein externes Modell befragt.
"""
from __future__ import annotations

from belegwaechter.modelle import (
    DOKUMENTART_ABO_BESTAETIGUNG,
    DOKUMENTART_RECHNUNG,
    DOKUMENTART_SONSTIGER_KOSTENNACHWEIS,
    DOKUMENTART_UNBESTIMMT,
    DOKUMENTART_ZAHLUNGSBELEG,
)

# Bewusst enge Wortlisten: "zahlung erhalten" statt "zahlung", damit ein
# Anbietername wie "Zahlbar GmbH" nie faelschlich als Zahlungsbeleg gilt.
_ZAHLUNGSBELEG_WOERTER = (
    "zahlungsbeleg",
    "zahlungsbestaetigung",
    "zahlungsbestätigung",
    "zahlung erhalten",
    "zahlungseingang",
)
_ABO_WOERTER = (
    "verlaengert sich",
    "verlängert sich",
    "abo-bestaetigung",
    "abo-bestätigung",
    "abonnement",
)
_RECHNUNG_WOERTER = ("rechnung", "invoice")


def klassifizieren(
    text: str, dateiname: str = "", betreff: str = "", betrag_vorhanden: bool = False
) -> tuple[str, str]:
    """Liefert (dokumentart, begruendung). Bei jedem Fehler oder fehlender
    Evidenz fail-closed 'unbestimmt'."""
    try:
        gesamt = "\n".join(teil for teil in (text or "", dateiname or "", betreff or "") if teil).lower()

        for wort in _ZAHLUNGSBELEG_WOERTER:
            if wort in gesamt:
                return (
                    DOKUMENTART_ZAHLUNGSBELEG,
                    f"Als Zahlungsbeleg eingeordnet: Schlüsselwort '{wort}' gefunden.",
                )
        for wort in _ABO_WOERTER:
            if wort in gesamt:
                return (
                    DOKUMENTART_ABO_BESTAETIGUNG,
                    f"Als Abo-Bestätigung eingeordnet: Schlüsselwort '{wort}' gefunden.",
                )
        for wort in _RECHNUNG_WOERTER:
            if wort in gesamt:
                return (
                    DOKUMENTART_RECHNUNG,
                    f"Als Rechnung eingeordnet: Schlüsselwort '{wort}' gefunden.",
                )
        if betrag_vorhanden:
            return (
                DOKUMENTART_SONSTIGER_KOSTENNACHWEIS,
                "Als sonstiger Kostennachweis eingeordnet: Betrag vorhanden, "
                "aber kein eindeutiges Schlüsselwort gefunden.",
            )
        return (
            DOKUMENTART_UNBESTIMMT,
            "Dokumentart unbestimmt: weder Schlüsselwort noch Betrag gefunden. Nichts geraten.",
        )
    except Exception:
        return (
            DOKUMENTART_UNBESTIMMT,
            "Dokumentart unbestimmt: Einordnung nicht möglich. Nichts geraten.",
        )
