"""Erzeugt den Ausfuehrungsplan eines Belegs: die einzige Steuerungsquelle
fuer den Executor (belegwaechter/agent.py). plan_erstellen entscheidet vor
jeder Werkzeugausfuehrung anhand der Quellenklasse, plan_verfeinern
revidiert danach anhand echter Evidenz (Lesefehler, Dublette,
unvollstaendige Checkliste) und vermerkt den Revisionsgrund. Der Executor
fragt ausschliesslich plan.werkzeug_aktiv(), er verzweigt nirgends erneut
selbst anhand von Stufe oder Dateityp.
"""
from __future__ import annotations

from dataclasses import dataclass, field

QUELLENKLASSE_TEXT_PDF = "text-pdf"
QUELLENKLASSE_BILD_OHNE_OCR = "bild-ohne-ocr"
QUELLENKLASSE_UNBEKANNT = "unbekannt"
QUELLENKLASSE_SIGNATUR_WIDERSPRUCH = "signatur-widerspruch"


@dataclass
class Werkzeugschritt:
    name: str
    werkzeug: str
    ausfuehren: bool
    begruendung: str


@dataclass
class Ausfuehrungsplan:
    version: int
    ziel: str
    quellenklasse: str
    werkzeuge: dict[str, Werkzeugschritt] = field(default_factory=dict)
    pruefungen: list[str] = field(default_factory=list)
    moegliche_aktionen: list[str] = field(default_factory=list)
    stopbedingungen: list[str] = field(default_factory=list)
    revisionsgrund: str | None = None

    def werkzeug_aktiv(self, name: str) -> bool:
        schritt = self.werkzeuge.get(name)
        return bool(schritt and schritt.ausfuehren)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "ziel": self.ziel,
            "quellenklasse": self.quellenklasse,
            "werkzeuge": [
                {
                    "name": w.name,
                    "werkzeug": w.werkzeug,
                    "ausfuehren": w.ausfuehren,
                    "begruendung": w.begruendung,
                }
                for w in self.werkzeuge.values()
            ],
            "pruefungen": self.pruefungen,
            "moegliche_aktionen": self.moegliche_aktionen,
            "stopbedingungen": self.stopbedingungen,
            "revisionsgrund": self.revisionsgrund,
        }


_ZIEL = "Beleg pruefen, einordnen und mit nachvollziehbarer Begruendung entscheiden."


def _quellenklasse(stufe: str, endung_konsistent: bool) -> str:
    if not endung_konsistent:
        return QUELLENKLASSE_SIGNATUR_WIDERSPRUCH
    if stufe == "A":
        return QUELLENKLASSE_TEXT_PDF
    if stufe == "B":
        return QUELLENKLASSE_BILD_OHNE_OCR
    return QUELLENKLASSE_UNBEKANNT


