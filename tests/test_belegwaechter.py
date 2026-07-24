"""Automatisierte Tests fuer den Belegwaechter-Kern.

Jeder Test laeuft gegen eine isolierte temporaere SQLite-Datenbank
(tempfile.mkdtemp), niemals gegen runtime/belegwaechter.db. Keine Tests
greifen auf Optifyx, Port 8737 oder das Netzwerk zu.
"""
from __future__ import annotations

import http.client
import json
import re
import shutil
import socket
import sqlite3
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
FIXTURES = REPO_ROOT / "fixtures"

from belegwaechter import (  # noqa: E402
    agent,
    dateien,
    dateinamen,
    dokumentart,
    entscheiden,
    extrahieren,
    fehlertexte,
    mailparser,
    speicher,
    vorgang,
)
from belegwaechter.modelle import (  # noqa: E402
    AUSGANG_DUBLETTE,
    AUSGANG_FEHLGESCHLAGEN,
    AUSGANG_ORIGINAL_ANFORDERN,
    AUSGANG_REVIEW,
    AUSGANG_UEBERNOMMEN,
    QUELLE_ERFASSUNGSNACHWEIS,
    RADAR_NEU,
    RADAR_VERAENDERT_EINDEUTIG,
    RADAR_VERGLEICH_ERFORDERLICH,
    REVIEWSTATUS_KEINE,
    REVIEWSTATUS_OFFEN,
)


