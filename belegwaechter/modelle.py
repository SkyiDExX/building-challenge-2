"""Datentypen des Belegwaechter-Kerns. Reine Werte-Objekte, keine Logik."""
from __future__ import annotations

from dataclasses import dataclass, field


FELDNAMEN = ["anbieter", "datum", "betrag", "waehrung", "zeitraum", "tarif", "referenz"]

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


@dataclass
class Checkpunkt:
    name: str
    erfuellt: bool


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
    erfasst_am: str = ""
    schritte: list[AgentSchritt] = field(default_factory=list)
    plaene: list = field(default_factory=list)

    def feldwert(self, name: str) -> str | None:
        f = self.felder.get(name)
        return f.wert if f else None


@dataclass
class RadarEintrag:
    anbieter: str
    rhythmus: str
    letzter_betrag: str | None
    einschaetzung: str
    begruendung: str
