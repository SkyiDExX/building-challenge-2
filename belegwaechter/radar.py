"""Schritt 3/4 des Agent-Zyklus: erklaerbarer Abo-Vergleich (Wow-Funktion).

Ein Preis gilt nur dann als eindeutig vergleichbar, wenn Anbieter, Tarif,
Waehrung und Abrechnungszeitraum mit der letzten bestaetigten Baseline
desselben Anbieters uebereinstimmen (siehe belegwaechter/bestand.py,
letzte_baseline). Weicht eine dieser Dimensionen ab oder fehlt sie, lautet
die Einschaetzung "Vergleich erforderlich" statt eines falschen Alarms.
Menge/Seats, Netto-/Brutto-Basis, Rabatt und anteilige Abrechnung sind in
diesem Slice keine extrahierten Felder (keine Fixture variiert sie) und
werden daher nicht separat geprueft; das ist eine bewusste, dokumentierte
Grenze des MVP (siehe README, Abschnitt "Bekannte Einschraenkungen").
"""
from __future__ import annotations

from belegwaechter.betraege import betrag_zu_decimal
from belegwaechter.modelle import (
    RADAR_BELEG_FEHLT,
    RADAR_NEU,
    RADAR_STABIL,
    RADAR_VERAENDERT_EINDEUTIG,
    RADAR_VERGLEICH_ERFORDERLICH,
    Beleg,
    RadarEintrag,
)


def radar_bewerten(beleg: Beleg, vorheriger: dict | None) -> RadarEintrag:
    anbieter = beleg.feldwert("anbieter") or "Unbekannt"
    zeitraum = beleg.feldwert("zeitraum") or "unbekannt"
    betrag = beleg.feldwert("betrag")
    waehrung = beleg.feldwert("waehrung") or ""
    betrag_anzeige = f"{betrag} {waehrung}".strip() if betrag else None

    if vorheriger is None:
        return RadarEintrag(
            anbieter=anbieter,
            rhythmus=zeitraum,
            letzter_betrag=betrag_anzeige,
            einschaetzung=RADAR_NEU,
            begruendung=(
                f"Erster erfasster Beleg von {anbieter}. Es liegt noch kein "
                "Vergleichswert vor; die Historie wird ab jetzt aufgebaut."
            ),
        )

    abweichungen = []
    if (beleg.feldwert("tarif") or "") != (vorheriger.get("tarif") or ""):
        abweichungen.append("Tarif")
    if (beleg.feldwert("waehrung") or "") != (vorheriger.get("waehrung") or ""):
        abweichungen.append("Waehrung")
    if (beleg.feldwert("zeitraum") or "") != (vorheriger.get("zeitraum") or ""):
        abweichungen.append("Abrechnungszeitraum")

    if abweichungen:
        dimensionen = ", ".join(abweichungen)
        return RadarEintrag(
            anbieter=anbieter,
            rhythmus=zeitraum,
            letzter_betrag=betrag_anzeige,
            einschaetzung=RADAR_VERGLEICH_ERFORDERLICH,
            begruendung=(
                f"Preisänderung möglich, Vergleich erforderlich: {dimensionen} "
                f"weicht vom vorherigen Beleg ({vorheriger.get('datum')}) ab. "
                "Beträge sind nicht direkt vergleichbar."
            ),
        )

    alt = betrag_zu_decimal(vorheriger.get("betrag"))
    neu = betrag_zu_decimal(betrag)
    if alt is None or neu is None:
        return RadarEintrag(
            anbieter=anbieter,
            rhythmus=zeitraum,
            letzter_betrag=betrag_anzeige,
            einschaetzung=RADAR_VERGLEICH_ERFORDERLICH,
            begruendung="Vergleich erforderlich: Betrag konnte nicht in beiden Belegen eindeutig gelesen werden.",
        )

    if neu == alt:
        return RadarEintrag(
            anbieter=anbieter,
            rhythmus=zeitraum,
            letzter_betrag=betrag_anzeige,
            einschaetzung=RADAR_STABIL,
            begruendung=(
                f"{betrag_anzeige} unveraendert seit dem Beleg vom "
                f"{vorheriger.get('datum')}, gleicher Tarif, gleiche Waehrung, "
                "gleicher Zeitraum."
            ),
        )

    richtung = "teurer" if neu > alt else "guenstiger"
    return RadarEintrag(
        anbieter=anbieter,
        rhythmus=zeitraum,
        letzter_betrag=betrag_anzeige,
        einschaetzung=RADAR_VERAENDERT_EINDEUTIG,
        begruendung=(
            f"{vorheriger.get('betrag')} → {betrag} {waehrung} seit "
            f"{vorheriger.get('datum')}, gleicher Tarif, gleiche Waehrung, "
            f"gleicher Zeitraum. Vergleich eindeutig: {richtung} geworden."
        ),
    )
