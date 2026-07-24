# INSTALL.md — OptiTax lokal starten

Diese Anleitung funktioniert ohne Projektwissen. Sie gilt für Windows
(PowerShell); macOS/Linux-Abweichungen stehen jeweils dabei. Claude Code
kann die Schritte ebenfalls direkt ausführen.

## Voraussetzungen

- Python 3.11 oder neuer (getestet mit 3.14 unter Windows 11)
- Git
- Internet nur einmalig für `git clone` und die Installation der einen
  gepinnten Abhängigkeit (`pypdf`) — zur Laufzeit ist kein Internet nötig
- **Kein API-Key, kein Secret, keine externe Anmeldung erforderlich**

## 1. Repository klonen

```
git clone https://github.com/SkyiDExX/building-challenge-2.git
cd building-challenge-2
```

## 2. Virtuelle Umgebung und Abhängigkeiten

Windows (PowerShell):
```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

macOS/Linux:
```
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## 3. Tests ausführen

```
.venv\Scripts\python.exe -m unittest tests.test_belegwaechter
```
(macOS/Linux: `.venv/bin/python -m unittest tests.test_belegwaechter`)

Alle Tests laufen gegen eine isolierte temporäre Datenbank, niemals gegen
lokale Demo-Daten. Erwartetes Ergebnis: `OK`.

## 4. Synthetische Demo-Dateien

Im Ordner `fixtures/` liegen **ausschließlich synthetische, erfundene
Beispieldateien** (Rechnungen, E-Mails, ein Screenshot) — keine echten
Anbieter, Personen oder Beträge. Sie sind bereits im Repository enthalten.

Nur falls sie neu erzeugt werden sollen (optional, benötigt zusätzlich
Pillow — keine Laufzeit-Abhängigkeit der App):
```
.venv\Scripts\python.exe -m pip install pillow
.venv\Scripts\python.exe fixtures\erzeugen.py
```

## 5. Server starten

```
.venv\Scripts\python.exe web\server.py
```

Konsolenausgabe: `Belegwaechter laeuft auf http://127.0.0.1:8850`
(interner technischer Name des Pakets).

Dann im Browser öffnen: **http://127.0.0.1:8850**

Der Server bindet ausschließlich an die lokale Loopback-Adresse und lädt
keinerlei externe Ressourcen.

## 6. Demo bedienen

Dateien aus `fixtures/` einzeln oder gemeinsam auf die Upload-Fläche
ziehen. Belege, Abo-Übersicht und Auditverlauf füllen sich unmittelbar.

## 7. Demo zurücksetzen

Button **„Demo zurücksetzen"** oben rechts in der Oberfläche. Alternativ
manuell den Ordner `runtime/` löschen — er enthält ausschließlich lokale
Demo-Daten und ist per `.gitignore` nie Teil des Repositories.

## 8. Server beenden

Im Terminal `Strg+C` drücken. Es bleiben keine Hintergrundprozesse zurück.

## Typische Probleme und Lösungen

| Problem | Lösung |
|---|---|
| `python` wird nicht gefunden | Python von python.org installieren und „Add to PATH" aktivieren; alternativ `py -3` statt `python` verwenden. |
| Port 8850 ist belegt | Anderen lokalen Dienst beenden oder in `web/server.py` die Konstante `PORT` einmalig lokal ändern (nicht committen). |
| `pip install` scheitert (offline/Proxy) | Einmalig eine Internetverbindung ohne Proxy nutzen; es wird nur `pypdf` installiert. |
| Seite lädt, aber Uploads schlagen fehl | Prüfen, dass die Seite über `http://127.0.0.1:8850` geöffnet ist (nicht über einen anderen Hostnamen) — die API akzeptiert nur lokale Aufrufe. |
| Demo zeigt alte Daten | „Demo zurücksetzen" klicken oder `runtime/` löschen und den Server neu starten. |
| Tests schlagen mit Berechtigungsfehler fehl | Terminal im Projektordner mit Schreibrechten öffnen (Tests legen temporäre Verzeichnisse an). |

## Bekannte Grenzen dieser Version

Siehe `README.md`, Abschnitt „Grenzen und ehrliche Hinweise", sowie
`docs/FEASIBILITY_INPUTS.md` für die Details zum PDF-/OCR-Gate.
