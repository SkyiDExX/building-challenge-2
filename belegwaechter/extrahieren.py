"""Schritt 3 des Agent-Zyklus (Werkzeuge ausfuehren): Text- und Feldextraktion.

Nur fuer Stufe A (PDF mit Textebene, bzw. Mailtext) wird tatsaechlich
extrahiert. Die Extraktion ist regelbasiert (Zeilen-/Label-Muster), nicht
raten: Wird ein Feld nicht gefunden, bleibt sein Wert None und die Herkunft
"fehlt" statt eines erfundenen Wertes.

Bewusst KEIN allgemeiner Rechnungs-Parser fuer beliebige Layouts. Die
Muster decken zwei Faelle ab: (a) die eigenen synthetischen "Label: Wert"-
Fixtures (siehe fixtures/erzeugen.py) und (b) einen schmalen, deterministischen
Fallback fuer verbreitete deutsche und englische Text-PDF-Rechnungs-/
Zahlungsbeleg-Vorlagen (haeufige Feldbezeichnungen, deutsches und englisches
Datumsformat, ISO- und Symbol-Waehrungsangaben). Keine OCR, keine neue
Abhaengigkeit, keine freie Klassifikation.
"""
from __future__ import annotations

import re

from pypdf import PdfReader

from belegwaechter import steuerzeichen
from belegwaechter.modelle import FELDNAMEN, ExtrahiertesFeld

# Volle UND uebliche dreibuchstabige Abkuerzungen, deterministisch als feste
# Wortliste (kein Raten): reale Vorlagen nutzen beide Formen, z.B. "August"
# oder "Aug". "Sept" zusaetzlich zu "Sep", "März" zusaetzlich ohne Umlaut
# als "Maerz" fuer ASCII-gespeicherte PDF-Textebenen.
_MONATE_EN = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
    "|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)
_MONATE_DE = (
    "Januar|Februar|März|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember"
)

_LABEL_REFERENZ = (
    r"(?:Rechnungsnummer|Invoice\s*number|Belegnummer|Receipt\s*number|Rechnung\s+Nr\.?)"
)
_LABEL_DATUM = (
    r"(?:Ausstellungsdatum|Date\s+of\s+issue|Invoice\s+date|Bezahlt\s+am|Date\s+paid|"
    r"Receipt\s+date|Payment\s+date|Datum)"
)
# Spezifische Betrags-Label (der tatsaechlich faellige/bezahlte Betrag) vor
# generischen Summen-Labels (koennen auch als Zwischensumme frueher im
# Dokument auftauchen) -- zwei getrennte Suchdurchlaeufe statt einer
# gemeinsamen Alternation, damit "Amount due" nicht von einer frueher im
# Text stehenden "Total"-Zwischensumme ueberdeckt wird.
_LABEL_BETRAG_SPEZIFISCH = r"(?:Fälliger\s+Betrag|Amount\s+due|Bezahlter\s+Betrag|Amount\s+paid|Betrag)"
_LABEL_BETRAG_GENERISCH = r"(?:Summe|Total)"

# Drei Wertformate: deutsch numerisch (TT.MM.JJJJ), deutsch ausgeschrieben
# (TT. Monatsname JJJJ, z.B. "5. August 2026") und englisch (Monatsname TT,
# JJJJ, mit optionalem Punkt nach abgekuerztem Monatsnamen).
_WERT_DATUM_DE_NUMERISCH = r"\d{2}\.\d{2}\.\d{4}"
_WERT_DATUM_DE_AUSGESCHRIEBEN = rf"\d{{1,2}}\.\s*(?:{_MONATE_DE})\s+\d{{4}}"
_WERT_DATUM_EN = rf"(?:{_MONATE_EN})\.?\s+\d{{1,2}},\s*\d{{4}}"

# Trenner zwischen zwei Datumswerten eines Zeitraums: Bindestrich,
# Gedankenstrich oder ein einzelnes Nicht-Buchstaben-/Nicht-Ziffern-Zeichen
# (deckt Steuer-/Kontrollzeichen aus Tabellen-Spaltentrennern in der
# PDF-Textebene ab, die weder als Leerzeichen noch als Bindestrich
# extrahiert werden -- bewusst auf maximal 5 Zeichen begrenzt, damit nicht
# versehentlich zwei unabhaengige, weit auseinanderliegende Daten verbunden
# werden).
_ZEITRAUM_TRENNER = r"[^0-9A-Za-z]{1,5}"

