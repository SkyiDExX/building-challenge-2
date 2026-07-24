"""Persistenz: SQLite mit append-only Migrationsliste und Schema-Version.

Isolierte Demo-Datenbank unter runtime/ (per .gitignore nie im Repo). Reset
loescht runtime/ vollstaendig. Kein Zugriff auf Produktivdaten.

Kein absoluter Dateipfad wird persistiert: Belege werden ueber einen
relativen storage_key referenziert (siehe dateinamen.storage_key_gueltig,
pfad_aus_key). Bestehende Datenbanken im Schema v1 werden beim Oeffnen
automatisch migriert, mit Sicherungskopie ueber die SQLite-Backup-API und
einer expliziten Transaktion je Migrationsschritt (siehe
_ausstehende_migrationen_anwenden).
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from pathlib import Path

from belegwaechter import betraege, dateinamen
from belegwaechter.modelle import (
    AUSGANG_DUBLETTE,
    AUSGANG_UEBERNOMMEN,
    DOKUMENTSTATUS_AUSSORTIERT,
    DOKUMENTSTATUS_VORBEREITET,
    DOKUMENTSTATUS_ZURUECKGESTELLT,
    REVIEWSTATUS_KEINE,
    REVIEWSTATUS_OFFEN,
    AgentSchritt,
    Beleg,
    RadarEintrag,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = REPO_ROOT / "runtime"
EINGANG_DIR = RUNTIME_DIR / "eingang"
DB_PFAD = RUNTIME_DIR / "belegwaechter.db"

_AUSGANG_ZU_DOKUMENTSTATUS = {
    AUSGANG_UEBERNOMMEN: DOKUMENTSTATUS_VORBEREITET,
    AUSGANG_DUBLETTE: DOKUMENTSTATUS_AUSSORTIERT,
}


def _migration_001_initial_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE laeufe (
            id TEXT PRIMARY KEY,
            gestartet_am TEXT NOT NULL
        );

        CREATE TABLE belege (
            id TEXT PRIMARY KEY,
            lauf_id TEXT NOT NULL REFERENCES laeufe(id),
            dateiname TEXT NOT NULL,
            dateihash TEXT NOT NULL,
            dateipfad TEXT NOT NULL,
            dateityp TEXT NOT NULL,
            stufe TEXT NOT NULL,
            quellenstatus TEXT NOT NULL,
            anbieter TEXT,
            anbieter_schluessel TEXT,
            datum TEXT,
            betrag TEXT,
            waehrung TEXT,
            zeitraum TEXT,
            tarif TEXT,
            referenz TEXT,
            felder_json TEXT NOT NULL,
            checkliste_json TEXT NOT NULL,
            ausgang TEXT NOT NULL,
            begruendung TEXT NOT NULL,
            radar_einschaetzung TEXT,
            radar_begruendung TEXT,
            erfasst_am TEXT NOT NULL
        );

        CREATE TABLE agent_schritte (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lauf_id TEXT NOT NULL,
            beleg_id TEXT,
            schritt TEXT NOT NULL,
            status TEXT NOT NULL,
            werkzeug TEXT NOT NULL,
            begruendung TEXT NOT NULL,
            evidenz TEXT,
            start TEXT NOT NULL,
            ende TEXT NOT NULL
        );

        CREATE TABLE audit_ereignisse (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zeit TEXT NOT NULL,
            aktion TEXT NOT NULL,
            objekt TEXT NOT NULL,
            alt TEXT,
            neu TEXT
        );
        """
    )


