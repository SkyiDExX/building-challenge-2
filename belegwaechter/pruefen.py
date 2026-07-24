"""Schritt 4 des Agent-Zyklus: Bewerten der Vollstaendigkeit (fail-closed).

Die Pflichtangaben sind dokumentartabhaengig: eine Rechnung braucht andere
Angaben als ein Zahlungsbeleg oder eine Abo-Bestaetigung. Jeder Checkpunkt
traegt eine Kategorie:

- kritisch: fehlt der Punkt, ist der Beleg nicht uebernahme- und nicht
  exportfaehig. Eine "im Original nicht vorhanden"-Bestaetigung dokumentiert
  nur die Abwesenheit, erfuellt den Punkt aber NIE.
- pruefenswert: fehlt der Punkt, wird der Beleg trotzdem uebernommen und
  erhaelt eine offene Pruefaufgabe; eine ausdrueckliche
  "nicht vorhanden"-Bestaetigung schliesst den Punkt ab.
- optional: blockiert nie und erzeugt keine Aufgabe.

Fehlende oder widerspruechliche Angaben fuehren zu einem nicht erfuellten
Checkpunkt, nie zu einer Annahme oder einem geratenen Wert.
"""
from __future__ import annotations

from belegwaechter.betraege import betrag_zu_decimal
from belegwaechter.modelle import (
    DOKUMENTART_ABO_BESTAETIGUNG,
    DOKUMENTART_ZAHLUNGSBELEG,
    KATEGORIE_KRITISCH,
    KATEGORIE_OPTIONAL,
    KATEGORIE_PRUEFENSWERT,
    Beleg,
    Checkpunkt,
)

# Matrix je Dokumentart: (Punktname, Feldname, Kategorie). Der Feldname
# "betrag" steht fuer den kombinierten Punkt Betrag+Waehrung. Unbestimmte
# und sonstige Kostennachweise verwenden die Rechnungs-Matrix (fail-closed:
# im Zweifel gelten die strengeren Rechnungsanforderungen).
_MATRIX_RECHNUNG = [
    ("Anbieter erkannt", "anbieter", KATEGORIE_KRITISCH),
    ("Datum erkannt", "datum", KATEGORIE_KRITISCH),
    ("Betrag und Währung erkannt", "betrag", KATEGORIE_KRITISCH),
    ("Rechnungsnummer vorhanden", "referenz", KATEGORIE_PRUEFENSWERT),
    ("Zeitraum eindeutig", "zeitraum", KATEGORIE_PRUEFENSWERT),
    ("Tarif oder Beschreibung vorhanden", "tarif", KATEGORIE_OPTIONAL),
]
_MATRIX_ZAHLUNGSBELEG = [
    ("Anbieter erkannt", "anbieter", KATEGORIE_KRITISCH),
    ("Zahlungsdatum erkannt", "datum", KATEGORIE_KRITISCH),
    ("Betrag und Währung erkannt", "betrag", KATEGORIE_KRITISCH),
    ("Zahlungsreferenz vorhanden", "referenz", KATEGORIE_PRUEFENSWERT),
    ("Zeitraum eindeutig", "zeitraum", KATEGORIE_OPTIONAL),
    ("Tarif oder Beschreibung vorhanden", "tarif", KATEGORIE_OPTIONAL),
]
_MATRIX_ABO_BESTAETIGUNG = [
    ("Anbieter erkannt", "anbieter", KATEGORIE_KRITISCH),
    ("Betrag und Währung erkannt", "betrag", KATEGORIE_PRUEFENSWERT),
    ("Abrechnungsrhythmus erkannt", "zeitraum", KATEGORIE_PRUEFENSWERT),
    ("Produkt oder Tarif erkannt", "tarif", KATEGORIE_OPTIONAL),
    ("Referenz vorhanden", "referenz", KATEGORIE_OPTIONAL),
]