_SYMBOL_ZU_ISO = {"€": "EUR", "$": "USD", "£": "GBP"}
_US_BETRAG_MUSTER = re.compile(r"^\d{1,3}(?:,\d{3})*\.\d{2}$")

_MUSTER = {
    "referenz": re.compile(rf"{_LABEL_REFERENZ}\s*[:.]?\s*(\S+)", re.IGNORECASE),
    "datum": re.compile(
        rf"{_LABEL_DATUM}\s*:?\s*({_WERT_DATUM_DE_NUMERISCH}|{_WERT_DATUM_DE_AUSGESCHRIEBEN}|{_WERT_DATUM_EN})",
        re.IGNORECASE,
    ),
    "zeitraum_label": re.compile(
        r"Leistungszeitraum\s*:\s*(\d{2}\.\d{2}\.\d{4}\s*[-–—]\s*\d{2}\.\d{2}\.\d{4}|\w+)",
        re.IGNORECASE,
    ),
    # Bare Datumsbereich ohne vorangestelltes Label: manche reale Vorlagen
    # kodieren den Abrechnungszeitraum als Teil einer Positionsbeschreibung
    # statt als eigenes "Leistungszeitraum:"-Feld.
    "zeitraum_bereich_de": re.compile(
        rf"\d{{2}}\.\d{{2}}\.\d{{4}}{_ZEITRAUM_TRENNER}\d{{2}}\.\d{{2}}\.\d{{4}}"
    ),
    "zeitraum_bereich_en": re.compile(
        rf"(?:{_MONATE_EN})\.?\s+\d{{1,2}}(?:,\s*\d{{4}})?\s*[-–—]\s*(?:{_MONATE_EN})\.?\s+\d{{1,2}},\s*\d{{4}}",
        re.IGNORECASE,
    ),
    "tarif": re.compile(r"Tarif\s*:\s*(.+)", re.IGNORECASE),
    "waehrung_explizit": re.compile(r"Waehrung\s*:\s*([A-Z]{3})", re.IGNORECASE),
}

# Zeilen, die sicher KEIN Anbietername sind: Seitenfusszeilen (koennen am
# Dokumentanfang oder -ende stehen, Position ist vorlagenabhaengig),
# blanke Dokumentart-Woerter und generische Dokumentueberschriften ohne
# Organisationsbezug, reine Datums-/Betrags-/Zeitraumzeilen sowie
# Faelligkeits- und Zahlungszeilen.
_FUSSZEILE_MUSTER = re.compile(
    r"^(?:seite\s*\d+\s*(?:von|/)\s*\d+|page\s*\d+\s*of\s*\d+|\d+\s*of\s*\d+)$",
    re.IGNORECASE,
)
_DOKUMENTART_WORT_MUSTER = re.compile(
    r"^(?:rechnung|invoice|zahlungsbeleg|receipt|payment\s+receipt|quittung"
    r"|abo-?best(?:ä|ae)tigung|subscription\s+confirmation)$",
    re.IGNORECASE,
)
_DOKUMENT_TITEL_MUSTER = re.compile(
    r"^(?:deine|ihre|your)\s+(?:rechnung|invoice|zahlungsbest(?:ä|ae)tigung"
    r"|abo-?best(?:ä|ae)tigung|receipt)\b"
    r"|^(?:rechnung|invoice)\s+(?:nr|no|number|von|from|f(?:ü|ue)r|for)\b",
    re.IGNORECASE,
)
_LABEL_ZEILE_MUSTER = re.compile(
    rf"^(?:{_LABEL_REFERENZ}|{_LABEL_DATUM}|{_LABEL_BETRAG_SPEZIFISCH}|{_LABEL_BETRAG_GENERISCH}"
    rf"|Leistungszeitraum|Tarif|Waehrung)\s*[:.]?",
    re.IGNORECASE,
)
_FAELLIGKEIT_ZEILE_MUSTER = re.compile(
    r"^(?:f(?:ä|ae)llig\s+am|due\s+(?:on|by|date)|bezahlt\s+am|paid\s+on)\b",
    re.IGNORECASE,
)
_DATUM_WERT = rf"(?:{_WERT_DATUM_DE_NUMERISCH}|{_WERT_DATUM_DE_AUSGESCHRIEBEN}|{_WERT_DATUM_EN})"
_DATUM_ZEILE_MUSTER = re.compile(rf"^{_DATUM_WERT}$", re.IGNORECASE)
_ZEITRAUM_ZEILE_MUSTER = re.compile(
    rf"^{_DATUM_WERT}\s*{_ZEITRAUM_TRENNER}\s*{_DATUM_WERT}$", re.IGNORECASE
)
_BETRAG_ZEILE_MUSTER = re.compile(r"^[€$£]?\s*\d[\d.,\s]*\s*(?:[€$£]|[A-Z]{3})?$")


