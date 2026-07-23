"""Sichere Behandlung von Uploadnamen: Anzeigename vs. Speichername.

Der Anzeigename bleibt lesbar (Umlaute, Unicode) und wird nie fuer
Dateisystemzugriffe verwendet. Der Speichername ist eine harte Whitelist
und Grundlage fuer den tatsaechlichen Dateinamen unter runtime/eingang.
zielpfad() ist die einzige Stelle, die einen Schreibpfad freigibt, und
verweigert jeden Pfad ausserhalb der uebergebenen Basis.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path, PurePosixPath, PureWindowsPath

_RESERVIERTE_WINDOWS_NAMEN = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

_TRANSLITERATION = str.maketrans(
    {
        "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
        "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
    }
)


class UnsichererPfadFehler(Exception):
    """Wird ausgeloest, wenn ein Zielpfad die erlaubte Basis verlassen wuerde."""


def _letztes_segment(roh: str) -> str:
    """Schneidet Pfadanteile ab, unabhaengig davon ob Windows- oder
    Unix-Trenner oder ein Laufwerksbuchstabe im rohen Namen stecken."""
    text = roh.replace("\\", "/")
    segment = text.rsplit("/", 1)[-1]
    if ":" in segment:
        segment = segment.rsplit(":", 1)[-1]
    return segment


def anzeigename(roh: str) -> str:
    """Reiner Anzeigewert: lesbar, mit Unicode, niemals fuer Dateizugriffe."""
    text = unicodedata.normalize("NFC", roh or "")
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")
    text = _letztes_segment(text).strip()
    if not text:
        return "unbenannte Datei"
    return text[:120]


def speichername(roh: str) -> str:
    """Harte Whitelist fuer den tatsaechlichen Dateinamen auf der Platte.
    Arbeitet bewusst auf dem rohen (nur pfad-bereinigten) Namen statt auf
    anzeigename(): dessen Platzhalter "unbenannte Datei" fuer einen leeren
    Namen wuerde sonst selbst wieder bereinigt statt den beleg-Fallback
    auszuloesen."""
    text = _letztes_segment(unicodedata.normalize("NFC", roh or "")).strip()
    stamm, punkt, endung = text.rpartition(".")
    if not punkt:
        stamm, endung = text, ""

    def _bereinigen(teil: str) -> str:
        teil = teil.translate(_TRANSLITERATION)
        teil = unicodedata.normalize("NFKD", teil)
        teil = teil.encode("ascii", "ignore").decode("ascii")
        teil = re.sub(r"[^A-Za-z0-9._-]", "_", teil)
        teil = re.sub(r"_{2,}", "_", teil)
        teil = re.sub(r"\.{2,}", ".", teil)
        return teil.strip("._-")

    stamm_bereinigt = _bereinigen(stamm)[:80]
    endung_bereinigt = _bereinigen(endung)[:16]

    if not stamm_bereinigt:
        stamm_bereinigt = "beleg"

    if stamm_bereinigt.upper() in _RESERVIERTE_WINDOWS_NAMEN:
        stamm_bereinigt = f"datei_{stamm_bereinigt}"

    if endung_bereinigt:
        return f"{stamm_bereinigt}.{endung_bereinigt}"
    return stamm_bereinigt


def zielpfad(basis: Path, name: str) -> Path:
    """Loest den Zielpfad auf und verweigert alles ausserhalb von `basis`."""
    kandidat = (basis / name).resolve()
    basis_aufgeloest = basis.resolve()
    if not kandidat.is_relative_to(basis_aufgeloest):
        raise UnsichererPfadFehler(f"Zielpfad ausserhalb der erlaubten Basis: {name!r}")
    return kandidat


_ERLAUBTE_KEY_ZEICHEN = re.compile(r"^[A-Za-z0-9._/-]+$")


def storage_key_gueltig(key: str) -> bool:
    """Statische Vorpruefung eines Storage-Keys, bevor er aufgeloest wird.
    Lehnt Traversal, absolute Pfade und Laufwerksbuchstaben ab, ohne das
    Dateisystem zu beruehren."""
    if not key or not _ERLAUBTE_KEY_ZEICHEN.match(key):
        return False
    if ".." in PurePosixPath(key).parts:
        return False
    if PurePosixPath(key).is_absolute():
        return False
    if PureWindowsPath(key).is_absolute() or PureWindowsPath(key).drive:
        return False
    if key.startswith("/") or key.startswith("\\"):
        return False
    return True