def _lesen(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class IsolierteDatenbankTestCase(unittest.TestCase):
    """Basisklasse: jede Testklasse bekommt ein frisches Temp-Verzeichnis,
    nie die echte runtime/belegwaechter.db."""

    def setUp(self) -> None:
        self._tempdir = tempfile.mkdtemp(prefix="belegwaechter_test_")
        self._original_runtime = speicher.RUNTIME_DIR
        self._original_eingang = speicher.EINGANG_DIR
        self._original_db = speicher.DB_PFAD
        speicher.RUNTIME_DIR = Path(self._tempdir) / "runtime"
        speicher.EINGANG_DIR = speicher.RUNTIME_DIR / "eingang"
        speicher.DB_PFAD = speicher.RUNTIME_DIR / "belegwaechter.db"
        self.conn = speicher.verbindung()

    def tearDown(self) -> None:
        self.conn.close()
        speicher.RUNTIME_DIR = self._original_runtime
        speicher.EINGANG_DIR = self._original_eingang
        speicher.DB_PFAD = self._original_db
        shutil.rmtree(self._tempdir, ignore_errors=True)


class NormalfallTest(IsolierteDatenbankTestCase):
    def test_vollstaendige_pdf_rechnung_wird_uebernommen(self):
        beleg = agent.verarbeite_datei(
            self.conn, speicher.neuer_lauf(self.conn), "domainly_juli.pdf", _lesen("domainly_juli.pdf")
        )
        self.assertEqual(beleg.ausgang, AUSGANG_UEBERNOMMEN)
        self.assertEqual(beleg.stufe, "A")
        self.assertTrue(all(c.erfuellt for c in beleg.checkliste))
        self.assertIn("Original vorhanden", beleg.begruendung)


class AboHistorieTest(IsolierteDatenbankTestCase):
    def test_erster_beleg_baut_historie_auf(self):
        lauf = speicher.neuer_lauf(self.conn)
        beleg = agent.verarbeite_datei(self.conn, lauf, "cloudbasis_juni.pdf", _lesen("cloudbasis_juni.pdf"))
        self.assertEqual(beleg.ausgang, AUSGANG_UEBERNOMMEN)
        # Radar-Einschaetzung wird erst nach dem Speichern sichtbar:
        radar = speicher.radar_uebersicht(self.conn)
        self.assertEqual(len(radar), 1)
        self.assertEqual(radar[0]["radar_einschaetzung"], RADAR_NEU)

    def test_eindeutige_preissteigerung_wird_erkannt(self):
        lauf = speicher.neuer_lauf(self.conn)
        agent.verarbeite_datei(self.conn, lauf, "cloudbasis_juni.pdf", _lesen("cloudbasis_juni.pdf"))
        zweiter = agent.verarbeite_datei(self.conn, lauf, "cloudbasis_juli.pdf", _lesen("cloudbasis_juli.pdf"))
        self.assertEqual(zweiter.ausgang, AUSGANG_UEBERNOMMEN)
        self.assertIsNotNone(zweiter.radar_hinweis)
        self.assertIn("19,00", zweiter.radar_hinweis)
        self.assertIn("23,00", zweiter.radar_hinweis)
        self.assertIn("eindeutig", zweiter.radar_hinweis)
        radar = speicher.radar_uebersicht(self.conn)
        cloudbasis = [r for r in radar if r["anbieter"] == "CloudBasis GmbH"][0]
        self.assertEqual(cloudbasis["radar_einschaetzung"], RADAR_VERAENDERT_EINDEUTIG)

    def test_zeitraumwechsel_ergibt_vergleich_erforderlich_kein_falscher_alarm(self):
        lauf = speicher.neuer_lauf(self.conn)
        agent.verarbeite_datei(self.conn, lauf, "schreibki_monatlich.pdf", _lesen("schreibki_monatlich.pdf"))
        zweiter = agent.verarbeite_datei(
            self.conn, lauf, "schreibki_jahresrechnung.pdf", _lesen("schreibki_jahresrechnung.pdf")
        )
        self.assertEqual(zweiter.ausgang, AUSGANG_UEBERNOMMEN)
        self.assertIn("Vergleich erforderlich", zweiter.radar_hinweis)
        self.assertNotIn("teurer geworden", zweiter.radar_hinweis)
        self.assertEqual(zweiter.reviewstatus, REVIEWSTATUS_OFFEN)
        self.assertEqual(zweiter.review_aufgabe, "Preisänderung prüfen")
        radar = speicher.radar_uebersicht(self.conn)
        schreibki = [r for r in radar if r["anbieter"] == "SchreibKI Plus"][0]
        self.assertEqual(schreibki["radar_einschaetzung"], RADAR_VERGLEICH_ERFORDERLICH)


class DubletteTest(IsolierteDatenbankTestCase):
    def test_dublette_wird_erkannt_und_nicht_doppelt_gezaehlt(self):
        lauf = speicher.neuer_lauf(self.conn)
        agent.verarbeite_datei(self.conn, lauf, "cloudbasis_juli.pdf", _lesen("cloudbasis_juli.pdf"))
        dublette = agent.verarbeite_datei(
            self.conn, lauf, "cloudbasis_juli_dublette.pdf", _lesen("cloudbasis_juli_dublette.pdf")
        )
        self.assertEqual(dublette.ausgang, AUSGANG_DUBLETTE)
        self.assertIn("RE-3301-07", dublette.begruendung)
        bestand = speicher.bestand_uebernommen(self.conn)
        self.assertEqual(len(bestand), 1, "Dublette darf den Bestand nicht verdoppeln")


class ScreenshotReviewTest(IsolierteDatenbankTestCase):
    def test_screenshot_wird_nie_als_original_behandelt(self):
        beleg = agent.verarbeite_datei(
            self.conn, speicher.neuer_lauf(self.conn), "mobiltel_screenshot.png", _lesen("mobiltel_screenshot.png")
        )
        self.assertEqual(beleg.stufe, "B")
        self.assertEqual(beleg.quellenstatus, QUELLE_ERFASSUNGSNACHWEIS)
        self.assertEqual(beleg.ausgang, AUSGANG_ORIGINAL_ANFORDERN)
        self.assertTrue(all(f.wert is None for f in beleg.felder.values()), "Keine erfundenen Feldwerte aus einem Bild")


class FehlendePflichtwerteTest(IsolierteDatenbankTestCase):
    def test_beleg_ohne_rechnungsnummer_landet_in_review(self):
        unvollstaendiges_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        try:
            sys.path.insert(0, str(REPO_ROOT / "fixtures"))
            import erzeugen  # type: ignore

            erzeugen._pdf_schreiben(
                Path(unvollstaendiges_pdf.name),
                ["Unvollstaendig AG", "Datum: 01.07.2026", "Betrag: 5,00 EUR", "Waehrung: EUR"],
            )
            inhalt = Path(unvollstaendiges_pdf.name).read_bytes()
        finally:
            unvollstaendiges_pdf.close()
            Path(unvollstaendiges_pdf.name).unlink(missing_ok=True)

        beleg = agent.verarbeite_datei(self.conn, speicher.neuer_lauf(self.conn), "unvollstaendig.pdf", inhalt)
        self.assertEqual(beleg.ausgang, AUSGANG_REVIEW)
        fehlend = [c.name for c in beleg.checkliste if not c.erfuellt]
        self.assertIn("Rechnungsnummer vorhanden", fehlend)
        self.assertNotEqual(beleg.feldwert("betrag"), None, "Vorhandene Felder duerfen trotzdem erkannt werden")


class AuditUndProvenienzTest(IsolierteDatenbankTestCase):
    def test_audittrace_und_agentschritte_vollstaendig(self):
        lauf_id, ergebnisse = agent.verarbeite_charge(self.conn, [("domainly_juli.pdf", _lesen("domainly_juli.pdf"))])
        audit = speicher.audit_liste(self.conn)
        self.assertEqual(len(audit), 1)
        self.assertIn("Beleg verarbeitet", audit[0]["aktion"])

        schritte = speicher.agent_schritte_fuer_lauf(self.conn, lauf_id)
        namen = [s["schritt"] for s in schritte]
        erwartete_schritte = [
            "Eingang erkannt", "Quellenqualität bewertet", "Ausführungsplan erstellt",
            "Felder extrahiert", "Dokumentart bestimmt", "Vollständigkeit geprüft",
            "Bestand abgeglichen", "Abovergleich bewertet", "Entscheidung getroffen",
            "Ergebnis gespeichert", "Auditverlauf aktualisiert",
        ]
        self.assertEqual(namen, erwartete_schritte)

    def test_provenienz_datei_hash_und_pfad_stimmen(self):
        original = _lesen("domainly_juli.pdf")
        beleg = agent.verarbeite_datei(self.conn, speicher.neuer_lauf(self.conn), "domainly_juli.pdf", original)
        gespeichert = speicher.alle_belege(self.conn)[0]
        self.assertEqual(gespeichert["dateipfad"], "", "Kein absoluter Pfad darf persistiert werden")
        self.assertTrue(gespeichert["storage_key"].startswith("eingang/"))
        pfad = speicher.pfad_aus_key(gespeichert["storage_key"])
        self.assertTrue(pfad.exists(), "Originaldatei muss unter runtime/eingang liegen")
        self.assertEqual(pfad.read_bytes(), original)

        import hashlib

        self.assertEqual(beleg.dateihash, hashlib.sha256(original).hexdigest())


class ExportTest(IsolierteDatenbankTestCase):
    def test_csv_export_enthaelt_nur_uebernommene_belege(self):
        lauf = speicher.neuer_lauf(self.conn)
        agent.verarbeite_datei(self.conn, lauf, "cloudbasis_juni.pdf", _lesen("cloudbasis_juni.pdf"))
        agent.verarbeite_datei(self.conn, lauf, "mobiltel_screenshot.png", _lesen("mobiltel_screenshot.png"))

        belege = speicher.alle_belege(self.conn)
        uebernommen = [b for b in belege if b["ausgang"] == AUSGANG_UEBERNOMMEN]
        nicht_uebernommen = [b for b in belege if b["ausgang"] != AUSGANG_UEBERNOMMEN]
        self.assertEqual(len(uebernommen), 1)
        self.assertEqual(len(nicht_uebernommen), 1)


class ResetTest(IsolierteDatenbankTestCase):
    def test_reset_stellt_leeren_ausgangszustand_her(self):
        agent.verarbeite_datei(self.conn, speicher.neuer_lauf(self.conn), "domainly_juli.pdf", _lesen("domainly_juli.pdf"))
        self.assertEqual(len(speicher.alle_belege(self.conn)), 1)
        self.conn.close()

        speicher.reset()
        self.assertFalse(speicher.DB_PFAD.exists())

        self.conn = speicher.verbindung()
        self.assertEqual(speicher.alle_belege(self.conn), [])


class DeterminismusTest(IsolierteDatenbankTestCase):
    def test_identischer_wiederholungslauf_liefert_gleiches_ergebnis(self):
        reihenfolge = [
            "domainly_juli.pdf", "cloudbasis_juni.pdf", "cloudbasis_juli.pdf",
            "cloudbasis_juli_dublette.pdf", "schreibki_monatlich.pdf", "schreibki_jahresrechnung.pdf",
        ]
        dateien = [(name, _lesen(name)) for name in reihenfolge]

        _, erster_lauf = agent.verarbeite_charge(self.conn, dateien)
        erste_ausgaenge = [(b.dateiname, b.ausgang, b.begruendung) for b in erster_lauf]

        self.conn.close()  # Windows sperrt offene Dateien: vor reset() schliessen
        speicher.reset()
        self.conn = speicher.verbindung()
        _, zweiter_lauf = agent.verarbeite_charge(self.conn, dateien)
        zweite_ausgaenge = [(b.dateiname, b.ausgang, b.begruendung) for b in zweiter_lauf]

        self.assertEqual(erste_ausgaenge, zweite_ausgaenge)


class KeinNetzwerkzugriffTest(IsolierteDatenbankTestCase):
    def test_verarbeitung_oeffnet_keine_netzwerksockets(self):
        original_socket = socket.socket

        def gesperrt(*args, **kwargs):
            raise AssertionError("Netzwerkzugriff waehrend der Verarbeitung ist nicht erlaubt.")

        socket.socket = gesperrt
        try:
            beleg = agent.verarbeite_datei(
                self.conn, speicher.neuer_lauf(self.conn), "domainly_juli.pdf", _lesen("domainly_juli.pdf")
            )
            self.assertEqual(beleg.ausgang, AUSGANG_UEBERNOMMEN)
        finally:
            socket.socket = original_socket


class PortIsolationTest(unittest.TestCase):
    def test_server_port_ist_nicht_8737(self):
        """Statische Pruefung, kein Netzwerkzugriff: der Belegwaechter-Port
        darf niemals mit dem Optifyx-Produktionsport kollidieren."""
        sys.path.insert(0, str(REPO_ROOT))
        from web import server

        self.assertNotEqual(server.PORT, 8737)
        self.assertEqual(server.HOST, "127.0.0.1")


def _synthetische_rechnung(zeilen: list[str]) -> bytes:
    """Baut eine synthetische PDF-Rechnung mit frei waehlbaren Zeilen ueber
    fixtures/erzeugen.py._pdf_schreiben. Nur fuer Tests, keine Laufzeit-
    Abhaengigkeit der App."""
    sys.path.insert(0, str(REPO_ROOT / "fixtures"))
    import erzeugen  # type: ignore

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    try:
        erzeugen._pdf_schreiben(Path(tmp.name), zeilen)
        return Path(tmp.name).read_bytes()
    finally:
        tmp.close()
        Path(tmp.name).unlink(missing_ok=True)


class DateinamenTest(unittest.TestCase):
    def test_traversal_unix(self):
        self.assertEqual(dateinamen.anzeigename("../../../datei.pdf"), "datei.pdf")
        name = dateinamen.speichername("../../../datei.pdf")
        self.assertNotIn("/", name)
        self.assertNotIn("..", name)

    def test_traversal_windows(self):
        self.assertEqual(dateinamen.anzeigename("..\\..\\datei.pdf"), "datei.pdf")
        self.assertNotIn("\\", dateinamen.speichername("..\\..\\datei.pdf"))

    def test_absoluter_windows_pfad(self):
        name = dateinamen.speichername("C:\\Windows\\System32\\datei.pdf")
        self.assertNotIn(":", name)
        self.assertNotIn("\\", name)

    def test_absoluter_unix_pfad(self):
        name = dateinamen.speichername("/etc/passwd")
        self.assertNotIn("/", name)
        self.assertEqual(name, "passwd")

    def test_sehr_langer_name(self):
        name = dateinamen.speichername("a" * 500 + ".pdf")
        self.assertLessEqual(len(name), 90)

    def test_leerer_name(self):
        self.assertEqual(dateinamen.anzeigename(""), "unbenannte Datei")
        self.assertEqual(dateinamen.speichername(""), "beleg")

    def test_reservierter_windows_name(self):
        self.assertTrue(dateinamen.speichername("CON.pdf").upper().startswith("DATEI_CON"))
        self.assertTrue(dateinamen.speichername("NUL").upper().startswith("DATEI_NUL"))

    def test_deutscher_name_mit_umlauten(self):
        anzeige = dateinamen.anzeigename("Rechnung Müller & Söhne (Juli).pdf")
        self.assertIn("Müller", anzeige)
        name = dateinamen.speichername("Rechnung Müller & Söhne (Juli).pdf")
        self.assertRegex(name, r"^[A-Za-z0-9._-]+$")

    def test_kyrillischer_name(self):
        anzeige = dateinamen.anzeigename("квитанция.pdf")
        self.assertEqual(anzeige, "квитанция.pdf")
        name = dateinamen.speichername("квитанция.pdf")
        self.assertRegex(name, r"^[A-Za-z0-9._-]+$")
        self.assertGreater(len(name), 0)

    def test_zielpfad_bleibt_innerhalb_der_basis(self):
        with tempfile.TemporaryDirectory() as tmp:
            basis = Path(tmp)
            pfad = dateinamen.zielpfad(basis, "abc123_beleg.pdf")
            self.assertTrue(pfad.is_relative_to(basis.resolve()))

    def test_zielpfad_verweigert_ausserhalb(self):
        with tempfile.TemporaryDirectory() as tmp:
            basis = Path(tmp) / "eingang"
            basis.mkdir()
            with self.assertRaises(dateinamen.UnsichererPfadFehler):
                dateinamen.zielpfad(basis, "../ausserhalb.pdf")


class StorageKeyTest(IsolierteDatenbankTestCase):
    def test_gespeicherter_key_ist_relativ(self):
        beleg = agent.verarbeite_datei(
            self.conn, speicher.neuer_lauf(self.conn), "domainly_juli.pdf", _lesen("domainly_juli.pdf")
        )
        self.assertTrue(beleg.storage_key.startswith("eingang/"))
        self.assertNotIn(":", beleg.storage_key)
        self.assertNotIn("\\", beleg.storage_key)

    def test_rekonstruktion_innerhalb_der_basis(self):
        beleg = agent.verarbeite_datei(
            self.conn, speicher.neuer_lauf(self.conn), "domainly_juli.pdf", _lesen("domainly_juli.pdf")
        )
        pfad = speicher.pfad_aus_key(beleg.storage_key)
        self.assertTrue(pfad.is_relative_to(speicher.RUNTIME_DIR.resolve()))
        self.assertTrue(pfad.exists())

    def test_ablehnung_von_traversal(self):
        with self.assertRaises(dateinamen.UnsichererPfadFehler):
            speicher.pfad_aus_key("eingang/../../../ausserhalb.pdf")

    def test_ablehnung_absoluter_windows_key(self):
        with self.assertRaises(dateinamen.UnsichererPfadFehler):
            speicher.pfad_aus_key("C:/Windows/System32/evil.pdf")

    def test_ablehnung_absoluter_unix_key(self):
        with self.assertRaises(dateinamen.UnsichererPfadFehler):
            speicher.pfad_aus_key("/etc/passwd")

    def test_keine_datenbankspalte_enthaelt_laufwerksbuchstaben(self):
        agent.verarbeite_datei(
            self.conn, speicher.neuer_lauf(self.conn), "domainly_juli.pdf", _lesen("domainly_juli.pdf")
        )
        for row in speicher.alle_belege(self.conn):
            for wert in row.values():
                if isinstance(wert, str):
                    self.assertNotIn("C:\\", wert)
                    self.assertNotRegex(wert, r"^[A-Za-z]:[\\/]")


class StatusTrennungTest(IsolierteDatenbankTestCase):
    def test_unklarer_abovergleich_ergibt_offene_reviewaufgabe(self):
        lauf = speicher.neuer_lauf(self.conn)
        agent.verarbeite_datei(self.conn, lauf, "schreibki_monatlich.pdf", _lesen("schreibki_monatlich.pdf"))
        zweiter = agent.verarbeite_datei(
            self.conn, lauf, "schreibki_jahresrechnung.pdf", _lesen("schreibki_jahresrechnung.pdf")
        )
        self.assertEqual(zweiter.ausgang, AUSGANG_UEBERNOMMEN)
        self.assertEqual(zweiter.dokumentstatus, "vorbereitet")
        self.assertEqual(zweiter.reviewstatus, REVIEWSTATUS_OFFEN)
        self.assertEqual(zweiter.review_aufgabe, "Preisänderung prüfen")

    def test_eindeutige_preisaenderung_hat_keine_offene_reviewaufgabe(self):
        lauf = speicher.neuer_lauf(self.conn)
        agent.verarbeite_datei(self.conn, lauf, "cloudbasis_juni.pdf", _lesen("cloudbasis_juni.pdf"))
        zweiter = agent.verarbeite_datei(self.conn, lauf, "cloudbasis_juli.pdf", _lesen("cloudbasis_juli.pdf"))
        self.assertEqual(zweiter.ausgang, AUSGANG_UEBERNOMMEN)
        self.assertEqual(zweiter.dokumentstatus, "vorbereitet")
        self.assertEqual(zweiter.reviewstatus, REVIEWSTATUS_KEINE)
        self.assertIsNone(zweiter.review_aufgabe)


class BaselineTest(IsolierteDatenbankTestCase):
    def test_monatlicher_beleg_wird_bestaetigte_baseline(self):
        beleg = agent.verarbeite_datei(
            self.conn, speicher.neuer_lauf(self.conn), "cloudbasis_juni.pdf", _lesen("cloudbasis_juni.pdf")
        )
        self.assertTrue(beleg.baseline_bestaetigt)

    def test_jahresbeleg_mit_offenem_vergleich_wird_nicht_baseline(self):
        lauf = speicher.neuer_lauf(self.conn)
        agent.verarbeite_datei(self.conn, lauf, "schreibki_monatlich.pdf", _lesen("schreibki_monatlich.pdf"))
        jahresbeleg = agent.verarbeite_datei(
            self.conn, lauf, "schreibki_jahresrechnung.pdf", _lesen("schreibki_jahresrechnung.pdf")
        )
        self.assertEqual(jahresbeleg.ausgang, AUSGANG_UEBERNOMMEN)
        self.assertFalse(jahresbeleg.baseline_bestaetigt)
        self.assertEqual(len(speicher.bestand_uebernommen(self.conn)), 2, "Offener Fall bleibt im Bestand sichtbar")

    def test_naechster_monatsbeleg_vergleicht_gegen_bestaetigte_baseline(self):
        lauf = speicher.neuer_lauf(self.conn)
        agent.verarbeite_datei(self.conn, lauf, "schreibki_monatlich.pdf", _lesen("schreibki_monatlich.pdf"))
        agent.verarbeite_datei(self.conn, lauf, "schreibki_jahresrechnung.pdf", _lesen("schreibki_jahresrechnung.pdf"))

        dritte_rechnung = _synthetische_rechnung(
            [
                "SchreibKI Plus",
                "Rechnung Nr. INV-99180",
                "Datum: 05.08.2026",
                "Leistungszeitraum: monatlich",
                "Tarif: Plus",
                "Betrag: 12,00 EUR",
                "Waehrung: EUR",
            ]
        )
        dritter = agent.verarbeite_datei(self.conn, lauf, "schreibki_august.pdf", dritte_rechnung)

        self.assertEqual(dritter.ausgang, AUSGANG_UEBERNOMMEN)
        self.assertIn("unverändert", dritter.radar_hinweis)
        self.assertIn("05.06.2026", dritter.radar_hinweis, "Vergleich muss gegen die bestaetigte Monats-Baseline laufen")
        self.assertNotIn("05.07.2026", dritter.radar_hinweis, "Der offene Jahresbeleg darf nie als Referenz dienen")
        self.assertNotIn("120,00", dritter.radar_hinweis)


class PlanTest(IsolierteDatenbankTestCase):
    def test_text_pdf_aktiviert_alle_werkzeuge(self):
        beleg = agent.verarbeite_datei(
            self.conn, speicher.neuer_lauf(self.conn), "domainly_juli.pdf", _lesen("domainly_juli.pdf")
        )
        finaler_plan = beleg.plaene[-1]
        for name in ("extraktion", "checkliste", "bestand", "radar"):
            self.assertTrue(finaler_plan.werkzeug_aktiv(name), name)

    def test_bild_ohne_ocr_deaktiviert_extraktion_und_radar(self):
        beleg = agent.verarbeite_datei(
            self.conn, speicher.neuer_lauf(self.conn), "mobiltel_screenshot.png", _lesen("mobiltel_screenshot.png")
        )
        finaler_plan = beleg.plaene[-1]
        self.assertFalse(finaler_plan.werkzeug_aktiv("extraktion"))
        self.assertFalse(finaler_plan.werkzeug_aktiv("radar"))

    def test_dublette_deaktiviert_nur_radar(self):
        lauf = speicher.neuer_lauf(self.conn)
        agent.verarbeite_datei(self.conn, lauf, "cloudbasis_juli.pdf", _lesen("cloudbasis_juli.pdf"))
        dublette = agent.verarbeite_datei(
            self.conn, lauf, "cloudbasis_juli_dublette.pdf", _lesen("cloudbasis_juli_dublette.pdf")
        )
        finaler_plan = dublette.plaene[-1]
        self.assertTrue(finaler_plan.werkzeug_aktiv("checkliste"))
        self.assertTrue(finaler_plan.werkzeug_aktiv("bestand"))
        self.assertFalse(finaler_plan.werkzeug_aktiv("radar"))
        self.assertEqual(len(dublette.plaene), 2, "Dublette muss eine protokollierte Planrevision ausloesen")

    def test_verschiedene_eingaenge_erzeugen_verschiedene_plaene(self):
        pdf_beleg = agent.verarbeite_datei(
            self.conn, speicher.neuer_lauf(self.conn), "domainly_juli.pdf", _lesen("domainly_juli.pdf")
        )
        bild_beleg = agent.verarbeite_datei(
            self.conn, speicher.neuer_lauf(self.conn), "mobiltel_screenshot.png", _lesen("mobiltel_screenshot.png")
        )
        self.assertNotEqual(pdf_beleg.plaene[0].quellenklasse, bild_beleg.plaene[0].quellenklasse)


class PlanKonsistenzTest(IsolierteDatenbankTestCase):
    def test_plan_und_ausgefuehrte_schritte_sind_deckungsgleich(self):
        beleg = agent.verarbeite_datei(
            self.conn, speicher.neuer_lauf(self.conn), "domainly_juli.pdf", _lesen("domainly_juli.pdf")
        )
        agent._plan_und_schritte_pruefen(beleg.plaene, beleg.schritte)

    def test_gespeicherte_plaene_stimmen_mit_beleg_plaene_ueberein(self):
        beleg = agent.verarbeite_datei(
            self.conn, speicher.neuer_lauf(self.conn), "cloudbasis_juli_dublette.pdf",
            _lesen("cloudbasis_juli_dublette.pdf"),
        )
        gespeichert = speicher.plaene_fuer_beleg(self.conn, beleg.id)
        self.assertEqual(len(gespeichert), len(beleg.plaene))
        for eintrag, plan in zip(gespeichert, beleg.plaene):
            self.assertEqual(eintrag["version"], plan.version)

    def test_quelltext_verzweigt_nicht_erneut_anhand_von_stufe(self):
        agent_quelltext = (REPO_ROOT / "belegwaechter" / "agent.py").read_text(encoding="utf-8")
        entscheiden_quelltext = (REPO_ROOT / "belegwaechter" / "entscheiden.py").read_text(encoding="utf-8")
        muster = re.compile(r"stufe\s*(==|in\s*\()")
        self.assertIsNone(muster.search(entscheiden_quelltext))
        self.assertIsNone(muster.search(agent_quelltext))


class FehlertextTest(IsolierteDatenbankTestCase):
    def test_defektes_pdf_erzeugt_wertfreie_meldung_ohne_pfade(self):
        kaputt = b"%PDF-" + bytes(range(256)) * 4
        beleg = agent.verarbeite_datei(self.conn, speicher.neuer_lauf(self.conn), "kaputt.pdf", kaputt)
        self.assertEqual(beleg.ausgang, AUSGANG_FEHLGESCHLAGEN)
        self.assertIsNotNone(beleg.fehlercode)
        texte = [beleg.begruendung] + [s.begruendung for s in beleg.schritte]
        for text in texte:
            self.assertNotIn("C:\\", text)
            self.assertNotIn(str(REPO_ROOT), text)
            self.assertNotIn("Traceback", text)
            self.assertNotIn("file://", text)

        gespeichert = speicher.alle_belege(self.conn)[0]
        self.assertNotIn("C:\\", gespeichert["begruendung"])
        self.assertIsNotNone(gespeichert["fehlercode"])

    def test_bereinigen_entfernt_pfade_und_tracebacks(self):
        roh = (
            "Fehler in C:\\Users\\enric\\projekt\\datei.py, siehe auch "
            "/home/enric/projekt/datei.py und file:///C:/tmp/x.txt\n"
            "Traceback (most recent call last):\n"
            '  File "C:\\Users\\enric\\projekt\\datei.py", line 42, in irgendwas\n'
            "ValueError: kaputt"
        )
        bereinigt = fehlertexte.bereinigen(roh)
        self.assertNotIn("C:\\", bereinigt)
        self.assertNotIn("/home/enric", bereinigt)
        self.assertNotIn("file://", bereinigt)
        self.assertNotIn("Traceback (most recent call last):", bereinigt)


class MigrationTest(unittest.TestCase):
    """Baut eine v1-Datenbank von Hand (ohne den aktuellen Migrationscode)
    und prueft, dass das Oeffnen mit dem neuen Code sicher auf v2 migriert:
    Daten bleiben erhalten, ein WAL-Backup wird konsistent erstellt, ein
    nicht aufloesbarer Fremdpfad wird ehrlich markiert statt geraten, und
    eine fehlschlagende Migration beschaedigt den Bestand nicht."""

    def setUp(self) -> None:
        self._tempdir = tempfile.mkdtemp(prefix="belegwaechter_migration_test_")
        self.runtime_dir = Path(self._tempdir) / "runtime"
        self.eingang_dir = self.runtime_dir / "eingang"
        self.db_pfad = self.runtime_dir / "belegwaechter.db"
        self.runtime_dir.mkdir(parents=True)
        self.eingang_dir.mkdir(parents=True)

        self._original_runtime = speicher.RUNTIME_DIR
        self._original_eingang = speicher.EINGANG_DIR
        self._original_db = speicher.DB_PFAD
        speicher.RUNTIME_DIR = self.runtime_dir
        speicher.EINGANG_DIR = self.eingang_dir
        speicher.DB_PFAD = self.db_pfad

    def tearDown(self) -> None:
        speicher.RUNTIME_DIR = self._original_runtime
        speicher.EINGANG_DIR = self._original_eingang
        speicher.DB_PFAD = self._original_db
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def _v1_db_bauen(self) -> None:
        conn = sqlite3.connect(self.db_pfad)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        speicher._migration_001_initial_schema(conn)
        conn.execute("INSERT INTO schema_version (version) VALUES (1)")
        conn.execute("INSERT INTO laeufe (id, gestartet_am) VALUES ('lauf-1', datetime('now'))")

        gueltiger_pfad = self.eingang_dir / "abc123_rechnung.pdf"
        gueltiger_pfad.write_bytes(b"%PDF-1.4 test")

        spalten = (
            "id, lauf_id, dateiname, dateihash, dateipfad, dateityp, stufe, quellenstatus, "
            "anbieter, anbieter_schluessel, datum, betrag, waehrung, zeitraum, tarif, referenz, "
            "felder_json, checkliste_json, ausgang, begruendung, radar_einschaetzung, "
            "radar_begruendung, erfasst_am"
        )
        conn.execute(
            f"""
            INSERT INTO belege ({spalten}) VALUES (
                'beleg-gueltig', 'lauf-1', 'rechnung.pdf', 'hash1', ?, 'PDF', 'A', 'original_vorhanden',
                'CloudBasis GmbH', 'cloudbasis gmbh', '01.06.2026', '19,00', 'EUR', 'monatlich', 'Standard', 'RE-1',
                '{{}}', '[]', 'uebernommen', 'Uebernommen: Test.', 'neu', 'Erster Beleg.', datetime('now')
            )
            """,
            (str(gueltiger_pfad),),
        )
        conn.execute(
            f"""
            INSERT INTO belege ({spalten}) VALUES (
                'beleg-fremd', 'lauf-1', 'fremd.pdf', 'hash2',
                'C:\\Users\\irgendwer\\Desktop\\fremd.pdf', 'PDF', 'A', 'original_vorhanden',
                'Fremd GmbH', 'fremd gmbh', '01.06.2026', '10,00', 'EUR', 'monatlich', 'Standard', 'RE-2',
                '{{}}', '[]', 'uebernommen', 'Uebernommen: Test.', 'neu', 'Erster Beleg.', datetime('now')
            )
            """
        )
        conn.commit()
        conn.close()

    def test_migration_ueberfuehrt_bestand_und_ist_idempotent(self):
        self._v1_db_bauen()

        conn = speicher.verbindung()
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        self.assertEqual(version, len(speicher.MIGRATIONEN))

        zeilen = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM belege").fetchall()}
        self.assertEqual(len(zeilen), 2)

        gueltig = zeilen["beleg-gueltig"]
        self.assertEqual(gueltig["dateipfad"], "")
        self.assertTrue(gueltig["storage_key"].startswith("eingang/"))
        self.assertIsNone(gueltig["fehlercode"])
        self.assertEqual(gueltig["dokumentstatus"], "vorbereitet")
        self.assertEqual(gueltig["baseline_bestaetigt"], 1)

        fremd = zeilen["beleg-fremd"]
        self.assertIsNone(fremd["storage_key"])
        self.assertEqual(fremd["fehlercode"], "PFAD_NICHT_AUFLOESBAR")
        self.assertEqual(fremd["dokumentstatus"], "zurueckgestellt")
        self.assertEqual(fremd["reviewstatus"], "offen")

        plaene_tabelle = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='beleg_plaene'"
        ).fetchone()
        self.assertIsNotNone(plaene_tabelle)

        sicherung = self.runtime_dir / "belegwaechter.db.vor-migration-v2"
        self.assertTrue(sicherung.exists(), "Backup ueber die SQLite-Backup-API muss vor der Migration entstehen")
        sicherungs_conn = sqlite3.connect(sicherung)
        anzahl_vorher = sicherungs_conn.execute("SELECT COUNT(*) FROM belege").fetchone()[0]
        self.assertEqual(anzahl_vorher, 2, "Backup muss trotz WAL-Modus konsistent alle Zeilen enthalten")
        sicherungs_conn.close()
        conn.close()

        conn2 = speicher.verbindung()
        self.assertEqual(conn2.execute("SELECT version FROM schema_version").fetchone()[0], len(speicher.MIGRATIONEN))
        self.assertEqual(conn2.execute("SELECT COUNT(*) FROM belege").fetchone()[0], 2)
        conn2.close()

    def test_fehlgeschlagene_migration_beschaedigt_bestand_nicht(self):
        self._v1_db_bauen()

        def _kaputte_migration(conn: sqlite3.Connection) -> None:
            conn.execute("ALTER TABLE belege ADD COLUMN testspalte TEXT")
            raise RuntimeError("simulierter Migrationsfehler")

        original_migrationen = speicher.MIGRATIONEN
        speicher.MIGRATIONEN = [speicher._migration_001_initial_schema, _kaputte_migration]
        try:
            with self.assertRaises(RuntimeError):
                speicher.verbindung()
        finally:
            speicher.MIGRATIONEN = original_migrationen

        conn = sqlite3.connect(self.db_pfad)
        conn.row_factory = sqlite3.Row
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        self.assertEqual(version, 1, "Schema-Version darf bei fehlgeschlagener Migration nicht steigen")
        anzahl = conn.execute("SELECT COUNT(*) FROM belege").fetchone()[0]
        self.assertEqual(anzahl, 2, "Bestehende Daten muessen trotz fehlgeschlagener Migration erhalten bleiben")
        conn.close()