def plan_erstellen(stufe: str, endung_konsistent: bool) -> Ausfuehrungsplan:
    klasse = _quellenklasse(stufe, endung_konsistent)

    if klasse == QUELLENKLASSE_TEXT_PDF:
        werkzeuge = {
            "extraktion": Werkzeugschritt(
                "extraktion", "pypdf", True, "Stufe A: Textebene wird gelesen."
            ),
            "checkliste": Werkzeugschritt(
                "checkliste", "checkliste-fail-closed", True,
                "Stufe A: Vollstaendigkeit wird geprueft.",
            ),
            "bestand": Werkzeugschritt(
                "bestand", "referenz-betrag-datum-abgleich", True,
                "Stufe A: Dublettenpruefung moeglich.",
            ),
            "radar": Werkzeugschritt(
                "radar", "radar-vergleichbarkeit", True,
                "Vorlaeufig aktiv, wird nach Evidenz erneut geprueft.",
            ),
        }
        pruefungen = ["Vollstaendigkeit (fail-closed)", "Dublettenabgleich", "Abovergleich"]
        aktionen = ["uebernehmen", "review", "dublette-aussortieren"]
        stopbedingungen = ["Datei nicht lesbar", "Pflichtfelder fehlen", "Dublette erkannt"]
    elif klasse == QUELLENKLASSE_BILD_OHNE_OCR:
        werkzeuge = {
            "extraktion": Werkzeugschritt(
                "extraktion", "keins", False,
                "Bild ohne aktivierte OCR: keine automatische Feldextraktion.",
            ),
            "checkliste": Werkzeugschritt(
                "checkliste", "keins", False, "Kein lesbarer Originalbeleg vorhanden."
            ),
            "bestand": Werkzeugschritt(
                "bestand", "keins", False, "Kein vergleichbarer Originalbeleg vorhanden."
            ),
            "radar": Werkzeugschritt(
                "radar", "keins", False, "Ohne Original kein Abovergleich moeglich."
            ),
        }
        pruefungen = []
        aktionen = ["original-anfordern"]
        stopbedingungen = ["Kein Original vorhanden"]
    elif klasse == QUELLENKLASSE_SIGNATUR_WIDERSPRUCH:
        werkzeuge = {
            "extraktion": Werkzeugschritt(
                "extraktion", "keins", False,
                "Dateiendung und Dateisignatur widersprechen sich.",
            ),
            "checkliste": Werkzeugschritt(
                "checkliste", "keins", False, "Kein vertrauenswuerdiger Originalinhalt."
            ),
            "bestand": Werkzeugschritt(
                "bestand", "keins", False, "Kein vertrauenswuerdiger Originalinhalt."
            ),
            "radar": Werkzeugschritt(
                "radar", "keins", False, "Kein vertrauenswuerdiger Originalinhalt."
            ),
        }
        pruefungen = []
        aktionen = ["review"]
        stopbedingungen = ["Endung widerspricht Dateisignatur"]
    else:
        werkzeuge = {
            "extraktion": Werkzeugschritt("extraktion", "keins", False, "Unbekannter Dateityp."),
            "checkliste": Werkzeugschritt("checkliste", "keins", False, "Unbekannter Dateityp."),
            "bestand": Werkzeugschritt("bestand", "keins", False, "Unbekannter Dateityp."),
            "radar": Werkzeugschritt("radar", "keins", False, "Unbekannter Dateityp."),
        }
        pruefungen = []
        aktionen = ["original-anfordern"]
        stopbedingungen = ["Dateityp nicht erkannt"]

    return Ausfuehrungsplan(
        version=1,
        ziel=_ZIEL,
        quellenklasse=klasse,
        werkzeuge=werkzeuge,
        pruefungen=pruefungen,
        moegliche_aktionen=aktionen,
        stopbedingungen=stopbedingungen,
    )


def plan_verfeinern(
    plan: Ausfuehrungsplan,
    *,
    lesefehler: bool,
    dublette: bool,
    checkliste_vollstaendig: bool | None,
) -> Ausfuehrungsplan:
    """Zweite, evidenzgetriebene Revision. Nur relevant fuer Text-PDFs.

    Ein Lesefehler deaktiviert Checkliste, Bestandsabgleich UND Radar: ohne
    lesbaren Inhalt kann keines der drei Werkzeuge sinnvoll laufen. Eine
    erkannte Dublette oder eine unvollstaendige Checkliste deaktiviert nur
    das Radar -- Checkliste und Bestandsabgleich sind zu diesem Zeitpunkt
    bereits gelaufen und liefern die Evidenz fuer genau diese Entscheidung."""
    if plan.quellenklasse != QUELLENKLASSE_TEXT_PDF:
        return plan

    neue_werkzeuge = dict(plan.werkzeuge)
    grund = None

    if lesefehler:
        neue_werkzeuge["checkliste"] = Werkzeugschritt(
            "checkliste", "keins", False, "Uebersprungen: kein lesbarer Originalbeleg vorhanden."
        )
        neue_werkzeuge["bestand"] = Werkzeugschritt(
            "bestand", "keins", False, "Uebersprungen: kein vergleichbarer Originalbeleg vorhanden."
        )
        neue_werkzeuge["radar"] = Werkzeugschritt(
            "radar", "keins", False, "Uebersprungen: Lesefehler, kein auswertbarer Inhalt."
        )
        grund = "Lesefehler: Checkliste, Bestandsabgleich und Radar deaktiviert."
    elif dublette:
        neue_werkzeuge["radar"] = Werkzeugschritt(
            "radar", "keins", False, "Uebersprungen: Beleg ist eine Dublette, keine Historienaktualisierung."
        )
        grund = "Dublette erkannt: Radar deaktiviert."
    elif checkliste_vollstaendig is False:
        neue_werkzeuge["radar"] = Werkzeugschritt(
            "radar", "keins", False, "Uebersprungen: Checkliste unvollstaendig, Automatikpfad endet in Review."
        )
        grund = "Checkliste unvollstaendig: Radar deaktiviert."

    if grund is None:
        return plan

    return Ausfuehrungsplan(
        version=plan.version + 1,
        ziel=plan.ziel,
        quellenklasse=plan.quellenklasse,
        werkzeuge=neue_werkzeuge,
        pruefungen=plan.pruefungen,
        moegliche_aktionen=plan.moegliche_aktionen,
        stopbedingungen=plan.stopbedingungen,
        revisionsgrund=grund,
    )
