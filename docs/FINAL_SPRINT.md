# Final Sprint — Belegwächter

Ab jetzt maßgebliche Arbeitsgrundlage für alle verbleibenden Schritte bis
zur Abgabe. MASTER_PLAN.md und UX_DEMO_SPEC.md bleiben als historisches
Build Journal erhalten, sind aber nicht mehr die aktuelle Steuerung.

## 1. Ziel und Feature-Freeze

Produktumfang ist eingefroren. Keine neuen Features, Integrationen,
OCR-, Steuer- oder Agentik-Erweiterungen mehr. Ab jetzt ausschließlich:
Hintergrund-Abnahme, Dokumentation, Demoprobe, Aufnahme, Abgabe.

## 2. Bestätigter Ist-Stand

- Lokaler HEAD `3075eab`, 8 Commits vor `origin/main`.
- Funktionsumfang: EML-Upload, PDF-Pipeline, Kostenvorgänge, Dokumentarten
  (Rechnung/Zahlungsbeleg/Abo-Bestätigung/sonstiger Kostennachweis),
  Datei- und Referenz-Duplikate, evidenzbasierte nächste Aktivität
  (bestätigt/erwartet/unbekannt), Audit, CSV-Export, Reset, Liquid-Glass-UI.
- 115 Tests gehören zum letzten committeten Stand (HEAD `3075eab`).
- 119 Tests sind grün mit der noch uncommitteten Hintergrundintegration
  (Working Tree: `web/static/styles.css`, `web/server.py`,
  `tests/test_belegwaechter.py`, `web/static/assets/hintergrund-1600.jpg`,
  `web/static/assets/hintergrund-2560.jpg`).

## 3. Noch offenes visuelles Hintergrund-Gate

Die Hintergrundintegration bleibt **uncommittet**, bis manuell im echten
Browser bestätigt sind:

- Lesbarkeit in Header, Upload-Kachel, Belegliste, Abo-Radar, Modal, Footer
- Responsive-Verhalten (breiter Monitor, schmales Fenster, 16:9)
- Reset funktioniert weiterhin fehlerfrei
- Browser-Konsole ohne Fehler

Erst nach dieser Bestätigung wird committet.

## 4. Commit- und Push-Reihenfolge

1. Manuelle Hintergrund-QA (Abschnitt 3) bestanden.
2. Vollständige Testsuite erneut ausführen (Soll: 119 grün).
3. Vollständigen Diff gegen `origin/main` erneut prüfen.
4. Ein Commit für die Hintergrundintegration.
5. Push nach `origin/main` — nur nach ausdrücklicher Freigabe.
6. Danach README, INSTALL, ABGABE aktualisieren (Abschnitt 5) — eigener
   Commit, eigener Push nach Freigabe.

## 5. Finale Dokumentationsaufgaben

- **README.md**: Learnings-Abschnitt füllen, aktuellen Funktionsstand
  (inkl. Hintergrund/Liquid-Glass) bestätigen, finalen Demo-Link eintragen.
- **INSTALL.md**: aktuelle Zahl und Auswahl der Demo-Fixtures nennen
  (Stand: 6 PDF/PNG-Fixtures + 4 EML-Fixtures, siehe `fixtures/`).
- **ABGABE.md**: Vorlage mit echtem Projekttext, Repo-Link und Video-Link
  ausfüllen — kein Platzhalter mehr zur Abgabe.
- MASTER_PLAN.md / UX_DEMO_SPEC.md unverändert lassen (historisch).

## 6. Verbindlicher Demoablauf

Ein ungeschnittener Durchlauf, in dieser Reihenfolge:

1. Leerer Zustand, Problem in einem Satz.
2. CloudBasis-EML hochladen.
3. Einen Vorgang mit Rechnung und Zahlungsbeleg zeigen.
4. Nächste erwartete Aktivität und Agentenplan zeigen.
5. SchreibKI-Abo-Bestätigung hochladen.
6. Bestätigten Termin und konkrete Review-Aufgabe zeigen.
7. CloudBasis erneut hochladen.
8. Byte-identische Duplikaterkennung zeigen.
9. Audit kurz öffnen.
10. Sauberer Schlusssatz.

## 7. Video- und Abgabecheckliste

- Drei fehlerfreie vollständige Demo-Proben vor der eigentlichen Aufnahme.
- Zielvideo 2 bis 3 Minuten, ein Durchlauf, kein Schnitt.
- Ausschließlich synthetische Fixtures — keine echten Belege, keine
  privaten Daten, keine externen Dienste im Video.
- ABGABE.md vollständig ausgefüllt, Repo-Link und Video-Link geprüft.
- Vor Aufnahme: Reset, damit die Demo im leeren Zustand beginnt.

## 8. Stop-Regeln

- Nach dem Feature-Freeze werden ausschließlich P0-Blocker (Demo
  funktioniert nicht) oder eindeutige P1-Demo-Blocker (falsche
  Vorgangszuordnung, falsche Dublette, kaputtes Layout, JS-Fehler,
  Reset fehlerhaft) behoben.
- Keine kosmetischen P2-Schleifen mehr nach der Hintergrundabnahme.
- Jede Abweichung von diesem Dokument braucht eine bewusste, kurz
  begründete Entscheidung — nicht stillschweigend weiterbauen.