def _multipart_body(dateien: list[tuple[str, bytes]], feldname: str = "dateien",
                     boundary: str = "TESTBOUNDARY123456") -> tuple[bytes, str]:
    teile = []
    for name, inhalt in dateien:
        kopf = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{feldname}"; '
            f'filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n'
        ).encode("utf-8")
        teile.append(kopf + inhalt + b"\r\n")
    teile.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(teile), f"multipart/form-data; boundary={boundary}"


class HttpTestCase(unittest.TestCase):
    """Startet den echten Belegwaechter-Server auf Port 0 in einem Thread,
    gegen eine isolierte Temp-Datenbank. Die Allowlist im Server wird zur
    Laufzeit aus dem tatsaechlich zugewiesenen Port abgeleitet."""

    def setUp(self) -> None:
        self._tempdir = tempfile.mkdtemp(prefix="belegwaechter_http_test_")
        self._original_runtime = speicher.RUNTIME_DIR
        self._original_eingang = speicher.EINGANG_DIR
        self._original_db = speicher.DB_PFAD
        speicher.RUNTIME_DIR = Path(self._tempdir) / "runtime"
        speicher.EINGANG_DIR = speicher.RUNTIME_DIR / "eingang"
        speicher.DB_PFAD = speicher.RUNTIME_DIR / "belegwaechter.db"

        from web.server import BelegwaechterHandler

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), BelegwaechterHandler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        speicher.RUNTIME_DIR = self._original_runtime
        speicher.EINGANG_DIR = self._original_eingang
        speicher.DB_PFAD = self._original_db
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def _verbindung(self) -> http.client.HTTPConnection:
        return http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)

    def _senden(self, method: str, path: str, body: bytes = b"",
                extra_headers: dict | None = None, host: str | None = None) -> tuple[int, bytes]:
        extra_headers = dict(extra_headers or {})
        conn = self._verbindung()
        try:
            conn.putrequest(method, path, skip_host=(host is not None))
            if host is not None:
                conn.putheader("Host", host)
            for key, value in extra_headers.items():
                conn.putheader(key, value)
            conn.putheader("Content-Length", str(len(body)))
            conn.endheaders(body)
            resp = conn.getresponse()
            daten = resp.read()
            status = resp.status
        finally:
            conn.close()
        return status, daten

    def _upload(self, dateien: list[tuple[str, bytes]], host: str | None = None,
                origin: str | None = None, content_type: str | None = None) -> tuple[int, bytes]:
        body, ctype = _multipart_body(dateien)
        headers = {"Content-Type": content_type if content_type is not None else ctype}
        if origin is not None:
            headers["Origin"] = origin
        if host is None:
            host = f"127.0.0.1:{self.port}"
        return self._senden("POST", "/api/verarbeiten", body=body, extra_headers=headers, host=host)

    def _upload_ok(self, dateien: list[tuple[str, bytes]]) -> tuple[int, bytes]:
        return self._upload(dateien)


class AssetRouteTest(HttpTestCase):
    """Statische Auslieferung des lokalen Hintergrundfotos unter
    /assets/*: nur bekannte Bilddateien, kein Pfad-Traversal."""

    def test_hintergrundfotos_werden_ausgeliefert(self):
        for name, content_type in (
            ("hintergrund-1600.jpg", "image/jpeg"),
            ("hintergrund-2560.jpg", "image/jpeg"),
        ):
            status, daten = self._senden("GET", f"/assets/{name}", host=f"127.0.0.1:{self.port}")
            self.assertEqual(status, 200, name)
            self.assertGreater(len(daten), 1000, f"{name} sollte kein leerer Platzhalter sein")

        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", "/assets/hintergrund-1600.jpg", headers={"Content-Length": "0"})
        resp = conn.getresponse()
        resp.read()
        self.assertEqual(resp.getheader("Content-Type"), "image/jpeg")
        conn.close()

    def test_traversal_ausserhalb_von_assets_wird_abgelehnt(self):
        for pfad in (
            "/assets/../server.py",
            "/assets/..%2Fserver.py",
            "/assets/unterordner/datei.jpg",
        ):
            status, _ = self._senden("GET", pfad, host=f"127.0.0.1:{self.port}")
            self.assertEqual(status, 404, pfad)

    def test_unbekannte_dateiendung_wird_abgelehnt(self):
        status, _ = self._senden("GET", "/assets/hintergrund-1600.exe", host=f"127.0.0.1:{self.port}")
        self.assertEqual(status, 404)

    def test_nicht_vorhandene_datei_liefert_404(self):
        status, _ = self._senden("GET", "/assets/gibt-es-nicht.jpg", host=f"127.0.0.1:{self.port}")
        self.assertEqual(status, 404)


class HttpSicherheitTest(HttpTestCase):
    def test_gueltiger_upload_mit_ip_host(self):
        status, daten = self._upload([("domainly_juli.pdf", _lesen("domainly_juli.pdf"))])
        self.assertEqual(status, 200)
        antwort = json.loads(daten)
        self.assertEqual(antwort["belege"][0]["ausgang"], AUSGANG_UEBERNOMMEN)

    def test_gueltiger_upload_mit_localhost_host(self):
        status, _ = self._upload(
            [("domainly_juli.pdf", _lesen("domainly_juli.pdf"))], host=f"localhost:{self.port}"
        )
        self.assertEqual(status, 200)

    def test_ungueltiger_port_im_host_wird_abgelehnt(self):
        anderer_port = self.port - 1 if self.port > 1 else self.port + 1
        status, _ = self._upload(
            [("domainly_juli.pdf", _lesen("domainly_juli.pdf"))], host=f"127.0.0.1:{anderer_port}"
        )
        self.assertEqual(status, 403)

    def test_fremder_host_wird_abgelehnt(self):
        status, _ = self._upload([("domainly_juli.pdf", _lesen("domainly_juli.pdf"))], host="evil.example.com")
        self.assertEqual(status, 403)

    def test_fremder_origin_wird_abgelehnt(self):
        status, _ = self._upload(
            [("domainly_juli.pdf", _lesen("domainly_juli.pdf"))], origin="http://evil.example.com"
        )
        self.assertEqual(status, 403)

    def test_reset_mit_fremdem_origin_wird_abgelehnt(self):
        status, _ = self._senden(
            "POST", "/api/reset", body=b"",
            extra_headers={"Origin": "http://evil.example.com"}, host=f"127.0.0.1:{self.port}",
        )
        self.assertEqual(status, 403)

    def test_falscher_content_type_wird_abgelehnt(self):
        body = b'{"nicht": "multipart"}'
        status, _ = self._senden(
            "POST", "/api/verarbeiten", body=body,
            extra_headers={"Content-Type": "application/json"}, host=f"127.0.0.1:{self.port}",
        )
        self.assertEqual(status, 415)

    def test_traversal_dateiname_landet_sicher_unter_eingang(self):
        status, daten = self._upload([("../../../evil.pdf", _lesen("domainly_juli.pdf"))])
        self.assertEqual(status, 200)
        antwort = json.loads(daten)
        self.assertEqual(antwort["belege"][0]["ausgang"], AUSGANG_UEBERNOMMEN)
        eingang_dateien = list(speicher.EINGANG_DIR.iterdir())
        self.assertEqual(len(eingang_dateien), 1)
        for pfad in eingang_dateien:
            self.assertTrue(pfad.resolve().is_relative_to(speicher.EINGANG_DIR.resolve()))

    def test_ergebnis_enthaelt_keinen_absoluten_pfad(self):
        self._upload([("domainly_juli.pdf", _lesen("domainly_juli.pdf"))])
        status, daten = self._senden("GET", "/api/ergebnis", host=f"127.0.0.1:{self.port}")
        self.assertEqual(status, 200)
        text = daten.decode("utf-8")
        self.assertNotIn("dateipfad", text)
        self.assertNotIn("C:\\", text)
        self.assertNotIn(str(REPO_ROOT), text)


