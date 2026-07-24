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
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from belegwaechter import agent, betraege, dateinamen, datumformat, exportregeln, korrekturen, kostenprofil, speicher, steuerzeichen  # noqa: E402
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

# Original-PDF-Route: die Beleg-ID ist der einzige Client-Input, der die
# geladene Datei bestimmt; der optionale sichtbare Namens-Slug (max. 100
# sichere ASCII-Zeichen) wird NIE als Dateipfad verwendet und dient nur
# einem verstaendlichen Tab-/Dateinamen.
_BELEG_ORIGINAL_MUSTER = re.compile(
    r"^/api/belege/([A-Za-z0-9-]{1,64})/original(?:/[A-Za-z0-9._-]{1,100}\.pdf)?$"
)

_DOKUMENTART_DATEINAME = {
    "rechnung": "Rechnung",
    "zahlungsbeleg": "Zahlungsbeleg",
    "abo_bestaetigung": "Abo-Bestaetigung",
    "sonstiger_kostennachweis": "Kostennachweis",
}


def _pdf_slug(row: dict, werte: dict) -> str:
    """Serverseitig erzeugter, aussagekraeftiger PDF-Name aus Produkt,
    Dokumentart, Rechnungsmonat und Betrag -- ohne persoenliche Namen,
    E-Mail-Adressen oder Referenznummern. Die harte ASCII-Whitelist von
    dateinamen.speichername() begrenzt Zeichen und Laenge."""
    teile = []
    produkt = werte.get("produkt") or kostenprofil.anzeige_name(werte.get("anbieter"))
    if produkt:
        teile.append(produkt)
    teile.append(_DOKUMENTART_DATEINAME.get(row["dokumentart"], "Beleg"))
    datum_iso = datumformat.datum_csv(werte.get("datum"))
    if datum_iso and re.match(r"^\d{4}-\d{2}-\d{2}$", datum_iso):
        teile.append(datum_iso[:7])
    if row.get("betrag_dezimal") and werte.get("waehrung"):
        teile.append(f"{row['betrag_dezimal'].replace('.', '-')}-{werte['waehrung']}")
    return dateinamen.speichername("_".join(teile)[:90] + ".pdf")
_BELEG_KORREKTUR_MUSTER = re.compile(r"^/api/belege/([A-Za-z0-9-]{1,64})/korrekturen$")
# Original-EML-Routen: ausschliesslich per Vorgangs-ID, nie per Pfad.
_VORGANG_EML_MUSTER = re.compile(r"^/api/vorgaenge/([A-Za-z0-9-]{1,64})/original-eml$")
_VORGANG_ANSICHT_MUSTER = re.compile(r"^/api/vorgaenge/([A-Za-z0-9-]{1,64})/ansicht$")
_WAEHRUNG_MUSTER = re.compile(r"^[A-Z]{3}$")
_MAX_KORREKTUR_FELDLAENGE = 200
_MAX_KORREKTUR_BODY = 64 * 1024

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


def _original_eml_verfuegbar(conn, row: dict) -> bool:
    """Nur ein Mailtext-Beleg mit Vorgang und sicher aufloesbarer,
    vorhandener EML-Rohdatei bekommt eine Download-URL. PDF-Kinder einer
    EML behalten stattdessen ihr Original-PDF am Dokument."""
    if row["dateityp"] != "MAILTEXT" or not row["vorgang_id"]:
        return False
    vorgang = conn.execute(
        "SELECT eml_storage_key FROM vorgaenge WHERE id = ?", (row["vorgang_id"],)
    ).fetchone()
    if vorgang is None or not vorgang["eml_storage_key"]:
        return False
    try:
        return speicher.pfad_aus_key(vorgang["eml_storage_key"]).is_file()
    except (dateinamen.UnsichererPfadFehler, OSError):
        return False


