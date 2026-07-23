# Premortem: Warum wir NICHT in den Top 5 landen

Datum: 23.07.2026. Annahme: Es ist Sonntagabend, wir haben verloren. Was ist passiert?

Skalen: Wahrscheinlichkeit (W) und Auswirkung (A) jeweils niedrig / mittel / hoch.
Rollen: Enrico (E), Claude (C), ChatGPT (G).

---

## Risiko 1: Wirkt wie OCR statt Agent

- **W:** hoch | **A:** hoch
- **Frühwarnzeichen:** Demo-Probe beginnt mit Upload und Feldliste; Testzuschauer sagt "ah, ein Scanner".
- **Gegenmaßnahme:** Demo und UI führen mit Entscheidungen und Begründungen (Dublette, Radar, Review), Extraktion ist nur der stille erste Schritt.
- **Kill-/Kürzungskriterium:** Wenn eine Probeperson nach 60 Sekunden "OCR-Tool" sagt, wird die Demo-Dramaturgie umgebaut, nicht das Produkt.
- **Verantwortlich:** C (Bau), E (Probe-Urteil)
- **Spätester Entscheidungszeitpunkt:** Samstag 25.07. mittags (vor Demo-Proben).

## Risiko 2: Input zu umständlich

- **W:** mittel | **A:** hoch
- **Frühwarnzeichen:** Demo braucht Erklärsätze, bevor der erste Beleg drin ist; Dateien müssen vorbereitet/umbenannt werden.
- **Gegenmaßnahme:** Eine einzige Drag-and-drop-Fläche als primäre Aktion; Demo-Belege liegen fertig auf dem Desktop.
- **Kill-/Kürzungskriterium:** Jeder Eingangsweg außer Web-Upload fliegt aus der Demo.
- **Verantwortlich:** C
- **Spätester Entscheidungszeitpunkt:** Freitag 24.07. abends.

## Risiko 3: Screenshot wird fälschlich als Original behandelt

- **W:** mittel | **A:** hoch
- **Frühwarnzeichen:** Screenshot-Fixture landet mit Status "Übernommen" ohne Kennzeichnung.
- **Gegenmaßnahme:** Statusmodell trennt "Original vorhanden" von "Erfassungsnachweis"; Screenshots ohne Pflichtangaben gehen in Review mit "Original anfordern".
- **Kill-/Kürzungskriterium:** Wenn Stufe-B-Extraktion unzuverlässig ist, werden Screenshots im MVP grundsätzlich Review-Fälle (ehrlich, kein Feature-Fake).
- **Verantwortlich:** C
- **Spätester Entscheidungszeitpunkt:** Feasibility-Gate Freitag 24.07. vormittags.

## Risiko 4: Extraktion instabil

- **W:** mittel | **A:** hoch
- **Frühwarnzeichen:** Gleicher Beleg liefert bei zwei Läufen verschiedene Felder; PDF-Textlayer leer.
- **Gegenmaßnahme:** MVP-Kern arbeitet deterministisch auf Stufe-A-Fixtures (PDF mit Textlayer, strukturierte Textbelege); OCR nur nach bestandenem Spike.
- **Kill-/Kürzungskriterium:** Besteht der Spike nicht, ist Bild-Extraktion raus und wird als "geplant" gezeigt, nie simuliert als funktionierend.
- **Verantwortlich:** C
- **Spätester Entscheidungszeitpunkt:** Freitag 24.07. vormittags.

## Risiko 5: Preiserhöhungsalarm erzeugt Fehlalarme

- **W:** mittel | **A:** hoch
- **Frühwarnzeichen:** Jahresrechnung wird mit Monatsrechnung verglichen; Brutto gegen Netto; Alarm bei Währungswechsel.
- **Gegenmaßnahme:** Vergleich nur bei Übereinstimmung von Anbieter, Tarif, Währung, Zeitraum, Menge, Netto/Brutto, Rabatt, anteiliger Abrechnung; sonst Status "Preisänderung möglich, Vergleich erforderlich".
- **Kill-/Kürzungskriterium:** Lieber ein ehrlicher "Vergleich erforderlich"-Fall in der Demo als ein einziger falscher Alarm.
- **Verantwortlich:** C
- **Spätester Entscheidungszeitpunkt:** Samstag 25.07. vormittags (Testphase).