class GrenzenTest(HttpTestCase):
    def test_einzelne_datei_zu_gross_wird_abgelehnt(self):
        riesendatei = b"%PDF-1.4" + b"0" * (10 * 1024 * 1024 + 10)
        status, _ = self._upload_ok([("riesig.pdf", riesendatei)])
        self.assertEqual(status, 413)
        conn = speicher.verbindung()
        self.assertEqual(len(speicher.alle_belege(conn)), 0)
        conn.close()

    def test_gesamte_anfrage_zu_gross_wird_abgelehnt(self):
        teil = b"%PDF-1.4" + b"0" * (8 * 1024 * 1024)
        status, _ = self._upload_ok([("a.pdf", teil), ("b.pdf", teil), ("c.pdf", teil)])
        self.assertEqual(status, 413)

    def test_mehrere_gueltige_kleine_dateien_werden_verarbeitet(self):
        dateien = [
            ("domainly_juli.pdf", _lesen("domainly_juli.pdf")),
            ("cloudbasis_juni.pdf", _lesen("cloudbasis_juni.pdf")),
        ]
        status, daten = self._upload_ok(dateien)
        self.assertEqual(status, 200)
        antwort = json.loads(daten)
        self.assertEqual(len(antwort["belege"]), 2)

    def test_zu_grosse_datei_zwischen_gueltigen_lehnt_ganze_charge_ab(self):
        riesendatei = b"%PDF-1.4" + b"0" * (10 * 1024 * 1024 + 10)
        dateien = [
            ("domainly_juli.pdf", _lesen("domainly_juli.pdf")),
            ("riesig.pdf", riesendatei),
            ("cloudbasis_juni.pdf", _lesen("cloudbasis_juni.pdf")),
        ]
        status, _ = self._upload_ok(dateien)
        self.assertEqual(status, 413)
        conn = speicher.verbindung()
        self.assertEqual(len(speicher.alle_belege(conn)), 0, "Bei Groessenverletzung darf keine Datei gespeichert werden")
        conn.close()

    def test_defektes_pdf_zwischen_gueltigen_stoppt_charge_nicht(self):
        kaputt = b"%PDF-" + bytes(range(256)) * 4
        dateien = [
            ("domainly_juli.pdf", _lesen("domainly_juli.pdf")),
            ("kaputt.pdf", kaputt),
            ("cloudbasis_juni.pdf", _lesen("cloudbasis_juni.pdf")),
        ]
        status, daten = self._upload_ok(dateien)
        self.assertEqual(status, 200)
        antwort = json.loads(daten)
        ausgaenge = [b["ausgang"] for b in antwort["belege"]]
        self.assertEqual(ausgaenge.count(AUSGANG_UEBERNOMMEN), 2)
        self.assertIn(AUSGANG_FEHLGESCHLAGEN, ausgaenge)


class CsvKostenexportTest(HttpTestCase):
    """Die Kosten-CSV bildet wirtschaftliche Kosten ab, nicht jede
    vorhandene Nachweisdatei: Rechnung und Zahlungsbeleg desselben Vorgangs
    duerfen die Kosten nicht doppelt zaehlen."""

    def _csv_holen(self) -> str:
        status, daten = self._senden("GET", "/api/export.csv", host=f"127.0.0.1:{self.port}")
        self.assertEqual(status, 200)
        return daten.decode("utf-8-sig")

    def _datenzeilen(self, csv_text: str) -> list[str]:
        zeilen = [z for z in csv_text.splitlines() if z.strip()]
        return zeilen[1:]  # erste Zeile ist der Header

    def test_rechnung_und_zahlungsbeleg_gleicher_betrag_ergibt_genau_eine_kostenzeile(self):
        self._upload_ok(
            [("cloudbasis_rechnung_und_zahlung.eml", _lesen("cloudbasis_rechnung_und_zahlung.eml"))]
        )
        zeilen = self._datenzeilen(self._csv_holen())
        self.assertEqual(len(zeilen), 1, "Rechnung und Zahlungsbeleg desselben Vorgangs duerfen nicht doppelt zaehlen")
        self.assertIn("23.00", zeilen[0])
        self.assertNotIn("46.00", zeilen[0])

    def test_nur_zahlungsbeleg_ergibt_keine_kostenzeile(self):
        zahlungsbeleg = _synthetische_rechnung(
            [
                "Anbieter GmbH", "Zahlungsbeleg", "Zahlung erhalten zur Rechnung Nr. RE-1",
                "Datum: 01.08.2026", "Leistungszeitraum: monatlich", "Tarif: Standard",
                "Betrag: 23,00 EUR", "Waehrung: EUR",
            ]
        )
        status, antwort = self._upload_ok([("zahlungsbeleg.pdf", zahlungsbeleg)])
        antwort_json = json.loads(antwort)
        self.assertEqual(antwort_json["belege"][0]["ausgang"], AUSGANG_UEBERNOMMEN)
        self.assertEqual(antwort_json["belege"][0]["dokumentart"], "zahlungsbeleg")
        zeilen = self._datenzeilen(self._csv_holen())
        self.assertEqual(zeilen, [])

    def test_abo_bestaetigung_ergibt_keine_kostenzeile(self):
        self._upload_ok(
            [("schreibki_abo_bestaetigung.eml", _lesen("schreibki_abo_bestaetigung.eml"))]
        )
        zeilen = self._datenzeilen(self._csv_holen())
        self.assertEqual(zeilen, [])

    def test_uebernommene_rechnung_ergibt_eine_kostenzeile(self):
        rechnung = _synthetische_rechnung(
            [
                "Anbieter GmbH", "Rechnung Nr. RE-2", "Datum: 01.08.2026",
                "Leistungszeitraum: monatlich", "Tarif: Standard",
                "Betrag: 15,00 EUR", "Waehrung: EUR",
            ]
        )
        self._upload_ok([("rechnung.pdf", rechnung)])
        zeilen = self._datenzeilen(self._csv_holen())
        self.assertEqual(len(zeilen), 1)
        self.assertIn("15.00", zeilen[0])


class CsvSicherheitTest(HttpTestCase):
    def _csv_holen(self) -> str:
        status, daten = self._senden("GET", "/api/export.csv", host=f"127.0.0.1:{self.port}")
        self.assertEqual(status, 200)
        return daten.decode("utf-8-sig")

    def test_textspalten_werden_escaped(self):
        gefaehrlich = _synthetische_rechnung(
            [
                "=FORMEL()",
                "Rechnung Nr. -TEST",
                "Datum: 01.07.2026",
                "Leistungszeitraum: monatlich",
                "Tarif: Standard",
                "Betrag: 5,00 EUR",
                "Waehrung: EUR",
            ]
        )
        status, _ = self._upload_ok([("@test.pdf", gefaehrlich)])
        self.assertEqual(status, 200)

        text = self._csv_holen()
        self.assertIn("'=FORMEL()", text)
        self.assertIn("'-TEST", text)
        self.assertIn("'@test.pdf", text)

    def test_positiver_betrag_bleibt_numerisch(self):
        inhalt = _synthetische_rechnung(
            [
                "Zahlbar GmbH", "Rechnung Nr. ZB-1", "Datum: 01.07.2026",
                "Leistungszeitraum: monatlich", "Tarif: Standard",
                "Betrag: 5,00 EUR", "Waehrung: EUR",
            ]
        )
        self._upload_ok([("zahlbar.pdf", inhalt)])
        text = self._csv_holen()
        self.assertIn("5.00", text)
        self.assertNotIn("'5.00", text)

    def test_negativer_betrag_bleibt_numerisch(self):
        # Die bestehende PDF-Extraktion (belegwaechter/extrahieren.py) erkennt
        # kein Vorzeichen im Betragsfeld -- das ist eine vorbestehende Grenze
        # der Extraktion, nicht Teil dieses Security-/Agentik-Laufs. Der Test
        # setzt betrag_dezimal daher direkt, um ausschliesslich den
        # CSV-Exportpfad (belegwaechter.betraege / web/server._csv_text) zu
        # pruefen, unabhaengig von der Extraktionsregex.
        self._upload_ok([("normal.pdf", _lesen("domainly_juli.pdf"))])
        conn = speicher.verbindung()
        conn.execute("UPDATE belege SET betrag_dezimal = '-5.00' WHERE dateiname = 'normal.pdf'")
        conn.commit()
        conn.close()
        text = self._csv_holen()
        self.assertIn("-5.00", text)
        self.assertNotIn("'-5.00", text)

    def test_ungueltiger_betrag_wird_nicht_als_zahl_exportiert(self):
        inhalt = _synthetische_rechnung(
            [
                "Kaputt GmbH", "Rechnung Nr. KA-1", "Datum: 01.07.2026",
                "Leistungszeitraum: monatlich", "Tarif: Standard",
                "Betrag: 1.2.3,00 EUR", "Waehrung: EUR",
            ]
        )
        status, daten = self._upload_ok([("kaputt.pdf", inhalt)])
        self.assertEqual(status, 200)
        antwort = json.loads(daten)
        self.assertEqual(antwort["belege"][0]["ausgang"], AUSGANG_REVIEW)

        text = self._csv_holen()
        self.assertNotIn("1.2.3,00", text)
        self.assertNotIn("kaputt.pdf", text)


class EmlErkennungTest(unittest.TestCase):
    """EML-Erkennung per Header-Heuristik: E-Mails werden erkannt, bestehende
    Typen bleiben unberuehrt, beliebige Textdateien gelten nicht als E-Mail."""

    def test_eml_fixtures_werden_als_eml_erkannt(self):
        for name in (
            "cloudbasis_rechnung_und_zahlung.eml",
            "schreibki_abo_bestaetigung.eml",
            "mobiltel_zahlungsbestaetigung.eml",
            "domainly_nur_html_rechnung.eml",
        ):
            self.assertEqual(dateien.dateityp_erkennen(_lesen(name)), "EML", name)

    def test_pdf_und_png_erkennung_bleibt_unveraendert(self):
        self.assertEqual(dateien.dateityp_erkennen(_lesen("domainly_juli.pdf")), "PDF")
        self.assertEqual(dateien.dateityp_erkennen(_lesen("mobiltel_screenshot.png")), "PNG")

    def test_label_wert_textdatei_ist_keine_eml(self):
        inhalt = "Anbieter: Test GmbH\nDatum: 01.07.2026\nBetrag: 5,00 EUR\n".encode("utf-8")
        self.assertEqual(dateien.dateityp_erkennen(inhalt), "unbekannt")

    def test_einzelne_headerzeile_reicht_nicht(self):
        inhalt = b"Subject: nur ein einzelner Header\n\nRestlicher Text ohne Mailstruktur."
        self.assertEqual(dateien.dateityp_erkennen(inhalt), "unbekannt")

    def test_eml_endung_gilt_nur_fuer_eml_dateien(self):
        self.assertTrue(dateien.endung_passt_zu_typ("rechnung.eml", "EML"))
        self.assertFalse(dateien.endung_passt_zu_typ("rechnung.txt", "EML"))

    def test_eml_und_mailtext_sind_stufe_a_original(self):
        self.assertEqual(dateien.stufe_und_quelle("EML")[0], "A")
        self.assertEqual(dateien.stufe_und_quelle("MAILTEXT")[0], "A")


class MailparserTest(unittest.TestCase):
    """Zerlegung der synthetischen EML-Fixtures: MIME-Varianten, Encodings
    und die Magic-Bytes-Pruefung der Anhaenge."""

    def test_zwei_pdf_anhaenge_werden_extrahiert(self):
        eml = mailparser.zerlegen(_lesen("cloudbasis_rechnung_und_zahlung.eml"))
        self.assertEqual(len(eml.anhaenge), 2)
        namen = [a.dateiname for a in eml.anhaenge]
        self.assertIn("cloudbasis_august_rechnung.pdf", namen)
        self.assertIn("cloudbasis_august_zahlungsbeleg.pdf", namen)

    def test_octet_stream_anhang_ist_per_signatur_ein_pdf(self):
        eml = mailparser.zerlegen(_lesen("cloudbasis_rechnung_und_zahlung.eml"))
        zahlungsbeleg = [a for a in eml.anhaenge if "zahlungsbeleg" in a.dateiname][0]
        self.assertEqual(zahlungsbeleg.deklarierter_typ, "application/octet-stream")
        self.assertEqual(dateien.dateityp_erkennen(zahlungsbeleg.inhalt), "PDF",
                         "Magic-Bytes muessen den deklarierten MIME-Typ ueberstimmen")

    def test_base64_textkoerper_wird_dekodiert(self):
        roh = _lesen("cloudbasis_rechnung_und_zahlung.eml")
        self.assertIn(b"base64", roh, "Fixture muss einen base64-Textteil enthalten")
        eml = mailparser.zerlegen(roh)
        self.assertEqual(eml.text_quelle, "text/plain")
        self.assertIn("Zahlungsbeleg fuer August 2026", eml.text)

    def test_html_only_alternative_ohne_plain_wird_text(self):
        eml = mailparser.zerlegen(_lesen("schreibki_abo_bestaetigung.eml"))
        self.assertEqual(eml.text_quelle, "text/html")
        self.assertIn("verlaengert sich am 05.08.2026", eml.text)
        self.assertIn("Betrag: 12,00 EUR", eml.text)

    def test_nicht_multipart_html_mail_wird_zerlegt(self):
        eml = mailparser.zerlegen(_lesen("domainly_nur_html_rechnung.eml"))
        self.assertEqual(eml.text_quelle, "text/html")
        self.assertEqual(eml.anhaenge, [])
        self.assertIn("Rechnung Nr. RE-9001-08", eml.text)

    def test_tracking_pixel_und_styles_erzeugen_keinen_text(self):
        eml = mailparser.zerlegen(_lesen("domainly_nur_html_rechnung.eml"))
        self.assertNotIn("tracking.invalid", eml.text)
        self.assertNotIn("https://", eml.text)
        abo = mailparser.zerlegen(_lesen("schreibki_abo_bestaetigung.eml"))
        self.assertNotIn("color:", abo.text, "Inline-CSS darf nicht im Text landen")

    def test_html_zu_text_erzeugt_label_wert_zeilen(self):
        text = mailparser.html_zu_text(
            "<html><head><script>boese()</script></head><body>"
            "<table><tr><td>Betrag:</td><td>7,00 EUR</td></tr></table></body></html>"
        )
        self.assertEqual(text, "Betrag: 7,00 EUR")
        self.assertNotIn("boese", text)

    def test_zerlegung_oeffnet_keine_netzwerksockets(self):
        original_socket = socket.socket

        def gesperrt(*args, **kwargs):
            raise AssertionError("Netzwerkzugriff waehrend der EML-Zerlegung ist nicht erlaubt.")

        socket.socket = gesperrt
        try:
            for name in (
                "cloudbasis_rechnung_und_zahlung.eml",
                "schreibki_abo_bestaetigung.eml",
                "domainly_nur_html_rechnung.eml",
            ):
                mailparser.zerlegen(_lesen(name))
        finally:
            socket.socket = original_socket

    def test_kaputte_eml_faellt_leer_und_ohne_ausnahme_zurueck(self):
        eml = mailparser.zerlegen(b"From: x@example.invalid\r\nSubject: kaputt\r\n\r\n")
        self.assertEqual(eml.text, "")
        self.assertEqual(eml.text_quelle, "keine")
        self.assertEqual(eml.anhaenge, [])


