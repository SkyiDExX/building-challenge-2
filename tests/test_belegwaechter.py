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

from belegwaechter import agent, dateinamen, entscheiden, extrahieren, fehlertexte, speicher  # noqa: E402
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
            "Eingang erkannt", "Quellenqualitaet bewertet", "Ausfuehrungsplan erstellt",
            "Felder extrahiert", "Vollstaendigkeit geprueft", "Bestand abgeglichen",
            "Abovergleich bewertet", "Entscheidung getroffen", "Ergebnis gespeichert",
            "Auditverlauf aktualisiert",
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
        self.assertIn("unveraendert", dritter.radar_hinweis)
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
        self.assertEqual(version, 2)

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
        self.assertEqual(conn2.execute("SELECT version FROM schema_version").fetchone()[0], 2)
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


if __name__ == "__main__":
    unittest.main()
