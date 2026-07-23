"""Wertfreie, pfadfreie Fehlertexte fuer Anzeige und Speicherung.

Roh-Ausnahmetexte (z.B. von pypdf) koennen absolute Pfade, Tracebacks oder
Repository-Namen enthalten und werden deshalb nie direkt gespeichert oder
angezeigt. sicherer_fehler() liefert stattdessen einen stabilen Fehlercode
plus eine feste, wertfreie Nutzermeldung.
"""
from __future__ import annotations

import re

FEHLERCODE_PDF_UNLESBAR = "PDF_UNLESBAR"
FEHLERCODE_PDF_OHNE_TEXT = "PDF_OHNE_TEXT"
FEHLERCODE_MAILTEXT_LEER = "MAILTEXT_LEER"
FEHLERCODE_DATEI_ZU_GROSS = "DATEI_ZU_GROSS"
FEHLERCODE_PFAD_UNSICHER = "PFAD_UNSICHER"
FEHLERCODE_PFAD_NICHT_AUFLOESBAR = "PFAD_NICHT_AUFLOESBAR"
FEHLERCODE_SIGNATUR_WIDERSPRUCH = "SIGNATUR_WIDERSPRUCH"
FEHLERCODE_BETRAG_UNLESBAR = "BETRAG_UNLESBAR"
FEHLERCODE_UNBEKANNTER_FEHLER = "UNBEKANNTER_FEHLER"

_NUTZERMELDUNGEN = {
    FEHLERCODE_PDF_UNLESBAR: "Diese PDF konnte nicht gelesen werden. Bitte das Original erneut ablegen.",
    FEHLERCODE_PDF_OHNE_TEXT: "In dieser PDF ist keine Textebene vorhanden.",
    FEHLERCODE_MAILTEXT_LEER: "Im Mailtext wurde kein lesbarer Inhalt gefunden.",
    FEHLERCODE_DATEI_ZU_GROSS: "Die Datei ueberschreitet die zulaessige Groesse.",
    FEHLERCODE_PFAD_UNSICHER: "Der Dateiname wurde abgelehnt.",
    FEHLERCODE_PFAD_NICHT_AUFLOESBAR: "Die Quelldatei ist nicht mehr auffindbar. Bitte das Original erneut ablegen.",
    FEHLERCODE_SIGNATUR_WIDERSPRUCH: "Dateiendung und Dateiinhalt passen nicht zusammen.",
    FEHLERCODE_BETRAG_UNLESBAR: "Der Betrag konnte nicht eindeutig gelesen werden.",
    FEHLERCODE_UNBEKANNTER_FEHLER: "Die Datei konnte nicht verarbeitet werden.",
}

# Windows-Pfad (C:\..., \\server\share\...), Unix-Pfad, file://-URL,
# "Traceback (most recent call last)"-Header, "File "..." line N" Angaben.
_MUSTER_PFAD_UND_TRACE = re.compile(
    r"([A-Za-z]:[\\/][^\s\"']*"
    r"|\\\\[^\s\"']+"
    r"|/(?:[\w.\-]+/)+[\w.\-]+"
    r"|file://\S*"
    r"|Traceback \(most recent call last\):.*"
    r"|File \"[^\"]*\", line \d+(?:, in \S+)?)",
    re.DOTALL,
)


def nutzermeldung(fehlercode: str) -> str:
    return _NUTZERMELDUNGEN.get(fehlercode, _NUTZERMELDUNGEN[FEHLERCODE_UNBEKANNTER_FEHLER])


def sicherer_fehler(fehlercode: str) -> tuple[str, str]:
    """Liefert (fehlercode, wertfreie Nutzermeldung). Der rohe Ausnahmetext
    wird bewusst nicht entgegengenommen: er darf gar nicht erst in einen
    gespeicherten oder angezeigten Text gelangen."""
    return fehlercode, nutzermeldung(fehlercode)


def bereinigen(text: str) -> str:
    """Netz fuer Texte, die trotzdem einmal einen rohen Ausnahmetext
    enthalten koennten: entfernt Pfade, file://-URLs, Tracebacks und
    Datei/Zeilen-Angaben ohne Nutzwert fuer die Nutzerin."""
    if not text:
        return text
    return _MUSTER_PFAD_UND_TRACE.sub("[entfernt]", text)