class DokumentartTest(unittest.TestCase):
    """Regelbasierte Dokumentart-Einordnung: deterministisch, feste
    Prioritaet, fail-closed."""

    def test_zahlungsbeleg_hat_vorrang_vor_rechnung(self):
        art, begruendung = dokumentart.klassifizieren(
            "Zahlungsbeleg\nZahlung erhalten zur Rechnung Nr. RE-1"
        )
        self.assertEqual(art, "zahlungsbeleg")
        self.assertIn("zahlungsbeleg", begruendung.lower())

    def test_abo_bestaetigung_hat_vorrang_vor_rechnung(self):
        art, _ = dokumentart.klassifizieren("Ihr Abo verlaengert sich am 05.08.2026. Rechnung folgt.")
        self.assertEqual(art, "abo_bestaetigung")

    def test_rechnung_wird_erkannt(self):
        art, _ = dokumentart.klassifizieren("CloudBasis GmbH\nRechnung Nr. RE-1")
        self.assertEqual(art, "rechnung")

    def test_betrag_ohne_schluesselwort_ist_sonstiger_kostennachweis(self):
        art, _ = dokumentart.klassifizieren("Unvollstaendig AG\nDatum: 01.07.2026", betrag_vorhanden=True)
        self.assertEqual(art, "sonstiger_kostennachweis")

    def test_ohne_evidenz_fail_closed_unbestimmt(self):
        art, begruendung = dokumentart.klassifizieren("")
        self.assertEqual(art, "unbestimmt")
        self.assertIn("geraten", begruendung)

    def test_anbietername_mit_zahl_wortstamm_ist_kein_zahlungsbeleg(self):
        art, _ = dokumentart.klassifizieren("Zahlbar GmbH\nRechnung Nr. ZB-1")
        self.assertEqual(art, "rechnung")

    def test_englische_schluesselwoerter_werden_erkannt(self):
        self.assertEqual(dokumentart.klassifizieren("Invoice\nInvoice number: INV-1")[0], "rechnung")
        self.assertEqual(dokumentart.klassifizieren("Receipt\nPayment received")[0], "zahlungsbeleg")
        self.assertEqual(dokumentart.klassifizieren("Payment receipt\nInvoice number: INV-1")[0], "zahlungsbeleg")

    def test_eigener_textinhalt_hat_vorrang_vor_betreff(self):
        """Der Betreff einer Zahlungsbeleg-Mail darf eine enthaltene
        Rechnungs-PDF nicht zum Zahlungsbeleg machen: der eigene Textinhalt
        des Anhangs gewinnt immer."""
        art, begruendung = dokumentart.klassifizieren(
            "Anbieter GmbH\nRechnung Nr. RE-1", betreff="Ihr Zahlungsbeleg"
        )
        self.assertEqual(art, "rechnung")
        self.assertIn("Textinhalt", begruendung)

    def test_dateiname_ist_zweite_prioritaet_vor_betreff(self):
        art, begruendung = dokumentart.klassifizieren(
            "", dateiname="zahlungsbeleg.pdf", betreff="Ihre Rechnung"
        )
        self.assertEqual(art, "zahlungsbeleg")
        self.assertIn("Dateiname", begruendung)

    def test_betreff_und_mailtext_nur_als_letzter_fallback(self):
        art, begruendung = dokumentart.klassifizieren(
            "", dateiname="anhang.pdf", betreff="Ihr Zahlungsbeleg"
        )
        self.assertEqual(art, "zahlungsbeleg")
        self.assertIn("Fallback", begruendung)

        art2, _ = dokumentart.klassifizieren("", dateiname="anhang.pdf", mailtext="Vielen Dank fuer Ihre Rechnung.")
        self.assertEqual(art2, "rechnung")


def _eml_mit_generischen_anhaengen(betreff: str, anhaenge: list[tuple[str, list[str]]]) -> bytes:
    """Baut eine synthetische EML mit gegebenem Betreff und PDF-Anhaengen,
    ausschliesslich fuer Tests der Dokumentart-Evidenzpriorisierung. Nur
    generische Bezeichnungen, keine Firmennamen oder echten Werte."""
    from email.message import EmailMessage

    sys.path.insert(0, str(REPO_ROOT / "fixtures"))
    import erzeugen  # type: ignore

    msg = EmailMessage()
    msg["From"] = "Anbieter GmbH <rechnungen@beispiel.invalid>"
    msg["To"] = "demo@belegwaechter.invalid"
    msg["Subject"] = betreff
    msg["Date"] = "Mon, 03 Aug 2026 09:00:00 +0200"
    msg["Message-ID"] = "<test-generisch@beispiel.invalid>"
    msg.set_content("Anbei die Dokumente zu Ihrem Vorgang.")
    for name, zeilen in anhaenge:
        msg.add_attachment(
            erzeugen._pdf_bytes(zeilen), maintype="application", subtype="pdf", filename=name
        )
    for teil in msg.walk():
        if teil.is_multipart():
            teil.set_boundary("test-boundary-fixiert")
    return msg.as_bytes()


class DokumentklassifikationEvidenzTest(IsolierteDatenbankTestCase):
    """Akzeptanzkriterium: eine EML mit dem Betreff 'Ihr Zahlungsbeleg' kann
    trotzdem eine Rechnung und einen Zahlungsbeleg enthalten -- jeder
    Anhang wird nach seinem EIGENEN Textinhalt klassifiziert, nicht nach
    dem irrefuehrenden Betreff."""

    def test_irrefuehrender_betreff_aendert_anhang_klassifikation_nicht(self):
        eml_bytes = _eml_mit_generischen_anhaengen(
            "Ihr Zahlungsbeleg",
            [
                (
                    "rechnung.pdf",
                    [
                        "Anbieter GmbH", "Rechnung Nr. RE-9001", "Datum: 01.08.2026",
                        "Leistungszeitraum: monatlich", "Tarif: Standard",
                        "Betrag: 19,00 EUR", "Waehrung: EUR",
                    ],
                ),
                (
                    "zahlungsbeleg.pdf",
                    [
                        "Anbieter GmbH", "Zahlungsbeleg", "Zahlung erhalten zur Rechnung Nr. RE-9001",
                        "Datum: 01.08.2026", "Leistungszeitraum: monatlich",
                        "Tarif: Standard", "Betrag: 19,00 EUR", "Waehrung: EUR",
                    ],
                ),
            ],
        )
        _, belege = agent.verarbeite_eml(
            self.conn, speicher.neuer_lauf(self.conn), "test.eml", eml_bytes
        )
        arten = {b.dateiname: b.dokumentart for b in belege}
        self.assertEqual(arten["rechnung.pdf"], "rechnung")
        self.assertEqual(arten["zahlungsbeleg.pdf"], "zahlungsbeleg")
        ausgaenge = {b.dateiname: b.ausgang for b in belege}
        self.assertEqual(ausgaenge["rechnung.pdf"], AUSGANG_UEBERNOMMEN)
        self.assertEqual(ausgaenge["zahlungsbeleg.pdf"], AUSGANG_UEBERNOMMEN)


class DokumentartWerkzeugTest(IsolierteDatenbankTestCase):
    """Das Werkzeug 'dokumentart' laeuft im Plan, wird protokolliert und
    unterliegt den Planinvarianten."""

    def test_pdf_rechnung_bekommt_dokumentart_und_schritt(self):
        beleg = agent.verarbeite_datei(
            self.conn, speicher.neuer_lauf(self.conn), "domainly_juli.pdf", _lesen("domainly_juli.pdf")
        )
        self.assertEqual(beleg.dokumentart, "rechnung")
        self.assertTrue(beleg.plaene[-1].werkzeug_aktiv("dokumentart"))
        schritt = [s for s in beleg.schritte if s.schritt == "Dokumentart bestimmt"][0]
        self.assertEqual(schritt.status, "ok")
        self.assertEqual(schritt.werkzeug, "dokumentart-regeln")
        gespeichert = speicher.alle_belege(self.conn)[0]
        self.assertEqual(gespeichert["dokumentart"], "rechnung")

    def test_screenshot_ohne_text_bleibt_unbestimmt_und_uebersprungen(self):
        beleg = agent.verarbeite_datei(
            self.conn, speicher.neuer_lauf(self.conn), "mobiltel_screenshot.png", _lesen("mobiltel_screenshot.png")
        )
        self.assertEqual(beleg.dokumentart, "unbestimmt")
        self.assertFalse(beleg.plaene[-1].werkzeug_aktiv("dokumentart"))
        schritt = [s for s in beleg.schritte if s.schritt == "Dokumentart bestimmt"][0]
        self.assertEqual(schritt.status, "uebersprungen")


class EmlVorgangTest(IsolierteDatenbankTestCase):
    """Akzeptanzkern: eine EML mit Rechnung und Zahlungsbeleg ergibt genau
    einen Kostenvorgang mit zwei getrennten Dokumenten."""

    def test_eine_eml_ergibt_einen_vorgang_mit_zwei_getrennten_dokumenten(self):
        vorgang_obj, belege = agent.verarbeite_eml(
            self.conn, speicher.neuer_lauf(self.conn),
            "cloudbasis_rechnung_und_zahlung.eml", _lesen("cloudbasis_rechnung_und_zahlung.eml"),
        )
        self.assertEqual(len(belege), 2)
        self.assertEqual(sorted(b.dokumentart for b in belege), ["rechnung", "zahlungsbeleg"])
        self.assertEqual([b.ausgang for b in belege], [AUSGANG_UEBERNOMMEN, AUSGANG_UEBERNOMMEN],
                         "Rechnung und Zahlungsbeleg desselben Vorgangs sind keine Dubletten")
        for beleg in belege:
            self.assertEqual(beleg.vorgang_id, vorgang_obj.id)
        vorgaenge = speicher.vorgaenge_liste(self.conn)
        self.assertEqual(len(vorgaenge), 1)
        self.assertEqual(vorgaenge[0]["id"], vorgang_obj.id)
        self.assertEqual(len(speicher.alle_belege(self.conn)), 2, "Der EML-Container ist kein Beleg")

    def test_leistungszeitraum_ergibt_hoechstens_beleg_erwartet(self):
        vorgang_obj, _ = agent.verarbeite_eml(
            self.conn, speicher.neuer_lauf(self.conn),
            "cloudbasis_rechnung_und_zahlung.eml", _lesen("cloudbasis_rechnung_und_zahlung.eml"),
        )
        self.assertEqual(vorgang_obj.naechste_aktivitaet_art, "beleg")
        self.assertEqual(vorgang_obj.naechste_aktivitaet_status, "erwartet")
        self.assertNotEqual(vorgang_obj.naechste_aktivitaet_status, "bestaetigt")
        self.assertNotEqual(vorgang_obj.naechste_aktivitaet_art, "zahlung",
                            "Ein Leistungszeitraum ist nie eine Zahlungszusage")

    def test_zahlungsbeleg_wird_nie_preisbaseline(self):
        _, belege = agent.verarbeite_eml(
            self.conn, speicher.neuer_lauf(self.conn),
            "cloudbasis_rechnung_und_zahlung.eml", _lesen("cloudbasis_rechnung_und_zahlung.eml"),
        )
        rechnung = [b for b in belege if b.dokumentart == "rechnung"][0]
        zahlungsbeleg = [b for b in belege if b.dokumentart == "zahlungsbeleg"][0]
        self.assertTrue(rechnung.baseline_bestaetigt)
        self.assertFalse(zahlungsbeleg.baseline_bestaetigt)
        self.assertFalse(zahlungsbeleg.plaene[-1].werkzeug_aktiv("radar"))

    def test_container_plan_steuert_textkoerper_als_protokollierte_revision(self):
        vorgang_obj, _ = agent.verarbeite_eml(
            self.conn, speicher.neuer_lauf(self.conn),
            "cloudbasis_rechnung_und_zahlung.eml", _lesen("cloudbasis_rechnung_und_zahlung.eml"),
        )
        container_plaene = self.conn.execute(
            "SELECT beleg_id, vorgang_id, version, revisionsgrund FROM beleg_plaene "
            "WHERE vorgang_id = ? AND beleg_id IS NULL ORDER BY version ASC",
            (vorgang_obj.id,),
        ).fetchall()
        self.assertEqual(len(container_plaene), 2, "Textkoerper-Deaktivierung muss eine Planrevision sein")
        self.assertIn("Begleittext", container_plaene[1]["revisionsgrund"])
        fremde_beleg_ids = self.conn.execute(
            "SELECT COUNT(*) FROM beleg_plaene WHERE beleg_id = ?", (vorgang_obj.id,)
        ).fetchone()[0]
        self.assertEqual(fremde_beleg_ids, 0, "Eine vorgang_id darf nie im beleg_id-Feld stehen")

    def test_mailtext_rechnung_wird_eigener_beleg(self):
        vorgang_obj, belege = agent.verarbeite_eml(
            self.conn, speicher.neuer_lauf(self.conn),
            "domainly_nur_html_rechnung.eml", _lesen("domainly_nur_html_rechnung.eml"),
        )
        self.assertEqual(len(belege), 1)
        beleg = belege[0]
        self.assertEqual(beleg.plaene[0].quellenklasse, "mailtext")
        self.assertEqual(beleg.dokumentart, "rechnung")
        self.assertEqual(beleg.ausgang, AUSGANG_UEBERNOMMEN)
        self.assertEqual(beleg.feldwert("betrag"), "9,00")
        self.assertEqual(beleg.vorgang_id, vorgang_obj.id)

    def test_abo_bestaetigung_mit_explizitem_datum_ist_bestaetigt(self):
        vorgang_obj, belege = agent.verarbeite_eml(
            self.conn, speicher.neuer_lauf(self.conn),
            "schreibki_abo_bestaetigung.eml", _lesen("schreibki_abo_bestaetigung.eml"),
        )
        self.assertEqual(vorgang_obj.naechste_aktivitaet_art, "zahlung")
        self.assertEqual(vorgang_obj.naechste_aktivitaet_status, "bestaetigt")
        self.assertEqual(vorgang_obj.naechste_aktivitaet_datum, "05.08.2026")
        self.assertEqual(belege[0].dokumentart, "abo_bestaetigung")

    def test_abo_bestaetigung_begruendung_ist_fachlich_konkret_statt_generische_checkliste(self):
        """Eine Abo-Bestaetigung ist keine Rechnung: die sichtbare Begruendung
        darf nicht die generische 'fehlende Rechnungsfelder'-Liste sein,
        sondern muss Abo/Verlaengerung, die bestaetigte naechste Zahlung und
        das Fehlen einer Rechnung konkret benennen -- ohne Steuer- oder
        Compliance-Zusage."""
        _, belege = agent.verarbeite_eml(
            self.conn, speicher.neuer_lauf(self.conn),
            "schreibki_abo_bestaetigung.eml", _lesen("schreibki_abo_bestaetigung.eml"),
        )
        beleg = belege[0]
        self.assertNotIn("folgende Punkte sind nicht eindeutig erfüllt", beleg.begruendung)
        self.assertNotIn("Fehlende Angaben ergänzen", beleg.review_aufgabe or "")
        self.assertIn("Abo", beleg.begruendung)
        self.assertIn("Verlängerung", beleg.begruendung)
        self.assertIn("bestätigt", beleg.begruendung)
        self.assertIn("05.08.2026", beleg.begruendung)
        self.assertIn("noch keine Rechnung", beleg.begruendung)
        self.assertIn("Rechnung zum Zahlungstermin", beleg.review_aufgabe)
        self.assertEqual(beleg.reviewstatus, REVIEWSTATUS_OFFEN)
        for verbotenes_wort in ("Steuer", "Finanzamt", "konform", "GoBD"):
            self.assertNotIn(verbotenes_wort, beleg.begruendung)

        gespeichert = speicher.alle_belege(self.conn)[0]
        self.assertEqual(gespeichert["begruendung"], beleg.begruendung)
        self.assertEqual(gespeichert["review_aufgabe"], beleg.review_aufgabe)


