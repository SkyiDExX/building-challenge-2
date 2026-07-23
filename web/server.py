"""Lokaler Web-Server fuer den Belegwaechter: reine Python-Standardbibliothek
(http.server), liefert die statische Oberflaeche aus und bietet eine kleine
JSON-API fuer Upload, Ergebnis, Radar, Audit, Export und Reset.

Bindet ausschliesslich an 127.0.0.1. Fester Port 8850, niemals 8737 (Optifyx-
Produktionsdienst). Kein CORS, keine externen Aufrufe.
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

HOST = "127.0.0.1"
PORT = 8850
STATIC_DIR = Path(__file__).resolve().parent / "static"

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB Gesamtgroesse je Anfrage, Demo-Grenze


def _beleg_zu_json(row: dict) -> dict:
    felder = json.loads(row["felder_json"])
    checkliste = json.loads(row["checkliste_json"])
    return {
        "id": row["id"],
        "dateiname": row["dateiname"],
        "dateihash": row["dateihash"],
        "dateipfad": row["dateipfad"],
        "dateityp": row["dateityp"],
        "stufe": row["stufe"],
        "quellenstatus": row["quellenstatus"],
        "felder": felder,
        "checkliste": checkliste,
        "ausgang": row["ausgang"],
        "begruendung": row["begruendung"],
        "radar_einschaetzung": row["radar_einschaetzung"],
        "radar_begruendung": row["radar_begruendung"],
        "erfasst_am": row["erfasst_am"],
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
    if laenge > MAX_UPLOAD_BYTES:
        raise ValueError("Anfrage zu gross fuer die Demo-Grenze.")
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
            conn = speicher.verbindung()
            belege = [_beleg_zu_json(r) for r in speicher.alle_belege(conn)]
            conn.close()
            self._json(200, {"belege": belege})
        elif self.path == "/api/radar":
            conn = speicher.verbindung()
            radar = [
                {
                    "anbieter": r["anbieter"],
                    "einschaetzung": r["radar_einschaetzung"],
                    "begruendung": r["radar_begruendung"],
                    "zeitraum": r["zeitraum"],
                    "betrag": r["betrag"],
                    "waehrung": r["waehrung"],
                }
                for r in speicher.radar_uebersicht(conn)
            ]
            conn.close()
            self._json(200, {"radar": radar})
        elif self.path == "/api/audit":
            conn = speicher.verbindung()
            audit = [dict(r) for r in speicher.audit_liste(conn)]
            conn.close()
            self._json(200, {"audit": audit})
        elif self.path == "/api/export.csv":
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
                    [b["anbieter"], b["datum"], b["betrag"], b["waehrung"], b["zeitraum"], b["referenz"], b["quellenstatus"], b["dateiname"]]
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
            try:
                dateien_liste = _lese_multipart(self)
            except ValueError as exc:
                self._json(400, {"fehler": str(exc)})
                return
            if not dateien_liste:
                self._json(400, {"fehler": "Keine Dateien im Upload gefunden."})
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
                            "begruendung": b.begruendung,
                            "stufe": b.stufe,
                        }
                        for b in ergebnisse
                    ],
                    "schritte": schritte,
                },
            )
        elif self.path == "/api/reset":
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
