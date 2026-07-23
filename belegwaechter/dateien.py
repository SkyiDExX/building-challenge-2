"""Schritt 1 des Agent-Zyklus: Wahrnehmen.

Erkennt den tatsaechlichen Dateityp anhand von Magic-Bytes (nicht anhand der
Dateiendung, die sich faelschen liesse), bildet einen Hash und bestimmt die
Quellenqualitaet (Stufe A/B/C). Reine Standardbibliothek, keine Abhaengigkeit.
"""
from __future__ import annotations

import hashlib

from belegwaechter.modelle import QUELLE_ERFASSUNGSNACHWEIS, QUELLE_ORIGINAL

_PDF_MAGIC = b"%PDF-"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"

_TYP_ZU_ENDUNGEN = {
    "PDF": {"pdf"},
    "PNG": {"png"},
    "JPEG": {"jpg", "jpeg"},
}


def dateihash(inhalt: bytes) -> str:
    return hashlib.sha256(inhalt).hexdigest()


def dateityp_erkennen(inhalt: bytes) -> str:
    """Erkennt den Dateityp anhand der ersten Bytes, unabhaengig vom Dateinamen."""
    if inhalt.startswith(_PDF_MAGIC):
        return "PDF"
    if inhalt.startswith(_PNG_MAGIC):
        return "PNG"
    if inhalt.startswith(_JPEG_MAGIC):
        return "JPEG"
    return "unbekannt"


def stufe_und_quelle(dateityp: str) -> tuple[str, str]:
    """Ordnet den erkannten Dateityp der Input-Leiter aus MASTER_PLAN Abschnitt 6 zu.

    Stufe A (PDF): bevorzugte Originalquelle.
    Stufe B (PNG/JPEG): komfortable Bildquelle, niemals automatisch Original.
    Stufe C (unbekannt): Hinweis ohne verwertbaren Beleginhalt.
    """
    if dateityp == "PDF":
        return "A", QUELLE_ORIGINAL
    if dateityp in ("PNG", "JPEG"):
        return "B", QUELLE_ERFASSUNGSNACHWEIS
    return "C", QUELLE_ERFASSUNGSNACHWEIS


def endung_passt_zu_typ(anzeigename: str, dateityp: str) -> bool:
    """Vergleicht die Dateiendung mit dem per Magic-Bytes erkannten Typ.
    Kein Ersatz fuer die Signaturpruefung, sondern ein zusaetzliches Signal:
    ein Widerspruch (z.B. eine als .pdf benannte PNG-Datei) fuehrt nie zu
    automatischer Uebernahme."""
    erlaubte = _TYP_ZU_ENDUNGEN.get(dateityp)
    if erlaubte is None:
        return True
    _, punkt, endung = anzeigename.rpartition(".")
    if not punkt:
        return False
    return endung.lower() in erlaubte
