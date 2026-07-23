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
QUELLENKLASSE_MAILTEXT = "mailtext"
QUELLENKLASSE_EML_CONTAINER = "eml-container"

# Quellenklassen, deren Belege lesbaren Text liefern und deshalb dieselben
# evidenzgetriebenen Planrevisionen durchlaufen.
_TEXTQUELLEN = (QUELLENKLASSE_TEXT_PDF, QUELLENKLASSE_MAILTEXT)


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


_ZIEL = "Beleg prüfen, einordnen und mit nachvollziehbarer Begründung entscheiden."


def _quellenklasse(stufe: str, endung_konsistent: bool, dateityp: str = "") -> str:
    if not endung_konsistent:
        return QUELLENKLASSE_SIGNATUR_WIDERSPRUCH
    if dateityp == "MAILTEXT":
        return QUELLENKLASSE_MAILTEXT
    if stufe == "A":
        return QUELLENKLASSE_TEXT_PDF
    if stufe == "B":
        return QUELLENKLASSE_BILD_OHNE_OCR
    return QUELLENKLASSE_UNBEKANNT


def _werkzeuge_textquelle(extraktionswerkzeug: str, quelle_beschreibung: str) -> dict[str, Werkzeugschritt]:
    return {
        "extraktion": Werkzeugschritt(
            "extraktion", extraktionswerkzeug, True, f"{quelle_beschreibung}: Text wird gelesen."
        ),
        "dokumentart": Werkzeugschritt(
            "dokumentart", "dokumentart-regeln", True,
            f"{quelle_beschreibung}: Dokumentart wird regelbasiert bestimmt.",
        ),
        "checkliste": Werkzeugschritt(
            "checkliste", "checkliste-fail-closed", True,
            f"{quelle_beschreibung}: Vollständigkeit wird geprüft.",
        ),
        "bestand": Werkzeugschritt(
            "bestand", "hash-und-referenz-abgleich", True,
            f"{quelle_beschreibung}: Duplikat- und Dublettenprüfung möglich.",
        ),
        "radar": Werkzeugschritt(
            "radar", "radar-vergleichbarkeit", True,
            "Vorläufig aktiv, wird nach Evidenz erneut geprüft.",
        ),
    }


def _werkzeuge_inaktiv(begruendung: str) -> dict[str, Werkzeugschritt]:
    return {
        name: Werkzeugschritt(name, "keins", False, begruendung)
        for name in ("extraktion", "dokumentart", "checkliste", "bestand", "radar")
    }


def plan_erstellen(stufe: str, endung_konsistent: bool, dateityp: str = "") -> Ausfuehrungsplan:
    klasse = _quellenklasse(stufe, endung_konsistent, dateityp)

    if klasse == QUELLENKLASSE_TEXT_PDF:
        werkzeuge = _werkzeuge_textquelle("pypdf", "Stufe A")
        pruefungen = ["Vollstaendigkeit (fail-closed)", "Dublettenabgleich", "Abovergleich"]
        aktionen = ["uebernehmen", "review", "dublette-aussortieren"]
        stopbedingungen = ["Datei nicht lesbar", "Pflichtfelder fehlen", "Dublette erkannt"]
    elif klasse == QUELLENKLASSE_MAILTEXT:
        werkzeuge = _werkzeuge_textquelle("mailtext", "Mailtext (Stufe A)")
        pruefungen = ["Vollstaendigkeit (fail-closed)", "Dublettenabgleich", "Abovergleich"]
        aktionen = ["uebernehmen", "review", "dublette-aussortieren"]
        stopbedingungen = ["Kein lesbarer Mailtext", "Pflichtfelder fehlen", "Dublette erkannt"]
    elif klasse == QUELLENKLASSE_BILD_OHNE_OCR:
        werkzeuge = _werkzeuge_inaktiv("Bild ohne aktivierte OCR: kein lesbarer Originalbeleg vorhanden.")
        werkzeuge["extraktion"] = Werkzeugschritt(
            "extraktion", "keins", False,
            "Bild ohne aktivierte OCR: keine automatische Feldextraktion.",
        )
        pruefungen = []
        aktionen = ["original-anfordern"]
        stopbedingungen = ["Kein Original vorhanden"]
    elif klasse == QUELLENKLASSE_SIGNATUR_WIDERSPRUCH:
        werkzeuge = _werkzeuge_inaktiv("Kein vertrauenswürdiger Originalinhalt.")
        werkzeuge["extraktion"] = Werkzeugschritt(
            "extraktion", "keins", False,
            "Dateiendung und Dateisignatur widersprechen sich.",
        )
        pruefungen = []
        aktionen = ["review"]
        stopbedingungen = ["Endung widerspricht Dateisignatur"]
    else:
        werkzeuge = _werkzeuge_inaktiv("Unbekannter Dateityp.")
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
    dokumentart: str | None = None,
) -> Ausfuehrungsplan:
    """Zweite, evidenzgetriebene Revision. Nur relevant fuer Textquellen
    (Text-PDF und Mailtext).

    Ein Lesefehler deaktiviert Dokumentart, Checkliste, Bestandsabgleich UND
    Radar: ohne lesbaren Inhalt kann keines dieser Werkzeuge sinnvoll laufen.
    Eine erkannte Dublette oder eine unvollstaendige Checkliste deaktiviert
    nur das Radar -- Checkliste und Bestandsabgleich sind zu diesem Zeitpunkt
    bereits gelaufen und liefern die Evidenz fuer genau diese Entscheidung.
    Fuer Zahlungsbelege und Abo-Bestaetigungen wird das Radar ebenfalls
    deaktiviert: der Abovergleich vergleicht Rechnungsbetraege, ein
    Zahlungsnachweis darf die Preisbaseline nicht verfaelschen."""
    if plan.quellenklasse not in _TEXTQUELLEN:
        return plan

    neue_werkzeuge = dict(plan.werkzeuge)
    grund = None

    if lesefehler:
        neue_werkzeuge["dokumentart"] = Werkzeugschritt(
            "dokumentart", "keins", False, "Übersprungen: kein lesbarer Inhalt für die Einordnung."
        )
        neue_werkzeuge["checkliste"] = Werkzeugschritt(
            "checkliste", "keins", False, "Übersprungen: kein lesbarer Originalbeleg vorhanden."
        )
        neue_werkzeuge["bestand"] = Werkzeugschritt(
            "bestand", "keins", False, "Übersprungen: kein vergleichbarer Originalbeleg vorhanden."
        )
        neue_werkzeuge["radar"] = Werkzeugschritt(
            "radar", "keins", False, "Übersprungen: Lesefehler, kein auswertbarer Inhalt."
        )
        grund = "Lesefehler: Dokumentart, Checkliste, Bestandsabgleich und Radar deaktiviert."
    elif dublette:
        neue_werkzeuge["radar"] = Werkzeugschritt(
            "radar", "keins", False, "Übersprungen: Beleg ist eine Dublette, keine Historienaktualisierung."
        )
        grund = "Dublette erkannt: Radar deaktiviert."
    elif checkliste_vollstaendig is False:
        neue_werkzeuge["radar"] = Werkzeugschritt(
            "radar", "keins", False, "Übersprungen: Checkliste unvollständig, Automatikpfad endet in Review."
        )
        grund = "Checkliste unvollständig: Radar deaktiviert."
    elif dokumentart in ("zahlungsbeleg", "abo_bestaetigung"):
        neue_werkzeuge["radar"] = Werkzeugschritt(
            "radar", "keins", False,
            "Übersprungen: kein Abovergleich für diese Dokumentart, "
            "sie darf die Preisbaseline nicht verfälschen.",
        )
        grund = f"Dokumentart '{dokumentart}': Radar deaktiviert, keine Baseline-Aktualisierung."

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