## Risiko 6: Demo dauert zu lange

- **W:** mittel | **A:** hoch
- **Frühwarnzeichen:** Probe läuft über 2:45; Kernnutzen erst nach Minute 1 sichtbar.
- **Gegenmaßnahme:** Sekundengenaue Choreografie (UX_DEMO_SPEC), Kernautomation vor Sekunde 60, Proben mit Stoppuhr.
- **Kill-/Kürzungskriterium:** Jede Szene, die die 3 Minuten sprengt, fliegt in dieser Reihenfolge: zweiter Radar-Fall, Auditverlauf-Detail, Export-Öffnen.
- **Verantwortlich:** E (Aufnahme), C (Choreografie)
- **Spätester Entscheidungszeitpunkt:** Samstag 25.07. abends (erste Aufnahme).

## Risiko 7: Ergebnis für Nicht-Finanzmenschen unverständlich

- **W:** mittel | **A:** mittel
- **Frühwarnzeichen:** UI-Texte enthalten "Provenienz", "fail-closed", "Belegpaket" ohne Erklärung.
- **Gegenmaßnahme:** Deutsche Klartext-Labels ("Fertig", "Bitte ansehen", "Doppelt, aussortiert", "Abo teurer geworden"); Fachsprache nur in Doku.
- **Kill-/Kürzungskriterium:** Versteht eine fachfremde Probeperson einen Status nicht, wird das Label geändert, nicht erklärt.
- **Verantwortlich:** C, G (Textvarianten), E (Probe)
- **Spätester Entscheidungszeitpunkt:** Samstag 25.07. nachmittags.

## Risiko 8: UI wirkt wie ein Debug-Tool

- **W:** mittel | **A:** mittel
- **Frühwarnzeichen:** Rohe Tabellen, JSON-Reste, Entwickler-Ästhetik im Prototyp.
- **Gegenmaßnahme:** UX-Prototyp zuerst (dieser Arbeitsblock), klare Hierarchie, Status-Badges, Karten statt Rohdaten.
- **Kill-/Kürzungskriterium:** Backend-Funktionen ohne saubere Darstellung bleiben aus der Demo draußen.
- **Verantwortlich:** C
- **Spätester Entscheidungszeitpunkt:** Samstag 25.07. nachmittags (Polish).

## Risiko 9: Zu viele Funktionen verwässern die Story

- **W:** hoch | **A:** mittel
- **Frühwarnzeichen:** "Nur noch schnell" Features (Kontierung, Mail-Import, zweites Radar); Demo-Skript wächst.
- **Gegenmaßnahme:** Genau eine Wow-Funktion (erklärbares Abo-Radar); Nicht-Ziele-Liste im MASTER_PLAN ist bindend.
- **Kill-/Kürzungskriterium:** Kürzungsreihenfolge im MASTER_PLAN gilt; neue Features nur nach Streichung eines alten.
- **Verantwortlich:** E (Scope-Wächter), C
- **Spätester Entscheidungszeitpunkt:** laufend, hart ab Freitag 24.07. abends.

## Risiko 10: Sicherheits- oder Datenschutzfehler

- **W:** niedrig | **A:** hoch
- **Frühwarnzeichen:** Echte Dateinamen, Beträge oder Mail-Adressen in Repo, Demo oder Video; .env oder DB im Diff.
- **Gegenmaßnahme:** Gehärtete .gitignore, nur synthetische Fixtures, Diff-Prüfung vor jedem Commit, Video nur mit frischem Demo-Datenstand.
- **Kill-/Kürzungskriterium:** Bei Fund sensibler Daten sofortiger Stopp und Bereinigung vor jedem weiteren Push.
- **Verantwortlich:** C (technisch), E (Video)
- **Spätester Entscheidungszeitpunkt:** vor jedem Commit; final Sonntag 26.07. 11:30.

## Risiko 11: Keine glaubwürdige Zeitersparnis

