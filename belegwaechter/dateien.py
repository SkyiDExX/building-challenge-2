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
