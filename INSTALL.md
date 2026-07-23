# INSTALL.md — Anleitung für Claude Code

> **An Claude:** Diese Datei ist an dich adressiert. Führe die Schritte
> nacheinander aus, wenn ein Mensch dich bittet, den Belegwächter lokal
> lauffähig zu machen (z.B. auf einem frischen Rechner oder nach einem
> `git clone`).

## Voraussetzungen

- Python 3.11 oder neuer (getestet mit 3.14.3 unter Windows 11)
- Kein Internetzugang zur Laufzeit nötig; nur einmalig zur Installation der
  einen gepinnten Abhängigkeit (`pypdf`)
- Kein API-Key, kein Secret, keine externe Anmeldung

## Schritte

1. Virtuelle Umgebung im Projektordner anlegen (Windows PowerShell):
   ```
   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```
   Unter macOS/Linux entsprechend `python3 -m venv .venv` und
   `.venv/bin/python -m pip install -r requirements.txt`.

2. Synthetische Demo-Fixtures liegen bereits unter `fixtures/` im Repo
   (erfundene Rechnungen und ein Screenshot). Falls sie fehlen oder neu
   erzeugt werden sollen, benötigt der Generator zusätzlich Pillow (nur
   für die Fixture-Erzeugung, keine Laufzeit-Abhängigkeit der App):
   ```
   pip install pillow
   python fixtures/erzeugen.py
   ```

3. Server starten:
   ```
   .venv\Scripts\python.exe web\server.py
   ```
   Ausgabe: `Belegwaechter laeuft auf http://127.0.0.1:8850`

4. Im Browser öffnen: `http://127.0.0.1:8850`

5. Demo durchführen: Die Dateien aus `fixtures/` (alle 7) auf die
   Upload-Fläche ziehen oder per Klick auswählen. Ergebnis, Abo-Radar und
   Auditverlauf füllen sich in unter einer Sekunde.

6. Zurücksetzen: Knopf "Demo zurücksetzen" in der Oberfläche, oder manuell
   den Ordner `runtime/` löschen (enthält ausschließlich lokale Demo-Daten,
   ist per `.gitignore` ohnehin nie im Repo).

## Tests ausführen

```
.venv\Scripts\python.exe -m unittest tests.test_belegwaechter -v
```

Alle Tests laufen gegen eine isolierte temporäre Datenbank (siehe
`tests/test_belegwaechter.py`), niemals gegen `runtime/belegwaechter.db`.

## Bekannte Grenzen dieser Version

Siehe `README.md`, Abschnitt "Bekannte Einschränkungen", und
`docs/FEASIBILITY_INPUTS.md` für die Details zum PDF-/OCR-Gate.
