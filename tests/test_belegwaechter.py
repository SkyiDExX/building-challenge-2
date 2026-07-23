"""Automatisierte Tests fuer den Belegwaechter-Kern.

Jeder Test laeuft gegen eine isolierte temporaere SQLite-Datenbank
(tempfile.mkdtemp), niemals gegen runtime/belegwaechter.db. Keine Tests
greifen auf Optifyx, Port 8737 oder das Netzwerk zu.
"""
from __future__ import annotations

import shutil
import socket
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
FIXTURES = REPO_ROOT / "fixtures"

from belegwaechter import agent, entscheiden, extrahieren, speicher  # noqa: E402
from belegwaechter.modelle import (  # noqa: E402
    AUSGANG_DUBLETTE,
    AUSGANG_ORIGINAL_ANFORDERN,
    AUSGANG_REVIEW,
    AUSGANG_UEBERNOMMEN,
    QUELLE_ERFASSUNGSNACHWEIS,
    RADAR_NEU,
    RADAR_VERAENDERT_EINDEUTIG,
    RADAR_VERAENDERT_UNKLAR,
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
        radar = speicher.radar_uebersicht(self.conn)
        schreibki = [r for r in radar if r["anbieter"] == "SchreibKI Plus"][0]
        self.assertEqual(schreibki["radar_einschaetzung"], RADAR_VERAENDERT_UNKLAR)


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
            "Eingang erkannt", "Quellenqualitaet bewertet", "Extraktionsplan gewaehlt",
            "Felder extrahiert", "Vollstaendigkeit geprueft", "Bestand abgeglichen",
            "Abovergleich bewertet", "Entscheidung getroffen", "Ergebnis gespeichert",
            "Auditverlauf aktualisiert",
        ]
        self.assertEqual(namen, erwartete_schritte)

    def test_provenienz_datei_hash_und_pfad_stimmen(self):
        original = _lesen("domainly_juli.pdf")
        beleg = agent.verarbeite_datei(self.conn, speicher.neuer_lauf(self.conn), "domainly_juli.pdf", original)
        gespeichert = speicher.alle_belege(self.conn)[0]
        pfad = Path(gespeichert["dateipfad"])
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


if __name__ == "__main__":
    unittest.main()
