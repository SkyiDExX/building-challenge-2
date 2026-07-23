# Feasibility-Gate: PDF- und Bild-Eingänge

Datum: 24.07.2026 (Arbeitsblock 3). Zeitbox: 45 Minuten, eingehalten.
Umgebung: Windows 11, Python 3.14.3 (lokal installiert), pip 25.3.

---

## Getestete Formate

### 1. PDF mit Textebene

**Werkzeug:** `pypdf==6.14.2`, installiert in einer projektlokalen virtuellen Umgebung (`.venv/`, nicht Teil des Repos), via `pip install pypdf==6.14.2`. Kein systemweiter Eingriff, keine Cloud, kein API-Key.

**Testaufbau:** Drei synthetische PDF-Dateien wurden von Hand in reiner PDF-1.4-Syntax erzeugt (kein Generator-Framework nötig, da Fixtures statisch sind): CloudBasis-Rechnung Juni, CloudBasis-Rechnung Juli, SchreibKI-Rechnung mit Umlauten. Jede enthält Anbieter, Rechnungsnummer, Datum, Zeitraum, Tarif, Betrag als echten Textinhalt (kein Bild).

**Ergebnis:**
```
--- fixture1.pdf ---
CloudBasis GmbH
Rechnung Nr. RE-3301-06
Datum: 01.06.2026
Leistungszeitraum: monatlich
Tarif: Standard
Betrag: 19,00 EUR
Waehrung: EUR

--- fixture2.pdf ---
CloudBasis GmbH
Rechnung Nr. RE-3301-07
Datum: 01.07.2026
Leistungszeitraum: monatlich
Tarif: Standard
Betrag: 23,00 EUR
Waehrung: EUR

--- fixture3.pdf ---
SchreibKI Plus
Rechnung Nr. INV-99120
Datum: 05.07.2026
Leistungszeitraum: jaehrlich
Betrag: 120,00 EUR
Hinweis: Umlaute ae oe ue funktionieren.
```
Alle Felder vollständig und korrekt extrahiert, inklusive Umlaute. Jede Datei wurde zweimal unabhängig verarbeitet; beide Läufe lieferten byteidentischen Text (Determinismus-Test bestanden für alle drei Fixtures).

**Bewertung:** PDF-Textextraktion ist **deterministisch, offline und zuverlässig**. Gate bestanden.

### 2. PNG / JPG (Screenshot, Foto)

**Werkzeug für Klassifizierung:** reine Python-Standardbibliothek (Magic-Bytes-Prüfung der ersten Dateibytes, z.B. `\x89PNG` für PNG, `\xff\xd8\xff` für JPEG). Kein zusätzliches Paket nötig.

**Werkzeug für OCR (Feldextraktion aus dem Bild):** `tesseract` (lokales OCR-Programm). Prüfung: `where.exe tesseract` findet **keine Installation** auf diesem Rechner. `pytesseract` (Python-Anbindung) ist ebenfalls nicht installiert.

**Testaufbau:** Ein synthetisches Screenshot-PNG wurde mit Pillow (nur zur Fixture-Erzeugung, nicht Laufzeit-Abhängigkeit der App) erzeugt und die PNG-Signatur erfolgreich per Magic-Bytes erkannt.

**Bewertung:** Die **Klassifizierung** von Bilddateien (Format erkennen, als Stufe B einstufen) funktioniert zuverlässig mit reiner Standardbibliothek. Eine **Feldextraktion per OCR** ist auf diesem Rechner nicht möglich, ohne eine systemweite Installation eines nativen Programms (Tesseract-Binary) vorzunehmen. Das ist laut Vorgabe ausdrücklich nicht erlaubt ("keine systemweiten riskanten Installationen"). Der OCR-Teil des Gates wurde daher nicht künstlich erzwungen, sondern als nicht bestanden gewertet.

## Gate-Entscheidung

- **PDF-Teil: bestanden.** Stufe A (PDF mit Textebene) wird echte, deterministische Kernfunktion des Vertical Slice.
- **OCR-Teil: nicht bestanden** (kein lokales OCR-Werkzeug vorhanden, keine systemweite Installation erlaubt). Entscheidung gemäß Regel: Bilder werden **angenommen, per Magic-Bytes korrekt klassifiziert und automatisch in Review geroutet** ("Erfassungsnachweis, Original fehlt", Status `original_anfordern`). Es wird keine funktionierende Bildextraktion vorgetäuscht.

## Unterstützte MVP-Formate (Ergebnis dieses Gates)

| Format | Unterstützung im Slice |
|---|---|
| PDF mit Textebene | Volle Extraktion, Checkliste, Bestandsabgleich, Entscheidung |
| PNG / JPG | Angenommen, klassifiziert, immer Review mit "Original anfordern" |
| EML | Nicht implementiert in diesem Slice (siehe Kürzungsreihenfolge, Punkt 1) |

## Ausgeschlossene Formate in diesem Slice

- Gescannte Bild-PDFs ohne Textebene (würden wie Stufe C/B behandelt werden müssen; kein Fixture dafür in diesem Gate, da PDF-Textebene der Kernfall ist).
- EML-Dateien (aus Zeitgründen zurückgestellt, keine technische Blockade bekannt).

## Fazit

Der PDF-Normalfall ist der zuverlässige, deterministische Kern des Vertical Slice. Der ehrliche Umgang mit Bildern (Klassifizieren statt Raten) ist selbst ein Beleg für die fail-closed-Philosophie des Agenten und wird in der Demo als Stärke gezeigt, nicht versteckt.