class HashDuplikatTest(IsolierteDatenbankTestCase):
    def test_erneuter_upload_desselben_anhangs_ist_datei_duplikat(self):
        lauf = speicher.neuer_lauf(self.conn)
        agent.verarbeite_eml(
            self.conn, lauf, "cloudbasis_rechnung_und_zahlung.eml", _lesen("cloudbasis_rechnung_und_zahlung.eml")
        )
        anhang = mailparser.zerlegen(_lesen("cloudbasis_rechnung_und_zahlung.eml")).anhaenge[0]
        wiederholung = agent.verarbeite_datei(self.conn, lauf, anhang.dateiname, anhang.inhalt)
        self.assertEqual(wiederholung.ausgang, AUSGANG_DUBLETTE)
        self.assertIn("byte-identisch", wiederholung.begruendung)
        bestand = speicher.bestand_uebernommen(self.conn)
        self.assertEqual(len(bestand), 2, "Das Datei-Duplikat darf den Bestand nicht vergroessern")

    def test_wiederholter_screenshot_bleibt_original_anfordern(self):
        lauf = speicher.neuer_lauf(self.conn)
        agent.verarbeite_datei(self.conn, lauf, "mobiltel_screenshot.png", _lesen("mobiltel_screenshot.png"))
        wiederholung = agent.verarbeite_datei(
            self.conn, lauf, "mobiltel_screenshot.png", _lesen("mobiltel_screenshot.png")
        )
        self.assertEqual(wiederholung.ausgang, AUSGANG_ORIGINAL_ANFORDERN,
                         "Hash-Duplikate werden nur gegen uebernommene Belege geprueft")


class DokumentartDubletteTest(IsolierteDatenbankTestCase):
    """Gleiche Referenz, gleicher Betrag, gleiches Datum: nur bei gleicher
    Dokumentart eine Dublette."""

    _RECHNUNG = [
        "CloudBasis GmbH", "Rechnung Nr. RE-7001", "Datum: 01.08.2026",
        "Leistungszeitraum: monatlich", "Tarif: Standard",
        "Betrag: 19,00 EUR", "Waehrung: EUR",
    ]
    _ZAHLUNGSBELEG = [
        "CloudBasis GmbH", "Zahlungsbeleg", "Zahlung erhalten zur Rechnung Nr. RE-7001",
        "Datum: 01.08.2026", "Leistungszeitraum: monatlich", "Tarif: Standard",
        "Betrag: 19,00 EUR", "Waehrung: EUR",
    ]

    def test_andere_dokumentart_ist_keine_dublette(self):
        lauf = speicher.neuer_lauf(self.conn)
        agent.verarbeite_datei(self.conn, lauf, "rechnung.pdf", _synthetische_rechnung(self._RECHNUNG))
        zahlungsbeleg = agent.verarbeite_datei(
            self.conn, lauf, "zahlungsbeleg.pdf", _synthetische_rechnung(self._ZAHLUNGSBELEG)
        )
        self.assertEqual(zahlungsbeleg.dokumentart, "zahlungsbeleg")
        self.assertEqual(zahlungsbeleg.ausgang, AUSGANG_UEBERNOMMEN)

    def test_gleiche_dokumentart_bleibt_dublette(self):
        lauf = speicher.neuer_lauf(self.conn)
        agent.verarbeite_datei(self.conn, lauf, "rechnung.pdf", _synthetische_rechnung(self._RECHNUNG))
        erneut = agent.verarbeite_datei(
            self.conn, lauf, "rechnung_erneut.pdf",
            _synthetische_rechnung(["Erneuter Versand"] + self._RECHNUNG),
        )
        self.assertEqual(erneut.ausgang, AUSGANG_DUBLETTE)
        self.assertIn("RE-7001", erneut.begruendung)


class NaechsteAktivitaetTest(unittest.TestCase):
    """Naechste Aktivitaet nur mit Evidenz: bestaetigt, erwartet oder
    unbekannt. Keine Schaetzung."""

    def test_explizites_verlaengerungsdatum_ist_bestaetigte_zahlung(self):
        art, status, datum, begruendung = vorgang.naechste_aktivitaet(
            ["Ihr Abo verlaengert sich am 05.08.2026."]
        )
        self.assertEqual((art, status, datum), ("zahlung", "bestaetigt", "05.08.2026"))
        self.assertIn("bestätigt", begruendung)

    def test_leistungszeitraum_ist_hoechstens_erwarteter_beleg(self):
        art, status, datum, begruendung = vorgang.naechste_aktivitaet(["01.08.2026 - 31.08.2026"])
        self.assertEqual((art, status, datum), ("beleg", "erwartet", "31.08.2026"))
        self.assertNotEqual(status, "bestaetigt")
        self.assertIn("keine Aussage über eine sichere nächste Zahlung", begruendung)

    def test_verlaengerungsdatum_hat_vorrang_vor_zeitraum(self):
        art, status, datum, _ = vorgang.naechste_aktivitaet(
            ["Verlaengerung am 01.09.2026", "01.08.2026 - 31.08.2026"]
        )
        self.assertEqual((art, status, datum), ("zahlung", "bestaetigt", "01.09.2026"))

    def test_ohne_evidenz_unbekannt_ohne_art_und_datum(self):
        art, status, datum, _ = vorgang.naechste_aktivitaet(["Vielen Dank fuer Ihre Zahlung."])
        self.assertIsNone(art)
        self.assertEqual(status, "unbekannt")
        self.assertIsNone(datum)


class ZahlungOhneRechnungTest(IsolierteDatenbankTestCase):
    def test_zahlungsbestaetigung_ohne_rechnung_erzeugt_anforderungsaufgabe(self):
        vorgang_obj, belege = agent.verarbeite_eml(
            self.conn, speicher.neuer_lauf(self.conn),
            "mobiltel_zahlungsbestaetigung.eml", _lesen("mobiltel_zahlungsbestaetigung.eml"),
        )
        self.assertEqual(len(belege), 1)
        beleg = belege[0]
        self.assertEqual(beleg.dokumentart, "zahlungsbeleg")
        self.assertEqual(beleg.reviewstatus, REVIEWSTATUS_OFFEN)
        self.assertEqual(beleg.review_aufgabe, "Rechnung oder Originalbeleg anfordern")
        gespeichert = speicher.alle_belege(self.conn)[0]
        self.assertEqual(gespeichert["review_aufgabe"], "Rechnung oder Originalbeleg anfordern")
        self.assertEqual(vorgang_obj.naechste_aktivitaet_status, "unbekannt")

    def test_zahlungsbeleg_mit_rechnung_im_vorgang_braucht_keine_anforderung(self):
        _, belege = agent.verarbeite_eml(
            self.conn, speicher.neuer_lauf(self.conn),
            "cloudbasis_rechnung_und_zahlung.eml", _lesen("cloudbasis_rechnung_und_zahlung.eml"),
        )
        zahlungsbeleg = [b for b in belege if b.dokumentart == "zahlungsbeleg"][0]
        self.assertNotEqual(zahlungsbeleg.review_aufgabe, "Rechnung oder Originalbeleg anfordern")


class EmlDeterminismusTest(IsolierteDatenbankTestCase):
    def test_identischer_eml_wiederholungslauf_liefert_gleiches_ergebnis(self):
        namen = [
            "cloudbasis_rechnung_und_zahlung.eml", "schreibki_abo_bestaetigung.eml",
            "mobiltel_zahlungsbestaetigung.eml", "domainly_nur_html_rechnung.eml",
        ]

        def _lauf() -> tuple:
            lauf = speicher.neuer_lauf(self.conn)
            ergebnis = []
            for name in namen:
                vorgang_obj, belege = agent.verarbeite_eml(self.conn, lauf, name, _lesen(name))
                ergebnis.append(
                    (
                        vorgang_obj.betreff,
                        vorgang_obj.naechste_aktivitaet_art,
                        vorgang_obj.naechste_aktivitaet_status,
                        vorgang_obj.naechste_aktivitaet_datum,
                        vorgang_obj.naechste_aktivitaet_begruendung,
                        [(b.dateiname, b.dokumentart, b.ausgang, b.begruendung, b.review_aufgabe) for b in belege],
                    )
                )
            return tuple(ergebnis)

        erster = _lauf()
        self.conn.close()
        speicher.reset()
        self.conn = speicher.verbindung()
        zweiter = _lauf()
        self.assertEqual(erster, zweiter)


class ResetRaceTest(IsolierteDatenbankTestCase):
    """Regressionsschutz: Nach einem Reset ruft die Oberflaeche drei
    API-Endpunkte parallel auf; alle Threads muessen die geloeschte
    Datenbank gleichzeitig neu anlegen koennen, ohne dass ein Thread eine
    halb angelegte Datei ohne schema_version-Tabelle erwischt."""

    def test_parallele_erstanlage_nach_reset(self):
        self.conn.close()
        speicher.reset()

        fehler = []
        start = threading.Barrier(8)

        def oeffnen() -> None:
            try:
                start.wait(timeout=10)
                conn = speicher.verbindung()
                version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
                if version != len(speicher.MIGRATIONEN):
                    fehler.append(f"Unerwartete Schema-Version {version}")
                conn.close()
            except Exception as exc:  # noqa: BLE001
                fehler.append(repr(exc))

        threads = [threading.Thread(target=oeffnen) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)
        self.conn = speicher.verbindung()
        self.assertEqual(fehler, [], "Parallele Erstanlage nach Reset darf nie scheitern")


class DetailSchritteEingeklapptTest(unittest.TestCase):
    """Agentenschritte sind standardmaessig eingeklappt, der Agentenplan
    bleibt direkt sichtbar; keine ID- oder Logikaenderung."""

    def test_agentenschritte_stehen_in_details_ohne_open(self):
        html = (REPO_ROOT / "web" / "static" / "index.html").read_text(encoding="utf-8")
        treffer = re.search(
            r'<details class="schritte-details">\s*<summary>Agentenschritte</summary>\s*'
            r'<ul id="detail-schritte" class="audit-liste"></ul>\s*</details>',
            html,
        )
        self.assertIsNotNone(treffer, "Agentenschritte muessen in einem geschlossenen <details> stehen")
        self.assertIn('id="detail-plan"', html, "Agentenplan bleibt ausserhalb von <details> direkt sichtbar")


class RadarLeereElementeTest(IsolierteDatenbankTestCase):
    """Regressionsschutz: Ist der Abovergleich fuer den juengsten Beleg eines
    Anbieters bewusst deaktiviert (z.B. weil er ein Zahlungsbeleg ist), darf
    das Abo-Radar keinen leeren Badge und keine leere Begruendungsflaeche
    rendern -- der Radarstatus wird nie erfunden."""

    def test_juengster_beleg_ohne_radar_einschaetzung_liefert_null_statt_erfundenem_wert(self):
        agent.verarbeite_eml(
            self.conn, speicher.neuer_lauf(self.conn),
            "cloudbasis_rechnung_und_zahlung.eml", _lesen("cloudbasis_rechnung_und_zahlung.eml"),
        )
        radar = speicher.radar_uebersicht(self.conn)
        self.assertEqual(len(radar), 1)
        self.assertIsNone(radar[0]["radar_einschaetzung"], "Kein erfundener Radarstatus fuer einen Zahlungsbeleg")
        self.assertIsNone(radar[0]["radar_begruendung"])

    def test_app_js_rendert_badge_und_begruendung_nur_bei_vorhandenem_wert(self):
        js = (REPO_ROOT / "web" / "static" / "app.js").read_text(encoding="utf-8")
        treffer = re.search(r"function renderRadar\(radar\) \{.*?\n\}\n", js, re.DOTALL)
        self.assertIsNotNone(treffer, "renderRadar() nicht gefunden")
        rumpf = treffer.group(0)
        self.assertRegex(
            rumpf, r"const eintrag = RADAR_LABEL\[r\.einschaetzung\];\s*\n\s*if \(eintrag\)",
            "Badge darf nur erzeugt werden, wenn eine echte Radar-Einschaetzung vorliegt",
        )
        self.assertRegex(
            rumpf, r"if \(r\.begruendung\) \{",
            "Begruendungsflaeche darf nur bei vorhandenem Begruendungstext erzeugt werden",
        )


