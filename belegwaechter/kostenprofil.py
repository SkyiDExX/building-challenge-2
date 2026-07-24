"""Plansteuerbares Werkzeug 'kostenprofil_bestimmen': Produkt- und
Abrechnungsprofil eines Belegs.

Trennt das verwendete Produkt vom rechtlichen Rechnungsaussteller und
bestimmt Abrechnungskanal, Zahlungsdienst, Abrechnungsintervall sowie die
naechste Abbuchung bzw. erwartete Rechnung -- ausschliesslich regelbasiert
und generisch (keine vendorspezifischen Sonderregeln, keine realen
Firmennamen). Unbekanntes bleibt unbekannt; eine "naechste Abbuchung" wird
nur bei ausdruecklich belegtem Zahlungs- oder Verlaengerungsdatum
behauptet, eine "naechste Rechnung erwartet" darf aus dem
Leistungszeitraum abgeleitet werden und ist nie eine Zahlungszusage.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from belegwaechter import datumformat
from belegwaechter.extrahieren import _anbieter_plausibel  # generische Plausibilitaet

INTERVALL_MONATLICH = "monatlich"
INTERVALL_JAEHRLICH = "jährlich"
INTERVALL_UNREGELMAESSIG = "unregelmäßig"
INTERVALL_EINMALIG = "einmalig"
INTERVALL_UNBEKANNT = "unbekannt"
ERLAUBTE_INTERVALLE = (
    INTERVALL_MONATLICH, INTERVALL_JAEHRLICH, INTERVALL_UNREGELMAESSIG,
    INTERVALL_EINMALIG, INTERVALL_UNBEKANNT,
)

HERKUNFT_EXPLIZIT = "explizit genannt"
HERKUNFT_AUS_TARIF = "aus Tarif"
HERKUNFT_AUS_ZEITRAUM = "aus Zeitraum abgeleitet"
HERKUNFT_AUS_HISTORIE = "aus Historie abgeleitet"

PRODUKT_NICHT_EINDEUTIG = "Produkt nicht eindeutig"

# Nur abschliessende Rechtsformzusaetze werden fuer die ANZEIGE entfernt;
# der vollstaendige rechtliche Name bleibt in Pruefnachweis, API-Feld
# rechnungsaussteller, CSV und Audit erhalten. Keine Marken raten.
_RECHTSFORM_MUSTER = re.compile(
    r"[,\s]+(?:Inc\.?|Incorporated|PBC|LLC|L\.L\.C\.|Ltd\.?|Limited|Pty\s+Limited|GmbH|AG)\s*$",
    re.IGNORECASE,
)

_PRODUKT_LABEL_MUSTER = re.compile(
    r"^(?:Produkt|Product|Leistung|Service|Beschreibung|Description|Artikel|Item|Plan|Abo|Subscription)"
    r"\s*:\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)
_KANAL_LABELS = r"(?:Abrechnung\s+über|Abgerechnet\s+über|Billed\s+(?:via|through|by)|Store)"
_ZAHLUNGSDIENST_LABELS = (
    r"(?:Bezahlt\s+über|Bezahlt\s+mit|Paid\s+via|Paid\s+with|Zahlungsmethode"
    r"|Zahlungsart|Payment\s+method|Zahlungsdienst|Funding\s+source)"
)
_KANAL_LABEL_MUSTER = re.compile(
    rf"^{_KANAL_LABELS}\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE
)
_ZAHLUNGSDIENST_LABEL_MUSTER = re.compile(
    rf"^{_ZAHLUNGSDIENST_LABELS}\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE
)
_MERCHANT_LABEL_MUSTER = re.compile(
    r"^(?:H(?:ä|ae)ndler|Merchant|Verk(?:ä|ae)ufer|Seller)\s*:\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)
_BETREFF_PRODUKT_MUSTER = re.compile(
    r"(?:Rechnung|Invoice|Receipt|Zahlungsbest(?:ä|ae)tigung|Abo-Best(?:ä|ae)tigung)"
    r"\s+(?:für|fuer|for|von|from)\s+(.+)$",
    re.IGNORECASE,
)
_TITEL_PRODUKT_MUSTER = re.compile(
    r"^(?:Deine|Ihre|Your)\s+(.+?)[\s-]+(?:Rechnung|Invoice|Abo|Subscription)\b",
    re.IGNORECASE,
)

_INTERVALL_EXPLIZIT = (
    (INTERVALL_MONATLICH, re.compile(
        r"\b(?:monatlich|monthly|per\s+month|pro\s+monat|je\s+monat|/\s*monat|/\s*month|im\s+monatsabo)\b",
        re.IGNORECASE)),
    (INTERVALL_JAEHRLICH, re.compile(
        r"\b(?:jährlich|jaehrlich|annual(?:ly)?|yearly|per\s+year|pro\s+jahr|je\s+jahr|/\s*jahr|/\s*year|im\s+jahresabo)\b",
        re.IGNORECASE)),
    (INTERVALL_EINMALIG, re.compile(
        r"\b(?:einmalig|one[-\s]?time|einmalzahlung)\b", re.IGNORECASE)),
)

# Explizites Verlaengerungs-/Abbuchungs-/Zahlungsdatum: nur solche Treffer
# duerfen eine "naechste Abbuchung" behaupten.
_NAECHSTE_ABBUCHUNG_MUSTER = re.compile(
    r"(?:verl(?:ä|ae)ngert\s+sich\s+am|verl(?:ä|ae)ngerung\s+am|n(?:ä|ae)chste\s+abbuchung\s+am"
    r"|n(?:ä|ae)chste\s+zahlung\s+am|renews\s+on|next\s+(?:charge|payment|billing)\s+(?:date|on))"
    r"\s*:?\s*(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2}|[A-Za-z]+\.?\s+\d{1,2},\s*\d{4})",
    re.IGNORECASE,
)

_DOKUMENTNUMMER_MUSTER = re.compile(r"^[A-Za-z]{0,5}[-_ ]?\d[\d\-_/]*$")

# Ein Dateiname ist nur dann eine Produktquelle, wenn er wie ein reiner
# Produktname aussieht: keine Ziffern, keine Monatsnamen und keine
# Dokument- oder Intervallwoerter ("cloudbasis_juli" oder
# "produkt_jahresrechnung" benennen den Beleg, nicht das Produkt).
_DATEINAME_SPERRWOERTER = (
    "rechnung", "invoice", "receipt", "zahlungsbeleg", "zahlung", "payment",
    "beleg", "quittung", "abo", "subscription", "bestätigung", "bestaetigung",
    "confirmation", "monatlich", "monthly", "jährlich", "jaehrlich", "yearly",
    "annual", "mailtext", "scan", "screenshot", "export", "dokument", "statement",
    "betrag", "amount",
)
_MONATSWORT_MUSTER = re.compile(
    r"\b(?:" + "|".join(sorted(datumformat._MONATE, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_BEGRUESSUNG_MUSTER = re.compile(
    r"^(?:hallo|hi|hey|guten\s+tag|sehr\s+geehrte|dear|liebe[rs]?)\b", re.IGNORECASE
)


@dataclass
class Produktprofil:
    produkt: str | None = None
    produkt_herkunft: str = "fehlt"
    tarif: str | None = None
    rechnungsaussteller: str | None = None
    abrechnungskanal: str | None = None
    zahlungsdienst: str | None = None
    abrechnungsintervall: str = INTERVALL_UNBEKANNT
    intervall_herkunft: str = "fehlt"
    naechste_abbuchung: str | None = None
    naechste_rechnung: str | None = None
    begruendung: str = ""


def anzeige_name(rechtlicher_name: str | None) -> str | None:
    """Entfernt ausschliesslich ABSCHLIESSENDE Rechtsformzusaetze fuer die
    reine Anzeige. Der rechtliche Name selbst wird nie veraendert
    gespeichert."""
    if not rechtlicher_name:
        return None
    bereinigt = rechtlicher_name
    while True:
        neu = _RECHTSFORM_MUSTER.sub("", bereinigt).strip().rstrip(",")
        if neu == bereinigt:
            break
        bereinigt = neu
    return bereinigt or rechtlicher_name


def _produkt_plausibel(kandidat: str) -> bool:
    """Nie als Produkt zulaessig: Begruessungen, ganze Saetze, Datums- oder
    Faelligkeitszeilen, blanke Dokumentart-Woerter, Dokumentnummern und
    Seitenangaben. Nutzt die bestehende generische Anbieter-Plausibilitaet
    plus produktspezifische Sperren."""
    text = kandidat.strip().strip(".")
    if not text:
        return False
    if _BEGRUESSUNG_MUSTER.match(text):
        return False
    if _DOKUMENTNUMMER_MUSTER.match(text):
        return False
    klein = text.lower()
    if klein in ("rechnung", "invoice", "zahlungsbeleg", "receipt", "quittung",
                 "abo-bestätigung", "abo-bestaetigung", "zahlungsbestätigung",
                 "zahlungsbestaetigung", "subscription"):
        return False
    return _anbieter_plausibel(text)


def _erster_plausibler_treffer(muster: re.Pattern, text: str) -> str | None:
    treffer = muster.search(text or "")
    if not treffer:
        return None
    kandidat = treffer.group(1).strip().rstrip(".")
    return kandidat if _produkt_plausibel(kandidat) else None


def _label_wert(labels: str, text: str) -> str | None:
    """Wert zu einem Label, auch wenn er (typisch fuer PDF-Tabellenlayouts)
    erst auf der Folgezeile steht. Der Kandidat muss die generische
    Plausibilitaetspruefung bestehen."""
    muster = re.compile(rf"^[ \t]*{labels}[ \t]*:?[ \t]*(.*)$", re.IGNORECASE | re.MULTILINE)
    treffer = muster.search(text or "")
    if not treffer:
        return None
    kandidat = treffer.group(1).strip().rstrip(".")
    if not kandidat:
        rest = (text or "")[treffer.end():].lstrip("\r\n")
        naechste = rest.splitlines()[0].strip().rstrip(".") if rest.splitlines() else ""
        kandidat = naechste
    return kandidat if kandidat and _produkt_plausibel(kandidat) else None


def _intervall_bestimmen(
    text: str, tarif: str | None, zeitraum: str | None, historien_intervall: str | None
) -> tuple[str, str]:
    """Feste Prioritaet: explizite Formulierung, Tariftext, eindeutig
    abgegrenzter Leistungszeitraum (ca. 27-32 Tage monatlich, ca. 360-370
    Tage jaehrlich, Jahreswechsel inklusive), konsistente Historie, sonst
    unbekannt. Es wird nie eine Abbuchung behauptet."""
    for intervall, muster in _INTERVALL_EXPLIZIT:
        if muster.search(text or ""):
            return intervall, HERKUNFT_EXPLIZIT
    if tarif:
        for intervall, muster in _INTERVALL_EXPLIZIT:
            if muster.search(tarif):
                return intervall, HERKUNFT_AUS_TARIF
    if zeitraum:
        if zeitraum.strip().lower() in ("monatlich", "monthly"):
            return INTERVALL_MONATLICH, HERKUNFT_EXPLIZIT
        if zeitraum.strip().lower() in ("jährlich", "jaehrlich", "yearly", "annual"):
            return INTERVALL_JAEHRLICH, HERKUNFT_EXPLIZIT
        bereich = datumformat._bereich(zeitraum)
        if bereich is not None:
            tage = (bereich[1] - bereich[0]).days
            if 27 <= tage <= 32:
                return INTERVALL_MONATLICH, HERKUNFT_AUS_ZEITRAUM
            if 360 <= tage <= 370:
                return INTERVALL_JAEHRLICH, HERKUNFT_AUS_ZEITRAUM
    if historien_intervall:
        return historien_intervall, HERKUNFT_AUS_HISTORIE
    return INTERVALL_UNBEKANNT, "fehlt"


def historien_intervall(rechnungsdaten_iso: list[str]) -> str | None:
    """Intervall aus mindestens zwei konsistenten historischen Rechnungen
    desselben Produktprofils (ISO-Datumswerte). Liefert None statt zu
    raten, wenn die Abstaende nicht konsistent sind."""
    daten = sorted(d for d in {datumformat.datum_csv(d) for d in rechnungsdaten_iso if d} if d)
    if len(daten) < 2:
        return None
    from datetime import date

    try:
        werte = [date.fromisoformat(d) for d in daten]
    except ValueError:
        return None
    abstaende = [(b - a).days for a, b in zip(werte, werte[1:])]
    if all(27 <= t <= 32 for t in abstaende):
        return INTERVALL_MONATLICH
    if all(360 <= t <= 370 for t in abstaende):
        return INTERVALL_JAEHRLICH
    return INTERVALL_UNREGELMAESSIG


def produktprofil_bestimmen(
    *,
    felder: dict[str, str | None],
    text: str = "",
    dateiname: str = "",
    betreff: str = "",
    mailtext: str = "",
    historien_intervall_wert: str | None = None,
) -> Produktprofil:
    """Bestimmt das Produktprofil aus der vorhandenen Evidenz in fester
    Prioritaet (explizites Produktfeld, Leistungsbezeichnung, Dokumenttitel,
    Dateiname, E-Mail-Betreff, Merchant-Feld, bereinigter
    Rechnungsaussteller). `felder` sind die effektiven Basisfelder
    (anbieter, tarif, zeitraum, ...)."""
    profil = Produktprofil()
    profil.rechnungsaussteller = felder.get("anbieter")
    profil.tarif = felder.get("tarif")
    gesamt = "\n".join(t for t in (text, mailtext) if t)

    produkt_quellen: list[tuple[str | None, str]] = [
        (_erster_plausibler_treffer(_PRODUKT_LABEL_MUSTER, gesamt), "aus Produktfeld"),
        (_erster_plausibler_treffer(_TITEL_PRODUKT_MUSTER, gesamt), "aus Dokumenttitel"),
        (_erster_plausibler_treffer(_BETREFF_PRODUKT_MUSTER, betreff or ""), "aus E-Mail-Betreff"),
        (_erster_plausibler_treffer(_BETREFF_PRODUKT_MUSTER, gesamt), "aus Dokumenttitel"),
        (_erster_plausibler_treffer(_TITEL_PRODUKT_MUSTER, betreff or ""), "aus E-Mail-Betreff"),
        (_dateiname_kandidat(dateiname), "aus Dateiname"),
        (_erster_plausibler_treffer(_MERCHANT_LABEL_MUSTER, gesamt), "aus Händler-Feld"),
    ]
    for kandidat, herkunft in produkt_quellen:
        if kandidat:
            profil.produkt = kandidat
            profil.produkt_herkunft = herkunft
            break
    if not profil.produkt:
        anzeige = anzeige_name(profil.rechnungsaussteller)
        if anzeige and _produkt_plausibel(anzeige):
            profil.produkt = anzeige
            profil.produkt_herkunft = "aus Rechnungsaussteller"

    profil.abrechnungskanal = (
        _erster_plausibler_treffer(_KANAL_LABEL_MUSTER, gesamt)
        or _label_wert(_KANAL_LABELS, gesamt)
    )
    profil.zahlungsdienst = (
        _erster_plausibler_treffer(_ZAHLUNGSDIENST_LABEL_MUSTER, gesamt)
        or _label_wert(_ZAHLUNGSDIENST_LABELS, gesamt)
    )

    profil.abrechnungsintervall, profil.intervall_herkunft = _intervall_bestimmen(
        gesamt, profil.tarif, felder.get("zeitraum"), historien_intervall_wert
    )

    # Naechste Abbuchung nur bei explizit belegtem Datum; eine erwartete
    # naechste Rechnung darf aus dem Ende des Leistungszeitraums abgeleitet
    # werden und ist keine Zahlungszusage.
    treffer_abbuchung = _NAECHSTE_ABBUCHUNG_MUSTER.search(gesamt)
    if treffer_abbuchung:
        profil.naechste_abbuchung = datumformat.datum_csv(treffer_abbuchung.group(1))
    elif felder.get("zeitraum"):
        bereich = datumformat._bereich(felder["zeitraum"])
        if bereich is not None:
            profil.naechste_rechnung = bereich[1].isoformat()

    teile = []
    if profil.produkt:
        teile.append(f"Produkt '{profil.produkt}' ({profil.produkt_herkunft})")
    else:
        teile.append(PRODUKT_NICHT_EINDEUTIG)
    if profil.abrechnungsintervall != INTERVALL_UNBEKANNT:
        teile.append(f"Abrechnung {profil.abrechnungsintervall} ({profil.intervall_herkunft})")
    if profil.naechste_abbuchung:
        teile.append(f"nächste Abbuchung {datumformat.datum_ui(profil.naechste_abbuchung)} (explizit belegt)")
    elif profil.naechste_rechnung:
        teile.append(f"nächste Rechnung erwartet um {datumformat.datum_ui(profil.naechste_rechnung)}")
    profil.begruendung = "; ".join(teile) + "."
    return profil


def _dateiname_kandidat(dateiname: str) -> str | None:
    if not dateiname:
        return None
    stamm = dateiname.rsplit(".", 1)[0]
    stamm = re.sub(r"[_-]+", " ", stamm).strip()
    if re.search(r"\d", stamm) or _MONATSWORT_MUSTER.search(stamm):
        return None
    klein = stamm.lower()
    if any(wort in klein for wort in _DATEINAME_SPERRWOERTER):
        return None
    return stamm if _produkt_plausibel(stamm) else None


def intervall_ableiten(
    text: str, tarif: str | None, zeitraum: str | None
) -> tuple[str, str]:
    """Oeffentlicher Helfer: Abrechnungsintervall aus Text, Tarif und
    Leistungszeitraum (ohne Historie), z.B. fuer die Abo-Uebersicht nach
    manuellen Zeitraum-Korrekturen."""
    return _intervall_bestimmen(text, tarif, zeitraum, None)


def produkt_basis_schluessel(felder: dict[str, str | None]) -> str | None:
    """Basis-Schluessel fuer die Vergleichs-HISTORIE: nur Produkt und
    Waehrung. Tarif-, Kanal- oder Intervallwechsel bleiben in derselben
    Historie sichtbar und werden vom Preisvergleich als 'Vergleich
    erforderlich' gemeldet statt stillschweigend als neues Produkt zu
    gelten."""
    produkt = felder.get("produkt") or felder.get("anbieter")
    if not produkt:
        return None
    return f"{produkt.strip().lower()}|{(felder.get('waehrung') or '').strip().lower()}"


def produkt_schluessel(felder: dict[str, str | None]) -> str | None:
    """Stabiler Gruppierungsschluessel fuer Abo-Historie und Preisvergleich:
    Produkt, Tarif, Waehrung und Abrechnungskanal. Ein Wechsel von
    Aussteller oder Kanal wird nie stillschweigend als identischer
    Vergleich behandelt."""
    produkt = felder.get("produkt") or felder.get("anbieter")
    if not produkt:
        return None
    teile = [
        produkt.strip().lower(),
        (felder.get("tarif") or "").strip().lower(),
        (felder.get("waehrung") or "").strip().lower(),
        (felder.get("abrechnungskanal") or "").strip().lower(),
    ]
    return "|".join(teile)
