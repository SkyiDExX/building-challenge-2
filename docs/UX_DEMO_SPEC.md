# UX- und Demo-Spezifikation Belegwächter

Stand: 23.07.2026. Gilt für den statischen Prototyp (P0c) und die echte Oberfläche (B2 bis B4).
Leitfrage jeder Ansicht: Versteht ein Nicht-Techniker in Sekunden, was passiert ist und warum?

---

## 1. Informationshierarchie

Wichtigkeit von oben nach unten:
1. **Was braucht mich?** (Review-Fälle, "Bitte ansehen")
2. **Was hat der Agent entschieden?** (Belegliste mit Status und Begründung)
3. **Was kostet mich regelmäßig Geld?** (Abo-Radar)
4. **Was kann ich mitnehmen?** (Export)
5. **Was ist im Detail passiert?** (Auditverlauf)
Extraktion ist nie die Story, sondern nur der stille erste Schritt.

## 2. Seitenstruktur

Eine Seite, vier Zonen, keine Navigation nötig:
- **Kopf:** Name plus Einzeiler des Versprechens plus Demo-/Prototyp-Kennzeichnung plus Reset-Knopf.
- **Zone 1 Eingang:** große Drag-and-drop-Fläche ("Belege hier ablegen: PDF, EML, PNG, JPG"), darunter der sichtbare Agenten-Fortschritt mit 5 Schritten (Erfassen, Lesen, Prüfen, Abgleichen, Entscheiden).
- **Zone 2 Ergebnis:** Belegliste als Karten/Zeilen: Anbieter, Betrag, Datum, Status-Badge, Begründungssatz, Quellen-Kennzeichen ("Original vorhanden" / "Erfassungsnachweis"). Klick öffnet Detailansicht.
- **Zone 3 Abo-Radar:** Karten pro wiederkehrendem Anbieter mit Einschätzung und Begründung.
- **Zone 4 Fuß:** Export (CSV), Auditverlauf (aufklappbar), Zähler ("5 Belege verarbeitet: 3 fertig, 1 doppelt, 1 bitte ansehen").

## 3. Desktop und Mobil

- Desktop (Demo-Ziel): zweispaltig ab 900px (Ergebnis links, Radar rechts), Eingang volle Breite oben.
- Mobil: einspaltig, gleiche Reihenfolge, Upload-Fläche wird Knopf "Beleg auswählen". Kein mobiler Share-Adapter im MVP (bewusste Grenze, siehe MASTER_PLAN 6).
- Breakpoints: 600px, 900px. Keine horizontalen Scrollbalken.

## 4. Primäre Nutzeraktion

Genau eine: **Belege auf die Fläche ziehen** (oder klicken und auswählen). Alles andere ist Lesen, Prüfen, Mitnehmen. Sekundäraktionen (Export, Reset, Detail öffnen) sind sichtbar, aber nie im Weg.

## 5. Status- und Fehlermeldungen

- Status-Badges (Farbe plus Text, nie Farbe allein): "Fertig" (grün), "Bitte ansehen" (gelb), "Doppelt, aussortiert" (grau), "Original angefordert" (blau).
- Quellen-Kennzeichen: "Original vorhanden" / "Erfassungsnachweis" / "Hinweis, kein Beleg".
- Fehler sprechen Klartext und nennen den nächsten Schritt: "Diese Datei konnte nicht gelesen werden (beschädigtes PDF). Sie wurde nicht verarbeitet. Original erneut ablegen."
- Nichts scheitert still: jede abgelehnte Datei erscheint mit Grund in der Liste.
- Leerzustand erklärt das Produkt: "Noch keine Belege. Zieh eine Rechnung auf die Fläche, der Agent übernimmt den Rest."

## 6. Review-Interaktion

Review-Fälle stehen zuoberst, gelb markiert. Die Karte zeigt: was erkannt wurde, was fehlt ("keine Rechnungsnummer erkennbar"), warum der Agent nicht entschieden hat, und maximal zwei Aktionen: "Original nachreichen" und "Trotzdem übernehmen (als unvollständig markiert)". Im MVP darf die zweite Aktion auch als geplante Aktion sichtbar, aber deaktiviert sein, ehrlich beschriftet ("folgt nach der Challenge").