def _migration_002_provenienz_status_und_plan(conn: sqlite3.Connection) -> None:
    """Fuehrt relative Provenienz (storage_key statt Pfad), getrennte
    Statusfelder und die Ausfuehrungsplan-Tabelle ein. Nutzt bewusst
    einzelne execute()-Aufrufe statt executescript(): executescript()
    committet implizit vor dem Lauf und wuerde die vom Aufrufer
    kontrollierte Transaktion (BEGIN IMMEDIATE / ROLLBACK bei Fehler)
    aushebeln."""
    for anweisung in (
        "ALTER TABLE belege ADD COLUMN speichername TEXT",
        "ALTER TABLE belege ADD COLUMN storage_key TEXT",
        "ALTER TABLE belege ADD COLUMN extraktionsmethode TEXT",
        "ALTER TABLE belege ADD COLUMN fehlercode TEXT",
        "ALTER TABLE belege ADD COLUMN dokumentstatus TEXT",
        "ALTER TABLE belege ADD COLUMN reviewstatus TEXT",
        "ALTER TABLE belege ADD COLUMN review_aufgabe TEXT",
        "ALTER TABLE belege ADD COLUMN baseline_bestaetigt INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE belege ADD COLUMN betrag_dezimal TEXT",
        """
        CREATE TABLE beleg_plaene (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lauf_id TEXT NOT NULL,
            beleg_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            plan_json TEXT NOT NULL,
            revisionsgrund TEXT,
            erstellt_am TEXT NOT NULL
        )
        """,
        # Historischer Konstantenwert vor der Umbenennung auf "vergleich_erforderlich".
        "UPDATE belege SET radar_einschaetzung = 'vergleich_erforderlich' "
        "WHERE radar_einschaetzung = 'veraendert_unklar'",
    ):
        conn.execute(anweisung)

    _v1_zeilen_uebernehmen(conn)


def _v1_zeilen_uebernehmen(conn: sqlite3.Connection) -> None:
    """Ueberfuehrt bestehende v1-Zeilen in die neuen Felder. Ein alter
    absoluter Pfad wird nur dann zum relativen storage_key, wenn er nach
    resolve() nachweislich unterhalb von RUNTIME_DIR liegt. Andernfalls wird
    NICHT geraten: die Zeile wird als nicht auflösbar markiert und in
    Review geroutet."""
    basis = RUNTIME_DIR.resolve()
    zeilen = conn.execute(
        "SELECT id, dateiname, dateipfad, ausgang, radar_einschaetzung, betrag FROM belege"
    ).fetchall()

    for beleg_id, dateiname, alter_pfad, ausgang, radar_einschaetzung, betrag in zeilen:
        storage_key = None
        fehlercode = None

        if alter_pfad:
            try:
                aufgeloest = Path(alter_pfad).resolve()
                if aufgeloest.is_relative_to(basis):
                    storage_key = aufgeloest.relative_to(basis).as_posix()
                else:
                    fehlercode = "PFAD_NICHT_AUFLOESBAR"
            except (OSError, ValueError):
                fehlercode = "PFAD_NICHT_AUFLOESBAR"
        else:
            fehlercode = "PFAD_NICHT_AUFLOESBAR"

        dokumentstatus = _AUSGANG_ZU_DOKUMENTSTATUS.get(ausgang, DOKUMENTSTATUS_ZURUECKGESTELLT)
        reviewstatus = REVIEWSTATUS_KEINE if ausgang in (AUSGANG_UEBERNOMMEN, AUSGANG_DUBLETTE) else REVIEWSTATUS_OFFEN
        review_aufgabe = None if reviewstatus == REVIEWSTATUS_KEINE else "Bestehenden Beleg pruefen (Migration von Schema v1)."

        if fehlercode:
            dokumentstatus = DOKUMENTSTATUS_ZURUECKGESTELLT
            reviewstatus = REVIEWSTATUS_OFFEN
            review_aufgabe = "Quelldatei nicht auffindbar, Original erneut ablegen."

        betrag_dezimal_wert = betraege.betrag_zu_decimal(betrag)
        betrag_dezimal = format(betrag_dezimal_wert, "f") if betrag_dezimal_wert is not None else None

        baseline = 1 if (
            ausgang == AUSGANG_UEBERNOMMEN
            and fehlercode is None
            and radar_einschaetzung in ("neu", "stabil", "veraendert_eindeutig")
        ) else 0

        conn.execute(
            """
            UPDATE belege SET
                speichername = ?, storage_key = ?, extraktionsmethode = ?, fehlercode = ?,
                dokumentstatus = ?, reviewstatus = ?, review_aufgabe = ?,
                baseline_bestaetigt = ?, betrag_dezimal = ?, dateipfad = ''
            WHERE id = ?
            """,
            (
                dateinamen.speichername(dateiname) if dateiname else "beleg",
                storage_key,
                "unbekannt-migriert",
                fehlercode,
                dokumentstatus,
                reviewstatus,
                review_aufgabe,
                baseline,
                betrag_dezimal,
                beleg_id,
            ),
        )