- **W:** mittel | **A:** mittel
- **Frühwarnzeichen:** Nutzenversprechen bleibt abstrakt ("spart Zeit"); Jury fragt "wie viel?".
- **Gegenmaßnahme:** Demo zeigt konkreten Vorher-Nachher-Stapel (5 Belege, 0 Handgriffe im Normalfall); README nennt ehrliche Schätzung als Schätzung.
- **Kill-/Kürzungskriterium:** Keine erfundenen Messwerte; lieber kleiner, ehrlicher Claim.
- **Verantwortlich:** E, G (Formulierung)
- **Spätester Entscheidungszeitpunkt:** Samstag 25.07. abends (Video-Text).

## Risiko 12: Build Journal und Vorarbeit nicht sauber getrennt

- **W:** niedrig | **A:** hoch
- **Frühwarnzeichen:** Formulierungen, die Optifyx-Muster wie Challenge-Neubau klingen lassen; große Code-Drops ohne Historie.
- **Gegenmaßnahme:** README-Abschnitt zur Vorarbeit gepflegt halten; kleine, ehrliche Commits; kein Optifyx-Code.
- **Kill-/Kürzungskriterium:** Jeder Commit, der nicht in der Challenge entstanden ist, wäre Disqualifikationsrisiko: existiert nicht.
- **Verantwortlich:** C, E
- **Spätester Entscheidungszeitpunkt:** laufend.

## Risiko 13: Installation funktioniert nicht (Doku-/Teilbarkeits-Punkte)

- **W:** mittel | **A:** mittel
- **Frühwarnzeichen:** Setup nur auf Enricos Rechner getestet; Pfad- oder Versionsannahmen.
- **Gegenmaßnahme:** INSTALL.md an Claude adressiert (Template-Bonus), stdlib-first, Test auf frischem Ordner.
- **Kill-/Kürzungskriterium:** Wenn Zeit fehlt: ehrliches "getestet unter Windows 11, Python 3.x" statt breiter Versprechen.
- **Verantwortlich:** C
- **Spätester Entscheidungszeitpunkt:** Samstag 25.07. nachmittags.

## Risiko 14: Claude-Limit oder Zeitverlust

- **W:** mittel | **A:** hoch
- **Frühwarnzeichen:** Lange Sessions ohne Commit; große Refactorings; Usage-Warnungen.
- **Gegenmaßnahme:** Kleine Commits als Checkpoints; MASTER_PLAN als wiedereinstiegsfähige Arbeitsgrundlage; Kürzungsreihenfolge; ChatGPT übernimmt Text- und Planungsarbeit ohne Repo-Zugriff.
- **Kill-/Kürzungskriterium:** Ab Samstag 12:00 keine neuen Features, nur noch Stabilität, Polish, Video.
- **Verantwortlich:** E (Budget), C
- **Spätester Entscheidungszeitpunkt:** Samstag 25.07. 12:00.

## Risiko 15: Kein stabiler ungeschnittener Durchlauf

- **W:** mittel | **A:** hoch
- **Frühwarnzeichen:** Proben scheitern an wechselnden Zuständen; Reset unvollständig; Timing variiert.
- **Gegenmaßnahme:** Reset als erstklassige Funktion; deterministische Verarbeitung; mindestens drei fehlerfreie Proben vor Aufnahme; Aufnahme-Checkliste.
- **Kill-/Kürzungskriterium:** Klappt bis Samstagabend kein kompletter Durchlauf, wird die Demo auf den funktionierenden Kern gekürzt (Normalfall + ein Ausnahmefall + Radar).
- **Verantwortlich:** C (Stabilität), E (Aufnahme)
- **Spätester Entscheidungszeitpunkt:** Samstag 25.07. 20:00.

---

## Meta-Erkenntnis

Die drei tödlichsten Kombinationen: (1) "OCR-Eindruck" plus "Debug-UI", (2) Fehlalarm im Radar vor Fachpublikum, (3) instabile Demo am Sonntagmorgen. Alle drei werden durch dieselbe Disziplin verhindert: kleiner deterministischer Kern, ehrliche Status, sekundengenaue Proben.
