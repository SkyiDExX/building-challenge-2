"""Orchestriert den Agent-Zyklus je Eingang: Wahrnehmen, Planen, Werkzeuge
ausfuehren, Bewerten, Handeln, Erklaeren, Erinnern (docs/MASTER_PLAN.md 30b).

Der Ausfuehrungsplan (belegwaechter/planen.py) ist die einzige
Steuerungsquelle fuer Werkzeuge: dieser Executor fragt ausschliesslich
plan.werkzeug_aktiv(...) und verzweigt nirgends erneut eigenstaendig anhand
von beleg.stufe. Jeder Verarbeitungslauf erzeugt einen echten,
protokollierten Schritteverlauf; kein Schritt ist eine Ladeanimation ohne
echte Aktion dahinter.
"""
from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from belegwaechter import bestand as bestand_modul
from belegwaechter import betraege
from belegwaechter import dateien
from belegwaechter import dateinamen
from belegwaechter import dokumentart as dokumentart_modul
from belegwaechter import entscheiden as entscheiden_modul
from belegwaechter import extrahieren
from belegwaechter import fehlertexte
from belegwaechter import mailparser
from belegwaechter import planen
from belegwaechter import radar as radar_modul
from belegwaechter import speicher
from belegwaechter import vorgang as vorgang_modul
from belegwaechter.pruefen import checkliste_pruefen
from belegwaechter.modelle import (
    AUSGANG_DUBLETTE,
    AUSGANG_FEHLGESCHLAGEN,
    AUSGANG_ORIGINAL_ANFORDERN,
    AUSGANG_REVIEW,
    AUSGANG_UEBERNOMMEN,
    DOKUMENTART_ABO_BESTAETIGUNG,
    DOKUMENTART_UNBESTIMMT,
    DOKUMENTART_ZAHLUNGSBELEG,
    DOKUMENTSTATUS_AUSSORTIERT,
    DOKUMENTSTATUS_FEHLGESCHLAGEN,
    DOKUMENTSTATUS_VORBEREITET,
    DOKUMENTSTATUS_ZURUECKGESTELLT,
    RADAR_NEU,
    RADAR_STABIL,
    RADAR_VERAENDERT_EINDEUTIG,
    RADAR_VERGLEICH_ERFORDERLICH,
    REVIEWSTATUS_KEINE,
    REVIEWSTATUS_OFFEN,
    AgentSchritt,
    Beleg,
    Vorgang,
)


class PlanKonsistenzFehler(Exception):
    """Verletzung einer der drei Plan-Executor-Invarianten (siehe
    _plan_und_schritte_pruefen)."""


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


_BEKANNTE_SCHRITTNAMEN_JE_WERKZEUG = {
    "extraktion": "Felder extrahiert",
    "dokumentart": "Dokumentart bestimmt",
    "checkliste": "Vollständigkeit geprüft",
    "bestand": "Bestand abgeglichen",
    "radar": "Abovergleich bewertet",
}


@dataclass
class EmlKontext:
    """Verarbeitungskontext fuer Dokumente, die aus einer EML stammen: die
    Zuordnung zum Kostenvorgang, der Mail-Betreff als zusaetzliches
    Klassifikationssignal und -- nur fuer den Mailtext-Beleg -- der bereits
    dekodierte Text samt Dateityp-Festlegung."""

    vorgang_id: str
    betreff: str = ""
    text_override: str | None = None
    dateityp_override: str | None = None


def _plan_und_schritte_pruefen(plaene: list[planen.Ausfuehrungsplan], schritte: list[AgentSchritt]) -> None:
    """Drei Invarianten zwischen Plan und tatsaechlicher Ausfuehrung, nach
    jedem Lauf geprueft:
    1. kein ausgefuehrtes Werkzeug ohne aktiven Planeintrag
    2. kein aktiver Planeintrag ohne ausgefuehrten oder begruendet
       fehlgeschlagenen Agentenschritt
    3. keine Planaenderung ohne neue Version plus Revisionsgrund
    """
    finaler_plan = plaene[-1]
    schritte_je_name = {s.schritt: s for s in schritte}

    for werkzeug_name, schritt_name in _BEKANNTE_SCHRITTNAMEN_JE_WERKZEUG.items():
        aktiv = finaler_plan.werkzeug_aktiv(werkzeug_name)
        schritt = schritte_je_name.get(schritt_name)
        if schritt is None:
            raise PlanKonsistenzFehler(f"Kein Agentenschritt fuer Werkzeug '{werkzeug_name}' protokolliert.")
        ausgefuehrt = schritt.status in ("ok", "fehler")
        if ausgefuehrt and not aktiv:
            raise PlanKonsistenzFehler(
                f"Werkzeug '{werkzeug_name}' wurde ausgefuehrt, ist im finalen Plan aber inaktiv."
            )
        if aktiv and not ausgefuehrt:
            raise PlanKonsistenzFehler(
                f"Werkzeug '{werkzeug_name}' ist im finalen Plan aktiv, wurde aber nicht ausgefuehrt."
            )

    for index in range(1, len(plaene)):
        vorheriger, aktueller = plaene[index - 1], plaene[index]
        if aktueller.version <= vorheriger.version:
            raise PlanKonsistenzFehler("Planrevision ohne aufsteigende Version.")
        if not aktueller.revisionsgrund:
            raise PlanKonsistenzFehler("Planrevision ohne protokollierten Revisionsgrund.")


