"""Schritt 3/5 des Agent-Zyklus: Abgleich gegen den Bestand.

Reine Funktionen auf einfachen Verlaufs-Dicts (kein DB-Zugriff hier), damit
der Vergleich isoliert testbar ist. Die aufrufende Seite (agent.py) holt den
bisherigen Bestand aus belegwaechter/speicher.py und uebergibt ihn hier.
"""
from __future__ import annotations

import json

from belegwaechter import kostenprofil
from belegwaechter.modelle import Beleg


def anbieter_schluessel(beleg: Beleg) -> str | None:
    anbieter = beleg.feldwert("anbieter")
    return anbieter.strip().lower() if anbieter else None


def _feldwerte_aus_row(row: dict) -> dict:
    try:
        felder = json.loads(row.get("felder_json") or "{}")
    except (TypeError, ValueError):
        felder = {}
    werte = {name: (f or {}).get("wert") for name, f in felder.items()}
    werte.setdefault("anbieter", row.get("anbieter"))
    werte.setdefault("waehrung", row.get("waehrung"))
    werte.setdefault("tarif", row.get("tarif"))
    return werte


def produkt_basis_schluessel_aus_beleg(beleg: Beleg) -> str | None:
    return kostenprofil.produkt_basis_schluessel(
        {name: f.wert for name, f in beleg.felder.items()}
    )


def produkt_basis_schluessel_aus_row(row: dict) -> str | None:
    """Basis-Schluessel (Produkt+Waehrung) aus einer persistierten
    Belegzeile; aeltere Zeilen ohne Produktfeld fallen auf den Aussteller
    zurueck."""
    return kostenprofil.produkt_basis_schluessel(_feldwerte_aus_row(row))


def ist_dublette(beleg: Beleg, bestand: list[dict]) -> dict | None:
    """Eine Dublette liegt vor, wenn Referenz, Betrag und Datum eines bereits
    uebernommenen Belegs GLEICHER Dokumentart exakt uebereinstimmen.
    Absichtlich referenzbasiert (nicht nur Datei-Hash-basiert), damit auch
    ein erneut ausgestelltes PDF derselben Rechnung erkannt wird. Der
    Dokumentart-Filter stellt sicher, dass Rechnung und Zahlungsbeleg
    desselben Vorgangs (gleiche Referenz, gleicher Betrag, gleiches Datum)
    nie gegenseitig als Dublette gelten."""
    referenz = beleg.feldwert("referenz")
    betrag = beleg.feldwert("betrag")
    datum = beleg.feldwert("datum")
    if not (referenz and betrag and datum):
        return None
    eigene_art = beleg.dokumentart or "unbestimmt"
    for eintrag in bestand:
        if (eintrag.get("dokumentart") or "unbestimmt") != eigene_art:
            continue
        if (
            eintrag["referenz"] == referenz
            and eintrag["betrag"] == betrag
            and eintrag["datum"] == datum
        ):
            return eintrag
    return None


def ist_datei_duplikat(beleg: Beleg, bestand: list[dict]) -> dict | None:
    """Byte-identische Datei (gleicher SHA256-Hash) wie ein bereits
    uebernommener Beleg: ein echtes Datei-Duplikat, unabhaengig von der
    Dokumentart. Bewusst nur gegen uebernommene Belege geprueft, damit der
    Wiederhol-Upload eines Erfassungsnachweises weiterhin 'Original
    anfordern' ergibt statt ploetzlich 'Dublette'."""
    if not beleg.dateihash:
        return None
    for eintrag in bestand:
        if eintrag.get("dateihash") == beleg.dateihash:
            return eintrag
    return None


def anbieter_historie(beleg: Beleg, bestand: list[dict]) -> list[dict]:
    """Filtert den Bestand auf denselben Anbieter. `bestand` liegt bereits in
    Einfuegereihenfolge vor (siehe speicher.bestand_uebernommen), die hier
    NICHT nach der Datum-Textspalte neu sortiert wird: "01.06.2026" ist ein
    TT.MM.JJJJ-String und laesst sich nicht korrekt lexikographisch sortieren."""
    schluessel = anbieter_schluessel(beleg)
    if not schluessel:
        return []
    return [e for e in bestand if e["anbieter_schluessel"] == schluessel]


def produkt_historie(beleg: Beleg, bestand: list[dict]) -> list[dict]:
    """Filtert den Bestand auf dasselbe Produkt (Basis-Schluessel:
    Produkt+Waehrung). Tarif-, Kanal- oder Ausstellerwechsel bleiben in
    derselben Historie und werden vom Preisvergleich explizit als
    'Vergleich erforderlich' gemeldet -- nie stillschweigend als
    identischer Vergleich behandelt."""
    schluessel = produkt_basis_schluessel_aus_beleg(beleg)
    if not schluessel:
        return []
    return [e for e in bestand if produkt_basis_schluessel_aus_row(e) == schluessel]


def letzte_baseline(beleg: Beleg, bestand: list[dict]) -> dict | None:
    """Vergleichsbasis fuer den Preisvergleich ist der neueste Beleg
    desselben PRODUKTPROFILS mit ABGESCHLOSSENEM Preisvergleich
    (baseline_bestaetigt). Ein offener Vergleichsfall wird nie
    stillschweigend als Referenz fuer den naechsten Vergleich verwendet."""
    historie = [e for e in produkt_historie(beleg, bestand) if e.get("baseline_bestaetigt")]
    return historie[-1] if historie else None
