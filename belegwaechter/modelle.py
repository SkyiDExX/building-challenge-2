"""Datentypen des Belegwaechter-Kerns. Reine Werte-Objekte, keine Logik."""
from __future__ import annotations

from dataclasses import dataclass, field


# Basisfelder aus der Extraktion plus abgeleitete Produktprofil-Felder
# (kostenprofil.py). `anbieter` bleibt aus Kompatibilitaetsgruenden intern
# der rechtliche bzw. dokumentierte Rechnungsaussteller; `produkt` ist das
# verwendete Produkt, das die Oberflaeche primaer zeigt.
FELDNAMEN = [
    "anbieter", "datum", "betrag", "waehrung", "zeitraum", "tarif", "referenz",
    "produkt", "abrechnungskanal", "zahlungsdienst", "abrechnungsintervall",
    "naechste_abbuchung", "naechste_rechnung",
]

# Belegstatus (Ausgang der Agentenentscheidung)
AUSGANG_UEBERNOMMEN = "uebernommen"
AUSGANG_REVIEW = "review"
AUSGANG_DUBLETTE = "dublette"
AUSGANG_ORIGINAL_ANFORDERN = "original_anfordern"
AUSGANG_FEHLGESCHLAGEN = "fehlgeschlagen"

# Quellenstatus (orthogonal zum Ausgang)
QUELLE_ORIGINAL = "original_vorhanden"
QUELLE_ERFASSUNGSNACHWEIS = "erfassungsnachweis"
QUELLE_HINWEIS = "hinweis"

# Radar-Einschaetzung
RADAR_NEU = "neu"
RADAR_STABIL = "stabil"
RADAR_VERAENDERT_EINDEUTIG = "veraendert_eindeutig"
RADAR_VERGLEICH_ERFORDERLICH = "vergleich_erforderlich"
RADAR_BELEG_FEHLT = "beleg_fehlt"

# Dokumentart: regelbasierte, fail-closed bestimmte Einordnung des Dokuments.
DOKUMENTART_RECHNUNG = "rechnung"
DOKUMENTART_ZAHLUNGSBELEG = "zahlungsbeleg"
DOKUMENTART_ABO_BESTAETIGUNG = "abo_bestaetigung"
DOKUMENTART_SONSTIGER_KOSTENNACHWEIS = "sonstiger_kostennachweis"
DOKUMENTART_UNBESTIMMT = "unbestimmt"

# Naechste Aktivitaet eines Kostenvorgangs: Art und Status sind strukturell
# getrennt, damit "naechste Zahlung" nie mit "naechster Beleg erwartet"
# verwechselt wird. Ein Status wird nur mit expliziter Evidenz gesetzt.
AKTIVITAET_ART_ZAHLUNG = "zahlung"
AKTIVITAET_ART_BELEG = "beleg"
AKTIVITAET_BESTAETIGT = "bestaetigt"
AKTIVITAET_ERWARTET = "erwartet"
AKTIVITAET_UNBEKANNT = "unbekannt"

# Dokumentstatus: orthogonal zu `ausgang`, beschreibt den Paketzustand ohne
# den (moeglicherweise offenen) Abovergleich mitzumeinen.
DOKUMENTSTATUS_VORBEREITET = "vorbereitet"
DOKUMENTSTATUS_ZURUECKGESTELLT = "zurueckgestellt"
DOKUMENTSTATUS_AUSSORTIERT = "aussortiert"
DOKUMENTSTATUS_FEHLGESCHLAGEN = "fehlgeschlagen"

# Reviewstatus: haelt fest, ob eine konkrete, noch offene Pruefaufgabe
# besteht, unabhaengig davon ob der Beleg bereits im vorbereiteten Paket ist.
REVIEWSTATUS_KEINE = "keine"
REVIEWSTATUS_OFFEN = "offen"


@dataclass
class ExtrahiertesFeld:
    name: str
    wert: str | None
    herkunft: str  # "aus PDF-Text" | "aus Bild erfasst" | "fehlt"


# Kategorien der dokumentartabhaengigen Vollstaendigkeitspruefung:
# kritisch fehlend blockiert Uebernahme und Export; pruefenswert fehlend
# erzeugt nur eine offene Pruefaufgabe; optional blockiert nie.
KATEGORIE_KRITISCH = "kritisch"
KATEGORIE_PRUEFENSWERT = "pruefenswert"
KATEGORIE_OPTIONAL = "optional"


@dataclass
class Checkpunkt:
    name: str
    erfuellt: bool
    kategorie: str = KATEGORIE_KRITISCH
    # Feldname, auf den sich der Punkt bezieht (fuer manuelle Korrekturen
    # und die "im Original nicht vorhanden"-Bestaetigung); None fuer
    # feldunabhaengige Punkte wie die Lesbarkeit.
    feld: str | None = None
    # True, wenn der Punkt nur deshalb als erledigt gilt, weil der Nutzer
    # die Angabe ausdruecklich als im Original nicht vorhanden bestaetigt
    # hat. Fuer kritische Punkte ist das nie zulaessig.
    nicht_vorhanden: bool = False


@dataclass
class AgentSchritt:
    schritt: str
    status: str  # "ok" | "uebersprungen" | "fehler"
    werkzeug: str
    begruendung: str
    start: str
    ende: str
    evidenz: str | None = None


@dataclass
class Beleg:
    id: str
    lauf_id: str
    dateiname: str
    dateihash: str
    dateityp: str
    stufe: str  # "A" | "B" | "C"
    quellenstatus: str
    speichername: str = ""
    storage_key: str | None = None
    extraktionsmethode: str = "keine"
    fehlercode: str | None = None
    felder: dict[str, ExtrahiertesFeld] = field(default_factory=dict)
    checkliste: list[Checkpunkt] = field(default_factory=list)
    ausgang: str | None = None
    begruendung: str | None = None
    dokumentstatus: str | None = None
    reviewstatus: str | None = None
    review_aufgabe: str | None = None
    baseline_bestaetigt: bool = False
    betrag_dezimal: str | None = None
    radar_hinweis: str | None = None
    dokumentart: str | None = None
    vorgang_id: str | None = None
    erfasst_am: str = ""
    schritte: list[AgentSchritt] = field(default_factory=list)
    plaene: list = field(default_factory=list)

    def feldwert(self, name: str) -> str | None:
        f = self.felder.get(name)
        return f.wert if f else None


@dataclass
class Vorgang:
    """Ein Kostenvorgang buendelt mehrere Dokumente derselben Quelle (in
    diesem Slice: eine hochgeladene EML). Der EML-Container ist bewusst KEIN
    Beleg; seine Provenienz (Hash, Storage-Key, Mail-Kopfzeilen als rohe
    Anzeigetexte) lebt hier."""

    id: str
    lauf_id: str
    quelle: str  # "eml"
    eml_dateiname: str
    eml_hash: str
    eml_storage_key: str | None
    betreff: str
    absender: str
    mail_datum: str
    naechste_aktivitaet_art: str | None = None  # "zahlung" | "beleg" | None
    naechste_aktivitaet_status: str = AKTIVITAET_UNBEKANNT
    naechste_aktivitaet_datum: str | None = None
    naechste_aktivitaet_begruendung: str = ""


@dataclass
class RadarEintrag:
    anbieter: str
    rhythmus: str
    letzter_betrag: str | None
    einschaetzung: str
    begruendung: str