class ModalSichtbarkeitTest(unittest.TestCase):
    """Regressionsschutz gegen den Demo-Blocker 'Overlay immer sichtbar':
    Autoren-CSS (display:flex auf .detail-overlay) ueberstimmt die
    Browser-Standardregel [hidden] { display:none }. Beide Pruefungen sind
    statisch und brauchen keinen Browser."""

    def test_overlays_starten_mit_hidden_attribut(self):
        html = (REPO_ROOT / "web" / "static" / "index.html").read_text(encoding="utf-8")
        for overlay_id in ("detail-overlay", "reset-overlay"):
            treffer = re.search(rf'<div id="{overlay_id}"[^>]*>', html)
            self.assertIsNotNone(treffer, f"Overlay {overlay_id} fehlt in index.html")
            self.assertIn("hidden", treffer.group(0),
                          f"Overlay {overlay_id} muss beim Seitenstart das hidden-Attribut tragen")

    def test_css_guard_verbirgt_versteckte_overlays(self):
        css = (REPO_ROOT / "web" / "static" / "styles.css").read_text(encoding="utf-8")
        guard = re.search(r"\.detail-overlay\[hidden\]\s*\{[^}]*display\s*:\s*none", css)
        self.assertIsNotNone(
            guard,
            "styles.css braucht die Regel '.detail-overlay[hidden] { display: none; }' -- "
            "sonst ueberstimmt display:flex das hidden-Attribut und beide Dialoge "
            "sind dauerhaft sichtbar (Seite unbedienbar).",
        )


class EmlHttpTest(HttpTestCase):
    """Ende-zu-Ende ueber die echte HTTP-API: EML-Upload, Vorgang in der
    Ergebnis-Antwort, keine absoluten Pfade."""

    def test_eml_upload_ende_zu_ende(self):
        status, daten = self._upload(
            [("cloudbasis_rechnung_und_zahlung.eml", _lesen("cloudbasis_rechnung_und_zahlung.eml"))]
        )
        self.assertEqual(status, 200)
        antwort = json.loads(daten)
        self.assertEqual(len(antwort["belege"]), 2)
        self.assertEqual(
            sorted(b["dokumentart"] for b in antwort["belege"]), ["rechnung", "zahlungsbeleg"]
        )
        self.assertEqual([b["ausgang"] for b in antwort["belege"]], ["uebernommen", "uebernommen"])

        status, daten = self._senden("GET", "/api/ergebnis", host=f"127.0.0.1:{self.port}")
        self.assertEqual(status, 200)
        ergebnis = json.loads(daten)
        self.assertEqual(len(ergebnis["vorgaenge"]), 1)
        vorgang_json = ergebnis["vorgaenge"][0]
        self.assertEqual(vorgang_json["betreff"], "Ihre CloudBasis Rechnung August 2026")
        self.assertEqual(vorgang_json["naechste_aktivitaet_status"], "erwartet")
        self.assertEqual(vorgang_json["naechste_aktivitaet_art"], "beleg")
        beleg_vorgang_ids = {b["vorgang_id"] for b in ergebnis["belege"]}
        self.assertEqual(beleg_vorgang_ids, {vorgang_json["id"]})

        text = daten.decode("utf-8")
        self.assertNotIn("C:\\", text)
        self.assertNotIn(str(REPO_ROOT), text)

    def test_falsch_benannte_eml_landet_in_review(self):
        status, daten = self._upload(
            [("getarnt.txt", _lesen("mobiltel_zahlungsbestaetigung.eml"))]
        )
        self.assertEqual(status, 200)
        antwort = json.loads(daten)
        self.assertEqual(len(antwort["belege"]), 1)
        self.assertEqual(antwort["belege"][0]["ausgang"], AUSGANG_REVIEW)
        self.assertIn("widersprechen", antwort["belege"][0]["begruendung"])


class Migration3Test(unittest.TestCase):
    """Eine bestehende v2-Datenbank migriert sicher auf v3: Backfill ohne
    Raten, neue vorgaenge-Tabelle, optionale beleg_id in beleg_plaene."""

    def setUp(self) -> None:
        self._tempdir = tempfile.mkdtemp(prefix="belegwaechter_migration3_test_")
        self.runtime_dir = Path(self._tempdir) / "runtime"
        self.db_pfad = self.runtime_dir / "belegwaechter.db"
        self.runtime_dir.mkdir(parents=True)
        (self.runtime_dir / "eingang").mkdir()

        self._original_runtime = speicher.RUNTIME_DIR
        self._original_eingang = speicher.EINGANG_DIR
        self._original_db = speicher.DB_PFAD
        speicher.RUNTIME_DIR = self.runtime_dir
        speicher.EINGANG_DIR = self.runtime_dir / "eingang"
        speicher.DB_PFAD = self.db_pfad

    def tearDown(self) -> None:
        speicher.RUNTIME_DIR = self._original_runtime
        speicher.EINGANG_DIR = self._original_eingang
        speicher.DB_PFAD = self._original_db
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def _v2_db_bauen(self) -> None:
        conn = sqlite3.connect(self.db_pfad)
        conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        speicher._migration_001_initial_schema(conn)
        speicher._migration_002_provenienz_status_und_plan(conn)
        conn.execute("INSERT INTO schema_version (version) VALUES (2)")
        conn.execute("INSERT INTO laeufe (id, gestartet_am) VALUES ('lauf-1', datetime('now'))")
        conn.execute(
            """
            INSERT INTO belege (
                id, lauf_id, dateiname, dateihash, dateipfad, dateityp, stufe, quellenstatus,
                referenz, felder_json, checkliste_json, ausgang, begruendung, erfasst_am
            ) VALUES (
                'beleg-v2', 'lauf-1', 'rechnung.pdf', 'hash1', '', 'PDF', 'A', 'original_vorhanden',
                'RE-1', '{}', '[]', 'uebernommen', 'Uebernommen: Test.', datetime('now')
            )
            """
        )
        conn.execute(
            "INSERT INTO beleg_plaene (lauf_id, beleg_id, version, plan_json, revisionsgrund, erstellt_am) "
            "VALUES ('lauf-1', 'beleg-v2', 1, '{}', NULL, datetime('now'))"
        )
        conn.commit()
        conn.close()

    def test_v2_migriert_ohne_raten_auf_v3(self):
        self._v2_db_bauen()

        conn = speicher.verbindung()
        self.assertEqual(conn.execute("SELECT version FROM schema_version").fetchone()[0], 3)

        beleg = conn.execute("SELECT * FROM belege WHERE id = 'beleg-v2'").fetchone()
        self.assertEqual(beleg["dokumentart"], "unbestimmt", "Backfill darf nie eine Dokumentart raten")
        self.assertIsNone(beleg["vorgang_id"])

        self.assertIsNotNone(
            conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vorgaenge'").fetchone()
        )

        alte_plaene = conn.execute("SELECT * FROM beleg_plaene WHERE beleg_id = 'beleg-v2'").fetchall()
        self.assertEqual(len(alte_plaene), 1, "Bestehende Plaene muessen die Migration ueberleben")

        conn.execute(
            "INSERT INTO beleg_plaene (lauf_id, beleg_id, vorgang_id, version, plan_json, erstellt_am) "
            "VALUES ('lauf-1', NULL, 'vorgang-1', 1, '{}', datetime('now'))"
        )
        conn.execute(
            "INSERT INTO agent_schritte (lauf_id, beleg_id, vorgang_id, schritt, status, werkzeug, "
            "begruendung, start, ende) VALUES ('lauf-1', NULL, 'vorgang-1', 'EML zerlegt', 'ok', "
            "'mail-parser', 'Test', '', '')"
        )
        conn.commit()

        sicherung = self.runtime_dir / "belegwaechter.db.vor-migration-v3"
        self.assertTrue(sicherung.exists(), "Sicherungskopie vor Migration 3 muss existieren")
        conn.close()


class MarkenIntegrationTest(unittest.TestCase):
    """OptiTax-Markenintegration: oeffentlicher Produktname ist OptiTax
    (Wortmarke im Desktop-Header, Icon fuer schmale Ansichten, orange
    Markenfarben), interne technische Namen bleiben belegwaechter, alle
    Referenzen lokal."""

    @classmethod
    def setUpClass(cls):
        cls.html = (REPO_ROOT / "web" / "static" / "index.html").read_text(encoding="utf-8")
        cls.js = (REPO_ROOT / "web" / "static" / "app.js").read_text(encoding="utf-8")
        cls.css = (REPO_ROOT / "web" / "static" / "styles.css").read_text(encoding="utf-8")

    def test_seitentitel_ist_optitax(self):
        titel = re.search(r"<title>(.*?)</title>", self.html, re.DOTALL)
        self.assertIsNotNone(titel, "index.html braucht einen <title>")
        self.assertEqual(titel.group(1), "OptiTax – Rechnungen und Abos im Blick")

    def test_kein_sichtbarer_produktname_belegwaechter_mehr(self):
        self.assertNotIn("Belegwächter", self.html)
        self.assertNotIn("Belegwächter", self.js)

    def test_lokales_favicon_und_touch_icon_eingebunden(self):
        self.assertIn('rel="icon" href="/assets/brand/optitax-favicon.ico"', self.html)
        self.assertIn('rel="apple-touch-icon" href="/assets/brand/optitax-icon-192.png"', self.html)
        self.assertNotIn("data:image/svg", self.html, "Das alte Inline-SVG-Favicon muss ersetzt sein")

    def test_wortmarke_im_desktop_header_und_icon_fuer_schmale_ansicht(self):
        kopf = re.search(r"<header.*?</header>", self.html, re.DOTALL)
        self.assertIsNotNone(kopf)
        self.assertIn('src="/assets/brand/optitax-wordmark.png"', kopf.group(0))
        self.assertIn('src="/assets/brand/optitax-icon-64.png"', kopf.group(0))
        # Schmale Ansicht: Wortmarke weicht dem Icon (CSS-Umschaltung).
        self.assertIn(".marke-wortmarke { display: none; }", self.css)
        self.assertIn(".marke-icon { display: block;", self.css)
        # Der alte Schild-Pfad (M12 2 4 5 ...) darf nirgends mehr vorkommen.
        self.assertNotIn("M12 2 4 5", self.html, "Altes Schildsymbol muss entfernt sein")

    def test_zugaenglicher_markenname_und_untertitel_als_html_text(self):
        # Kein doppeltes O: keine ausgeschriebene sichtbare Ueberschrift neben
        # der Wortmarke, aber ein zugaenglicher Textname in der h1.
        self.assertIn('<span class="nur-vorleser">OptiTax</span>', self.html)
        self.assertIn("Rechnungen und Abos im Blick.", self.html)
        self.assertIn("Belege und Kostennachweise rein, geprüfte Übersicht raus.", self.html)

    def test_footer_verwendet_optitax(self):
        self.assertIn("OptiTax — lokal, ohne externe Dienste.", self.html)

    def test_csv_export_heisst_optitax_export(self):
        self.assertIn('"optitax_export.csv wird heruntergeladen …"', self.js)
        server_py = (REPO_ROOT / "web" / "server.py").read_text(encoding="utf-8")
        self.assertIn('filename="optitax_export.csv"', server_py)
        self.assertNotIn("belegwaechter_export.csv", server_py)

    def test_brand_variablen_definiert_und_verwendet(self):
        for var in ("--brand-orange-hell", "--brand-orange", "--brand-orange-dunkel",
                    "--brand-orange-glow", "--brand-focus"):
            self.assertIn(f"{var}:", self.css, f"Brand-Variable {var} fehlt")
        btn = re.search(r"\.btn-primaer \{.*?\}", self.css, re.DOTALL)
        self.assertIsNotNone(btn)
        self.assertIn("var(--brand-orange-hell)", btn.group(0))
        self.assertIn("var(--brand-orange-dunkel)", btn.group(0))
        upload = re.search(r"\.upload-icon \{.*?\}", self.css, re.DOTALL)
        self.assertIsNotNone(upload)
        self.assertIn("var(--brand-orange", upload.group(0))

    def test_keine_alten_blauen_primaerwerte_mehr(self):
        for alt in ("#85b4f2", "#6a9de0", "#8ab8f8", "#2a4f86", "rgba(133, 180, 242"):
            self.assertNotIn(alt, self.css, f"Alter blauer Markenwert {alt} verbleibt in styles.css")

    def test_semantische_statusfarben_bleiben_getrennt(self):
        # Erfolg gruen, Review/Warnung gelb, Dublette grau -- unveraendert.
        self.assertIn("--gruen-bg: rgba(72, 190, 120, 0.16); --gruen-text: #93e2ad;", self.css)
        self.assertIn("--gelb-bg: rgba(238, 195, 90, 0.15); --gelb-text: #f2d489;", self.css)
        self.assertIn("--grau-bg: rgba(165, 180, 200, 0.13); --grau-text: #bcc7d5;", self.css)
        # "Original angefordert" bleibt neutral (Silber), nicht Markenorange.
        blau = re.search(r"--blau-bg: ([^;]+);", self.css)
        self.assertIsNotNone(blau)
        self.assertNotIn("242, 138, 69", blau.group(1))

    def test_optitax_asset_dateien_vollstaendig(self):
        brand_dir = REPO_ROOT / "web" / "static" / "assets" / "brand"
        namen = [p.name for p in brand_dir.iterdir()]
        self.assertEqual(
            sorted(namen),
            [
                "optitax-close-x-24.png",
                "optitax-close-x-32.png",
                "optitax-favicon.ico",
                "optitax-icon-192.png",
                "optitax-icon-512.png",
                "optitax-icon-64.png",
                "optitax-wordmark.png",
            ],
        )

    def test_schliessen_buttons_nutzen_grosses_x_mit_labels(self):
        for button_id in ("detail-schliessen", "reset-schliessen"):
            treffer = re.search(rf'<button id="{button_id}".*?</button>', self.html, re.DOTALL)
            self.assertIsNotNone(treffer, f"Button {button_id} fehlt in index.html")
            block = treffer.group(0)
            self.assertIn('aria-label="Schließen"', block)
            self.assertIn('title="Schließen"', block)
            self.assertIn('src="/assets/brand/optitax-close-x-32.png"', block)
            self.assertIn('width="28" height="28"', block)

    def test_schliessen_klickflaeche_mindestens_44_pixel(self):
        btn = re.search(r"\.schliessen-btn \{.*?\}", self.css, re.DOTALL)
        self.assertIsNotNone(btn)
        self.assertIn("width: 44px;", btn.group(0))
        self.assertIn("height: 44px;", btn.group(0))
        self.assertIn(".schliessen-btn img { display: block; width: 28px; height: 28px;", self.css)

    def test_destruktive_aktionen_nutzen_kein_marken_x(self):
        # Der bestaetigende Reset-Button und der Abbrechen-Button bleiben
        # Textbuttons ohne Markensymbol.
        for button_id in ("reset-ja", "reset-nein"):
            treffer = re.search(rf'<button id="{button_id}".*?</button>', self.html, re.DOTALL)
            self.assertIsNotNone(treffer)
            self.assertNotIn("optitax-close-x", treffer.group(0))

    def test_detail_schliesst_per_button_und_esc(self):
        self.assertIn('$("detail-schliessen").addEventListener("click", detailSchliessen)', self.js)
        self.assertIn('if (e.key === "Escape")', self.js)
        self.assertIn('if (!$("detail-overlay").hidden) detailSchliessen();', self.js)

    def test_reset_dialog_schliesst_per_abbrechen_esc_x_und_reset(self):
        self.assertIn('$("reset-nein").addEventListener("click", () => { $("reset-overlay").hidden = true; })', self.js)
        self.assertIn('$("reset-schliessen").addEventListener("click", () => { $("reset-overlay").hidden = true; })', self.js)
        self.assertIn('if (!$("reset-overlay").hidden) $("reset-overlay").hidden = true;', self.js)
        # Erfolgreicher Reset blendet den Dialog ebenfalls aus.
        reset_ja = re.search(r'\$\("reset-ja"\).addEventListener\(.*?ladeAlles\(\);\s*\}\);', self.js, re.DOTALL)
        self.assertIsNotNone(reset_ja)
        self.assertIn('$("reset-overlay").hidden = true;', reset_ja.group(0))

    def test_keine_externen_urls_oder_absolute_private_pfade(self):
        for name, inhalt in (("index.html", self.html), ("app.js", self.js), ("styles.css", self.css)):
            self.assertNotIn("https://", inhalt, f"{name} darf keine externen URLs enthalten")
            self.assertNotIn("http://", inhalt, f"{name} darf keine externen URLs enthalten")
            self.assertNotRegex(inhalt, r"[A-Za-z]:\\", f"{name} darf keine absoluten Windows-Pfade enthalten")
            self.assertNotIn("C:/", inhalt, f"{name} darf keine absoluten Windows-Pfade enthalten")