def _plan_revidieren(
    beleg: Beleg,
    plaene: list[planen.Ausfuehrungsplan],
    plan: planen.Ausfuehrungsplan,
    *,
    lesefehler: bool,
    dublette: bool,
    checkliste_vollstaendig: bool | None,
    dokumentart: str | None = None,
) -> planen.Ausfuehrungsplan:
    """Wendet planen.plan_verfeinern an, protokolliert die Revision als
    eigenen Agentenschritt und haengt sie an die Planhistorie an, falls sich
    tatsaechlich etwas geaendert hat."""
    neuer_plan = planen.plan_verfeinern(
        plan, lesefehler=lesefehler, dublette=dublette,
        checkliste_vollstaendig=checkliste_vollstaendig, dokumentart=dokumentart,
    )
    if neuer_plan.version == plan.version:
        return plan
    t0 = _jetzt()
    _schritt(beleg, "Ausführungsplan aktualisiert", "ok", "planung", neuer_plan.revisionsgrund, t0, _jetzt())
    plaene.append(neuer_plan)
    return neuer_plan


def _status_ableiten(
    ausgang: str, fehlende_checkliste: list[str], radar_einschaetzung: str | None
) -> tuple[str, str, str | None]:
    """Leitet die drei orthogonalen Statusfelder aus dem fachlichen Ausgang
    und der Radar-Einschaetzung ab. `ausgang` bleibt die primaere,
    ausfuehrliche Fachentscheidung (siehe entscheiden.py); dokumentstatus/
    reviewstatus/review_aufgabe machen zusaetzlich explizit, ob ein
    vorbereiteter Beleg trotzdem noch eine offene Pruefaufgabe hat -- ein
    unklarer Preisvergleich darf den Beleg ins Paket aufnehmen, ohne den
    Vergleich als abgeschlossen darzustellen."""
    if ausgang == AUSGANG_UEBERNOMMEN:
        if radar_einschaetzung == RADAR_VERGLEICH_ERFORDERLICH:
            return DOKUMENTSTATUS_VORBEREITET, REVIEWSTATUS_OFFEN, "Preisänderung prüfen"
        return DOKUMENTSTATUS_VORBEREITET, REVIEWSTATUS_KEINE, None
    if ausgang == AUSGANG_DUBLETTE:
        return DOKUMENTSTATUS_AUSSORTIERT, REVIEWSTATUS_KEINE, None
    if ausgang == AUSGANG_ORIGINAL_ANFORDERN:
        return DOKUMENTSTATUS_ZURUECKGESTELLT, REVIEWSTATUS_OFFEN, "Original anfordern"
    if ausgang == AUSGANG_REVIEW:
        if fehlende_checkliste:
            aufgabe = "Fehlende Angaben ergänzen: " + ", ".join(fehlende_checkliste)
        else:
            aufgabe = "Dateiendung und Dateiinhalt widersprechen sich, bitte prüfen."
        return DOKUMENTSTATUS_ZURUECKGESTELLT, REVIEWSTATUS_OFFEN, aufgabe
    if ausgang == AUSGANG_FEHLGESCHLAGEN:
        return DOKUMENTSTATUS_FEHLGESCHLAGEN, REVIEWSTATUS_OFFEN, "Original erneut ablegen"
    return DOKUMENTSTATUS_ZURUECKGESTELLT, REVIEWSTATUS_OFFEN, "Beleg prüfen"


