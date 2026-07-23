"""Orchestriert den Agent-Zyklus je Eingang: Wahrnehmen, Planen, Werkzeuge
ausfuehren, Bewerten, Handeln, Erklaeren, Erinnern (docs/MASTER_PLAN.md 30b).

Jeder Verarbeitungslauf erzeugt einen echten, protokollierten Schritteverlauf
(mindestens: Eingang erkannt, Quellenqualitaet bewertet, Extraktionsplan
gewaehlt, Felder extrahiert, Vollstaendigkeit geprueft, Bestand abgeglichen,
Abovergleich bewertet, Entscheidung getroffen, Ergebnis gespeichert,
Auditverlauf aktualisiert). Kein Schritt ist eine Ladeanimation ohne echte
Aktion dahinter.
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from belegwaechter import bestand as bestand_modul
from belegwaechter import dateien
from belegwaechter import entscheiden as entscheiden_modul
from belegwaechter import extrahieren
from belegwaechter import radar as radar_modul
from belegwaechter import speicher
from belegwaechter.pruefen import checkliste_pruefen
from belegwaechter.modelle import AUSGANG_UEBERNOMMEN, AgentSchritt, Beleg


def _jetzt() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _schritt(
    beleg: Beleg,
    name: str,
    status: str,
    werkzeug: str,
    begruendung: str,
    start: str,
    ende: str,
    evidenz: str | None = None,
) -> None:
    beleg.schritte.append(
        AgentSchritt(
            schritt=name,
            status=status,
            werkzeug=werkzeug,
            begruendung=begruendung,
            start=start,
            ende=ende,
            evidenz=evidenz,
        )
    )


def verarbeite_datei(
    conn: sqlite3.Connection, lauf_id: str, dateiname: str, inhalt: bytes
) -> Beleg:
    beleg = Beleg(
        id=str(uuid.uuid4()),
        lauf_id=lauf_id,
        dateiname=dateiname,
        dateihash="",
        dateityp="",
        stufe="",
        quellenstatus="",
    )

    # 1. Wahrnehmen: Eingang erkannt
    t0 = _jetzt()
    hash_ = dateien.dateihash(inhalt)
    dateityp = dateien.dateityp_erkennen(inhalt)
    beleg.dateihash = hash_
    beleg.dateityp = dateityp
    _schritt(
        beleg, "Eingang erkannt", "ok", "sha256+magic-bytes",
        f"Dateityp {dateityp} anhand der Dateisignatur erkannt (nicht anhand "
        f"der Dateiendung), Hash {hash_[:12]}... gebildet.",
        t0, _jetzt(),
    )

    # 2. Wahrnehmen: Quellenqualitaet bewertet
    t0 = _jetzt()
    stufe, quellenstatus = dateien.stufe_und_quelle(dateityp)
    beleg.stufe = stufe
    beleg.quellenstatus = quellenstatus
    _schritt(
        beleg, "Quellenqualitaet bewertet", "ok", "input-leiter",
        f"Stufe {stufe} zugeordnet ({quellenstatus}).",
        t0, _jetzt(),
    )

    dateipfad = speicher.EINGANG_DIR / f"{hash_[:12]}_{dateiname}"
    dateipfad.write_bytes(inhalt)

    # 3. Planen: Extraktionsplan gewaehlt
    t0 = _jetzt()
    if stufe == "A":
        plan = "PDF-Textextraktion, Checkliste, Bestandsabgleich, Abovergleich."
    else:
        plan = (
            "Keine automatische Extraktion: OCR-Gate nicht bestanden "
            "(docs/FEASIBILITY_INPUTS.md). Direkt Original anfordern."
        )
    _schritt(beleg, "Extraktionsplan gewaehlt", "ok", "planung", plan, t0, _jetzt())

    # 4. Werkzeuge ausfuehren: Felder extrahiert
    lesefehler: str | None = None
    text_lesbar = False
    if stufe == "A":
        t0 = _jetzt()
        try:
            text = extrahieren.pdf_text_lesen(str(dateipfad))
            text_lesbar = bool(text.strip())
            if text_lesbar:
                beleg.felder = extrahieren.felder_aus_pdf_text(text)
                gefunden = sum(1 for f in beleg.felder.values() if f.wert)
                begr = f"{len(text)} Zeichen gelesen, {gefunden}/{len(beleg.felder)} Felder gefunden."
                status = "ok"
            else:
                beleg.felder = extrahieren.leere_felder()
                begr = "Kein Text in der PDF gefunden (moeglicherweise gescanntes Bild-PDF)."
                status = "fehler"
        except Exception as exc:  # defekte/unlesbare PDF: ehrlich melden, nichts erfinden
            lesefehler = str(exc)
            beleg.felder = extrahieren.leere_felder()
            begr = f"PDF konnte nicht gelesen werden: {lesefehler}"
            status = "fehler"
        _schritt(beleg, "Felder extrahiert", status, "pypdf", begr, t0, _jetzt())
    else:
        t0 = _jetzt()
        beleg.felder = extrahieren.leere_felder()
        _schritt(
            beleg, "Felder extrahiert", "uebersprungen", "keins",
            "Uebersprungen: automatische Feldextraktion aus Bildern ist in "
            "dieser Version nicht aktiviert.",
            t0, _jetzt(),
        )

    # 5. Bewerten: Vollstaendigkeit geprueft
    t0 = _jetzt()
    if stufe == "A" and not lesefehler:
        checkliste = checkliste_pruefen(beleg, text_lesbar=text_lesbar)
        beleg.checkliste = checkliste
        erfuellt = sum(1 for c in checkliste if c.erfuellt)
        _schritt(
            beleg, "Vollstaendigkeit geprueft", "ok", "checkliste-fail-closed",
            f"{erfuellt}/{len(checkliste)} Checklisten-Punkte erfuellt.",
            t0, _jetzt(),
        )
    else:
        checkliste = []
        beleg.checkliste = checkliste
        _schritt(
            beleg, "Vollstaendigkeit geprueft", "uebersprungen", "keins",
            "Uebersprungen: kein lesbarer Originalbeleg vorhanden.",
            t0, _jetzt(),
        )

    # 6. Werkzeuge ausfuehren: Bestand abgeglichen
    bestand = speicher.bestand_uebernommen(conn)
    t0 = _jetzt()
    dublette_treffer: dict | None = None
    if stufe == "A" and not lesefehler:
        dublette_treffer = bestand_modul.ist_dublette(beleg, bestand)
        begr = (
            f"Dublette erkannt: Referenz {beleg.feldwert('referenz')} bereits "
            f"am {dublette_treffer['datum']} uebernommen."
            if dublette_treffer
            else "Keine Dublette im bisherigen Bestand gefunden."
        )
        _schritt(beleg, "Bestand abgeglichen", "ok", "referenz-betrag-datum-abgleich", begr, t0, _jetzt())
    else:
        _schritt(
            beleg, "Bestand abgeglichen", "uebersprungen", "keins",
            "Uebersprungen: kein vergleichbarer Originalbeleg vorhanden.",
            t0, _jetzt(),
        )

    # Handeln: Entscheidung treffen (Grundlage fuer Schritt 7 und 8)
    ausgang, begruendung = entscheiden_modul.entscheiden(beleg, checkliste, dublette_treffer, lesefehler)
    beleg.ausgang = ausgang
    beleg.begruendung = begruendung
    anbieter_schluessel_wert = bestand_modul.anbieter_schluessel(beleg)

    # 7. Bewerten/Handeln: Abovergleich bewertet (nur fuer uebernommene Belege)
    t0 = _jetzt()
    radar_eintrag = None
    if ausgang == AUSGANG_UEBERNOMMEN:
        historie = bestand_modul.anbieter_historie(beleg, bestand)
        vorheriger = historie[-1] if historie else None
        radar_eintrag = radar_modul.radar_bewerten(beleg, vorheriger)
        beleg.radar_hinweis = radar_eintrag.begruendung
        _schritt(beleg, "Abovergleich bewertet", "ok", "radar-vergleichbarkeit", radar_eintrag.begruendung, t0, _jetzt())
    else:
        _schritt(
            beleg, "Abovergleich bewertet", "uebersprungen", "keins",
            "Uebersprungen: Beleg wurde nicht uebernommen, keine Historienaktualisierung.",
            t0, _jetzt(),
        )

    # 8. Handeln: Entscheidung getroffen
    _schritt(beleg, "Entscheidung getroffen", "ok", "entscheidungsregeln", begruendung, _jetzt(), _jetzt())

    # 9. Erinnern: Ergebnis gespeichert
    t0 = _jetzt()
    # Absoluter Pfad, nicht relativ zu REPO_ROOT: runtime/ liegt bei isolierten
    # Tests bewusst in einem temporaeren Verzeichnis ausserhalb des Repos.
    speicher.beleg_speichern(conn, beleg, str(dateipfad), anbieter_schluessel_wert, radar_eintrag)
    _schritt(beleg, "Ergebnis gespeichert", "ok", "sqlite", f"Beleg gespeichert mit Ausgang '{ausgang}'.", t0, _jetzt())

    # 10. Erinnern: Auditverlauf aktualisiert
    t0 = _jetzt()
    speicher.audit_schreiben(conn, aktion=f"Beleg verarbeitet: {ausgang}", objekt=beleg.dateiname, alt=None, neu=begruendung)
    _schritt(beleg, "Auditverlauf aktualisiert", "ok", "audit-log", "Ereignis im Auditverlauf vermerkt.", t0, _jetzt())

    for schritt in beleg.schritte:
        speicher.agent_schritt_speichern(conn, lauf_id, beleg.id, schritt)

    return beleg


def verarbeite_charge(conn: sqlite3.Connection, dateien_liste: list[tuple[str, bytes]]) -> tuple[str, list[Beleg]]:
    """Verarbeitet mehrere Dateien nacheinander im selben Lauf. Die
    Reihenfolge ist bedeutsam: Sie bestimmt, welcher Beleg als 'vorheriger'
    Vergleichswert fuer den Abo-Radar gilt."""
    lauf_id = speicher.neuer_lauf(conn)
    ergebnisse = [verarbeite_datei(conn, lauf_id, name, inhalt) for name, inhalt in dateien_liste]
    return lauf_id, ergebnisse
