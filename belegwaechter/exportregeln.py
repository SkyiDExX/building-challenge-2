"""Zentrale, alleinige Quelle fuer die Exportfaehigkeit eines Belegs.

CSV-Export, Baseline-Freigabe, kostenrelevante Radar-Eintraege und die
UI-Anzeige "Für Export bereit" leiten sich ausschliesslich aus
exportfaehig() ab -- nie allein aus ausgang, dokumentstatus oder
reviewstatus. Regeln:

- Nur Rechnungen und sonstige Kostennachweise koennen exportfaehig sein.
- Zahlungsbelege (Zahlungsnachweis) und Abo-Bestaetigungen (Ankuendigung)
  sind NIE eine eigene Kostenzeile.
- Duplikate, fehlgeschlagene Belege, angeforderte Originale und Belege mit
  kritischer Luecke sind nie exportfaehig.
- Eine offene, nur pruefenswerte Aufgabe (z.B. bestaetigt fehlender
  Zeitraum) verhindert den Export nicht.
"""
from __future__ import annotations

from belegwaechter.modelle import (
    AUSGANG_UEBERNOMMEN,
    DOKUMENTART_RECHNUNG,
    DOKUMENTART_SONSTIGER_KOSTENNACHWEIS,
    KATEGORIE_KRITISCH,
    Checkpunkt,
)
from belegwaechter.pruefen import kritisch_vollstaendig

KOSTENARTEN = {DOKUMENTART_RECHNUNG, DOKUMENTART_SONSTIGER_KOSTENNACHWEIS}


def exportfaehig(dokumentart: str | None, ausgang: str | None, checkliste: list[Checkpunkt]) -> bool:
    if dokumentart not in KOSTENARTEN:
        return False
    # ausgang und Checkliste werden BEIDE geprueft: ein versehentlich auf
    # "uebernommen" stehender Beleg mit kritischer Luecke bleibt gesperrt,
    # ebenso ein kritisch vollstaendiger Beleg mit Dubletten- oder
    # Fehlerausgang.
    if ausgang != AUSGANG_UEBERNOMMEN:
        return False
    return kritisch_vollstaendig(checkliste)


def checkliste_aus_json(eintraege: list[dict]) -> list[Checkpunkt]:
    """Rekonstruiert Checkpunkte aus persistiertem checkliste_json.
    Altbestand ohne Kategorie wird fail-closed als kritisch gelesen."""
    return [
        Checkpunkt(
            name=e.get("name", ""),
            erfuellt=bool(e.get("erfuellt")),
            kategorie=e.get("kategorie", KATEGORIE_KRITISCH),
            feld=e.get("feld"),
            nicht_vorhanden=bool(e.get("nicht_vorhanden")),
        )
        for e in eintraege
    ]


def exportfaehig_zeile(row: dict) -> bool:
    """Exportfaehigkeit direkt aus einer belege-Datenbankzeile (fuer CSV
    und Radar), ueber dieselbe zentrale Regel."""
    import json

    try:
        checkliste = checkliste_aus_json(json.loads(row["checkliste_json"]))
    except (KeyError, TypeError, ValueError):
        return False
    return exportfaehig(row["dokumentart"], row["ausgang"], checkliste)
