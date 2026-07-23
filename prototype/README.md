# Belegwächter — Statischer UX-Prototyp

**Das ist ein reiner UX-Prototyp mit simulierten Daten. Es gibt keine Agentenlogik, keine Verarbeitung, keine Persistenz, kein Netzwerk.** Er dient dazu, Oberfläche, Sprache und Demo-Dramaturgie zu testen, bevor der echte Agent gebaut wird (siehe `docs/MASTER_PLAN.md`).

## Öffnen

`prototype/index.html` per Doppelklick im Browser öffnen. Keine Installation, kein Server nötig.

## Was der Prototyp zeigt (alles simuliert)

- Upload-Fläche für PDF, EML, PNG, JPG; ein Klick (oder Drop) startet den simulierten Agentenlauf
- Sichtbarer Agenten-Fortschritt in fünf Schritten: Erfassen, Lesen, Prüfen, Abgleichen, Entscheiden
- Ergebnisübersicht mit fünf erfundenen Belegen: drei vollständige, eine Dublette, ein Screenshot-Review-Fall mit "Original angefordert"
- Erklärbares Abo-Radar mit vier Fällen: teurer geworden (eindeutiger Vergleich), Vergleich erforderlich (Zeitraumwechsel), Beleg fehlt, stabil
- Detailansicht: Quelle neben erkannten Angaben, jede Angabe mit Herkunft, Checkliste, Entscheidungssatz
- Auditverlauf, CSV-Download (erzeugt eine kleine Datei mit den simulierten Daten im Browser) und Reset mit Bestätigung

## Ehrlichkeits-Grenzen

- Auf die Fläche gezogene echte Dateien werden **nicht gelesen**; der Prototyp sagt das auch in der Oberfläche.
- Zeitstempel im Auditverlauf sind eine simulierte Demo-Uhr.
- Alle Anbieter, Beträge und Belege sind erfunden.

## Technik

Eine HTML-Datei, ein Stylesheet, ein Skript. Systemschriften, eigene SVG-Icons, automatischer Dark Mode über die Systemeinstellung, responsive ab Smartphone-Breite, Tastatur bedienbar (Tab, Enter, Esc), `prefers-reduced-motion` wird respektiert. Keine externen Fonts, CDNs oder Tracker.