def pdf_text_lesen(pdf_pfad: str) -> str:
    """Liest die eingebettete Textebene einer PDF-Datei. Deterministisch fuer
    Text-PDFs (siehe docs/FEASIBILITY_INPUTS.md). Liefert '' wenn keine
    Textebene vorhanden ist (z.B. reines Bild-PDF) statt eine Ausnahme zu
    werfen, damit der Aufrufer das als 'nicht lesbar' werten kann."""
    reader = PdfReader(pdf_pfad)
    teile = [seite.extract_text() or "" for seite in reader.pages]
    return "\n".join(teile)


def _betrag_de_normalisieren(rohtext: str) -> str:
    """Wandelt eine im US-/englischen Format erkannte Zahl (Komma als
    Tausender-, Punkt als Dezimaltrenner, z.B. '1,234.56' oder '23.00') in
    die im Projekt kanonische deutsche Notation um. Bereits deutsch
    formatierte Werte (Komma als Dezimaltrenner) bleiben unveraendert --
    die Erkennung ist rein strukturell (Endung auf Punkt+zwei Ziffern ohne
    abschliessendes Komma), kein Raten."""
    text = rohtext.strip()
    if _US_BETRAG_MUSTER.match(text):
        return text.replace(",", "\0").replace(".", ",").replace("\0", ".")
    return text


def _betrag_treffer(text: str, label_fragment: str) -> tuple[str | None, str | None]:
    """Sucht Betrag+Waehrung fuer eine Label-Alternation in drei
    Notationsformen: ISO-Code nach der Zahl (bestehend), Symbol vor der
    Zahl, Symbol nach der Zahl. Liefert (betrag, waehrung) oder (None, None)."""
    iso = re.compile(rf"{label_fragment}\s*:?\s*([\d.,]+)\s*([A-Z]{{3}})", re.IGNORECASE)
    treffer = iso.search(text)
    if treffer:
        return _betrag_de_normalisieren(treffer.group(1)), treffer.group(2).upper()

    symbol_vor = re.compile(rf"{label_fragment}\s*:?\s*([€$£])\s*([\d.,]+)", re.IGNORECASE)
    treffer = symbol_vor.search(text)
    if treffer:
        return _betrag_de_normalisieren(treffer.group(2)), _SYMBOL_ZU_ISO[treffer.group(1)]

    symbol_nach = re.compile(rf"{label_fragment}\s*:?\s*([\d.,]+)\s*([€$£])", re.IGNORECASE)
    treffer = symbol_nach.search(text)
    if treffer:
        return _betrag_de_normalisieren(treffer.group(1)), _SYMBOL_ZU_ISO[treffer.group(2)]

    return None, None


def _bereinigter_absender(absender: str) -> str | None:
    """Extrahiert aus einem rohen From-Header ('Name <adresse@beispiel.de>')
    nur den lesbaren Anzeigenamen, ohne E-Mail-Adresse oder spitze Klammern.
    Liefert None, wenn kein brauchbarer Name uebrig bleibt (z.B. nur eine
    bloße E-Mail-Adresse ohne Namen)."""
    if not absender:
        return None
    ohne_adresse = re.sub(r"<[^>]*>", "", absender).strip().strip('"').strip()
    if not ohne_adresse or "@" in ohne_adresse:
        return None
    return ohne_adresse


def _anbieter_kandidat(zeilen: list[str]) -> str | None:
    """Erste Zeile, die keine Seitenfusszeile, kein blankes Dokumentart-Wort,
    keine generische Dokumentueberschrift, keine erkannte Label:Wert-Zeile,
    keine Faelligkeits-/Zahlungszeile und keine reine Datums-, Zeitraum-
    oder Betragszeile ist. Fusszeilen und Organisationszeile koennen je nach
    Vorlage an unterschiedlichen Positionen stehen (siehe
    docs/FEASIBILITY_INPUTS.md); es wird deshalb nie einfach 'erste Zeile'
    angenommen, sondern aktiv nach Nicht-Kandidaten gefiltert. Bleibt keine
    belastbare Organisationszeile uebrig, liefert der Aufrufer den
    bereinigten E-Mail-Absender als transparent gekennzeichneten Fallback."""
    for zeile in zeilen:
        if _FUSSZEILE_MUSTER.match(zeile):
            continue
        if _DOKUMENTART_WORT_MUSTER.match(zeile):
            continue
        if _DOKUMENT_TITEL_MUSTER.match(zeile):
            continue
        if _LABEL_ZEILE_MUSTER.match(zeile):
            continue
        if _FAELLIGKEIT_ZEILE_MUSTER.match(zeile):
            continue
        if _DATUM_ZEILE_MUSTER.match(zeile):
            continue
        if _ZEITRAUM_ZEILE_MUSTER.match(zeile):
            continue
        if _BETRAG_ZEILE_MUSTER.match(zeile):
            continue
        return zeile
    return None