## 7. Quellen- und Ergebnisansicht

Detailansicht zweigeteilt: links die Quelle (Dateiname, Typ, Eingangsweg, Eingangszeit, bei Bildern eine Vorschau), rechts die extrahierten Felder, jedes mit Herkunft ("aus PDF-Text", "aus Bild erfasst", "fehlt"). Darunter der Entscheidungssatz des Agenten und der Checklisten-Status Punkt für Punkt. So ist die Verbindung Quelle-zu-Ergebnis immer beweisbar.

## 8. Abo-Radar

Eine Karte pro erkanntem wiederkehrendem Anbieter:
- Kopf: Anbieter, Rhythmus, aktueller Betrag.
- Einschätzung als Badge: "Stabil" / "Teurer geworden" / "Vergleich erforderlich" / "Beleg fehlt".
- Begründungssatz, z.B.: "19,00 → 23,00 EUR seit Dezember, gleicher Tarif, gleiche Währung, Vergleich eindeutig." oder "Zeitraum wechselt von monatlich auf jährlich, Beträge nicht direkt vergleichbar."
- Bei "Beleg fehlt": "Im Januar kein CloudHost-Beleg eingegangen, zuletzt 23,00 EUR im Dezember."
- Nie Alarm-Ästhetik (kein Rot-Blinken); ruhige, begründete Hinweise.

## 9. Auditverlauf

Aufklappbare, chronologische Liste: Zeit, Aktion, Objekt, alt/neu wo sinnvoll ("Status: neu → fertig"). Sprache bleibt Klartext ("Beleg RE-2107 als doppelt aussortiert, Referenz stimmt mit Beleg vom 01.12. überein"). Zweck in der Demo: beweisen, dass nichts im Verborgenen passiert.

## 10. Export

Ein Knopf "Als CSV exportieren". Export enthält nur übernommene Belege, mit Spalte für Quellenverweis und Quellenstatus. Nach Klick: Bestätigung "export.csv erstellt, 3 Belege." Der Export öffnet sich in der Demo kurz sichtbar.

## 11. Reset

Knopf "Demo zurücksetzen" oben rechts, mit Bestätigungsdialog ("Alle Demo-Daten löschen und von vorn beginnen?"). Danach ist der Zustand identisch zum Erststart. Reset ist Demo-Feature Nummer eins (Reproduzierbarkeit) und bleibt auch im echten Produkt für den Demo-Modus.

## 12. Barrierefreiheit

Semantisches HTML (button, table/list, headings in Reihenfolge), Kontrast mindestens 4,5:1 in beiden Farbschemata, Status nie nur über Farbe, Fokus-Ringe sichtbar, `prefers-reduced-motion` respektiert (dann keine Schritt-Animationen, Ergebnisse erscheinen sofort), Alt-Texte für Vorschaubilder, aria-live für den Verarbeitungsfortschritt.

## 13. Tastaturbedienung

Alles per Tab erreichbar in sinnvoller Reihenfolge (Upload, Liste, Radar, Export, Reset). Enter/Space aktiviert; Esc schließt Detailansicht und Dialoge; Upload-Fläche ist als Knopf fokussierbar ("Beleg auswählen").

## 14. UI-Texte (verbindliche deutsche Formulierungen)

| Kontext | Text |
|---|---|
| Kopfzeile | "Belegwächter — Belege rein, geprüfte Übersicht raus." |
| Prototyp-Banner | "Statischer UX-Prototyp: simulierte Daten, noch keine Agentenlogik." |
| Demo-Banner (später) | "Demo-Modus: alle Daten sind erfunden." |
| Upload | "Belege hier ablegen: PDF, EML, PNG, JPG" |
| Schritte | "Erfassen, Lesen, Prüfen, Abgleichen, Entscheiden" |
| Status | "Fertig" / "Bitte ansehen" / "Doppelt, aussortiert" / "Original angefordert" |
| Quelle | "Original vorhanden" / "Erfassungsnachweis" / "Hinweis, kein Beleg" |
| Radar | "Stabil" / "Teurer geworden" / "Vergleich erforderlich" / "Beleg fehlt" |
| Export | "Als CSV exportieren" |
| Reset | "Demo zurücksetzen" |
Verbotene Wörter in der UI: verbuchen, konform, rechtssicher, Provenienz, fail-closed, Extraktion (stattdessen "gelesen/erfasst").