def verarbeite_datei(
    conn: sqlite3.Connection, lauf_id: str, roher_dateiname: str, inhalt: bytes,
    kontext: EmlKontext | None = None,
) -> Beleg:
    anzeigename = dateinamen.anzeigename(roher_dateiname)
    beleg = Beleg(
        id=str(uuid.uuid4()),
        lauf_id=lauf_id,
        dateiname=anzeigename,
        dateihash="",
        dateityp="",
        stufe="",
        quellenstatus="",
    )
    if kontext is not None:
        beleg.vorgang_id = kontext.vorgang_id

    # 1. Wahrnehmen: Eingang erkannt
    t0 = _jetzt()
    hash_ = dateien.dateihash(inhalt)
    if kontext is not None and kontext.dateityp_override:
        dateityp = kontext.dateityp_override
    else:
        dateityp = dateien.dateityp_erkennen(inhalt)
    beleg.dateihash = hash_
    beleg.dateityp = dateityp
    _schritt(
        beleg, "Eingang erkannt", "ok", "sha256+magic-bytes",
        f"Dateityp {dateityp} anhand der Dateisignatur erkannt (nicht anhand "
        f"der Dateiendung), Hash {hash_[:12]}... gebildet.",
        t0, _jetzt(),
    )

    # 2. Wahrnehmen: Quellenqualität bewertet
    t0 = _jetzt()
    stufe, quellenstatus = dateien.stufe_und_quelle(dateityp)
    beleg.stufe = stufe
    beleg.quellenstatus = quellenstatus
    _schritt(
        beleg, "Quellenqualität bewertet", "ok", "input-leiter",
        f"Stufe {stufe} zugeordnet ({quellenstatus}).",
        t0, _jetzt(),
    )

    endung_konsistent = dateien.endung_passt_zu_typ(anzeigename, dateityp)

    # 3. Planen: Ausführungsplan erstellt (Version 1, einzige Steuerungsquelle)
    t0 = _jetzt()
    plan = planen.plan_erstellen(stufe, endung_konsistent, dateityp=dateityp)
    plaene = [plan]
    _schritt(
        beleg, "Ausführungsplan erstellt", "ok", "planung",
        f"Quellenklasse '{plan.quellenklasse}'. Aktive Werkzeuge: "
        + ", ".join(w.name for w in plan.werkzeuge.values() if w.ausfuehren) or "keine",
        t0, _jetzt(),
    )

    interner_speichername = dateinamen.speichername(roher_dateiname)
    beleg.speichername = interner_speichername
    interner_dateiname = f"{hash_[:12]}_{interner_speichername}"

    pfad_unsicher = False
    try:
        zielpfad = dateinamen.zielpfad(speicher.EINGANG_DIR, interner_dateiname)
    except dateinamen.UnsichererPfadFehler:
        pfad_unsicher = True
        zielpfad = None

    if pfad_unsicher:
        # In der Praxis unerreichbar: dateinamen.speichername() entfernt
        # bereits jedes Trennzeichen und jeden Laufwerksbuchstaben, bevor
        # ueberhaupt ein Zielpfad gebildet wird. Dies ist ausschliesslich
        # ein Netz gegen einen hypothetischen Fehler in der Sanitisierung;
        # betrifft nur diese eine Datei, nicht die restliche Charge.
        beleg.storage_key = None
        beleg.fehlercode = fehlertexte.FEHLERCODE_PFAD_UNSICHER
        beleg.ausgang = AUSGANG_FEHLGESCHLAGEN
        beleg.begruendung = f"{fehlertexte.nutzermeldung(fehlertexte.FEHLERCODE_PFAD_UNSICHER)} Diese Datei wurde nicht verarbeitet."
        beleg.dokumentstatus = DOKUMENTSTATUS_FEHLGESCHLAGEN
        beleg.reviewstatus = REVIEWSTATUS_OFFEN
        beleg.review_aufgabe = "Datei mit anderem Namen erneut hochladen."
        t0 = _jetzt()
        beleg.dokumentart = DOKUMENTART_UNBESTIMMT
        for name in _BEKANNTE_SCHRITTNAMEN_JE_WERKZEUG:
            _schritt(
                beleg, _BEKANNTE_SCHRITTNAMEN_JE_WERKZEUG[name], "uebersprungen", "keins",
                "Uebersprungen: unsicherer Dateiname abgelehnt.", t0, _jetzt(),
            )
        _schritt(beleg, "Entscheidung getroffen", "ok", "entscheidungsregeln", beleg.begruendung, t0, _jetzt())
        speicher.beleg_speichern(conn, beleg, None, None)
        speicher.audit_schreiben(conn, aktion=f"Beleg verarbeitet: {beleg.ausgang}", objekt=beleg.dateiname, alt=None, neu=beleg.begruendung)
        speicher.plan_speichern(conn, lauf_id, beleg.id, plan)
        for schritt in beleg.schritte:
            speicher.agent_schritt_speichern(conn, lauf_id, beleg.id, schritt)
        return beleg

    zielpfad.write_bytes(inhalt)
    beleg.storage_key = speicher.storage_key_fuer(interner_dateiname)

    # 4. Werkzeuge ausfuehren: Felder extrahiert. Die Implementierung waehlt
    # der Plan ueber den Werkzeugnamen (pypdf oder mailtext), nicht der
    # Executor anhand einer erneuten Typ-Verzweigung.
    fehlercode_extraktion: str | None = None
    text_lesbar = False
    extrahierter_text = ""
    if plan.werkzeug_aktiv("extraktion"):
        werkzeugname = plan.werkzeuge["extraktion"].werkzeug
        t0 = _jetzt()
        try:
            if werkzeugname == "mailtext":
                text = kontext.text_override if (kontext and kontext.text_override) else ""
                fehlercode_leer = fehlertexte.FEHLERCODE_MAILTEXT_LEER
                methode = "mailtext"
            else:
                text = extrahieren.pdf_text_lesen(str(zielpfad))
                fehlercode_leer = fehlertexte.FEHLERCODE_PDF_OHNE_TEXT
                methode = "pypdf-textlayer"
            text_lesbar = bool(text.strip())
            if text_lesbar:
                herkunft = "aus Mailtext" if werkzeugname == "mailtext" else "aus PDF-Text"
                beleg.felder = extrahieren.felder_aus_text(text, herkunft=herkunft)
                beleg.extraktionsmethode = methode
                extrahierter_text = text
                gefunden = sum(1 for f in beleg.felder.values() if f.wert)
                begr = f"{len(text)} Zeichen gelesen, {gefunden}/{len(beleg.felder)} Felder gefunden."
                status = "ok"
            else:
                beleg.felder = extrahieren.leere_felder()
                beleg.extraktionsmethode = "keine"
                fehlercode_extraktion = fehlercode_leer
                begr = fehlertexte.nutzermeldung(fehlercode_extraktion)
                status = "fehler"
        except Exception:
            beleg.felder = extrahieren.leere_felder()
            beleg.extraktionsmethode = "keine"
            fehlercode_extraktion = fehlertexte.FEHLERCODE_PDF_UNLESBAR
            begr = fehlertexte.nutzermeldung(fehlercode_extraktion)
            status = "fehler"
        _schritt(beleg, "Felder extrahiert", status, werkzeugname, begr, t0, _jetzt())
    else:
        t0 = _jetzt()
        beleg.felder = extrahieren.leere_felder()
        beleg.extraktionsmethode = (
            "keine-ocr" if plan.quellenklasse == planen.QUELLENKLASSE_BILD_OHNE_OCR else "keine"
        )
        werkzeugschritt = plan.werkzeuge["extraktion"]
        _schritt(
            beleg, "Felder extrahiert", "uebersprungen", werkzeugschritt.werkzeug,
            werkzeugschritt.begruendung, t0, _jetzt(),
        )

    # Planrevision (Teil 1): ein Lesefehler deaktiviert Checkliste, Bestand
    # und Radar gleichermassen -- angewendet, bevor plan.werkzeug_aktiv()
    # fuer die naechsten beiden Schritte abgefragt wird.
    if fehlercode_extraktion:
        plan = _plan_revidieren(
            beleg, plaene, plan, lesefehler=True, dublette=False, checkliste_vollstaendig=None
        )

    # 4b. Werkzeuge ausfuehren: Dokumentart bestimmt (regelbasiert, fail-closed)
    if plan.werkzeug_aktiv("dokumentart"):
        t0 = _jetzt()
        art, begr_art = dokumentart_modul.klassifizieren(
            extrahierter_text,
            dateiname=beleg.dateiname,
            betreff=kontext.betreff if kontext else "",
            betrag_vorhanden=bool(beleg.feldwert("betrag")),
        )
        beleg.dokumentart = art
        _schritt(beleg, "Dokumentart bestimmt", "ok", "dokumentart-regeln", begr_art, t0, _jetzt())
    else:
        beleg.dokumentart = DOKUMENTART_UNBESTIMMT
        t0 = _jetzt()
        werkzeugschritt = plan.werkzeuge["dokumentart"]
        _schritt(beleg, "Dokumentart bestimmt", "uebersprungen", "keins", werkzeugschritt.begruendung, t0, _jetzt())

    # 5. Bewerten: Vollständigkeit geprüft
    checkliste_vollstaendig: bool | None = None
    if plan.werkzeug_aktiv("checkliste"):
        t0 = _jetzt()
        checkliste = checkliste_pruefen(beleg, text_lesbar=text_lesbar)
        beleg.checkliste = checkliste
        checkliste_vollstaendig = all(c.erfuellt for c in checkliste)
        erfuellt = sum(1 for c in checkliste if c.erfuellt)
        _schritt(
            beleg, "Vollständigkeit geprüft", "ok", "checkliste-fail-closed",
            f"{erfuellt}/{len(checkliste)} Checklisten-Punkte erfüllt.",
            t0, _jetzt(),
        )
    else:
        checkliste = []
        beleg.checkliste = checkliste
        t0 = _jetzt()
        werkzeugschritt = plan.werkzeuge["checkliste"]
        _schritt(beleg, "Vollständigkeit geprüft", "uebersprungen", "keins", werkzeugschritt.begruendung, t0, _jetzt())

    # 6. Werkzeuge ausfuehren: Bestand abgeglichen. Zuerst der harte
    # Datei-Hash-Vergleich (byte-identisches Duplikat), erst danach der
    # fachliche Referenz-Betrag-Datum-Abgleich je Dokumentart.
    bestand = speicher.bestand_uebernommen(conn)
    dublette_treffer: dict | None = None
    if plan.werkzeug_aktiv("bestand"):
        t0 = _jetzt()
        datei_duplikat = bestand_modul.ist_datei_duplikat(beleg, bestand)
        if datei_duplikat:
            dublette_treffer = dict(datei_duplikat)
            dublette_treffer["_grund"] = "datei-hash"
            begr = (
                f"Datei-Duplikat erkannt: byte-identisch mit dem bereits "
                f"uebernommenen Beleg '{datei_duplikat['dateiname']}' (gleicher Datei-Hash)."
            )
        else:
            dublette_treffer = bestand_modul.ist_dublette(beleg, bestand)
            begr = (
                f"Dublette erkannt: Referenz {beleg.feldwert('referenz')} bereits "
                f"am {dublette_treffer['datum']} uebernommen."
                if dublette_treffer
                else "Kein Datei-Duplikat und keine Dublette im bisherigen Bestand gefunden."
            )
        _schritt(beleg, "Bestand abgeglichen", "ok", plan.werkzeuge["bestand"].werkzeug, begr, t0, _jetzt())
    else:
        t0 = _jetzt()
        werkzeugschritt = plan.werkzeuge["bestand"]
        _schritt(beleg, "Bestand abgeglichen", "uebersprungen", "keins", werkzeugschritt.begruendung, t0, _jetzt())

    # Planrevision (Teil 2): Radar wird anhand der inzwischen vorliegenden
    # Evidenz (Dublette, unvollstaendige Checkliste, Dokumentart) bestaetigt
    # oder begruendet deaktiviert.
    plan = _plan_revidieren(
        beleg, plaene, plan,
        lesefehler=False, dublette=bool(dublette_treffer), checkliste_vollstaendig=checkliste_vollstaendig,
        dokumentart=beleg.dokumentart,
    )

    # Handeln: Entscheidung treffen (Grundlage fuer Schritt 7 und 8)
    ausgang, begruendung, fehlercode_entscheidung = entscheiden_modul.entscheiden(
        beleg, plan, checkliste, dublette_treffer, fehlercode_extraktion
    )
    beleg.ausgang = ausgang
    beleg.begruendung = begruendung
    beleg.fehlercode = fehlercode_entscheidung
    anbieter_schluessel_wert = bestand_modul.anbieter_schluessel(beleg)
    betrag_dezimal_wert = betraege.betrag_zu_decimal(beleg.feldwert("betrag"))
    beleg.betrag_dezimal = betraege.decimal_zu_csv_zahl(betrag_dezimal_wert) or None

    # 7. Bewerten/Handeln: Abovergleich bewertet
    t0 = _jetzt()
    radar_eintrag = None
    if plan.werkzeug_aktiv("radar"):
        vorheriger = bestand_modul.letzte_baseline(beleg, bestand)
        radar_eintrag = radar_modul.radar_bewerten(beleg, vorheriger)
        beleg.radar_hinweis = radar_eintrag.begruendung
        _schritt(beleg, "Abovergleich bewertet", "ok", "radar-vergleichbarkeit", radar_eintrag.begruendung, t0, _jetzt())
    else:
        werkzeugschritt = plan.werkzeuge["radar"]
        _schritt(beleg, "Abovergleich bewertet", "uebersprungen", "keins", werkzeugschritt.begruendung, t0, _jetzt())

    fehlende_checkliste = [c.name for c in checkliste if not c.erfuellt]
    dokumentstatus, reviewstatus, review_aufgabe = _status_ableiten(
        ausgang, fehlende_checkliste, radar_eintrag.einschaetzung if radar_eintrag else None
    )
    beleg.dokumentstatus = dokumentstatus
    beleg.reviewstatus = reviewstatus
    beleg.review_aufgabe = review_aufgabe
    beleg.baseline_bestaetigt = (
        ausgang == AUSGANG_UEBERNOMMEN
        and reviewstatus == REVIEWSTATUS_KEINE
        and (radar_eintrag is None or radar_eintrag.einschaetzung in (RADAR_NEU, RADAR_STABIL, RADAR_VERAENDERT_EINDEUTIG))
        # Zahlungsbelege und Abo-Bestaetigungen werden nie Preis-Baseline:
        # der Abovergleich vergleicht ausschliesslich Rechnungsbetraege.
        and beleg.dokumentart not in (DOKUMENTART_ZAHLUNGSBELEG, DOKUMENTART_ABO_BESTAETIGUNG)
    )

    # 8. Handeln: Entscheidung getroffen
    _schritt(beleg, "Entscheidung getroffen", "ok", "entscheidungsregeln", begruendung, _jetzt(), _jetzt())

    # 9. Erinnern: Ergebnis gespeichert
    t0 = _jetzt()
    speicher.beleg_speichern(conn, beleg, anbieter_schluessel_wert, radar_eintrag)
    _schritt(beleg, "Ergebnis gespeichert", "ok", "sqlite", f"Beleg gespeichert mit Ausgang '{ausgang}'.", t0, _jetzt())

    # 10. Erinnern: Auditverlauf aktualisiert
    t0 = _jetzt()
    speicher.audit_schreiben(conn, aktion=f"Beleg verarbeitet: {ausgang}", objekt=beleg.dateiname, alt=None, neu=begruendung)
    _schritt(beleg, "Auditverlauf aktualisiert", "ok", "audit-log", "Ereignis im Auditverlauf vermerkt.", t0, _jetzt())

    beleg.plaene = plaene
    for eintrag in plaene:
        speicher.plan_speichern(conn, lauf_id, beleg.id, eintrag, vorgang_id=beleg.vorgang_id)
    for schritt in beleg.schritte:
        speicher.agent_schritt_speichern(conn, lauf_id, beleg.id, schritt, vorgang_id=beleg.vorgang_id)

    _plan_und_schritte_pruefen(plaene, beleg.schritte)

    return beleg


