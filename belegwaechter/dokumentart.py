"""Werkzeug 'dokumentart_bestimmen': regelbasierte, deterministische
Einordnung eines Dokuments in genau eine Dokumentart.

Evidenzquellen werden NACHEINANDER geprueft, nicht zu einem Blob vermischt:
1. Textinhalt des einzelnen Anhangs (bzw. des Mailtext-Belegs selbst)
2. Dateiname des einzelnen Anhangs
3. E-Mail-Betreff und E-Mail-Text -- nur als letzter Fallback

Das verhindert den Fehler, dass der Betreff einer Zahlungsbeleg-Mail eine
darin enthaltene Rechnungs-PDF ebenfalls zum Zahlungsbeleg macht: sobald
der eigene Text des Anhangs ein Schluesselwort liefert, zaehlt ausschliesslich
dieser Treffer.

Innerhalb jeder Quelle gilt die feste Prioritaetsreihenfolge (spezifisch vor
generisch): Zahlungsbeleg-Woerter vor Abo-Woertern vor Rechnungs-Woertern.
Liefert keine Quelle ein Schluesselwort, aber ein Betrag ist vorhanden, ist
es ein sonstiger Kostennachweis; sonst endet die Einordnung fail-closed bei
'unbestimmt'. Es wird nie geraten und nie ein externes Modell befragt.
"""
from __future__ import annotations

import re

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
    "payment receipt",
    "receipt",
)
_ABO_WOERTER = (
    "verlaengert sich",
    "verlängert sich",
    "abo-bestaetigung",
    "abo-bestätigung",
    "abonnement",
)
_RECHNUNG_WOERTER = ("rechnung", "invoice")

# Explizite Rechnungsmerkmale: ein Dokumenttitel ("Rechnung", "Deine
# Rechnung von ...") oder Rechnungsfelder (Rechnungsnummer, Rechnungsdatum).
# Ein solches Merkmal hat Vorrang vor einem beilaeufigen
# Verlaengerungshinweis ("Ihr Abo verlaengert sich") in derselben Quelle.
# Bewusst eng: "Rechnung folgt." oder "Rechnung im Anhang" sind KEINE
# Titel und KEINE Rechnungsfelder -- eine reine Ankuendigung bleibt
# Abo-Bestaetigung.
_RECHNUNG_EXPLIZIT_MUSTER = re.compile(
    r"(?:^|\n)\s*(?:deine|ihre|your)?\s*(?:rechnung|invoice)\s*(?:$|\n)"
    r"|(?:^|\n)\s*(?:deine|ihre)\s+rechnung\s+von\b"
    r"|(?:^|\n)\s*your\s+invoice\s+from\b"
    r"|\brechnungs\s*(?:nummer|datum|nr\.?)\b"
    r"|\brechnung\s+nr\.?\b"
    r"|\binvoice\s+(?:number|no\.?|date)\b",
    re.IGNORECASE,
)


def _cascade(quelle: str) -> tuple[str, str] | None:
    """Prueft eine einzelne Evidenzquelle gegen die feste
    Prioritaetsreihenfolge. Liefert None, wenn diese Quelle kein
    Schluesselwort enthaelt -- der Aufrufer probiert dann die naechste,
    schwaechere Quelle."""
    klein = (quelle or "").lower()
    if not klein:
        return None
    for wort in _ZAHLUNGSBELEG_WOERTER:
        if wort in klein:
            return (
                DOKUMENTART_ZAHLUNGSBELEG,
                f"Schlüsselwort '{wort}' gefunden",
            )
    for wort in _ABO_WOERTER:
        if wort in klein:
            if _RECHNUNG_EXPLIZIT_MUSTER.search(quelle):
                return (
                    DOKUMENTART_RECHNUNG,
                    "explizites Rechnungsmerkmal (Titel oder Rechnungsfeld) hat "
                    f"Vorrang vor dem beiläufigen Verlängerungshinweis '{wort}'",
                )
            return (
                DOKUMENTART_ABO_BESTAETIGUNG,
                f"Schlüsselwort '{wort}' gefunden",
            )
    for wort in _RECHNUNG_WOERTER:
        if wort in klein:
            return (
                DOKUMENTART_RECHNUNG,
                f"Schlüsselwort '{wort}' gefunden",
            )
    return None


def klassifizieren(
    text: str, dateiname: str = "", betreff: str = "", mailtext: str = "",
    betrag_vorhanden: bool = False,
) -> tuple[str, str]:
    """Liefert (dokumentart, begruendung). Bei jedem Fehler oder fehlender
    Evidenz fail-closed 'unbestimmt'. `text` ist der eigene Textinhalt des
    Dokuments (PDF-Anhang oder Mailtext-Beleg) und hat immer Vorrang vor
    Dateiname und E-Mail-Betreff/-Text."""
    try:
        # Feste Evidenzreihenfolge: eigener Textinhalt (inkl. explizitem
        # Dokumenttitel) vor Dateiname vor E-Mail-Betreff vor den uebrigen
        # Schluesselwoertern im Mailtext. Betreff und Mailtext sind bewusst
        # getrennte Stufen: ein expliziter Betreff-Titel wie "Deine Rechnung
        # von ..." gewinnt gegen einen beilaeufigen Verlaengerungssatz, der
        # nur irgendwo im Mailtext steht.
        for quelle, bezeichnung in (
            (text, "Textinhalt des Dokuments"),
            (dateiname, "Dateiname"),
            (betreff, "E-Mail-Betreff, Fallback"),
            (mailtext, "E-Mail-Text, Fallback"),
        ):
            treffer = _cascade(quelle)
            if treffer:
                art, grund = treffer
                artname = {
                    DOKUMENTART_ZAHLUNGSBELEG: "Zahlungsbeleg",
                    DOKUMENTART_ABO_BESTAETIGUNG: "Abo-Bestätigung",
                    DOKUMENTART_RECHNUNG: "Rechnung",
                }[art]
                return art, f"Als {artname} eingeordnet ({bezeichnung}): {grund}."

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
