"""Lokaler Web-Server fuer den Belegwaechter: reine Python-Standardbibliothek
(http.server), liefert die statische Oberflaeche aus und bietet eine kleine
JSON-API fuer Upload, Ergebnis, Radar, Audit, Export und Reset.

Bindet ausschliesslich an 127.0.0.1. Fester Port 8850, niemals 8737 (Optifyx-
Produktionsdienst). Kein CORS, keine externen Aufrufe.

Alle /api/*-Routen pruefen Client-IP (nur Loopback) und Host gegen eine zur
Laufzeit aus der tatsaechlich gebundenen Serveradresse abgeleitete Allowlist
(siehe _erlaubte_hosts) -- das erlaubt Tests auf Port 0, ohne die Pruefung
global aufzuweichen. Veraendernde Endpunkte pruefen zusaetzlich Origin/Referer.
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from belegwaechter import agent, dateinamen, datumformat, exportregeln, speicher, steuerzeichen  # noqa: E402
from belegwaechter.fehlertexte import bereinigen  # noqa: E402

HOST = "127.0.0.1"
PORT = 8850
STATIC_DIR = Path(__file__).resolve().parent / "static"
ASSETS_DIR = STATIC_DIR / "assets"

# Nur einfache Dateinamen ohne Pfadtrennzeichen, optional im festen
# Unterordner brand/ (Marken-Assets) -- kein Traversal moeglich, unabhaengig
# von der zusaetzlichen Basis-Pruefung in _asset_datei.
_ASSET_PFAD_MUSTER = re.compile(r"^/assets/(?:brand/)?[A-Za-z0-9._-]+$")
_ASSET_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
}

# Die Kosten-CSV bildet wirtschaftliche Kosten ab, nicht jede vorhandene
# Nachweisdatei. Die alleinige Quelle fuer Exportfaehigkeit (Dokumentart,
# Ausgang, kritische Vollstaendigkeit) ist exportregeln.exportfaehig().

# Benutzerfreundliche Anzeige des Quellenstatus in der Kosten-CSV statt des
# internen Slugs; unbekannte Werte fallen unveraendert durch.
_QUELLENSTATUS_ANZEIGE = {
    "original_vorhanden": "Original vorhanden",
    "erfassungsnachweis": "Erfassungsnachweis",
    "hinweis": "Hinweis, kein Beleg",
}

# Original-PDF-Route: die Beleg-ID ist der einzige Client-Input; sie wird
# nur als DB-Schluessel verwendet, nie als Pfadbestandteil.
_BELEG_ORIGINAL_MUSTER = re.compile(r"^/api/belege/([A-Za-z0-9-]{1,64})/original$")

MAX_ANFRAGE_BYTES = 20 * 1024 * 1024  # gesamte HTTP-Anfrage
MAX_DATEI_BYTES = 10 * 1024 * 1024  # einzelne Datei
MAX_DATEIEN_JE_CHARGE = 25

_ZUGRIFF_VERWEIGERT = {"fehler": "Zugriff nur von der lokalen Oberfläche erlaubt."}


class AnfrageZuGrossFehler(ValueError):
    """Groessenverletzung (Anfrage oder Content-Length), fuehrt zu HTTP 413
    statt zum generischen 400 fuer sonstige Parsing-Fehler."""


def _rumpf_verwerfen(rfile, laenge: int) -> None:
    """Liest und verwirft angekuendigte Body-Bytes, bevor eine Fehlerantwort
    gesendet wird. Ohne das drainen wuerde der Client waehrend eines noch
    laufenden Sendevorgangs einen abrupten Verbindungsabbruch erleben, statt
    die Fehlerantwort sauber zu erhalten. Nach oben begrenzt: dieser Server
    akzeptiert ohnehin nur Loopback-Verbindungen (siehe _zugriff_erlaubt)."""
    rest = min(laenge, MAX_ANFRAGE_BYTES * 4)
    while rest > 0:
        stueck = rfile.read(min(rest, 1024 * 1024))
        if not stueck:
            break
        rest -= len(stueck)


def _api_text(wert):
    """Defensive Bereinigung beim Ausliefern: bestehende, vor der zentralen
    Steuerzeichen-Normalisierung persistierte Werte werden beim Lesen
    bereinigt (keine Migration noetig). None bleibt None."""
    if not isinstance(wert, str):
        return wert
    return steuerzeichen.feldwert_bereinigen(wert) or ""


def _original_pdf_verfuegbar(row: dict) -> bool:
    """Serverseitig berechnete Wahrheit fuer die Oberflaeche: ein
    Original-PDF gilt nur als verfuegbar, wenn der Beleg ein PDF ist, ein
    gueltiger storage_key existiert, der Pfad sicher aufloesbar ist, die
    Datei existiert und die ersten Bytes erneut %PDF bestaetigen. Ein
    MAILTEXT-Beleg oder ein Bild bekommt nie eine PDF-URL."""
    if row["dateityp"] != "PDF" or not row["storage_key"]:
        return False
    try:
        pfad = speicher.pfad_aus_key(row["storage_key"])
        with open(pfad, "rb") as datei:
            return datei.read(5) == b"%PDF-"
    except (dateinamen.UnsichererPfadFehler, OSError):
        return False


def _beleg_zu_json(row: dict, plaene: list[dict]) -> dict:
    felder = json.loads(row["felder_json"])
    for feld in felder.values():
        if feld.get("wert") is not None:
            feld["wert"] = steuerzeichen.feldwert_bereinigen(feld["wert"])
    # Sichtbare Darstellung normalisieren, interne Werte bleiben gespeichert:
    # einzelne Daten als TT.MM.JJJJ, Zeitraeume als "TT.MM.JJJJ bis TT.MM.JJJJ".
    if felder.get("datum", {}).get("wert"):
        felder["datum"]["wert"] = datumformat.datum_ui(felder["datum"]["wert"])
    if felder.get("zeitraum", {}).get("wert"):
        felder["zeitraum"]["wert"] = datumformat.zeitraum_ui(felder["zeitraum"]["wert"])
    checkliste = json.loads(row["checkliste_json"])
    pdf_verfuegbar = _original_pdf_verfuegbar(row)
    ergebnis_zusatz = (
        {"original_pdf_url": f"/api/belege/{row['id']}/original"} if pdf_verfuegbar else {}
    )
    return {
        **ergebnis_zusatz,
        "original_pdf_verfuegbar": pdf_verfuegbar,
        # Berechnetes Feld aus der zentralen Exportregel -- die UI leitet
        # "Für Export bereit" nie selbst aus Statuswerten ab.
        "exportbereit": exportregeln.exportfaehig(
            row["dokumentart"], row["ausgang"], exportregeln.checkliste_aus_json(checkliste)
        ),
        "id": row["id"],
        "lauf_id": row["lauf_id"],
        "dateiname": row["dateiname"],
        "dateihash": row["dateihash"],
        "dateityp": row["dateityp"],
        "stufe": row["stufe"],
        "quellenstatus": row["quellenstatus"],
        "extraktionsmethode": row["extraktionsmethode"],
        "felder": felder,
        "checkliste": checkliste,
        "ausgang": row["ausgang"],
        "begruendung": _api_text(bereinigen(row["begruendung"])),
        "dokumentart": row["dokumentart"],
        "vorgang_id": row["vorgang_id"],
        "dokumentstatus": row["dokumentstatus"],
        "reviewstatus": row["reviewstatus"],
        "review_aufgabe": _api_text(row["review_aufgabe"]),
        "radar_einschaetzung": row["radar_einschaetzung"],
        "radar_begruendung": _api_text(row["radar_begruendung"]),
        "erfasst_am": row["erfasst_am"],
        "plaene": [p["plan"] for p in plaene],
    }


def _vorgang_zu_json(row: dict) -> dict:
    return {
        "id": row["id"],
        "lauf_id": row["lauf_id"],
        "quelle": row["quelle"],
        "eml_dateiname": row["eml_dateiname"],
        "eml_hash": row["eml_hash"],
        "betreff": _api_text(row["betreff"]),
        "absender": _api_text(row["absender"]),
        "mail_datum": row["mail_datum"],
        "naechste_aktivitaet_art": row["naechste_aktivitaet_art"],
        "naechste_aktivitaet_status": row["naechste_aktivitaet_status"],
        "naechste_aktivitaet_datum": row["naechste_aktivitaet_datum"],
        "naechste_aktivitaet_begruendung": bereinigen(row["naechste_aktivitaet_begruendung"] or ""),
        "erstellt_am": row["erstellt_am"],
    }


def _lese_multipart(handler: "BelegwaechterHandler") -> list[tuple[str, bytes]]:
    """Minimaler multipart/form-data-Parser fuer Datei-Uploads. Reine
    Standardbibliothek, keine externe Formular-Bibliothek noetig fuer den
    Demo-Umfang (mehrere Dateien unter demselben Feldnamen)."""
    ctype = handler.headers.get("Content-Type", "")
    if "multipart/form-data" not in ctype or "boundary=" not in ctype:
        raise ValueError("Kein multipart/form-data mit boundary gefunden.")
    boundary = ctype.split("boundary=", 1)[1].strip().strip('"').encode("utf-8")
    laenge = int(handler.headers.get("Content-Length", "0"))
    if laenge > MAX_ANFRAGE_BYTES:
        _rumpf_verwerfen(handler.rfile, laenge)
        raise AnfrageZuGrossFehler("Anfrage überschreitet die zulässige Gesamtgröße.")
    rohdaten = handler.rfile.read(laenge)

    teile = rohdaten.split(b"--" + boundary)
    ergebnisse: list[tuple[str, bytes]] = []
    for teil in teile:
        teil = teil.strip(b"\r\n")
        if not teil or teil == b"--":
            continue
        if b"\r\n\r\n" not in teil:
            continue
        kopf, inhalt = teil.split(b"\r\n\r\n", 1)
        inhalt = inhalt.rstrip(b"\r\n")
        kopf_text = kopf.decode("utf-8", errors="replace")
        if "filename=" not in kopf_text:
            continue
        dateiname = kopf_text.split("filename=", 1)[1].split('"')[1]
        if not dateiname:
            continue
        ergebnisse.append((dateiname, inhalt))
    return ergebnisse


def _erlaubte_hosts(handler: "BelegwaechterHandler") -> set[str]:
    port = handler.server.server_address[1]
    return {f"127.0.0.1:{port}", f"localhost:{port}"}


def _herkunft_erlaubt(wert: str, erlaubte_hosts: set[str]) -> bool:
    for host in erlaubte_hosts:
        praefix = f"http://{host}"
        if wert == praefix or wert.startswith(praefix + "/"):
            return True
    return False


def _zugriff_erlaubt(handler: "BelegwaechterHandler", veraendernd: bool) -> tuple[bool, int, dict]:
    if handler.client_address[0] not in ("127.0.0.1", "::1"):
        return False, 403, _ZUGRIFF_VERWEIGERT

    erlaubte_hosts = _erlaubte_hosts(handler)
    host = handler.headers.get("Host", "")
    if host not in erlaubte_hosts:
        return False, 403, _ZUGRIFF_VERWEIGERT

    if veraendernd:
        for header_name in ("Origin", "Referer"):
            wert = handler.headers.get(header_name, "")
            if wert and not _herkunft_erlaubt(wert, erlaubte_hosts):
                return False, 403, _ZUGRIFF_VERWEIGERT

    return True, 200, {}


def _csv_text(wert) -> str:
    text = "" if wert is None else str(wert)
    # Erst Steuerzeichen normalisieren (defensiv auch fuer Altbestand),
    # DANN der Formelschutz -- die Reihenfolge stellt sicher, dass ein durch
    # die Normalisierung entstandener fuehrender Bindestrich ebenfalls
    # escaped wird.
    text = steuerzeichen.feldwert_bereinigen(text) or ""
    if text.lstrip()[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


class BelegwaechterHandler(BaseHTTPRequestHandler):
    server_version = "Belegwaechter/0.1"

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        sys.stderr.write(f"[belegwaechter] {self.address_string()} - {format % args}\n")

    def _json(self, status: int, payload: dict | list) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _datei(self, pfad: Path, content_type: str) -> None:
        if not pfad.exists():
            self._json(404, {"fehler": "nicht gefunden"})
            return
        body = pfad.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _asset_datei(self) -> None:
        """Liefert eine statische Datei aus web/static/assets/ (z.B. das
        Hintergrundfoto). Nur einfache Dateinamen ohne Pfadtrennzeichen
        (siehe _ASSET_PFAD_MUSTER) und nur bekannte Bildendungen; der
        aufgeloeste Pfad muss zusaetzlich nachweislich unterhalb von
        ASSETS_DIR liegen, bevor irgendetwas gelesen wird."""
        if not _ASSET_PFAD_MUSTER.match(self.path):
            self._json(404, {"fehler": "nicht gefunden"})
            return
        dateiname = self.path.removeprefix("/assets/")
        content_type = _ASSET_CONTENT_TYPES.get(Path(dateiname).suffix.lower())
        if content_type is None:
            self._json(404, {"fehler": "nicht gefunden"})
            return
        kandidat = (ASSETS_DIR / dateiname).resolve()
        if not kandidat.is_relative_to(ASSETS_DIR.resolve()):
            self._json(404, {"fehler": "nicht gefunden"})
            return
        self._datei(kandidat, content_type)

    def _beleg_original(self, beleg_id: str) -> None:
        """Liefert das gespeicherte Original-PDF eines Belegs. Der Beleg wird
        ausschliesslich ueber seine Datenbank-ID geladen; der interne
        storage_key stammt nie aus der URL und wird nur ueber
        speicher.pfad_aus_key() aufgeloest. Jede Abweichung (unbekannte ID,
        kein PDF, fehlende Datei, widerspruechliche Magic Bytes) endet in
        einem wertfreien 404 ohne Pfadangaben."""
        nicht_gefunden = {"fehler": "nicht gefunden"}
        conn = speicher.verbindung()
        row = conn.execute(
            "SELECT dateiname, speichername, dateityp, storage_key FROM belege WHERE id = ?",
            (beleg_id,),
        ).fetchone()
        conn.close()
        if row is None or row["dateityp"] != "PDF" or not row["storage_key"]:
            self._json(404, nicht_gefunden)
            return
        try:
            pfad = speicher.pfad_aus_key(row["storage_key"])
            inhalt = pfad.read_bytes()
        except (dateinamen.UnsichererPfadFehler, OSError):
            self._json(404, nicht_gefunden)
            return
        if not inhalt.startswith(b"%PDF-"):
            self._json(404, nicht_gefunden)
            return
        # speichername() ist eine harte ASCII-Whitelist -- header-sicher und
        # ohne Pfadbestandteile.
        anzeigename = dateinamen.speichername(row["speichername"] or row["dateiname"] or "beleg.pdf")
        if not anzeigename.lower().endswith(".pdf"):
            anzeigename += ".pdf"
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", f'inline; filename="{anzeigename}"')
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(inhalt)))
        self.end_headers()
        self.wfile.write(inhalt)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/" or self.path == "/index.html":
            self._datei(STATIC_DIR / "index.html", "text/html; charset=utf-8")
        elif self.path == "/styles.css":
            self._datei(STATIC_DIR / "styles.css", "text/css; charset=utf-8")
        elif self.path == "/app.js":
            self._datei(STATIC_DIR / "app.js", "application/javascript; charset=utf-8")
        elif self.path.startswith("/assets/"):
            self._asset_datei()
        elif self.path.startswith("/api/belege/"):
            treffer = _BELEG_ORIGINAL_MUSTER.match(self.path)
            if treffer is None:
                self._json(404, {"fehler": "nicht gefunden"})
                return
            erlaubt, code, fehler = _zugriff_erlaubt(self, veraendernd=False)
            if not erlaubt:
                self._json(code, fehler)
                return
            self._beleg_original(treffer.group(1))
        elif self.path == "/api/ergebnis":
            erlaubt, code, fehler = _zugriff_erlaubt(self, veraendernd=False)
            if not erlaubt:
                self._json(code, fehler)
                return
            conn = speicher.verbindung()
            belege = [
                _beleg_zu_json(r, speicher.plaene_fuer_beleg(conn, r["id"]))
                for r in speicher.alle_belege(conn)
            ]
            vorgaenge = [_vorgang_zu_json(r) for r in speicher.vorgaenge_liste(conn)]
            conn.close()
            self._json(200, {"belege": belege, "vorgaenge": vorgaenge})
        elif self.path == "/api/radar":
            erlaubt, code, fehler = _zugriff_erlaubt(self, veraendernd=False)
            if not erlaubt:
                self._json(code, fehler)
                return
            conn = speicher.verbindung()
            # Kostenrelevante Radar-Karten folgen der zentralen
            # Exportregel: nur exportfaehige Kosten-Belege bilden eine
            # eigene Karte.
            radar = [
                {
                    "anbieter": _api_text(r["anbieter"]),
                    "einschaetzung": r["radar_einschaetzung"],
                    "begruendung": _api_text(r["radar_begruendung"]),
                    "zeitraum": datumformat.zeitraum_ui(_api_text(r["zeitraum"])),
                    "betrag": _api_text(r["betrag"]),
                    "waehrung": _api_text(r["waehrung"]),
                    "reviewstatus": r["reviewstatus"],
                    "review_aufgabe": r["review_aufgabe"],
                }
                for r in speicher.radar_uebersicht(conn)
                if exportregeln.exportfaehig_zeile(r)
            ]
            conn.close()
            self._json(200, {"radar": radar})
        elif self.path == "/api/audit":
            erlaubt, code, fehler = _zugriff_erlaubt(self, veraendernd=False)
            if not erlaubt:
                self._json(code, fehler)
                return
            conn = speicher.verbindung()
            audit = [dict(r) for r in speicher.audit_liste(conn)]
            conn.close()
            self._json(200, {"audit": audit})
        elif self.path == "/api/export.csv":
            erlaubt, code, fehler = _zugriff_erlaubt(self, veraendernd=False)
            if not erlaubt:
                self._json(code, fehler)
                return
            conn = speicher.verbindung()
            belege = speicher.alle_belege(conn)
            conn.close()
            puffer = io.StringIO()
            schreiber = csv.writer(puffer, delimiter=";")
            schreiber.writerow(
                ["Anbieter", "Datum", "Betrag", "Waehrung", "Zeitraum", "Referenz", "Quellenstatus", "Quelldatei"]
            )
            for b in belege:
                if not exportregeln.exportfaehig_zeile(b):
                    continue
                schreiber.writerow(
                    [
                        _csv_text(b["anbieter"]),
                        _csv_text(datumformat.datum_csv(b["datum"])),
                        b["betrag_dezimal"] or "",
                        _csv_text(b["waehrung"]),
                        _csv_text(datumformat.zeitraum_csv(b["zeitraum"])),
                        _csv_text(b["referenz"]),
                        _csv_text(_QUELLENSTATUS_ANZEIGE.get(b["quellenstatus"], b["quellenstatus"])),
                        _csv_text(b["dateiname"]),
                    ]
                )
            body = ("﻿" + puffer.getvalue()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="optitax_export.csv"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._json(404, {"fehler": "nicht gefunden"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/verarbeiten":
            erlaubt, code, fehler = _zugriff_erlaubt(self, veraendernd=True)
            if not erlaubt:
                self._json(code, fehler)
                return

            ctype = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in ctype:
                self._json(415, {"fehler": "Erwartet wird multipart/form-data."})
                return

            try:
                dateien_liste = _lese_multipart(self)
            except AnfrageZuGrossFehler as exc:
                self._json(413, {"fehler": str(exc)})
                return
            except ValueError as exc:
                self._json(400, {"fehler": str(exc)})
                return

            if not dateien_liste:
                self._json(400, {"fehler": "Keine Dateien im Upload gefunden."})
                return
            if len(dateien_liste) > MAX_DATEIEN_JE_CHARGE:
                self._json(413, {"fehler": f"Zu viele Dateien in einer Charge (maximal {MAX_DATEIEN_JE_CHARGE})."})
                return

            gesamtgroesse = 0
            for _, inhalt in dateien_liste:
                if len(inhalt) > MAX_DATEI_BYTES:
                    self._json(413, {"fehler": "Eine Datei überschreitet die zulässige Größe."})
                    return
                gesamtgroesse += len(inhalt)
            if gesamtgroesse > MAX_ANFRAGE_BYTES:
                self._json(413, {"fehler": "Die Anfrage überschreitet die zulässige Gesamtgröße."})
                return

            conn = speicher.verbindung()
            lauf_id, ergebnisse = agent.verarbeite_charge(conn, dateien_liste)
            schritte = speicher.agent_schritte_fuer_lauf(conn, lauf_id)
            conn.close()
            self._json(
                200,
                {
                    "lauf_id": lauf_id,
                    "belege": [
                        {
                            "dateiname": b.dateiname,
                            "ausgang": b.ausgang,
                            "begruendung": bereinigen(b.begruendung),
                            "stufe": b.stufe,
                            "dokumentart": b.dokumentart,
                            "vorgang_id": b.vorgang_id,
                            "dokumentstatus": b.dokumentstatus,
                            "reviewstatus": b.reviewstatus,
                            "review_aufgabe": b.review_aufgabe,
                        }
                        for b in ergebnisse
                    ],
                    "schritte": schritte,
                },
            )
        elif self.path == "/api/reset":
            erlaubt, code, fehler = _zugriff_erlaubt(self, veraendernd=True)
            if not erlaubt:
                self._json(code, fehler)
                return
            speicher.reset()
            self._json(200, {"status": "zurueckgesetzt"})
        else:
            self._json(404, {"fehler": "nicht gefunden"})


def main() -> None:
    speicher.verbindung().close()  # legt runtime/ + Schema an, falls noch nicht vorhanden
    server = ThreadingHTTPServer((HOST, PORT), BelegwaechterHandler)
    print(f"Belegwaechter laeuft auf http://{HOST}:{PORT} (Strg+C zum Beenden)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")


if __name__ == "__main__":
    main()