class ContainerKonsistenzFehler(Exception):
    """Verletzung der Plan-Executor-Invarianten des EML-Container-Plans."""


def _container_plan_pruefen(plaene: list[planen.Ausfuehrungsplan], schritte: list[AgentSchritt]) -> None:
    """Invarianten des Container-Plans: die Zerlegung laeuft genau dann,
    wenn sie im finalen Plan aktiv ist, und jede Planaenderung traegt eine
    neue Version mit Revisionsgrund."""
    finaler_plan = plaene[-1]
    schritt_namen = {s.schritt for s in schritte}
    if finaler_plan.werkzeug_aktiv("zerlegung") != ("EML zerlegt" in schritt_namen):
        raise ContainerKonsistenzFehler("Zerlegung und Container-Plan sind nicht deckungsgleich.")
    for index in range(1, len(plaene)):
        vorheriger, aktueller = plaene[index - 1], plaene[index]
        if aktueller.version <= vorheriger.version:
            raise ContainerKonsistenzFehler("Container-Planrevision ohne aufsteigende Version.")
        if not aktueller.revisionsgrund:
            raise ContainerKonsistenzFehler("Container-Planrevision ohne protokollierten Revisionsgrund.")


def verarbeite_eml(
    conn: sqlite3.Connection, lauf_id: str, roher_dateiname: str, inhalt: bytes
) -> tuple[Vorgang, list[Beleg]]:
    """Verarbeitet eine hochgeladene EML: ein Kostenvorgang pro E-Mail, die
    Anhaenge und (falls kein Anhang vorhanden ist) der Mailtext laufen als
    eigenstaendige Belege durch verarbeite_datei. Der Container selbst wird
    nie ein Beleg; seine Schritte und Plaene werden ueber die vorgang_id
    protokolliert, nie ueber ein beleg_id-Feld."""
    anzeigename = dateinamen.anzeigename(roher_dateiname)
    vorgang_id = str(uuid.uuid4())
    schritte: list[AgentSchritt] = []

    def _container_schritt(name: str, status: str, werkzeug: str, begruendung: str, start: str) -> None:
        schritte.append(
            AgentSchritt(
                schritt=name, status=status, werkzeug=werkzeug,
                begruendung=begruendung, start=start, ende=_jetzt(),
            )
        )

    # 1. Wahrnehmen
    t0 = _jetzt()
    hash_ = dateien.dateihash(inhalt)
    _container_schritt(
        "Eingang erkannt", "ok", "sha256+kopfzeilen-heuristik",
        f"Dateityp EML anhand der Kopfzeilen erkannt, Hash {hash_[:12]}... gebildet.", t0,
    )

    # 2. Planen: Container-Plan (Version 1)
    t0 = _jetzt()
    plan = planen.plan_erstellen_eml()
    plaene = [plan]
    _container_schritt(
        "Ausführungsplan erstellt", "ok", "planung",
        f"Quellenklasse '{plan.quellenklasse}'. Aktive Werkzeuge: "
        + ", ".join(w.name for w in plan.werkzeuge.values() if w.ausfuehren), t0,
    )

    # Provenienz: die EML-Rohdatei wird wie jeder Eingang unter runtime/
    # abgelegt (relativer storage_key, nie ein absoluter Pfad).
    eml_storage_key: str | None = None
    interner_dateiname = f"{hash_[:12]}_{dateinamen.speichername(roher_dateiname)}"
    try:
        zielpfad = dateinamen.zielpfad(speicher.EINGANG_DIR, interner_dateiname)
        zielpfad.write_bytes(inhalt)
        eml_storage_key = speicher.storage_key_fuer(interner_dateiname)
    except dateinamen.UnsichererPfadFehler:
        # Praktisch unerreichbar (speichername() bereinigt vorher); die
        # Verarbeitung laeuft ohne gespeicherte Rohdatei ehrlich weiter.
        eml_storage_key = None

    # 3. Werkzeug: Zerlegung
    t0 = _jetzt()
    eml = mailparser.zerlegen(inhalt)
    _container_schritt(
        "EML zerlegt", "ok", "mail-parser",
        f"{len(eml.anhaenge)} Anhänge gefunden, Textkörper: {eml.text_quelle}.", t0,
    )
    speicher.audit_schreiben(
        conn, aktion="EML zerlegt", objekt=anzeigename, alt=None,
        neu=f"{len(eml.anhaenge)} Anhänge, Textkörper: {eml.text_quelle}.",
    )

    # 4. Planrevision nach Evidenz: Textkoerper-Einstufung
    neuer_plan = planen.eml_plan_verfeinern(
        plan, anzahl_anhaenge=len(eml.anhaenge), text_vorhanden=bool(eml.text.strip())
    )
    if neuer_plan.version != plan.version:
        t0 = _jetzt()
        _container_schritt("Ausführungsplan aktualisiert", "ok", "planung", neuer_plan.revisionsgrund, t0)
        plaene.append(neuer_plan)
        plan = neuer_plan

    vorgang = Vorgang(
        id=vorgang_id,
        lauf_id=lauf_id,
        quelle="eml",
        eml_dateiname=anzeigename,
        eml_hash=hash_,
        eml_storage_key=eml_storage_key,
        betreff=eml.betreff,
        absender=eml.absender,
        mail_datum=eml.mail_datum,
    )

    # 5. Dokumente verarbeiten: Anhaenge immer, der Mailtext nur, wenn der
    # Plan das Werkzeug 'textkoerper' aktiv gelassen hat.
    kontext = EmlKontext(vorgang_id=vorgang_id, betreff=eml.betreff)
    belege: list[Beleg] = []
    for anhang in eml.anhaenge:
        belege.append(verarbeite_datei(conn, lauf_id, anhang.dateiname, anhang.inhalt, kontext=kontext))

    if plan.werkzeug_aktiv("textkoerper"):
        stamm = anzeigename.rsplit(".", 1)[0] if "." in anzeigename else anzeigename
        mailtext_kontext = EmlKontext(
            vorgang_id=vorgang_id, betreff=eml.betreff,
            text_override=eml.text, dateityp_override="MAILTEXT",
        )
        belege.append(
            verarbeite_datei(
                conn, lauf_id, f"{stamm}_mailtext.txt",
                eml.text.encode("utf-8"), kontext=mailtext_kontext,
            )
        )

    # 6. Naechste Aktivitaet: nur mit expliziter Evidenz aus Mailtext und
    # extrahierten Zeitraum-Feldern.
    evidenz = [eml.text] + [b.feldwert("zeitraum") or "" for b in belege]
    art, status, datum, begruendung = vorgang_modul.naechste_aktivitaet(evidenz)
    vorgang.naechste_aktivitaet_art = art
    vorgang.naechste_aktivitaet_status = status
    vorgang.naechste_aktivitaet_datum = datum
    vorgang.naechste_aktivitaet_begruendung = begruendung

    # 7. Vorgangsregel: Zahlungsbeleg ohne Rechnung braucht das Original.
    if vorgang_modul.rechnung_fehlt(belege):
        for beleg in belege:
            if beleg.dokumentart == DOKUMENTART_ZAHLUNGSBELEG:
                alt_aufgabe = beleg.review_aufgabe
                beleg.reviewstatus = REVIEWSTATUS_OFFEN
                beleg.review_aufgabe = vorgang_modul.AUFGABE_RECHNUNG_ANFORDERN
                speicher.beleg_review_setzen(
                    conn, beleg.id, REVIEWSTATUS_OFFEN, vorgang_modul.AUFGABE_RECHNUNG_ANFORDERN
                )
                speicher.audit_schreiben(
                    conn, aktion="Review-Aufgabe gesetzt", objekt=beleg.dateiname,
                    alt=alt_aufgabe,
                    neu=f"{vorgang_modul.AUFGABE_RECHNUNG_ANFORDERN}: Zahlungsbeleg ohne zugehörige Rechnung im Vorgang.",
                )

    # 7b. Vorgangsregel: Abo-Bestaetigung ist keine Rechnung. Die generische
    # "fehlende Rechnungsfelder"-Meldung der Checkliste (Referenz, Datum,
    # Zeitraum) ist hier fachlich irrefuehrend -- eine Ankuendigung hat
    # naturgemaess keine Rechnungsnummer. Ersetzt Begruendung und
    # Review-Aufgabe durch eine Erklaerung, die ausschliesslich die bereits
    # ermittelte, evidenzbasierte naechste Aktivitaet nutzt.
    for beleg in belege:
        if beleg.dokumentart == DOKUMENTART_ABO_BESTAETIGUNG and beleg.ausgang == AUSGANG_REVIEW:
            alt_begruendung = beleg.begruendung
            alt_aufgabe = beleg.review_aufgabe
            neue_begruendung = vorgang_modul.abo_bestaetigung_begruendung(art, status, datum)
            neue_aufgabe = vorgang_modul.abo_bestaetigung_review_aufgabe(datum)
            beleg.begruendung = neue_begruendung
            beleg.reviewstatus = REVIEWSTATUS_OFFEN
            beleg.review_aufgabe = neue_aufgabe
            speicher.beleg_review_setzen(
                conn, beleg.id, REVIEWSTATUS_OFFEN, neue_aufgabe, begruendung=neue_begruendung
            )
            speicher.audit_schreiben(
                conn, aktion="Review-Aufgabe gesetzt", objekt=beleg.dateiname,
                alt=f"{alt_begruendung} / {alt_aufgabe}", neu=f"{neue_begruendung} / {neue_aufgabe}",
            )

    # 8. Erinnern: Vorgang, Plaene und Schritte speichern
    speicher.vorgang_speichern(conn, vorgang)
    speicher.audit_schreiben(
        conn, aktion="Vorgang angelegt", objekt=anzeigename, alt=None,
        neu=f"{len(belege)} Dokumente. {begruendung}",
    )
    for eintrag in plaene:
        speicher.plan_speichern(conn, lauf_id, None, eintrag, vorgang_id=vorgang_id)
    for schritt in schritte:
        speicher.agent_schritt_speichern(conn, lauf_id, None, schritt, vorgang_id=vorgang_id)

    _container_plan_pruefen(plaene, schritte)

    return vorgang, belege


