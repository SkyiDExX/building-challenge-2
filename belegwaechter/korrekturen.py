"""Effektive Feldwerte: automatische Extraktion plus letzte gueltige
manuelle Korrektur.

Die automatisch erkannten Rohwerte (felder_json) bleiben unveraendert
erhalten; jede manuelle Handlung wird append-only in beleg_korrekturen
historisiert (siehe speicher.korrektur_anhaengen). Dieses Modul bildet
daraus die EINZIGE fachliche Sicht: Checkliste, Entscheidung, API, UI, CSV,
Radar, Baseline und Anbieter-Schluessel arbeiten ausschliesslich mit den
effektiven Werten. 'zuruecksetzen' ist selbst eine append-only Zeile, die
zur automatischen Herkunft zurueckkehrt -- nichts wird geloescht.
"""
from __future__ import annotations

AKTION_SETZEN = "setzen"
AKTION_BESTAETIGEN = "bestaetigen"
AKTION_NICHT_VORHANDEN = "nicht_vorhanden"
AKTION_ZURUECKSETZEN = "zuruecksetzen"
AKTIONEN = (AKTION_SETZEN, AKTION_BESTAETIGEN, AKTION_NICHT_VORHANDEN, AKTION_ZURUECKSETZEN)

HERKUNFT_MANUELL_ERGAENZT = "manuell ergänzt"
HERKUNFT_MANUELL_BESTAETIGT = "manuell bestätigt"
HERKUNFT_NICHT_VORHANDEN = "im Original nicht vorhanden"

# Ausschliesslich fachliche Feldwerte sind korrigierbar -- nie Status,
# Hashes, Pfade oder sonstige Provenienzdaten. `anbieter` ist fachlich der
# Rechnungsaussteller; `naechste_abbuchung` ist nur korrigierbar, wenn sie
# im Original belegt ist (Datum wird serverseitig validiert).
KORRIGIERBARE_FELDER = (
    "anbieter", "referenz", "datum", "betrag", "waehrung", "zeitraum", "tarif",
    "produkt", "abrechnungsintervall", "naechste_abbuchung",
)


def letzte_korrektur_je_feld(korrekturen: list[dict]) -> dict[str, dict]:
    """Letzte Korrektur je Feld (Liste liegt in Einfuegereihenfolge vor)."""
    ergebnis: dict[str, dict] = {}
    for eintrag in korrekturen:
        ergebnis[eintrag["feld"]] = eintrag
    return ergebnis


def effektive_felder(
    auto_felder: dict[str, dict], korrekturen: list[dict]
) -> tuple[dict[str, dict], set[str]]:
    """Liefert (felder, nicht_vorhanden): `felder` ist je Feldname ein Dict
    {"wert", "herkunft"}; `nicht_vorhanden` enthaelt die Feldnamen, deren
    Abwesenheit der Nutzer ausdruecklich bestaetigt hat (schliesst nur
    pruefenswerte/optionale Checkpunkte ab, nie kritische -- siehe
    pruefen.checkliste_pruefen)."""
    letzte = letzte_korrektur_je_feld(korrekturen)
    felder: dict[str, dict] = {}
    nicht_vorhanden: set[str] = set()

    for name, auto in auto_felder.items():
        wert = auto.get("wert")
        herkunft = auto.get("herkunft", "fehlt")
        korrektur = letzte.get(name)
        if korrektur is not None:
            aktion = korrektur["aktion"]
            if aktion == AKTION_SETZEN:
                wert = korrektur["neuer_wert"]
                herkunft = HERKUNFT_MANUELL_ERGAENZT
            elif aktion == AKTION_BESTAETIGEN:
                herkunft = HERKUNFT_MANUELL_BESTAETIGT
            elif aktion == AKTION_NICHT_VORHANDEN:
                wert = None
                herkunft = HERKUNFT_NICHT_VORHANDEN
                nicht_vorhanden.add(name)
            # AKTION_ZURUECKSETZEN: automatischer Wert und Herkunft bleiben.
        felder[name] = {"wert": wert, "herkunft": herkunft}
    return felder, nicht_vorhanden