def _migration_003_dokumentart_und_vorgaenge(conn: sqlite3.Connection) -> None:
    """Fuehrt Dokumentart, Kostenvorgaenge und die Vorgangszuordnung von
    Plaenen und Agentenschritten ein. Bestehende Belege erhalten
    deterministisch dokumentart='unbestimmt' und vorgang_id=NULL (kein
    rueckwirkendes Raten). beleg_plaene wird einmalig kopierend neu
    aufgebaut, damit beleg_id optional wird: Container-Eintraege einer EML
    tragen NUR eine vorgang_id, nie eine vorgang_id im beleg_id-Feld."""
    for anweisung in (
        "ALTER TABLE belege ADD COLUMN dokumentart TEXT",
        "ALTER TABLE belege ADD COLUMN vorgang_id TEXT",
        "UPDATE belege SET dokumentart = 'unbestimmt'",
        "ALTER TABLE agent_schritte ADD COLUMN vorgang_id TEXT",
        """
        CREATE TABLE vorgaenge (
            id TEXT PRIMARY KEY,
            lauf_id TEXT NOT NULL,
            quelle TEXT NOT NULL,
            eml_dateiname TEXT,
            eml_hash TEXT,
            eml_storage_key TEXT,
            betreff TEXT,
            absender TEXT,
            mail_datum TEXT,
            naechste_aktivitaet_art TEXT,
            naechste_aktivitaet_status TEXT,
            naechste_aktivitaet_datum TEXT,
            naechste_aktivitaet_begruendung TEXT,
            erstellt_am TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE beleg_plaene_neu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lauf_id TEXT NOT NULL,
            beleg_id TEXT,
            vorgang_id TEXT,
            version INTEGER NOT NULL,
            plan_json TEXT NOT NULL,
            revisionsgrund TEXT,
            erstellt_am TEXT NOT NULL
        )
        """,
        "INSERT INTO beleg_plaene_neu (id, lauf_id, beleg_id, version, plan_json, revisionsgrund, erstellt_am) "
        "SELECT id, lauf_id, beleg_id, version, plan_json, revisionsgrund, erstellt_am FROM beleg_plaene",
        "DROP TABLE beleg_plaene",
        "ALTER TABLE beleg_plaene_neu RENAME TO beleg_plaene",
    ):
        conn.execute(anweisung)


MIGRATIONEN = [
    _migration_001_initial_schema,
    _migration_002_provenienz_status_und_plan,
    _migration_003_dokumentart_und_vorgaenge,
]


def _sicherungskopie_erstellen(conn: sqlite3.Connection, vor_version: int) -> None:
    sicherung_pfad = RUNTIME_DIR / f"belegwaechter.db.vor-migration-v{vor_version + 1}"
    ziel = sqlite3.connect(sicherung_pfad)
    try:
        conn.backup(ziel)
    finally:
        ziel.close()


def _ausstehende_migrationen_anwenden(conn: sqlite3.Connection) -> None:
    aktuell = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    ziel = len(MIGRATIONEN)
    if aktuell >= ziel:
        return

    _sicherungskopie_erstellen(conn, aktuell)

    vorheriger_isolation = conn.isolation_level
    conn.isolation_level = None
    try:
        for index in range(aktuell, ziel):
            conn.execute("BEGIN IMMEDIATE")
            try:
                MIGRATIONEN[index](conn)
                conn.execute("UPDATE schema_version SET version = ?", (index + 1,))
            except Exception:
                conn.execute("ROLLBACK")
                raise
            else:
                conn.execute("COMMIT")
    finally:
        conn.isolation_level = vorheriger_isolation