def _beleg_zu_json(
    row: dict, plaene: list[dict], korrekturliste: list[dict] | None = None, conn=None
) -> dict:
    # Effektive Felder (automatische Rohwerte plus letzte gueltige manuelle
    # Korrektur) sind die einzige fachliche Sicht der API.
    auto_felder = json.loads(row["felder_json"])
    felder, _ = korrekturen.effektive_felder(auto_felder, korrekturliste or [])
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
    ergebnis_zusatz = {}
    if pdf_verfuegbar:
        werte = {name: (f or {}).get("wert") for name, f in felder.items()}
        ergebnis_zusatz["original_pdf_url"] = (
            f"/api/belege/{row['id']}/original/{_pdf_slug(row, werte)}"
        )
    eml_verfuegbar = _original_eml_verfuegbar(conn, row) if conn is not None else False
    if eml_verfuegbar:
        ergebnis_zusatz["original_eml_url"] = f"/api/vorgaenge/{row['vorgang_id']}/original-eml"
    return {
        **ergebnis_zusatz,
        "original_pdf_verfuegbar": pdf_verfuegbar,
        "original_eml_verfuegbar": eml_verfuegbar,
        # `anbieter` bleibt intern der rechtliche Aussteller; die API stellt
        # ihn zusaetzlich unter seinem fachlichen Namen bereit.
        "rechnungsaussteller": (felder.get("anbieter") or {}).get("wert"),
        # Berechnetes Feld aus der zentralen Exportregel -- die UI leitet
        # "Für Export bereit" nie selbst aus Statuswerten ab.
        "exportbereit": exportregeln.exportfaehig(
            row["dokumentart"], row["ausgang"], exportregeln.checkliste_aus_json(checkliste)
        ),
        "korrekturversion": max((k["version"] for k in korrekturliste or []), default=0),
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


def _effektive_werte(conn, row: dict) -> dict:
    """Effektive Feldwerte einer Belegzeile (Auto-Rohwerte plus letzte
    gueltige manuelle Korrektur) als einfaches Name->Wert-Dict."""
    korrekturliste = speicher.korrekturen_fuer_beleg(conn, row["id"])
    felder, _ = korrekturen.effektive_felder(json.loads(row["felder_json"]), korrekturliste)
    werte = {name: (f or {}).get("wert") for name, f in felder.items()}
    werte.setdefault("anbieter", row["anbieter"])
    return werte


def _abo_uebersicht(conn) -> list[dict]:
    """Karten der Abo-Uebersicht: nur wiederkehrende Kosten mit Evidenz
    (explizites oder abgeleitetes Intervall, Abo-Bestaetigung oder
    mindestens zwei vergleichbare Rechnungen desselben Produktprofils).
    Zahlungsnachweise ohne Rechnung, Einmalzahlungen ohne
    Wiederholungsevidenz, Duplikate und kritische Review-Faelle erzeugen
    nie eine Kostenkarte."""
    gruppen: dict[str, dict] = {}
    for row in speicher.alle_belege(conn):
        werte = _effektive_werte(conn, row)
        schluessel = kostenprofil.produkt_schluessel(werte)
        if not schluessel:
            continue
        ist_kosten = exportregeln.exportfaehig_zeile(row)
        ist_abo = (
            row["dokumentart"] == "abo_bestaetigung"
            and row["ausgang"] in ("uebernommen", "review")
        )
        if not (ist_kosten or ist_abo):
            continue
        gruppe = gruppen.setdefault(schluessel, {"kosten": [], "abo": []})
        gruppe["kosten" if ist_kosten else "abo"].append((row, werte))

    karten = []
    for gruppe in gruppen.values():
        kosten = gruppe["kosten"]
        abo = gruppe["abo"]
        if kosten:
            row, werte = kosten[-1]
            typ = "kosten"
            intervall = werte.get("abrechnungsintervall")
            intervall_herkunft = "aus Beleg"
            if not intervall:
                # Nach manuellen Korrekturen (z.B. ergaenzter Zeitraum) wird
                # das Intervall zentral aus den effektiven Werten abgeleitet.
                abgeleitet, herkunft = kostenprofil.intervall_ableiten(
                    "", werte.get("tarif"), werte.get("zeitraum")
                )
                if abgeleitet != kostenprofil.INTERVALL_UNBEKANNT:
                    intervall, intervall_herkunft = abgeleitet, herkunft
            if not intervall and len(kosten) >= 2:
                daten = [w.get("datum") for _, w in kosten if w.get("datum")]
                intervall = kostenprofil.historien_intervall(daten)
                intervall_herkunft = "aus Historie abgeleitet"
            wiederkehrend = (
                (intervall and intervall != "einmalig")
                or len(kosten) >= 2
                or bool(abo)
            )
            if not wiederkehrend:
                continue
        else:
            row, werte = abo[-1]
            typ = "abo_bestaetigung"
            intervall = werte.get("abrechnungsintervall")
            intervall_herkunft = "aus Bestätigung"

        produkt = werte.get("produkt") or kostenprofil.anzeige_name(werte.get("anbieter"))
        dokumente = [
            {"beleg_id": r["id"], "dateiname": _api_text(r["dateiname"])}
            for r, _ in (kosten + abo)[-5:]
        ]
        karte = {
            "typ": typ,
            "produkt": _api_text(produkt) or "Produkt nicht eindeutig",
            "tarif": _api_text(werte.get("tarif")),
            "rechnungsaussteller": _api_text(werte.get("anbieter")),
            "abrechnungskanal": _api_text(werte.get("abrechnungskanal")),
            "zahlungsdienst": _api_text(werte.get("zahlungsdienst")),
            "abrechnung": intervall,
            "intervall_herkunft": intervall_herkunft if intervall else None,
            "naechste_abbuchung": datumformat.datum_ui(werte.get("naechste_abbuchung")),
            "naechste_rechnung": datumformat.datum_ui(werte.get("naechste_rechnung")),
            "letzte_rechnung": datumformat.datum_ui(werte.get("datum")),
            "zeitraum": datumformat.zeitraum_ui(_api_text(werte.get("zeitraum"))),
            "betrag": _api_text(werte.get("betrag")),
            "waehrung": _api_text(werte.get("waehrung")),
            "einschaetzung": row["radar_einschaetzung"],
            "begruendung": _api_text(row["radar_begruendung"]),
            # Kompatibilitaet: `anbieter` entspricht dem Rechnungsaussteller.
            "anbieter": _api_text(werte.get("anbieter")),
            "reviewstatus": row["reviewstatus"],
            "review_aufgabe": _api_text(row["review_aufgabe"]),
            "beleg_id": row["id"],
            "vorgang_id": row["vorgang_id"],
            "anzahl_rechnungen": len(kosten),
            "dokumente": dokumente,
        }
        if _original_pdf_verfuegbar(row):
            karte["original_pdf_url"] = (
                f"/api/belege/{row['id']}/original/{_pdf_slug(row, werte)}"
            )
        if _original_eml_verfuegbar(conn, row):
            karte["original_eml_url"] = f"/api/vorgaenge/{row['vorgang_id']}/original-eml"
        karten.append(karte)

    karten.sort(key=lambda k: (k["produkt"] or "").lower())
    return karten


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
        row = speicher.beleg_nach_id(conn, beleg_id)
        if row is None or row["dateityp"] != "PDF" or not row["storage_key"]:
            conn.close()
            self._json(404, nicht_gefunden)
            return
        werte = _effektive_werte(conn, row)
        conn.close()
        try:
            pfad = speicher.pfad_aus_key(row["storage_key"])
            inhalt = pfad.read_bytes()
        except (dateinamen.UnsichererPfadFehler, OSError):
            self._json(404, nicht_gefunden)
            return
        if not inhalt.startswith(b"%PDF-"):
            self._json(404, nicht_gefunden)
            return
        # Sichtbarer Dateiname: serverseitig generierter Slug (Produkt,
        # Dokumentart, Monat, Betrag), nie der URL-Slug und nie ein Pfad.
        anzeigename = _pdf_slug(row, werte)
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", f'inline; filename="{anzeigename}"')
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(inhalt)))
        self.end_headers()
        self.wfile.write(inhalt)

    def _vorgang_original_eml(self, vorgang_id: str) -> None:
        """Liefert die unveraendert gespeicherte Original-EML eines Vorgangs
        als Download. Nur per Vorgangs-ID; der eml_storage_key stammt nie
        aus der URL und wird ausschliesslich ueber speicher.pfad_aus_key()
        aufgeloest. Attachment statt Inline: fremder Mail-/HTML-Inhalt wird
        nie im OptiTax-DOM dargestellt."""
        nicht_gefunden = {"fehler": "nicht gefunden"}
        conn = speicher.verbindung()
        row = conn.execute(
            "SELECT eml_dateiname, eml_storage_key FROM vorgaenge WHERE id = ?",
            (vorgang_id,),
        ).fetchone()
        conn.close()
        if row is None or not row["eml_storage_key"]:
            self._json(404, nicht_gefunden)
            return
        try:
            pfad = speicher.pfad_aus_key(row["eml_storage_key"])
            inhalt = pfad.read_bytes()
        except (dateinamen.UnsichererPfadFehler, OSError):
            self._json(404, nicht_gefunden)
            return
        from belegwaechter import mailparser

        if not mailparser.ist_eml(inhalt):
            self._json(404, nicht_gefunden)
            return
        anzeigename = dateinamen.speichername(row["eml_dateiname"] or "vorgang.eml")
        if not anzeigename.lower().endswith(".eml"):
            anzeigename += ".eml"
        self.send_response(200)
        self.send_header("Content-Type", "message/rfc822")
        self.send_header("Content-Disposition", f'attachment; filename="{anzeigename}"')
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(inhalt)))
        self.end_headers()
        self.wfile.write(inhalt)

    def _vorgang_ansicht(self, vorgang_id: str) -> None:
        """Sichere E-Mail-Ansicht als JSON: Betreff, bereinigter Absender,
        Datum, reiner Textkoerper und die Anhangszuordnung zu vorhandenen
        Belegen. Es wird nie das urspruengliche HTML eingebettet, nichts
        extern nachgeladen und kein Skript aus der E-Mail ausgefuehrt; die
        Oberflaeche rendert ausschliesslich per textContent. Der
        eml_storage_key stammt nie aus der URL."""
        nicht_gefunden = {"fehler": "nicht gefunden"}
        conn = speicher.verbindung()
        vorgang = conn.execute(
            "SELECT eml_dateiname, eml_storage_key FROM vorgaenge WHERE id = ?",
            (vorgang_id,),
        ).fetchone()
        if vorgang is None or not vorgang["eml_storage_key"]:
            conn.close()
            self._json(404, nicht_gefunden)
            return
        try:
            pfad = speicher.pfad_aus_key(vorgang["eml_storage_key"])
            inhalt = pfad.read_bytes()
        except (dateinamen.UnsichererPfadFehler, OSError):
            conn.close()
            self._json(404, nicht_gefunden)
            return
        from belegwaechter import mailparser

        if not mailparser.ist_eml(inhalt):
            conn.close()
            self._json(404, nicht_gefunden)
            return
        eml = mailparser.zerlegen(inhalt)

        beleg_rows = [
            dict(r) for r in conn.execute(
                "SELECT * FROM belege WHERE vorgang_id = ?", (vorgang_id,)
            ).fetchall()
        ]
        beleg_je_name = {r["dateiname"]: r for r in beleg_rows}
        anhaenge = []
        for anhang in eml.anhaenge:
            name = dateinamen.anzeigename(anhang.dateiname)
            eintrag = {"dateiname": steuerzeichen.feldwert_bereinigen(name) or "Anhang"}
            row = beleg_je_name.get(name)
            if row is not None:
                eintrag["beleg_id"] = row["id"]
                if _original_pdf_verfuegbar(row):
                    werte = _effektive_werte(conn, row)
                    eintrag["original_pdf_url"] = (
                        f"/api/belege/{row['id']}/original/{_pdf_slug(row, werte)}"
                    )
            anhaenge.append(eintrag)
        conn.close()

        payload = {
            "betreff": _api_text(eml.betreff),
            "absender": _api_text(eml.absender),
            "datum": _api_text(eml.mail_datum),
            "text": steuerzeichen.flusstext_bereinigen(eml.text or "")[:20000],
            "anhaenge": anhaenge,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _korrektur_wert_pruefen(self, feld: str, wert) -> tuple[str | None, str | None]:
        """Serverseitige Validierung eines manuell gesetzten Werts. Liefert
        (normalisierter_wert, fehlermeldung). Alle Werte werden
        steuerzeichenbereinigt und laengenbegrenzt; Betrag, Waehrung, Datum
        und Zeitraum zusaetzlich fachlich geprueft. Datums- und
        Zeitraumwerte werden intern ISO-basiert gespeichert."""
        def _datum_iso(text) -> str | None:
            if not isinstance(text, str):
                return None
            sauber = steuerzeichen.feldwert_bereinigen(text)
            if not sauber:
                return None
            iso = datumformat.datum_csv(sauber)
            try:
                date.fromisoformat(iso)
            except (TypeError, ValueError):
                return None
            return iso

        if feld == "zeitraum":
            if not isinstance(wert, dict):
                return None, "Zeitraum braucht 'von' und 'bis'."
            von = _datum_iso(wert.get("von"))
            bis = _datum_iso(wert.get("bis"))
            if von is None or bis is None:
                return None, "Zeitraum braucht zwei gültige Datumswerte."
            if bis < von:
                return None, "Das Zeitraumende darf nicht vor dem Zeitraumstart liegen."
            return f"{von} bis {bis}", None

        if not isinstance(wert, str):
            return None, "Der Wert muss Text sein."
        sauber = steuerzeichen.feldwert_bereinigen(wert)
        if not sauber:
            return None, "Der Wert darf nicht leer sein."
        if len(sauber) > _MAX_KORREKTUR_FELDLAENGE:
            return None, "Der Wert ist zu lang."
        if feld == "betrag":
            if betraege.betrag_zu_decimal(sauber) is None:
                return None, "Der Betrag ist nicht als Zahl lesbar (z.B. 19,99)."
            return sauber, None
        if feld == "waehrung":
            sauber = sauber.upper()
            if not _WAEHRUNG_MUSTER.match(sauber):
                return None, "Die Währung muss ein ISO-Code mit drei Buchstaben sein."
            return sauber, None
        if feld in ("datum", "naechste_abbuchung"):
            iso = _datum_iso(sauber)
            if iso is None:
                return None, "Das Datum ist nicht als gültiges Datum lesbar."
            return iso, None
        if feld == "abrechnungsintervall":
            klein = sauber.lower()
            if klein not in kostenprofil.ERLAUBTE_INTERVALLE:
                return None, "Die Abrechnung muss monatlich, jährlich, unregelmäßig, einmalig oder unbekannt sein."
            return klein, None
        return sauber, None

    def _korrekturen_anwenden(self, beleg_id: str) -> None:
        """POST /api/belege/<id>/korrekturen: validiert manuelle Angaben,
        haengt sie append-only an und bewertet den Beleg erneut. Nur
        fachliche Felder sind korrigierbar; Status, Hashes und Provenienz
        sind nie schreibbar."""
        laenge = int(self.headers.get("Content-Length", "0"))
        if laenge > _MAX_KORREKTUR_BODY:
            _rumpf_verwerfen(self.rfile, laenge)
            self._json(413, {"fehler": "Die Anfrage ist zu groß."})
            return
        try:
            daten = json.loads(self.rfile.read(laenge).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"fehler": "Erwartet wird gültiges JSON."})
            return
        feld_angaben = daten.get("felder") if isinstance(daten, dict) else None
        if not isinstance(feld_angaben, dict) or not feld_angaben:
            self._json(400, {"fehler": "Es wurden keine Feldangaben übermittelt."})
            return

        conn = speicher.verbindung()
        try:
            row = speicher.beleg_nach_id(conn, beleg_id)
            if row is None or row["ausgang"] not in agent.NEUBEWERTBARE_AUSGAENGE:
                self._json(404, {"fehler": "nicht gefunden"})
                return
            auto_felder = json.loads(row["felder_json"])
            bisherige = speicher.korrekturen_fuer_beleg(conn, beleg_id)
            effektiv_vorher, _ = korrekturen.effektive_felder(auto_felder, bisherige)

            validierte: list[tuple[str, str, str | None, str | None]] = []
            for feld, angabe in feld_angaben.items():
                if feld not in korrekturen.KORRIGIERBARE_FELDER:
                    self._json(400, {"fehler": "Dieses Feld ist nicht korrigierbar."})
                    return
                aktion = angabe.get("aktion") if isinstance(angabe, dict) else None
                if aktion not in korrekturen.AKTIONEN:
                    self._json(400, {"fehler": "Unbekannte Aktion."})
                    return
                alter_wert = effektiv_vorher.get(feld, {}).get("wert")
                neuer_wert = None
                if aktion == korrekturen.AKTION_SETZEN:
                    neuer_wert, fehler = self._korrektur_wert_pruefen(feld, angabe.get("wert"))
                    if fehler:
                        self._json(400, {"fehler": fehler})
                        return
                elif aktion == korrekturen.AKTION_BESTAETIGEN:
                    if alter_wert in (None, ""):
                        self._json(400, {"fehler": "Ohne erkannten Wert gibt es nichts zu bestätigen."})
                        return
                    neuer_wert = alter_wert
                validierte.append((feld, aktion, alter_wert, neuer_wert))

            for feld, aktion, alter_wert, neuer_wert in validierte:
                speicher.korrektur_anhaengen(conn, beleg_id, feld, aktion, alter_wert, neuer_wert)

            agent.neubewerten(conn, beleg_id)
            row_neu = speicher.beleg_nach_id(conn, beleg_id)
            antwort = _beleg_zu_json(
                row_neu,
                speicher.plaene_fuer_beleg(conn, beleg_id),
                speicher.korrekturen_fuer_beleg(conn, beleg_id),
                conn=conn,
            )
        finally:
            conn.close()
        self._json(200, {"beleg": antwort})

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
        elif self.path.startswith("/api/vorgaenge/"):
            ansicht = _VORGANG_ANSICHT_MUSTER.match(self.path)
            eml_treffer = _VORGANG_EML_MUSTER.match(self.path)
            if ansicht is None and eml_treffer is None:
                self._json(404, {"fehler": "nicht gefunden"})
                return
            erlaubt, code, fehler = _zugriff_erlaubt(self, veraendernd=False)
            if not erlaubt:
                self._json(code, fehler)
                return
            if ansicht is not None:
                self._vorgang_ansicht(ansicht.group(1))
            else:
                self._vorgang_original_eml(eml_treffer.group(1))
        elif self.path == "/api/ergebnis":
            erlaubt, code, fehler = _zugriff_erlaubt(self, veraendernd=False)
            if not erlaubt:
                self._json(code, fehler)
                return
            conn = speicher.verbindung()
            belege = [
                _beleg_zu_json(
                    r,
                    speicher.plaene_fuer_beleg(conn, r["id"]),
                    speicher.korrekturen_fuer_beleg(conn, r["id"]),
                    conn=conn,
                )
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
            radar = _abo_uebersicht(conn)
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
            puffer = io.StringIO()
            schreiber = csv.writer(puffer, delimiter=";")
            schreiber.writerow(
                [
                    "Produkt", "Tarif", "Rechnungsaussteller", "Abrechnungskanal",
                    "Zahlungsdienst", "Rechnungsdatum", "Leistungszeitraum",
                    "Abrechnungsintervall", "Betrag", "Waehrung", "Referenz",
                    "Dokumentart", "Originaldatei", "Quellenstatus",
                ]
            )
            for b in belege:
                # Alleinige Quelle fuer Kostenzeilen ist die zentrale
                # Exportregel; Produkt und rechtlicher Aussteller bleiben
                # getrennte Spalten mit denselben effektiven Werten wie
                # UI und Abo-Uebersicht.
                if not exportregeln.exportfaehig_zeile(b):
                    continue
                werte = _effektive_werte(conn, b)
                schreiber.writerow(
                    [
                        _csv_text(werte.get("produkt") or kostenprofil.anzeige_name(werte.get("anbieter"))),
                        _csv_text(werte.get("tarif")),
                        _csv_text(werte.get("anbieter")),
                        _csv_text(werte.get("abrechnungskanal")),
                        _csv_text(werte.get("zahlungsdienst")),
                        _csv_text(datumformat.datum_csv(werte.get("datum"))),
                        _csv_text(datumformat.zeitraum_csv(werte.get("zeitraum"))),
                        _csv_text(werte.get("abrechnungsintervall")),
                        b["betrag_dezimal"] or "",
                        _csv_text(werte.get("waehrung")),
                        _csv_text(werte.get("referenz")),
                        _csv_text(b["dokumentart"]),
                        _csv_text(b["dateiname"]),
                        _csv_text(_QUELLENSTATUS_ANZEIGE.get(b["quellenstatus"], b["quellenstatus"])),
                    ]
                )
            conn.close()
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
        if self.path.startswith("/api/belege/"):
            treffer = _BELEG_KORREKTUR_MUSTER.match(self.path)
            if treffer is None:
                self._json(404, {"fehler": "nicht gefunden"})
                return
            erlaubt, code, fehler = _zugriff_erlaubt(self, veraendernd=True)
            if not erlaubt:
                self._json(code, fehler)
                return
            self._korrekturen_anwenden(treffer.group(1))
        elif self.path == "/api/verarbeiten":
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
