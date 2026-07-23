"""Schritt 3 des Agent-Zyklus (Werkzeuge ausfuehren): Text- und Feldextraktion.

Nur fuer Stufe A (PDF mit Textebene) wird tatsaechlich extrahiert. Die
Extraktion ist regelbasiert (Zeilen-Muster), nicht raten: Wird ein Feld nicht
gefunden, bleibt sein Wert None und die Herkunft "fehlt" statt eines
erfundenen Wertes. Das ist bewusst kein allgemeiner Rechnungs-Parser fuer
beliebige Formate, sondern deckt den in der Feasibility-Pruefung bestaetigten
Fall ab: Text-PDFs mit klaren "Label: Wert"-Zeilen (siehe fixtures/erzeugen.py).
"""
from __future__ import annotations

import re

from pypdf import PdfReader

from belegwaechter.modelle import FELDNAMEN, ExtrahiertesFeld

_MUSTER = {
    "referenz": re.compile(r"Rechnung\s+Nr\.?\s*[:.]?\s*(\S+)", re.IGNORECASE),
    "datum": re.compile(r"Datum\s*:\s*(\d{2}\.\d{2}\.\d{4})", re.IGNORECASE),
    "zeitraum": re.compile(
        r"Leistungszeitraum\s*:\s*(\d{2}\.\d{2}\.\d{4}\s*-\s*\d{2}\.\d{2}\.\d{4}|\w+)",
        re.IGNORECASE,
    ),
    "tarif": re.compile(r"Tarif\s*:\s*(.+)", re.IGNORECASE),
    "betrag_waehrung": re.compile(r"Betrag\s*:\s*([\d.,]+)\s*([A-Z]{3})", re.IGNORECASE),
    "waehrung_explizit": re.compile(r"Waehrung\s*:\s*([A-Z]{3})", re.IGNORECASE),
}


def pdf_text_lesen(pdf_pfad: str) -> str:
    """Liest die eingebettete Textebene einer PDF-Datei. Deterministisch fuer
    Text-PDFs (siehe docs/FEASIBILITY_INPUTS.md). Liefert '' wenn keine
    Textebene vorhanden ist (z.B. reines Bild-PDF) statt eine Ausnahme zu
    werfen, damit der Aufrufer das als 'nicht lesbar' werten kann."""
    reader = PdfReader(pdf_pfad)
    teile = [seite.extract_text() or "" for seite in reader.pages]
    return "\n".join(teile)


def felder_aus_text(text: str, herkunft: str = "aus PDF-Text") -> dict[str, ExtrahiertesFeld]:
    """Strukturiert die erste Zeile als Anbieter und sucht die uebrigen
    Felder per Muster. Arbeitet auf reinem Text, unabhaengig von der Quelle
    (PDF-Textebene oder Mailtext). Kein Feld wird erfunden: fehlt ein
    Treffer, wird der Wert None mit Herkunft 'fehlt' gesetzt."""
    zeilen = [z.strip() for z in text.splitlines() if z.strip()]
    ergebnis: dict[str, ExtrahiertesFeld] = {}

    anbieter = zeilen[0] if zeilen else None
    ergebnis["anbieter"] = ExtrahiertesFeld(
        "anbieter", anbieter, herkunft if anbieter else "fehlt"
    )

    treffer_referenz = _MUSTER["referenz"].search(text)
    ergebnis["referenz"] = ExtrahiertesFeld(
        "referenz",
        treffer_referenz.group(1) if treffer_referenz else None,
        herkunft if treffer_referenz else "fehlt",
    )

    treffer_datum = _MUSTER["datum"].search(text)
    ergebnis["datum"] = ExtrahiertesFeld(
        "datum",
        treffer_datum.group(1) if treffer_datum else None,
        herkunft if treffer_datum else "fehlt",
    )

    treffer_zeitraum = _MUSTER["zeitraum"].search(text)
    ergebnis["zeitraum"] = ExtrahiertesFeld(
        "zeitraum",
        " ".join(treffer_zeitraum.group(1).lower().split()) if treffer_zeitraum else None,
        herkunft if treffer_zeitraum else "fehlt",
    )

    treffer_tarif = _MUSTER["tarif"].search(text)
    ergebnis["tarif"] = ExtrahiertesFeld(
        "tarif",
        treffer_tarif.group(1).strip() if treffer_tarif else None,
        herkunft if treffer_tarif else "fehlt",
    )

    treffer_betrag = _MUSTER["betrag_waehrung"].search(text)
    if treffer_betrag:
        betrag_wert = treffer_betrag.group(1)
        waehrung_wert = treffer_betrag.group(2).upper()
    else:
        betrag_wert = None
        waehrung_wert = None
        treffer_waehrung_explizit = _MUSTER["waehrung_explizit"].search(text)
        if treffer_waehrung_explizit:
            waehrung_wert = treffer_waehrung_explizit.group(1).upper()

    ergebnis["betrag"] = ExtrahiertesFeld(
        "betrag", betrag_wert, herkunft if betrag_wert else "fehlt"
    )
    ergebnis["waehrung"] = ExtrahiertesFeld(
        "waehrung", waehrung_wert, herkunft if waehrung_wert else "fehlt"
    )

    for name in FELDNAMEN:
        ergebnis.setdefault(name, ExtrahiertesFeld(name, None, "fehlt"))
    return ergebnis


def felder_aus_pdf_text(text: str) -> dict[str, ExtrahiertesFeld]:
    return felder_aus_text(text, herkunft="aus PDF-Text")


def leere_felder(herkunft: str = "fehlt") -> dict[str, ExtrahiertesFeld]:
    """Felder-Dict fuer Stufe B/C: nichts wird automatisch extrahiert."""
    return {name: ExtrahiertesFeld(name, None, herkunft) for name in FELDNAMEN}