def verarbeite_charge(conn: sqlite3.Connection, dateien_liste: list[tuple[str, bytes]]) -> tuple[str, list[Beleg]]:
    """Verarbeitet mehrere Dateien nacheinander im selben Lauf. Die
    Reihenfolge ist bedeutsam: Sie bestimmt, welcher Beleg als 'vorheriger'
    Vergleichswert fuer den Abo-Radar gilt. Transportbezogene Grenzen
    (Dateigroesse, Anzahl, Content-Type) sind bereits von web/server.py vor
    diesem Aufruf geprueft; hier laufen nur noch fachliche Entscheidungen
    je Datei, die eine einzelne fehlerhafte Datei nicht die ganze Charge
    stoppen lassen."""
    lauf_id = speicher.neuer_lauf(conn)
    ergebnisse: list[Beleg] = []
    for name, inhalt in dateien_liste:
        dateityp = dateien.dateityp_erkennen(inhalt)
        if dateityp == "EML" and dateien.endung_passt_zu_typ(dateinamen.anzeigename(name), dateityp):
            _, eml_belege = verarbeite_eml(conn, lauf_id, name, inhalt)
            ergebnisse.extend(eml_belege)
        else:
            # Eine EML mit widerspruechlicher Endung faellt bewusst in den
            # regulaeren Pfad und endet dort als Signatur-Widerspruch-Review.
            ergebnisse.append(verarbeite_datei(conn, lauf_id, name, inhalt))
    return lauf_id, ergebnisse