# Serialisiert Erstanlage und Migration der Datenbank. Ohne den Lock koennen
# nach einem Reset mehrere parallele Server-Threads (die Oberflaeche laedt
# /api/ergebnis, /api/radar und /api/audit gleichzeitig) dieselbe leere
# DB-Datei anlegen: der erste Thread hat die Datei schon erzeugt, aber die
# Tabellen noch nicht, und der zweite scheitert mit
# "no such table: schema_version".
_INIT_LOCK = threading.Lock()


def verbindung() -> sqlite3.Connection:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    EINGANG_DIR.mkdir(parents=True, exist_ok=True)
    with _INIT_LOCK:
        conn = sqlite3.connect(DB_PFAD)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            # Idempotente Erstanlage statt "Datei existiert"-Heuristik.
            conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
            if conn.execute("SELECT version FROM schema_version").fetchone() is None:
                MIGRATIONEN[0](conn)
                conn.execute("INSERT INTO schema_version (version) VALUES (1)")
                conn.commit()
            _ausstehende_migrationen_anwenden(conn)
        except Exception:
            conn.close()
            raise
    return conn


def reset() -> None:
    """Loescht die gesamte Laufzeitdatenbank und alle gespeicherten
    Originaldateien. Danach ist der Zustand identisch zum Erststart."""
    import shutil

    if RUNTIME_DIR.exists():
        shutil.rmtree(RUNTIME_DIR)


def storage_key_fuer(interner_dateiname: str) -> str:
    return f"eingang/{interner_dateiname}"


def pfad_aus_key(key: str) -> Path:
    """Rekonstruiert den tatsaechlichen Dateipfad aus einem relativen
    storage_key. Wirft UnsichererPfadFehler bei Traversal, absoluten Pfaden
    oder wenn der aufgeloeste Pfad die Runtime-Basis verlassen wuerde."""
    if not dateinamen.storage_key_gueltig(key):
        raise dateinamen.UnsichererPfadFehler(f"Unsicherer Storage-Key: {key!r}")
    basis = RUNTIME_DIR.resolve()
    kandidat = (RUNTIME_DIR / key).resolve()
    if not kandidat.is_relative_to(basis):
        raise dateinamen.UnsichererPfadFehler(f"Storage-Key ausserhalb der Runtime-Basis: {key!r}")
    return kandidat


def neuer_lauf(conn: sqlite3.Connection) -> str:
    lauf_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO laeufe (id, gestartet_am) VALUES (?, datetime('now'))",
        (lauf_id,),
    )
    conn.commit()
    return lauf_id


def beleg_speichern(
    conn: sqlite3.Connection,
    beleg: Beleg,
    anbieter_schluessel: str | None,
    radar: RadarEintrag | None,
) -> None:
    felder_json = json.dumps(
        {name: {"wert": f.wert, "herkunft": f.herkunft} for name, f in beleg.felder.items()},
        ensure_ascii=False,
    )
    checkliste_json = json.dumps(
        [{"name": c.name, "erfuellt": c.erfuellt} for c in beleg.checkliste],
        ensure_ascii=False,
    )
    conn.execute(
        """
        INSERT INTO belege (
            id, lauf_id, dateiname, dateihash, dateipfad, dateityp, stufe,
            quellenstatus, anbieter, anbieter_schluessel, datum, betrag,
            waehrung, zeitraum, tarif, referenz, felder_json, checkliste_json,
            ausgang, begruendung, radar_einschaetzung, radar_begruendung,
            speichername, storage_key, extraktionsmethode, fehlercode,
            dokumentstatus, reviewstatus, review_aufgabe, baseline_bestaetigt,
            betrag_dezimal, dokumentart, vorgang_id, erfasst_am
        ) VALUES (
            ?, ?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now')
        )
        """,
        (
            beleg.id,
            beleg.lauf_id,
            beleg.dateiname,
            beleg.dateihash,
            beleg.dateityp,
            beleg.stufe,
            beleg.quellenstatus,
            beleg.feldwert("anbieter"),
            anbieter_schluessel,
            beleg.feldwert("datum"),
            beleg.feldwert("betrag"),
            beleg.feldwert("waehrung"),
            beleg.feldwert("zeitraum"),
            beleg.feldwert("tarif"),
            beleg.feldwert("referenz"),
            felder_json,
            checkliste_json,
            beleg.ausgang,
            beleg.begruendung,
            radar.einschaetzung if radar else None,
            radar.begruendung if radar else None,
            beleg.speichername,
            beleg.storage_key,
            beleg.extraktionsmethode,
            beleg.fehlercode,
            beleg.dokumentstatus,
            beleg.reviewstatus,
            beleg.review_aufgabe,
            1 if beleg.baseline_bestaetigt else 0,
            beleg.betrag_dezimal,
            beleg.dokumentart,
            beleg.vorgang_id,
        ),
    )
    conn.commit()