_ZIEL_EML = (
    "E-Mail lokal zerlegen, Dokumente einem Kostenvorgang zuordnen und die "
    "nächste Aktivität nur mit Evidenz einordnen."
)


def plan_erstellen_eml() -> Ausfuehrungsplan:
    """Container-Plan fuer eine hochgeladene EML. Der Container ist kein
    Beleg; sein Plan steuert nur die Zerlegung und die Frage, ob der
    Textkoerper ein eigenstaendiger Beleg wird."""
    return Ausfuehrungsplan(
        version=1,
        ziel=_ZIEL_EML,
        quellenklasse=QUELLENKLASSE_EML_CONTAINER,
        werkzeuge={
            "zerlegung": Werkzeugschritt(
                "zerlegung", "mail-parser", True,
                "EML erkannt: Textkörper und Anhänge werden lokal zerlegt.",
            ),
            "textkoerper": Werkzeugschritt(
                "textkoerper", "mailtext-beleg", True,
                "Vorläufig aktiv, wird nach der Zerlegung anhand der Anhänge erneut geprüft.",
            ),
        },
        pruefungen=["Anhaenge per Dateisignatur pruefen", "Textkoerper-Einstufung"],
        moegliche_aktionen=["anhaenge-verarbeiten", "mailtext-als-beleg-verarbeiten"],
        stopbedingungen=["EML nicht lesbar"],
    )


def eml_plan_verfeinern(
    plan: Ausfuehrungsplan, *, anzahl_anhaenge: int, text_vorhanden: bool
) -> Ausfuehrungsplan:
    """Evidenzgetriebene Revision des Container-Plans nach der Zerlegung:
    Sind Anhaenge vorhanden, ist der Textkoerper Begleittext und wird kein
    eigener Beleg; ohne lesbaren Text gibt es nichts zu verarbeiten."""
    if plan.quellenklasse != QUELLENKLASSE_EML_CONTAINER:
        return plan

    grund = None
    if anzahl_anhaenge > 0:
        grund = (
            f"Textkörper ist Begleittext zu {anzahl_anhaenge} "
            f"Anhängen, kein eigenständiger Beleg."
        )
    elif not text_vorhanden:
        grund = "Kein lesbarer Textkörper vorhanden."

    if grund is None:
        return plan

    neue_werkzeuge = dict(plan.werkzeuge)
    neue_werkzeuge["textkoerper"] = Werkzeugschritt(
        "textkoerper", "keins", False, f"Übersprungen: {grund}"
    )
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