class MarkenAssetRouteTest(HttpTestCase):
    """Die OptiTax-Marken-Assets werden lokal unter /assets/brand/ mit
    korrektem Content-Type ausgeliefert."""

    def test_marken_assets_liefern_http_200(self):
        erwartet = {
            "optitax-wordmark.png": "image/png",
            "optitax-icon-512.png": "image/png",
            "optitax-icon-192.png": "image/png",
            "optitax-icon-64.png": "image/png",
            "optitax-favicon.ico": "image/x-icon",
            "optitax-close-x-24.png": "image/png",
            "optitax-close-x-32.png": "image/png",
        }
        for name, content_type in erwartet.items():
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
            conn.request("GET", f"/assets/brand/{name}", headers={"Content-Length": "0"})
            resp = conn.getresponse()
            daten = resp.read()
            conn.close()
            self.assertEqual(resp.status, 200, name)
            self.assertEqual(resp.getheader("Content-Type"), content_type, name)
            self.assertGreater(len(daten), 500, f"{name} sollte kein leerer Platzhalter sein")

    def test_csv_download_heisst_optitax_export(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", "/api/export.csv")
        resp = conn.getresponse()
        resp.read()
        conn.close()
        self.assertEqual(resp.status, 200)
        self.assertIn('filename="optitax_export.csv"', resp.getheader("Content-Disposition", ""))

    def test_brand_route_erlaubt_kein_traversal(self):
        for pfad in (
            "/assets/brand/../server.py",
            "/assets/brand/..",
            "/assets/brand/unterordner/datei.png",
            "/assets/anderer-ordner/datei.png",
        ):
            status, _ = self._senden("GET", pfad, host=f"127.0.0.1:{self.port}")
            self.assertEqual(status, 404, pfad)


class SteuerzeichenTest(unittest.TestCase):
    """Zentrale Normalisierung: C0-Steuerzeichen (z.B. NUL-Spaltentrenner aus
    einer PDF-Textebene) erreichen keine Feldwerte; mittige Steuerzeichen
    werden zum sichtbaren Trenner statt Werte kommentarlos zu verkleben."""

    def test_datumsbereich_mit_nullzeichen_wird_sichtbarer_bereich(self):
        felder = extrahieren.felder_aus_text(
            "Beispiel Dienste AG\nLeistungszeitraum: 01.07.2026\x0031.07.2026\nBetrag: 12,00 EUR"
        )
        zeitraum = felder["zeitraum"].wert
        self.assertIsNotNone(zeitraum)
        self.assertNotIn("\x00", zeitraum)
        self.assertIn("01.07.2026", zeitraum)
        self.assertIn("31.07.2026", zeitraum)
        self.assertIn("-", zeitraum, "Der Bereich braucht einen sichtbaren Trenner")

    def test_referenz_mit_nullzeichen_erhaelt_normalen_trenner(self):
        felder = extrahieren.felder_aus_text(
            "Beispiel Dienste AG\nRechnungsnummer: RE\x00471\nBetrag: 12,00 EUR"
        )
        self.assertEqual(felder["referenz"].wert, "RE-471")

    def test_feldwert_bereinigen_regeln(self):
        from belegwaechter import steuerzeichen

        self.assertEqual(steuerzeichen.feldwert_bereinigen("RE\x00471"), "RE-471")
        self.assertEqual(steuerzeichen.feldwert_bereinigen("a \x00 b"), "a b")
        self.assertEqual(steuerzeichen.feldwert_bereinigen("a\tb\nc"), "a b c")
        self.assertIsNone(steuerzeichen.feldwert_bereinigen("\x00\x01"))
        self.assertIsNone(steuerzeichen.feldwert_bereinigen(None))
        self.assertIsNone(steuerzeichen.feldwert_bereinigen("   "))

    def test_flusstext_erhaelt_zeilenumbrueche(self):
        from belegwaechter import steuerzeichen

        self.assertEqual(
            steuerzeichen.flusstext_bereinigen("Zeile1\nZei\x00le2\x07"),
            "Zeile1\nZei-le2",
        )


class SteuerzeichenApiTest(HttpTestCase):
    """Defensive Bereinigung beim Lesen: auch ein VOR der zentralen
    Normalisierung persistierter Altbestand mit Steuerzeichen verlaesst den
    Server nie ueber API oder CSV -- ohne neue Migration."""

    _C0_VERBOTEN = set(range(0, 9)) | {11, 12} | set(range(14, 32))

    def _altbestand_mit_steuerzeichen_einfuegen(self) -> None:
        conn = speicher.verbindung()
        conn.execute("INSERT INTO laeufe (id, gestartet_am) VALUES ('lauf-c0', datetime('now'))")
        felder_json = json.dumps(
            {
                "anbieter": {"wert": "Beispiel Dienste AG", "herkunft": "aus PDF-Text"},
                "datum": {"wert": "01.07.2026", "herkunft": "aus PDF-Text"},
                "betrag": {"wert": "12,00", "herkunft": "aus PDF-Text"},
                "waehrung": {"wert": "EUR", "herkunft": "aus PDF-Text"},
                "zeitraum": {"wert": "01.07.2026\x0031.07.2026", "herkunft": "aus PDF-Text"},
                "tarif": {"wert": None, "herkunft": "fehlt"},
                "referenz": {"wert": "RE\x00471", "herkunft": "aus PDF-Text"},
            },
            ensure_ascii=False,
        )
        conn.execute(
            """
            INSERT INTO belege (
                id, lauf_id, dateiname, dateihash, dateipfad, dateityp, stufe,
                quellenstatus, anbieter, anbieter_schluessel, datum, betrag,
                waehrung, zeitraum, referenz, felder_json, checkliste_json,
                ausgang, begruendung, dokumentstatus, reviewstatus,
                baseline_bestaetigt, betrag_dezimal, dokumentart, erfasst_am
            ) VALUES (
                'beleg-c0', 'lauf-c0', 'alt.pdf', 'hash-c0', '', 'PDF', 'A',
                'original_vorhanden', 'Beispiel Dienste AG', 'beispiel dienste ag',
                '01.07.2026', '12,00', 'EUR', ?,
                ?, ?, '[]', 'uebernommen',
                'Alt gespeicherter Beleg.', 'vorbereitet', 'keine',
                1, '12.00', 'rechnung', datetime('now')
            )
            """,
            ("01.07.2026\x0031.07.2026", "RE\x00471", felder_json),
        )
        conn.commit()
        conn.close()

    def _c0_pruefen(self, rohbytes: bytes, quelle: str) -> None:
        gefunden = sorted({b for b in rohbytes if b in self._C0_VERBOTEN})
        self.assertEqual(gefunden, [], f"C0-Steuerzeichen in {quelle}: {gefunden}")

    def test_api_und_csv_sind_frei_von_steuerzeichen(self):
        self._altbestand_mit_steuerzeichen_einfuegen()

        status, body = self._senden("GET", "/api/ergebnis", host=f"127.0.0.1:{self.port}")
        self.assertEqual(status, 200)
        self._c0_pruefen(body, "/api/ergebnis")
        self.assertNotIn(b"\\u0000", body)
        daten = json.loads(body)
        beleg = daten["belege"][0]
        self.assertEqual(beleg["felder"]["referenz"]["wert"], "RE-471")
        self.assertEqual(beleg["felder"]["zeitraum"]["wert"], "01.07.2026-31.07.2026")

        status, csv_body = self._senden("GET", "/api/export.csv", host=f"127.0.0.1:{self.port}")
        self.assertEqual(status, 200)
        ohne_zeilenenden = csv_body.replace(b"\r", b"").replace(b"\n", b"")
        self._c0_pruefen(ohne_zeilenenden, "/api/export.csv")
        text = csv_body.decode("utf-8")
        self.assertIn("01.07.2026-31.07.2026", text, "Zeitraum braucht einen sichtbaren Trenner")
        self.assertIn("RE-471", text)

    def test_csv_formelschutz_bleibt_nach_normalisierung_erhalten(self):
        from web.server import _csv_text

        self.assertEqual(_csv_text("=SUMME(A1)"), "'=SUMME(A1)")
        self.assertEqual(_csv_text("\x00=SUMME(A1)"), "'=SUMME(A1)")
        self.assertEqual(_csv_text("a\x00b"), "a-b")


class AnbieterFallbackTest(unittest.TestCase):
    """Anbietererkennung: Datums-, Faelligkeits-, Betrags-, Zeitraum- und
    generische Titelzeilen sind nie ein Anbieter; ohne belastbare
    Organisationszeile greift transparent der E-Mail-Absender."""

    def test_faelligkeitszeile_wird_nie_anbieter_absender_ist_fallback(self):
        felder = extrahieren.felder_aus_text(
            "Fällig am 15.08.2026\nRechnung Nr. RE-77\nBetrag: 12,00 EUR\n01.08.2026\nSeite 1 von 1",
            absender_fallback="Beispiel Software GmbH <billing@beispiel.invalid>",
        )
        self.assertEqual(felder["anbieter"].wert, "Beispiel Software GmbH")
        self.assertEqual(felder["anbieter"].herkunft, "aus E-Mail-Absender")

    def test_gesperrte_zeilen_sind_keine_anbieter(self):
        for zeile in (
            "01.08.2026",
            "5. August 2026",
            "Aug 1, 2026",
            "01.07.2026 - 31.07.2026",
            "12,00 EUR",
            "€ 12,00",
            "Fällig am 15.08.2026",
            "Due on Aug 1, 2026",
            "Bezahlt am 01.08.2026",
            "Paid on Aug 1, 2026",
            "Rechnung",
            "Invoice",
            "Zahlungsbeleg",
            "Receipt",
            "Abo-Bestätigung",
            "Deine Rechnung von Beispiel",
            "Your invoice from Beispiel",
            "Rechnung Nr. RE-1",
        ):
            felder = extrahieren.felder_aus_text(zeile)
            self.assertIsNone(
                felder["anbieter"].wert, f"Zeile {zeile!r} darf nie Anbieter werden"
            )
            self.assertEqual(felder["anbieter"].herkunft, "fehlt")

    def test_echte_organisationszeile_bleibt_anbieter(self):
        felder = extrahieren.felder_aus_text(
            "Beispiel Software GmbH\nRechnung Nr. RE-77\nBetrag: 12,00 EUR",
            absender_fallback="Anderer Absender <x@beispiel.invalid>",
        )
        self.assertEqual(felder["anbieter"].wert, "Beispiel Software GmbH")
        self.assertEqual(felder["anbieter"].herkunft, "aus PDF-Text")


class RechnungVsAboTest(unittest.TestCase):
    """Evidenzreihenfolge Rechnung vs. Abo-Bestaetigung: ein explizites
    Rechnungsmerkmal (Titel, Rechnungsnummer, Rechnungsdatum) schlaegt einen
    beilaeufigen Verlaengerungshinweis; eine reine Bestaetigung ohne
    Rechnungsmerkmale bleibt Abo-Bestaetigung."""

    def test_betreff_deine_rechnung_gewinnt_gegen_verlaengerung_im_mailtext(self):
        art, begruendung = dokumentart.klassifizieren(
            "",
            dateiname="anhang.pdf",
            betreff="Deine Rechnung von Beispiel",
            mailtext="Betrag: 9,00 EUR\nRechnungsdatum: 01.08.2026\nIhr Abo verlängert sich automatisch.",
        )
        self.assertEqual(art, "rechnung")
        self.assertIn("E-Mail-Betreff", begruendung)

    def test_mailtext_mit_rechnungsmerkmalen_und_verlaengerung_ist_rechnung(self):
        art, begruendung = dokumentart.klassifizieren(
            "Deine Rechnung von Beispiel\n"
            "Betrag: 9,00 EUR\nRechnungsdatum: 01.08.2026\n"
            "Ihr Abo verlängert sich automatisch."
        )
        self.assertEqual(art, "rechnung")
        self.assertIn("Vorrang", begruendung)

    def test_reine_abo_bestaetigung_bleibt_abo(self):
        art, _ = dokumentart.klassifizieren(
            "Ihr Abo verlängert sich am 01.09.2026. Der Betrag wird automatisch abgebucht."
        )
        self.assertEqual(art, "abo_bestaetigung")

    def test_abo_bestaetigung_mit_beilaeufigem_rechnungswort_bleibt_abo(self):
        art, _ = dokumentart.klassifizieren(
            "Ihr Abo verlängert sich am 01.09.2026. Rechnung folgt."
        )
        self.assertEqual(art, "abo_bestaetigung")

    def test_zahlungsbeleg_bleibt_getrennt(self):
        art, _ = dokumentart.klassifizieren(
            "Zahlung erhalten\nRechnungsnummer: RE-1\nIhr Abo verlängert sich."
        )
        self.assertEqual(art, "zahlungsbeleg")


if __name__ == "__main__":
    unittest.main()