_MATRIX_JE_DOKUMENTART = {
    DOKUMENTART_ZAHLUNGSBELEG: _MATRIX_ZAHLUNGSBELEG,
    DOKUMENTART_ABO_BESTAETIGUNG: _MATRIX_ABO_BESTAETIGUNG,
}

_LESBARKEIT_PUNKT = "Dokument vollständig lesbar"


def checkliste_pruefen(
    beleg: Beleg,
    text_lesbar: bool,
    dokumentart: str | None = None,
    nicht_vorhanden: frozenset[str] | set[str] = frozenset(),
) -> list[Checkpunkt]:
    """Dokumentartabhaengige Vollstaendigkeitspruefung. `nicht_vorhanden`
    enthaelt Feldnamen, die der Nutzer ausdruecklich als im Original nicht
    vorhanden bestaetigt hat: das schliesst NUR pruefenswerte und optionale
    Punkte ab, nie kritische."""
    art = dokumentart or beleg.dokumentart or ""
    matrix = _MATRIX_JE_DOKUMENTART.get(art, _MATRIX_RECHNUNG)

    def hat(feld: str) -> bool:
        if feld == "betrag":
            return (
                betrag_zu_decimal(beleg.feldwert("betrag")) is not None
                and beleg.feldwert("waehrung") not in (None, "")
            )
        return beleg.feldwert(feld) not in (None, "")

    punkte: list[Checkpunkt] = []
    for name, feld, kategorie in matrix:
        vorhanden = hat(feld)
        bestaetigt_fehlend = (
            not vorhanden
            and kategorie != KATEGORIE_KRITISCH
            and feld in nicht_vorhanden
        )
        punkte.append(
            Checkpunkt(
                name=name,
                erfuellt=vorhanden or bestaetigt_fehlend,
                kategorie=kategorie,
                feld=feld,
                nicht_vorhanden=bestaetigt_fehlend,
            )
        )

    # Lesbarkeit ist immer kritisch und nie manuell bestaetigbar: ein
    # unlesbares Original laesst sich nicht durch Eingaben ersetzen.
    punkte.append(
        Checkpunkt(
            name=_LESBARKEIT_PUNKT,
            erfuellt=text_lesbar,
            kategorie=KATEGORIE_KRITISCH,
            feld=None,
        )
    )
    return punkte


def kritisch_vollstaendig(checkliste: list[Checkpunkt]) -> bool:
    """True, wenn alle kritischen Punkte echt erfuellt sind. Eine
    "nicht vorhanden"-Bestaetigung erfuellt kritische Punkte nie (siehe
    checkliste_pruefen); dieser doppelte Guard haelt die Invariante auch
    bei fehlerhaft konstruierten Punkten."""
    return all(
        p.erfuellt and not p.nicht_vorhanden
        for p in checkliste
        if p.kategorie == KATEGORIE_KRITISCH
    )


def fehlende_kritische(checkliste: list[Checkpunkt]) -> list[str]:
    return [
        p.name for p in checkliste
        if p.kategorie == KATEGORIE_KRITISCH and (not p.erfuellt or p.nicht_vorhanden)
    ]


def fehlende_pruefenswerte(checkliste: list[Checkpunkt]) -> list[str]:
    """Pruefenswerte Punkte, die weder erfuellt noch ausdruecklich als
    nicht vorhanden bestaetigt sind."""
    return [
        p.name for p in checkliste
        if p.kategorie == KATEGORIE_PRUEFENSWERT and not p.erfuellt
    ]


def vollstaendig(checkliste: list[Checkpunkt]) -> bool:
    """Historische Signatur: vollstaendig heisst seit der dokumentart-
    abhaengigen Matrix 'alle kritischen Punkte erfuellt'."""
    return kritisch_vollstaendig(checkliste)


def fehlende_punkte(checkliste: list[Checkpunkt]) -> list[str]:
    return [punkt.name for punkt in checkliste if not punkt.erfuellt]