## 15. Demo-Choreografie (Sekunde für Sekunde, Ziel 2:45)

Vorbereitung (vor Aufnahme): Reset ausgeführt, 5 Demo-Dateien sichtbar in einem Ordner "Belege Juli" auf dem Desktop, Browserfenster und Ordner nebeneinander, Benachrichtigungen aus, 3 fehlerfreie Proben absolviert.

| Zeit | Aktion | Sichtbar |
|---|---|---|
| 0:00-0:08 | Start auf geteiltem Bildschirm | Links Ordner mit 5 Belegdateien ("das Chaos"), rechts leerer Belegwächter. Texteinblendung: "Rechnungen überall. Abos unbemerkt." |
| 0:08-0:15 | Texteinblendung 2 | "Der Belegwächter macht daraus ein geprüftes Belegpaket und bewacht deine Abos." Kurzer Blick auf fertiges Endergebnis (eingeblendetes Standbild). |
| 0:15-0:25 | Alle 5 Dateien markieren und auf die Fläche ziehen | Upload-Fläche nimmt an, Agenten-Schritte starten sichtbar. |
| 0:25-0:50 | Agent arbeitet | Fortschritt "Erfassen, Lesen, Prüfen, Abgleichen, Entscheiden" läuft pro Beleg durch; Liste füllt sich live: 3x "Fertig", 1x "Doppelt, aussortiert", 1x "Bitte ansehen". |
| 0:50-0:60 | Zähler-Moment | "5 Belege verarbeitet: 3 fertig, 1 doppelt, 1 bitte ansehen." Kernautomation ist erfolgreich sichtbar. |
| 1:00-1:20 | Abo-Radar zeigen | Karte CloudHost: "Teurer geworden, 19,00 → 23,00 EUR, Vergleich eindeutig." Karte KI-Tool: "Vergleich erforderlich, Zeitraum wechselt von monatlich auf jährlich." |
| 1:20-1:40 | Ausnahmefall 1: Dublette öffnen | Begründung: gleiche Rechnungsnummer und gleicher Betrag wie Beleg vom 01.12., nicht doppelt gezählt. |
| 1:40-2:00 | Ausnahmefall 2: Review-Fall öffnen | Screenshot-Beleg: "Erfassungsnachweis, keine Rechnungsnummer erkennbar, Original angefordert." Ehrlichkeit als Feature. |
| 2:00-2:20 | Quelle-zu-Ergebnis plus Audit | Detailansicht: Felder mit Herkunft neben Quelldatei; Auditverlauf kurz aufklappen. |
| 2:20-2:35 | Export | "Als CSV exportieren" klicken, Datei kurz öffnen: 3 übernommene Belege mit Quellenverweis. |
| 2:35-2:45 | Reset | "Demo zurücksetzen", Startzustand erscheint. Schlusseinblendung: "Belegwächter. Belege rein, geprüfte Übersicht raus." |

Kürzungsregel bei Zeitnot (aus PREMORTEM Risiko 6): zuerst 1:00-1:20 auf einen Radar-Fall kürzen, dann Audit-Aufklappen streichen, dann Export nur klicken statt öffnen.

## 16. Die sieben Sofort-Antworten der Oberfläche

Jede Ansicht muss ohne Erklärung beantworten: Was wurde hochgeladen? Was hat der Agent getan? Was ist fertig? Was braucht mich? Warum wurde so entschieden? Welche wiederkehrenden Kosten gibt es? Was kann ich jetzt exportieren?