def plan_speichern(
    conn: sqlite3.Connection, lauf_id: str, beleg_id: str | None, plan, vorgang_id: str | None = None
) -> None:
    """beleg_id gehoert einem Beleg, vorgang_id einem Kostenvorgang. Ein
    Container-Plan einer EML traegt NUR die vorgang_id; eine vorgang_id
    landet nie im beleg_id-Feld."""
    conn.execute(
        """
        INSERT INTO beleg_plaene (lauf_id, beleg_id, vorgang_id, version, plan_json, revisionsgrund, erstellt_am)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (lauf_id, beleg_id, vorgang_id, plan.version, json.dumps(plan.to_dict(), ensure_ascii=False), plan.revisionsgrund),
    )
    conn.commit()


def plaene_fuer_beleg(conn: sqlite3.Connection, beleg_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM beleg_plaene WHERE beleg_id = ? ORDER BY version ASC", (beleg_id,)
    ).fetchall()
    ergebnis = []
    for r in rows:
        eintrag = dict(r)
        eintrag["plan"] = json.loads(eintrag["plan_json"])
        ergebnis.append(eintrag)
    return ergebnis


def agent_schritt_speichern(
    conn: sqlite3.Connection, lauf_id: str, beleg_id: str | None, schritt: AgentSchritt,
    vorgang_id: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO agent_schritte (
            lauf_id, beleg_id, vorgang_id, schritt, status, werkzeug, begruendung,
            evidenz, start, ende
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lauf_id,
            beleg_id,
            vorgang_id,
            schritt.schritt,
            schritt.status,
            schritt.werkzeug,
            schritt.begruendung,
            schritt.evidenz,
            schritt.start,
            schritt.ende,
        ),
    )
    conn.commit()


def vorgang_speichern(conn: sqlite3.Connection, vorgang) -> None:
    conn.execute(
        """
        INSERT INTO vorgaenge (
            id, lauf_id, quelle, eml_dateiname, eml_hash, eml_storage_key,
            betreff, absender, mail_datum, naechste_aktivitaet_art,
            naechste_aktivitaet_status, naechste_aktivitaet_datum,
            naechste_aktivitaet_begruendung, erstellt_am
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            vorgang.id,
            vorgang.lauf_id,
            vorgang.quelle,
            vorgang.eml_dateiname,
            vorgang.eml_hash,
            vorgang.eml_storage_key,
            vorgang.betreff,
            vorgang.absender,
            vorgang.mail_datum,
            vorgang.naechste_aktivitaet_art,
            vorgang.naechste_aktivitaet_status,
            vorgang.naechste_aktivitaet_datum,
            vorgang.naechste_aktivitaet_begruendung,
        ),
    )
    conn.commit()


