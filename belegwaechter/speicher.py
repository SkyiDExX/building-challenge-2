"""Persistenz: SQLite mit append-only Migrationsliste und Schema-Version.

Isolierte Demo-Datenbank unter runtime/ (per .gitignore nie im Repo). Reset
loescht runtime/ vollstaendig. Kein Zugriff auf Produktionsdaten, keine
Verbindung zu Optifyx.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

from belegwaechter.modelle import AgentSchritt, Beleg, RadarEintrag

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = REPO_ROOT / "runtime"
EINGANG_DIR = RUNTIME_DIR / "eingang"
DB_PFAD = RUNTIME_DIR / "belegwaechter.db"


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


MIGRATIONEN = [_migration_001_initial_schema]


def verbindung() -> sqlite3.Connection:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    EINGANG_DIR.mkdir(parents=True, exist_ok=True)
    neu = not DB_PFAD.exists()
    conn = sqlite3.connect(DB_PFAD)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if neu:
        conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        for i, migration in enumerate(MIGRATIONEN, start=1):
            migration(conn)
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (len(MIGRATIONEN),))
        conn.commit()
    return conn


def reset() -> None:
    """Loescht die gesamte Laufzeitdatenbank und alle gespeicherten
    Originaldateien. Danach ist der Zustand identisch zum Erststart."""
    import shutil

    if RUNTIME_DIR.exists():
        shutil.rmtree(RUNTIME_DIR)


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
    dateipfad: str,
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
            erfasst_am
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            beleg.id,
            beleg.lauf_id,
            beleg.dateiname,
            beleg.dateihash,
            dateipfad,
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
        ),
    )
    conn.commit()


def agent_schritt_speichern(
    conn: sqlite3.Connection, lauf_id: str, beleg_id: str | None, schritt: AgentSchritt
) -> None:
    conn.execute(
        """
        INSERT INTO agent_schritte (
            lauf_id, beleg_id, schritt, status, werkzeug, begruendung,
            evidenz, start, ende
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lauf_id,
            beleg_id,
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
    uebernommenen Belegs dieses Anbieters (nach Einfuegereihenfolge, nicht
    nach der nur sekundengenauen erfasst_am-Spalte)."""
    rows = conn.execute(
        """
        SELECT b.* FROM belege b
        INNER JOIN (
            SELECT anbieter_schluessel, MAX(rowid) AS letzte_seq
            FROM belege
            WHERE ausgang = 'uebernommen' AND anbieter_schluessel IS NOT NULL
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
