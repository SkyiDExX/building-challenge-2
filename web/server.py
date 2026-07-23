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
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from belegwaechter import agent, speicher  # noqa: E402
from belegwaechter.fehlertexte import bereinigen  # noqa: E402

HOST = "127.0.0.1"
PORT = 8850
STATIC_DIR = Path(__file__).resolve().parent / "static"

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


def _beleg_zu_json(row: dict, plaene: list[dict]) -> dict:
    felder = json.loads(row["felder_json"])
    checkliste = json.loads(row["checkliste_json"])
    return {
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
        "begruendung": bereinigen(row["begruendung"]),
        "dokumentart": row["dokumentart"],
        "vorgang_id": row["vorgang_id"],
        "dokumentstatus": row["dokumentstatus"],
        "reviewstatus": row["reviewstatus"],
        "review_aufgabe": row["review_aufgabe"],
        "radar_einschaetzung": row["radar_einschaetzung"],
        "radar_begruendung": row["radar_begruendung"],
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
        "betreff": row["betreff"],
        "absender": row["absender"],
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

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/" or self.path == "/index.html":
            self._datei(STATIC_DIR / "index.html", "text/html; charset=utf-8")
        elif self.path == "/styles.css":
            self._datei(STATIC_DIR / "styles.css", "text/css; charset=utf-8")
        elif self.path == "/app.js":
            self._datei(STATIC_DIR / "app.js", "application/javascript; charset=utf-8")
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
            radar = [
                {
                    "anbieter": r["anbieter"],
                    "einschaetzung": r["radar_einschaetzung"],
                    "begruendung": r["radar_begruendung"],
                    "zeitraum": r["zeitraum"],
                    "betrag": r["betrag"],
                    "waehrung": r["waehrung"],
                    "reviewstatus": r["reviewstatus"],
                    "review_aufgabe": r["review_aufgabe"],
                }
                for r in speicher.radar_uebersicht(conn)
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
                if b["ausgang"] != "uebernommen":
                    continue
                schreiber.writerow(
                    [
                        _csv_text(b["anbieter"]),
                        _csv_text(b["datum"]),
                        b["betrag_dezimal"] or "",
                        _csv_text(b["waehrung"]),
                        _csv_text(b["zeitraum"]),
                        _csv_text(b["referenz"]),
                        _csv_text(b["quellenstatus"]),
                        _csv_text(b["dateiname"]),
                    ]
                )
            body = ("﻿" + puffer.getvalue()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="belegwaechter_export.csv"')
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