def vorgaenge_liste(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT *, rowid AS _seq FROM vorgaenge ORDER BY rowid ASC").fetchall()
    return [dict(r) for r in rows]


def beleg_review_setzen(
    conn: sqlite3.Connection, beleg_id: str, reviewstatus: str, review_aufgabe: str,
    begruendung: str | None = None,
) -> None:
    """Setzt eine offene Pruefaufgabe nachtraeglich, z.B. wenn erst auf
    Vorgangsebene sichtbar wird, dass die Rechnung zum Zahlungsbeleg fehlt,
    oder wenn eine Dokumentart (Abo-Bestaetigung) eine fachlich konkretere
    Begruendung als die generische Checklisten-Luecke braucht. begruendung
    wird nur aktualisiert, wenn uebergeben."""
    if begruendung is not None:
        conn.execute(
            "UPDATE belege SET reviewstatus = ?, review_aufgabe = ?, begruendung = ? WHERE id = ?",
            (reviewstatus, review_aufgabe, begruendung, beleg_id),
        )
    else:
        conn.execute(
            "UPDATE belege SET reviewstatus = ?, review_aufgabe = ? WHERE id = ?",
            (reviewstatus, review_aufgabe, beleg_id),
        )
    conn.commit()


def audit_schreiben(
    conn: sqlite3.Connection, aktion: str, objekt: str, alt: str | None, neu: str | None
) -> None:
    conn.execute(
        "INSERT INTO audit_ereignisse (zeit, aktion, objekt, alt, neu) "
        "VALUES (datetime('now'), ?, ?, ?, ?)",
        (aktion, objekt, alt, neu),
    )
    conn.commit()


def bestand_uebernommen(conn: sqlite3.Connection) -> list[dict]:
    """Liefert alle bisher uebernommenen Belege als einfache Dicts, in
    Einfuegereihenfolge (SQLite-rowid, nicht die nur sekundengenaue
    erfasst_am-Spalte, damit eine schnelle Batch-Verarbeitung nicht zu
    Gleichstaenden fuehrt). Grundlage fuer Dublettenpruefung und Abo-Historie."""
    rows = conn.execute(
        "SELECT *, rowid AS _seq FROM belege WHERE ausgang = 'uebernommen' ORDER BY rowid ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def alle_belege(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT *, rowid AS _seq FROM belege ORDER BY rowid ASC").fetchall()
    return [dict(r) for r in rows]


def radar_uebersicht(conn: sqlite3.Connection) -> list[dict]:
    """Aktueller Radar-Zustand je Anbieter: die Einschaetzung des zuletzt
    uebernommenen KOSTEN-Belegs dieses Anbieters (nach Einfuegereihenfolge,
    nicht nach der nur sekundengenauen erfasst_am-Spalte). Das Radar zeigt
    wirtschaftlich relevante Kosten: Zahlungsbelege und Abo-Bestaetigungen
    sind nie eine eigene Radar-Karte (sie sind Nachweise bzw.
    Ankuendigungen, keine Kostenbasis) -- vertreten wird der Anbieter dann
    von seiner juengsten uebernommenen Rechnung. Offene Vergleichsfaelle
    bleiben bewusst sichtbar; nur die Vergleichsbasis fuer den naechsten
    Preisvergleich folgt der strengeren baseline_bestaetigt-Regel (siehe
    bestand.letzte_baseline)."""
    rows = conn.execute(
        """
        SELECT b.* FROM belege b
        INNER JOIN (
            SELECT anbieter_schluessel, MAX(rowid) AS letzte_seq
            FROM belege
            WHERE ausgang = 'uebernommen' AND anbieter_schluessel IS NOT NULL
              AND (dokumentart IS NULL
                   OR dokumentart NOT IN ('zahlungsbeleg', 'abo_bestaetigung'))
            GROUP BY anbieter_schluessel
        ) neuste
        ON b.anbieter_schluessel = neuste.anbieter_schluessel AND b.rowid = neuste.letzte_seq
        WHERE b.ausgang = 'uebernommen'
        ORDER BY b.anbieter ASC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def agent_schritte_fuer_lauf(conn: sqlite3.Connection, lauf_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM agent_schritte WHERE lauf_id = ? ORDER BY id ASC", (lauf_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def audit_liste(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM audit_ereignisse ORDER BY id ASC").fetchall()
    return [dict(r) for r in rows]