def felder_aus_text(
    text: str, herkunft: str = "aus PDF-Text", absender_fallback: str | None = None
) -> dict[str, ExtrahiertesFeld]:
    """Sucht Anbieter, Referenz, Datum, Betrag/Waehrung, Zeitraum und Tarif
    per Muster. Kein Feld wird erfunden: fehlt ein Treffer, wird der Wert
    None mit Herkunft 'fehlt' gesetzt. `absender_fallback` (roher
    E-Mail-From-Header) wird nur verwendet, wenn im Dokumenttext selbst
    keine belastbare Organisationszeile gefunden wird -- die Herkunft
    lautet dann transparent 'aus E-Mail-Absender', nicht 'aus PDF-Text'."""
    # Zentrale Steuerzeichen-Normalisierung VOR jeder Mustersuche: kein
    # extrahierter Wert kann danach noch C0-Zeichen enthalten, und ein
    # NUL-Spaltentrenner (z.B. mitten in einem Datumsbereich) wird zum
    # sichtbaren Bindestrich statt die Teile kommentarlos zu verkleben.
    text = steuerzeichen.flusstext_bereinigen(text)
    zeilen = [z.strip() for z in text.splitlines() if z.strip()]
    ergebnis: dict[str, ExtrahiertesFeld] = {}

    anbieter = _anbieter_kandidat(zeilen)
    anbieter_herkunft = herkunft
    if not anbieter:
        anbieter = _bereinigter_absender(absender_fallback or "")
        anbieter_herkunft = "aus E-Mail-Absender"
    ergebnis["anbieter"] = ExtrahiertesFeld(
        "anbieter", anbieter, anbieter_herkunft if anbieter else "fehlt"
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

    treffer_zeitraum_label = _MUSTER["zeitraum_label"].search(text)
    if treffer_zeitraum_label:
        zeitraum_roh = treffer_zeitraum_label.group(1)
    else:
        treffer_zeitraum_bereich = (
            _MUSTER["zeitraum_bereich_de"].search(text)
            or _MUSTER["zeitraum_bereich_en"].search(text)
        )
        zeitraum_roh = treffer_zeitraum_bereich.group(0) if treffer_zeitraum_bereich else None
    ergebnis["zeitraum"] = ExtrahiertesFeld(
        "zeitraum",
        " ".join(zeitraum_roh.lower().split()) if zeitraum_roh else None,
        herkunft if zeitraum_roh else "fehlt",
    )

    treffer_tarif = _MUSTER["tarif"].search(text)
    ergebnis["tarif"] = ExtrahiertesFeld(
        "tarif",
        treffer_tarif.group(1).strip() if treffer_tarif else None,
        herkunft if treffer_tarif else "fehlt",
    )

    betrag_wert, waehrung_wert = _betrag_treffer(text, _LABEL_BETRAG_SPEZIFISCH)
    if betrag_wert is None:
        betrag_wert, waehrung_wert = _betrag_treffer(text, _LABEL_BETRAG_GENERISCH)
    if betrag_wert is None:
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
    # Netz auf Feldwert-Ebene: kollabiert Rest-Whitespace und faengt jeden
    # Weg ab, auf dem doch noch ein Steuerzeichen in einen Wert gelangt.
    for feld in ergebnis.values():
        feld.wert = steuerzeichen.feldwert_bereinigen(feld.wert)
        if feld.wert is None and feld.herkunft != "fehlt":
            feld.herkunft = "fehlt"
    return ergebnis


def felder_aus_pdf_text(text: str) -> dict[str, ExtrahiertesFeld]:
    return felder_aus_text(text, herkunft="aus PDF-Text")


def leere_felder(herkunft: str = "fehlt") -> dict[str, ExtrahiertesFeld]:
    """Felder-Dict fuer Stufe B/C: nichts wird automatisch extrahiert."""
    return {name: ExtrahiertesFeld(name, None, herkunft) for name in FELDNAMEN}
