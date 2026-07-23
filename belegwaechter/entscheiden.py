"""Schritt 5 des Agent-Zyklus: Handeln (genau eine Entscheidung pro Beleg).

Trifft die endgueltige Entscheidung basierend auf der Quellenklasse des
Ausfuehrungsplans, Dublettenpruefung und Checkliste. Verzweigt bewusst
nicht mehr eigenstaendig anhand von beleg.stufe: die Quellenklasse im Plan
ist bereits die einmal getroffene Einordnung, sie wird hier nicht erneut
unabhaengig bestimmt. Erzeugt einen fallspezifischen Begruendungssatz,
keinen generischen Text.
"""
from __future__ import annotations

from belegwaechter import planen
from belegwaechter.fehlertexte import (
    FEHLERCODE_SIGNATUR_WIDERSPRUCH,
    nutzermeldung,
)
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
    plan: planen.Ausfuehrungsplan,
    checkliste: list[Checkpunkt],
    dublette_treffer: dict | None,
    fehlercode_extraktion: str | None,
) -> tuple[str, str, str | None]:
    """Liefert (ausgang, begruendung, fehlercode). fehlercode ist nur bei
    technischen Fehlern gesetzt (nie bei regulaeren Fachentscheidungen wie
    Review oder Dublette). Der rohe Ausnahmetext einer fehlgeschlagenen
    PDF-Extraktion wird hier nie entgegengenommen: agent.py uebergibt
    ausschliesslich einen stabilen Fehlercode, die Nutzermeldung kommt aus
    fehlertexte.nutzermeldung()."""
    if fehlercode_extraktion:
        return (
            AUSGANG_FEHLGESCHLAGEN,
            f"{nutzermeldung(fehlercode_extraktion)} Diese Datei wurde nicht verarbeitet.",
            fehlercode_extraktion,
        )

    if plan.quellenklasse == planen.QUELLENKLASSE_SIGNATUR_WIDERSPRUCH:
        return (
            AUSGANG_REVIEW,
            "Bitte ansehen: Dateiendung und Dateiinhalt widersprechen sich. "
            "Keine automatische Uebernahme bei widerspruechlicher Signatur.",
            FEHLERCODE_SIGNATUR_WIDERSPRUCH,
        )

    if plan.quellenklasse in (planen.QUELLENKLASSE_BILD_OHNE_OCR, planen.QUELLENKLASSE_UNBEKANNT):
        art = "Bild" if plan.quellenklasse == planen.QUELLENKLASSE_BILD_OHNE_OCR else "Datei"
        return (
            AUSGANG_ORIGINAL_ANFORDERN,
            f"Erfassungsnachweis: als {art} ({beleg.dateityp}) erkannt und angenommen. "
            "Ein Screenshot ist nicht automatisch der unveraenderte Originalbeleg. "
            "Automatische Feldextraktion aus Bildern ist in dieser Version nicht "
            "aktiviert (siehe docs/FEASIBILITY_INPUTS.md). Original wird zur "
            "Uebernahme benoetigt. Original angefordert.",
            None,
        )

    if dublette_treffer:
        if dublette_treffer.get("_grund") == "datei-hash":
            return (
                AUSGANG_DUBLETTE,
                "Doppelt, aussortiert: diese Datei ist byte-identisch mit dem "
                f"bereits uebernommenen Beleg '{dublette_treffer['dateiname']}' "
                "(gleicher Datei-Hash). Nicht doppelt gezaehlt.",
                None,
            )
        referenz = beleg.feldwert("referenz")
        betrag = beleg.feldwert("betrag")
        return (
            AUSGANG_DUBLETTE,
            f"Doppelt, aussortiert: gleiche Rechnungsnummer {referenz} und "
            f"gleicher Betrag {betrag} wie der bereits uebernommene Beleg vom "
            f"{dublette_treffer['datum']}. Nicht doppelt gezaehlt.",
            None,
        )

    if not vollstaendig(checkliste):
        fehlend = ", ".join(fehlende_punkte(checkliste))
        return (
            AUSGANG_REVIEW,
            f"Bitte ansehen: folgende Punkte sind nicht eindeutig erfuellt: "
            f"{fehlend}.",
            None,
        )

    return (
        AUSGANG_UEBERNOMMEN,
        f"Uebernommen: alle {len(checkliste)} Checklisten-Punkte erfuellt, "
        "Original vorhanden.",
        None,
    )
