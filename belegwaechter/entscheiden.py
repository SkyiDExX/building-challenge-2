"""Schritt 5 des Agent-Zyklus: Handeln (genau eine Entscheidung pro Beleg).

Trifft die endgueltige Entscheidung basierend auf Stufe, Dublettenpruefung
und Checkliste. Erzeugt einen fallspezifischen Begruendungssatz, keinen
generischen Text.
"""
from __future__ import annotations

from belegwaechter.modelle import (
    AUSGANG_DUBLETTE,
    AUSGANG_FEHLGESCHLAGEN,
    AUSGANG_ORIGINAL_ANFORDERN,
    AUSGANG_REVIEW,
    AUSGANG_UEBERNOMMEN,
    Beleg,
    Checkpunkt,
)
from belegwaechter.pruefen import fehlende_punkte, vollstaendig


def entscheiden(
    beleg: Beleg,
    checkliste: list[Checkpunkt],
    dublette_treffer: dict | None,
    lesefehler: str | None,
) -> tuple[str, str]:
    if lesefehler:
        return (
            AUSGANG_FEHLGESCHLAGEN,
            f"Diese Datei konnte nicht gelesen werden ({lesefehler}). "
            "Sie wurde nicht verarbeitet. Original erneut ablegen.",
        )

    if beleg.stufe in ("B", "C"):
        art = "Bild" if beleg.stufe == "B" else "Datei"
        return (
            AUSGANG_ORIGINAL_ANFORDERN,
            f"Erfassungsnachweis: als {art} ({beleg.dateityp}) erkannt und angenommen. "
            "Ein Screenshot ist nicht automatisch der unveraenderte Originalbeleg. "
            "Automatische Feldextraktion aus Bildern ist in dieser Version nicht "
            "aktiviert (siehe docs/FEASIBILITY_INPUTS.md). Original wird zur "
            "Uebernahme benoetigt. Original angefordert.",
        )

    if dublette_treffer:
        referenz = beleg.feldwert("referenz")
        betrag = beleg.feldwert("betrag")
        return (
            AUSGANG_DUBLETTE,
            f"Doppelt, aussortiert: gleiche Rechnungsnummer {referenz} und "
            f"gleicher Betrag {betrag} wie der bereits uebernommene Beleg vom "
            f"{dublette_treffer['datum']}. Nicht doppelt gezaehlt.",
        )

    if not vollstaendig(checkliste):
        fehlend = ", ".join(fehlende_punkte(checkliste))
        return (
            AUSGANG_REVIEW,
            f"Bitte ansehen: folgende Punkte sind nicht eindeutig erfuellt: "
            f"{fehlend}.",
        )

    return (
        AUSGANG_UEBERNOMMEN,
        f"Uebernommen: alle {len(checkliste)} Checklisten-Punkte erfuellt, "
        "Original vorhanden.",
    )
