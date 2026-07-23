# MASTER_PLAN Belegwächter

Verbindliche Arbeitsgrundlage bis Sonntag, 26.07.2026, 13:00 Uhr.
Stand: Donnerstag, 23.07.2026 (Challenge Tag 1, Arbeitsblock 2).
Ergänzende Dokumente: `ADVERSARIAL_REVIEW.md`, `PREMORTEM.md`, `UX_DEMO_SPEC.md`, `OPEN_QUESTIONS.md`, `decision-01-agent-selection.md`.

---

## 1. Executive Summary (für einen 18-Jährigen)

Wir bauen den Belegwächter. Das Problem: Rechnungen kommen überall an, als PDF, Mail oder Screenshot, und landen unsortiert in Ordnern. Abos laufen still weiter, Preiserhöhungen fallen erst auf, wenn das Geld weg ist. Vor Steuerterminen beginnt dann die Sucherei.

Die Lösung: Du wirfst deine Belege auf eine Fläche im Browser. Der Agent liest jeden Beleg, prüft ihn gegen eine Checkliste, vergleicht ihn mit dem Bestand und entscheidet selbst: fertig ablegen, als doppelt aussortieren oder dir zur Prüfung vorlegen. Jede Entscheidung steht mit Begründung daneben, und jeder Eintrag zeigt seinen Original-Beleg. Das Besondere ist das Abo-Radar: Es erkennt wiederkehrende Kosten, meldet ehrlich begründet, wenn ein Abo teurer wurde, und fällt auf, wenn ein erwarteter Beleg fehlt.

Bis Sonntag entsteht ein kleiner, stabiler Kern, der das mit erfundenen Demo-Belegen komplett offline vorführt: Belege rein, geprüfte Übersicht plus Abo-Radar raus, alles nachvollziehbar, mit einem Klick zurücksetzbar. Heute wurde der Plan aus neun Rollen angegriffen, ein Premortem erstellt und ein klickbarer UI-Prototyp gebaut. Ab morgen entsteht der echte Agent dahinter, klein, ehrlich und in einem ungeschnittenen Video vorführbar.

## 2. Verbindliches Produktversprechen

"Der Agent verwandelt eingehende Rechnungen in ein geprüftes, nachvollziehbares und buchhaltungsvorbereitendes Belegpaket und macht wiederkehrende Kosten sichtbar."

Sprachregeln (bindend, siehe auch Abschnitt 16): erlaubt sind "in das vorbereitete Belegpaket übernehmen", "geprüft nach interner Checkliste", "buchhaltungsvorbereitend", "Review erforderlich", "Original vorhanden", "Erfassungsnachweis", "Vergleich eindeutig / nicht eindeutig". Verboten sind "automatisch verbuchen", "finanzamtkonform", "GoBD-konform", "steuerlich korrekt", "rechtssicher" sowie jede Rechts- oder Steuerberatungsaussage.

## 3. Primäre Nutzerperson

Enrico: Solo-Founder (Optifyx), Windows, arbeitet lokal, hat wachsende SaaS-/KI-/Hosting-Kosten, keinen Buchhaltungshintergrund, will Belege in Sekunden loswerden und am Monatsende eine geprüfte, exportierbare Übersicht.

## 4. Nebenrollen und ausgeschlossene Zielgruppen

- **Nebenrollen:** Steuerberater bzw. vorbereitender Dienstleister als Empfänger des CSV-Exports (nur Empfänger, kein Nutzer der App); Community/Jury als Demo-Publikum.
- **Bewusst ausgeschlossen:** Agenturen und Teams (keine Mandanten-/Mehrbenutzerfähigkeit), Konzern-Buchhaltungen, Nutzer, die eine rechtliche Prüfung erwarten, mobile Nutzer als Primärweg (mobil ist späterer Adapter).

## 5. Gewinnerkriterien

- **Jury (laut Challenge-Post):** 1. Wie gut löst der Agent ein konkretes Problem (wichtigstes Kriterium), 2. Demo-Stärke, 3. Stabilität und Sauberkeit, 4. Nachvollziehbarkeit des Build Journals.
- **Community-Voting (Top 5):** Verständlichkeit in Sekunden, Aha-Moment ("mein Abo wurde teurer!"), Sympathie und Ehrlichkeit.
- **Konsequenz:** Die Demo führt mit sichtbaren Agenten-Entscheidungen und dem Abo-Radar, nicht mit Extraktion. UI-Sprache ist Laien-Deutsch. Build Journal bleibt kleinteilig und ehrlich.

## 6. Input-Strategie (Input-Leiter)

Grundsatz: **Ein Screenshot ist ein komfortabler Erfassungseingang, aber nicht automatisch der unveränderte Originalbeleg.** Fehlen Angaben oder sind Bereiche abgeschnitten, routet der Agent ehrlich in Review oder fordert den Originalbeleg an.

### Stufe A: bevorzugte Originalquellen

PDF mit eingebettetem Text; EML-Datei mit Rechnungsanhang oder -text; strukturierte E-Rechnung (XRechnung/ZUGFeRD) nur als spätere Option.
- **Darf der Agent:** Felder deterministisch extrahieren, Checkliste prüfen, Bestandsabgleich, bei Vollständigkeit in das vorbereitete Belegpaket übernehmen.
- **Kann fehlen:** einzelne Pflichtangaben trotz Originalqualität.
- **Review:** nur bei unvollständiger Checkliste oder widersprüchlichen Feldern.
- **Original anfordern:** entfällt (Original liegt vor).
- **UI-Status:** "Original vorhanden" plus "Übernommen" oder "Bitte ansehen".

### Stufe B: komfortable Bildquellen

PNG, JPG, Smartphone-Screenshot, Foto eines Papierbelegs.
- **Darf der Agent:** Erfassung dokumentieren; Felder nur extrahieren, wenn das OCR-Gate (Abschnitt 14) bestanden ist, und dann stets als "aus Bild erfasst" gekennzeichnet.
- **Kann fehlen:** Rechnungsnummer, Aussteller-Details, abgeschnittene Ränder, Brutto/Netto-Klarheit.
- **Review:** immer, solange das OCR-Gate nicht bestanden ist; danach bei jeder fehlenden Pflichtangabe.
- **Original anfordern:** immer als Hinweis, solange kein Stufe-A-Beleg zum Vorgang existiert.
- **UI-Status:** "Erfassungsnachweis, Original fehlt" plus "Bitte ansehen" oder "Original angefordert".

### Stufe C: unvollständige Hinweise

Bestellbestätigung, Zahlungsbestätigung, Screenshot ohne Rechnungsnummer oder mit abgeschnittenen Bereichen.
- **Darf der Agent:** als Vorgangs-Hinweis erfassen und dem Abo-Radar als Signal zuführen; niemals in das Belegpaket übernehmen.
- **Kann fehlen:** fast alles; es ist kein Beleg.
- **Review:** immer.
- **Original anfordern:** immer.
- **UI-Status:** "Hinweis, kein Beleg" plus "Original angefordert".

### Eingangswege (Bewertung)

| Weg | Bewertung | Zeitpunkt |
|---|---|---|
| Web-Upload / Drag-and-drop | primärer Demo- und MVP-Eingang | Challenge |
| Überwachter lokaler Ordner | einfach, aber unsichtbar in der Demo | nach Challenge |
| EML-Upload | Stufe A, guter zweiter Eingang | Challenge nur falls Zeit, sonst danach |
| Dedizierte Rechnungs-Mailadresse | echter Komfort, echte Komplexität | späterer Adapter |
| Mobile Teilen-Funktion | wichtig für Papierbelege | späterer Adapter |
| Claude-Code-Skill / Chat-Befehl | passt zu Enricos Arbeitsweise | späterer Adapter |

Kein späterer Adapter darf die Demo blockieren.

## 7. Exakter Agentenablauf

Pro eingehender Datei, streng sequenziell, jede Stufe protokolliert:

1. **Erfassen:** Datei annehmen, Hash bilden, Quelle und Zeitpunkt festhalten (Erfassungsnachweis).
2. **Einstufen:** Stufe A, B oder C bestimmen (Dateityp, Textlayer vorhanden?).
3. **Extrahieren:** Anbieter, Datum, Betrag, Währung, Zeitraum, Referenz; jede Angabe mit Herkunft (aus Textlayer, aus Bild, fehlend).
4. **Prüfen:** interne Checkliste fail-closed; fehlende oder widersprüchliche Angaben führen zu Review, nie zu Raten.
5. **Abgleichen:** gegen Bestand: exakte Dublette (Hash oder Referenz plus Betrag plus Datum)? bekannter wiederkehrender Anbieter? Preis vergleichbar (Abschnitt 13)?
6. **Entscheiden:** genau ein Ausgang mit Begründungssatz: Übernommen / Bitte ansehen (Review) / Doppelt, aussortiert / Original angefordert.
7. **Nachführen:** Belegpaket, Abo-Radar, Auditverlauf, Exportstand aktualisieren.

## 8. Sichtbare Agentenentscheidungen

Jede Entscheidung erscheint in der UI als Satz mit Belegbezug, z.B.:
- "Übernommen: alle 6 Checklisten-Punkte erfüllt, Original vorhanden."
- "Doppelt, aussortiert: gleiche Rechnungsnummer RE-2107 und gleicher Betrag wie Beleg vom 01.12."
- "Bitte ansehen: Betrag gefunden, aber keine Rechnungsnummer erkennbar (Screenshot, unten abgeschnitten)."
- "Abo teurer geworden: CloudHost Pro, monatlich, 19,00 → 23,00 EUR, gleicher Tarif, gleiche Währung, Vergleich eindeutig."
- "Preisänderung möglich, Vergleich erforderlich: Zeitraum wechselt von monatlich auf jährlich."

## 9. Statusmodell

Belegstatus (genau einer): `neu` → `verarbeitet` mit Ausgang `uebernommen` | `review` | `dublette` | `original_angefordert`.
Quellenstatus (orthogonal): `original_vorhanden` | `erfassungsnachweis` | `hinweis`.
Radar-Einschätzung pro wiederkehrendem Anbieter: `stabil` | `veraendert_eindeutig` | `veraendert_unklar` | `beleg_fehlt`.
UI-Labels dazu in Laien-Deutsch: "Fertig", "Bitte ansehen", "Doppelt, aussortiert", "Original angefordert"; "Stabil", "Teurer geworden", "Vergleich erforderlich", "Beleg fehlt".

## 10. Daten- und Provenienzmodell (konzeptionell)

- **Beleg:** id, Datei-Hash, Originaldateiname, Eingangsweg, Eingangszeit, Stufe (A/B/C), extrahierte Felder je mit Herkunftsangabe, Checklisten-Ergebnis, Ausgang, Begründung.
- **Vorgang/Abo:** Anbieter-Schlüssel, Rhythmus (monatlich/jährlich), erwarteter Betrag, Historie der Belege, Radar-Einschätzung mit Begründung.
- **Auditverlauf:** fortlaufende Ereignisse mit Zeit, Aktion, Objekt, alt/neu-Zustand, Auslöser.
- **Export:** CSV-Zeilen nur aus übernommenen Belegen, mit Quellenverweis.
Persistenz im MVP: eine lokale SQLite-Datei unter `runtime/` (nie im Repo), Schema versioniert, Reset löscht `runtime/` vollständig.

## 11. Academy-MVP

Web-Oberfläche (lokal, ein Python-stdlib-Server) mit: Upload-Fläche, Verarbeitungsanzeige mit den 5 sichtbaren Schritten, Belegliste mit Status und Begründungen, Detailansicht Quelle-neben-Feldern, erklärbares Abo-Radar, Auditverlauf, CSV-Export, Reset. Verarbeitet werden die synthetischen Fixtures (Stufe A vollständig; Stufe B/C mindestens als ehrliches Review-Routing).

## 12. Nicht-Ziele

Keine Steuer- oder Rechtsaussagen, keine Kontierung, kein DATEV, keine E-Rechnungs-Validierung, kein echter Mailzugriff, kein Bank-Abgleich, keine Mandanten/Teams, keine Cloud, keine echten Belege in Demo oder Repo, keine mobile App, kein Login-System, keine Zahlungsauslösung.

## 13. Wow-Funktion (genau eine)

**Das erklärbare Abo-Radar:** erkennt wiederkehrende Belege und zeigt pro Abo eine von vier begründeten Einschätzungen: stabil, teurer geworden (nur bei eindeutigem Vergleich), Vergleich erforderlich, Beleg fehlt.

Eindeutig vergleichbar ist ein Preis nur, wenn Anbieter, Tarif/Produkt, Währung, Abrechnungszeitraum, Menge/Seats, Netto-/Brutto-Basis übereinstimmen und weder Rabatt/Gutschrift noch anteilige Abrechnung den Vergleich verzerren. Sonst lautet die Einschätzung "Preisänderung möglich, Vergleich erforderlich" mit Angabe der abweichenden Dimension.

Begründung der Präzisierung: Ein reiner Preisalarm ist als Wow-Funktion angreifbar (Fehlalarm-Risiko, Rolle 5 im Adversarial Review) und schmaler als das eigentlich Beeindruckende: ein Agent, der seine Einschätzung erklärt und auch Fehlendes bemerkt. Dubletten- und Review-Erkennung bleiben Vertrauensfunktionen, keine zweite Wow-Funktion.

## 14. OCR- und PDF-Feasibility-Gate (harte Entscheidung)

**Spike B0, Freitag 24.07. vormittags, Timebox 60 Minuten:**
1. PDF-Textlayer-Extraktion (pypdf oder pdfplumber) gegen 3 synthetische Text-PDFs: müssen deterministisch und vollständig extrahieren.
2. Bild-OCR (Tesseract, lokal) gegen 2 synthetische Screenshots: bestanden nur, wenn Betrag, Datum und Anbieter in beiden Läufen identisch und korrekt erkannt werden.

**Gate-Entscheidung:**
- PDF-Teil bestanden (erwartet): Stufe A wird Kernfunktion.
- OCR-Teil bestanden: Stufe B liefert gekennzeichnete Felder plus Review bei Lücken.
- OCR-Teil nicht bestanden: Stufe B wird im MVP grundsätzlich Review-Fall ("Erfassungsnachweis, Original fehlt"); die Demo zeigt genau das als ehrliches Verhalten. Keine Simulation funktionierender OCR.
- PDF-Teil nicht bestanden (unerwartet): Rückfall auf strukturierte Text-Fixtures; Eintrag in OPEN_QUESTIONS mit Entscheidungsbedarf.

Externe Evidenz (Abruf 23.07.2026): PDF-Textlayer-Extraktion ist offline und deterministisch, bildbasierte OCR ist fehleranfällig (Zeichenverwechslung) — u.a. [pypdf-Doku](https://pypdf.readthedocs.io/en/latest/user/extract-text.html), Vergleichsartikel zu PDF-Extraktoren und Tesseract (siehe Abschnitt 30).

## 15. Technische Architektur

- **Backend:** Python 3, nur Standardbibliothek für den Server (`http.server`, 127.0.0.1, fester lokaler Port, kein CORS); Extraktions-Bibliotheken (pypdf, optional Tesseract-Anbindung) als einzige Abhängigkeiten, erst nach Gate B0.
- **Verarbeitungskern:** reine Python-Module ohne Server-Abhängigkeit (testbar ohne HTTP): `einstufen`, `extrahieren`, `pruefen`, `abgleichen`, `entscheiden`, `radar`.
- **Persistenz:** SQLite in `runtime/`, versioniertes Schema, append-only Migrationsliste.
- **Frontend:** statisches HTML/CSS/JS (aus dem Prototyp dieses Arbeitsblocks weiterentwickelt), vom Python-Server ausgeliefert.
- **Fixtures:** synthetische Belege in `fixtures/` (getrackt, ausdrücklich erfunden).
- **Kein Netzwerkzugriff** außer localhost; keine externen Fonts, CDNs oder Tracker.

## 16. Sicherheits- und Veröffentlichungsgrenzen

- Repo enthält ausschließlich Code, Doku und synthetische Fixtures. `runtime/` (DB, Uploads, Exporte, Logs) ist per .gitignore ausgeschlossen und wird in diesem Arbeitsblock technisch verankert.
- Keine Secrets: Academy-Demo benötigt keine; `.env.example` dokumentiert das ausdrücklich.
- Keine echten E-Mails, Rechnungen, Accounts, Browserprofile oder Produktionsdaten, auch nicht "nur zum Testen".
- Optifyx bleibt bis zur separaten Prüfung vollständig unangetastet (kein Lesen, kein git-Befehl, keine Inventur).
- Keine privaten absoluten Rechnerpfade in Produktdateien; lokale Pfade nur in als Entwicklungsnotiz gekennzeichneten Dokumenten.
- Vor jedem Commit: `git status --short`, vollständiger Diff, Vier-Fragen-Check (Optifyx-Dateien? Secrets? echte Daten? reine Zeilenumbruch-Änderungen?).
- Push nur nach `origin/main` des Challenge-Repos.

## 17. UI- und UX-Prinzipien

Details in `UX_DEMO_SPEC.md`. Kurzfassung: Laien-Deutsch, eine primäre Aktion (Belege ablegen), Status als farbige Klartext-Badges, jede Agentenentscheidung als Begründungssatz, Quelle neben Ergebnis, nichts scheitert still, Reset jederzeit sichtbar, responsive, Systemschriften, automatischer Dark Mode, Prototyp-/Demo-Kennzeichnung immer sichtbar.

## 18. Demo-Drehbuch

Sekundengenaue Choreografie in `UX_DEMO_SPEC.md`, Abschnitt "Demo-Choreografie". Rahmen: 0:00-0:15 Problem plus Versprechen plus Blick aufs Endergebnis; bis 0:60 Kernautomation sichtbar erfolgreich; danach Ausnahmefälle (Dublette, Screenshot-Review, Radar mit eindeutigem und nicht eindeutigem Fall), Auditverlauf, Export, Reset. Ein Durchlauf, ungeschnitten, unter 3 Minuten.

## 19. Teststrategie

- **Kern-Tests:** Verarbeitungskern gegen alle Fixtures, erwartete Ausgänge und Begründungen als Sollwerte (deterministisch, ohne Server).
- **API-Tests:** Endpunkte gegen Temp-DB (mkdtemp), Server auf freiem Port, nie gegen `runtime/`-Bestand.
- **Demo-Probe als Test:** kompletter Choreografie-Durchlauf mit Stoppuhr, mindestens drei fehlerfreie Proben vor Aufnahme.
- **Reset-Test:** nach Reset ist der Zustand bitidentisch zum Erststart.
- **Installations-Test:** frischer Ordner, INSTALL.md-Anweisungen wörtlich befolgen.

## 20. Commit- und Build-Journal-Plan

Kleine, ehrliche Commits, mindestens einer pro Bautag, Präfixe: `docs:`, `chore:`, `prototype:`, `feat:`, `test:`, `fix:`, `demo:`. Jeder Commit beschreibt, was wirklich passiert ist. Vorarbeit (Optifyx) wird nie als Challenge-Arbeit committet; die README-Abgrenzung bleibt aktuell.

## 21. Phasenplan

| Phase | Inhalt | Dateikreis | Tests | Stop-Bedingung | Commit |
|---|---|---|---|---|---|
| P0 (heute) | Analyse, Masterplan, UX-Spec | docs/ | keine | - | `docs: add adversarial premortem and master plan` |
| P0b (heute) | Sicherheits-Härtung | .gitignore, .env.example | Diff-Check | - | `chore: harden demo data and secret boundaries` |
| P0c (heute) | statischer UI-Prototyp | prototype/ | Klick-Probe | Prototyp täuscht Funktion vor → umbauen | `prototype: add static Belegwaechter UX concept` |
| B0 (Fr vorm.) | Feasibility-Spike PDF/OCR | scratch, dann `docs/` Ergebnisnotiz | Spike-Kriterien Abschnitt 14 | Timebox 60 min | `docs: record extraction feasibility gate result` |
| B1 (Fr mittag) | Verarbeitungskern Stufe A plus Fixtures | belegwaechter/, fixtures/, tests/ | Kern-Tests grün | kein stabiler Kern bis Fr abend → Kürzung nach Abschnitt 24 | `feat: deterministic processing core for level-A receipts` |
| B2 (Fr abend) | Server, UI-Anbindung, E2E | belegwaechter/, app-Teil | API- plus E2E-Test | Demo-Pfad instabil | `feat: end-to-end slice with web upload and results` |
| B3 (Sa vorm.) | Ausnahmefälle, Radar, Audit, Reset | wie B1/B2 | alle Tests plus Reset-Test | Fehlalarm im Radar nicht behebbar → Fall aus Demo | `feat: explainable subscription radar and audit trail` |
| B4 (Sa nachm.) | Polish, INSTALL.md, Demo-Proben | app-Teil, INSTALL.md | Installations-Test, 3 Proben | Probe scheitert → Demo kürzen | `docs: add install guide and polish demo flow` |
| B5 (Sa abend) | erste vollständige Videoaufnahme | keine Codeänderung | Choreografie-Zeit | - | `demo: record first full run` (nur falls Artefakt-Doku nötig) |
| B6 (So bis 11:30) | finaler Check, README, Abgabe-Vorbereitung | README.md, docs/ | Abschluss-Checkliste | 11:30 harte Grenze | `docs: final submission state` |

## 22. Zeitplan bis Sonntag

- **Donnerstag (heute):** P0, P0b, P0c abgeschlossen.
- **Freitag vormittag:** B0 Gate.
- **Freitag mittag:** B1 erster kompletter Backend-Vertical-Slice.
- **Freitag abend:** B2 stabile End-to-End-Demo.
- **Samstag vormittag:** B3 Ausnahmefälle, Tests, Sicherheit.
- **Samstag nachmittag:** B4 UI-Polish, Installation, Demo-Proben.
- **Samstag abend:** B5 erste vollständige Videoaufnahme.
- **Sonntag bis 11:30:** B6 finaler Check und Abgabe-Vorbereitung.
- **11:30 bis 13:00:** reine Notfallreserve, keine geplante Arbeit.

## 23. Aktive Stundenschätzung (Enrico plus Claude gemeinsam)

- **Optimistisch:** 9 Stunden (B0 0,5 / B1 2 / B2 2 / B3 2 / B4 1,5 / B5 0,5 / B6 0,5).
- **Realistisch:** 13 Stunden (Puffer für Extraktions-Ecken, UI-Anbindung, Probenschleifen).
- **Maximal:** 17 Stunden; darüber greift zwingend die Kürzungsreihenfolge.

## 24. Kürzungsreihenfolge (von zuerst streichen bis niemals streichen)

1. EML-Upload (Stufe A bleibt PDF plus Text-Fixtures)
2. OCR-Felder aus Bildern (Stufe B wird reiner Review-Weg)
3. Dark-Mode-Feinschliff
4. Auditverlauf als eigene Ansicht (Fallback: einfache Ereignisliste)
5. Detail-Ansicht Quelle-neben-Feldern (Fallback: Begründungstext plus Dateiname)
6. INSTALL.md-Bonus
7. Zweiter Radar-Fall in der Demo (nicht eindeutiger Vergleich)
- **Niemals streichen:** Upload, deterministischer Kern Stufe A, begründete Entscheidungen, Dublette, Review-Fall, Abo-Radar-Grundfall, CSV-Export, Reset, ehrliche Kennzeichnungen.

## 25. Claude-Limit-Notfallplan

- Kleine Commits als Checkpoints; nach jedem Commit ist das Repo allein lauffähig weiterbaubar.
- MASTER_PLAN und UX_DEMO_SPEC sind so geschrieben, dass eine frische Session ohne Vorwissen weiterarbeiten kann.
- Bei Limit-Warnung: sofort committen, dann nur noch Kürzungsreihenfolge abarbeiten.
- ChatGPT übernimmt limitfrei: Videotexte, Post-Formulierungen, Checklisten-Reviews (ohne Repo-Zugriff, Enrico kopiert Kontext).
- Absoluter Fallback für die Demo: der funktionierende Kern per CLI plus Ergebnisansicht; niemals der statische Prototyp als "echter Agent".

## 26. Manuelle Aufgaben für Enrico

- **Durch Template belegt:** Demo-Video aufnehmen (2-3 Min, ein Durchlauf, ungeschnitten, Loom oder YouTube unlisted); Abgabe-Post mit ABGABE.md-Vorlage in der Skool-Kategorie "Building Challenge"; ein kurzer Update-Post pro Woche.
- **Durch Challenge-Post belegt:** Teilnahme-Kommentar unter Sebastians Post (falls noch offen).
- **Noch extern zu prüfen:** Check-in-Post-Erwartung (siehe OPEN_QUESTIONS 1).
- **Erst später erforderlich:** Video-Link in README eintragen, finaler Abgabe-Post, Antworten auf OPEN_QUESTIONS 2-4.

## 27. Verantwortlichkeiten

- **Enrico:** Entscheidungen und Abnahmen, Scope-Wächter, Demo-Aufnahme, alle Community-Aktionen, Antworten auf OPEN_QUESTIONS.
- **Claude (dieses Repo):** Bau, Tests, Doku, Commits/Pushes nach Freigaberegeln, ehrliches Build Journal, Einhaltung der Sicherheitsgrenzen.
- **ChatGPT:** Sparring für Texte, Prompts und Zweitmeinungen; kein Repo-Zugriff, keine Quelle für Faktenbehauptungen ohne Beleg.

## 28. Exakt nächster Backend-Implementierungsschritt

**B0: OCR- und PDF-Feasibility-Spike** (Freitag vormittag, Timebox 60 Minuten):
Drei synthetische Text-PDFs und zwei synthetische Screenshots werden lokal erzeugt; pypdf-Extraktion und (falls ohne globale Installation möglich) Tesseract-OCR werden gegen die Kriterien aus Abschnitt 14 geprüfft; das Ergebnis wird als kurze Notiz in `docs/` festgehalten und entscheidet das Gate. Erst danach beginnt B1. Kein Produktcode vor Abnahme dieses Plans.

## 29. Entscheidungstore und späteste Abbruchzeiten

| Tor | Zeitpunkt | Entscheidung |
|---|---|---|
| Plan-Abnahme | vor B0 | Enrico gibt MASTER_PLAN frei |
| G1: Extraktion | Fr 24.07. 12:00 | Stufe-B-Umfang laut Gate B0 |
| G2: Kernstabilität | Fr 24.07. 22:00 | B1/B2 stabil? sonst Kürzungsreihenfolge ab Punkt 1 |
| G3: Radar-Ehrlichkeit | Sa 25.07. 12:00 | Fehlalarmfrei? sonst Fall aus Demo |
| G4: Feature-Freeze | Sa 25.07. 12:00 | keine neuen Features danach |
| G5: Demo-Stabilität | Sa 25.07. 20:00 | 3 fehlerfreie Proben? sonst Demo kürzen |
| G6: Abgabe-Cut | So 26.07. 11:30 | Stand einfrieren, nur noch Abgabe-Handgriffe |

## 30. Recherche-Quellen (Abruf 23.07.2026)

Kontextwissen, bewusst ohne Rechts- oder Steuerberatungsaussagen; Produktseiten sind Marketing und wurden nur als Feature-Landschaft gewertet:

- BMF: [FAQ zur verpflichtenden E-Rechnung ab 01.01.2025](https://www.bundesfinanzministerium.de/Content/DE/FAQ/e-rechnung.html); [BMF-Schreiben vom 15.10.2025 zur E-Rechnung](https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Umsatzsteuer/Umsatzsteuer-Anwendungserlass/2025-10-15-einfuehrung-obligatorische-e-rechnung.pdf?__blob=publicationFile&v=3); [§ 147 AO im amtlichen AO-Handbuch](https://ao.bundesfinanzministerium.de/ao/2025/Abgabenordnung/Vierter-Teil/Zweiter-Abschnitt/Erster-Unterabschnitt/Paragraf-147/inhalt.html) (Buchungsbelege grundsätzlich 8 Jahre; abweichend längere Fristen z.B. für Banken/Versicherungen laut [BMF-Pressemitteilung 06.08.2025](https://www.bundesfinanzministerium.de/Content/DE/Pressemitteilungen/Finanzpolitik/2025/08/2025-08-06-aufbewahrungsfristen-buchungsbelege.html)); [GoBD-Änderung vom 14.07.2025](https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Weitere_Steuerthemen/Abgabenordnung/2025-07-14-GoBD-2-aenderung.pdf?__blob=publicationFile&v=3). Produktrelevanz: Der Belegwächter trifft keine Konformitätsaussagen; die Quellen begründen nur, warum Original-Erhalt und ehrliche Statusunterscheidung wichtig sind.
- Feature-Landschaft etablierter Tools: [Lexware Office Belegerfassung](https://www.lexware.de/funktionen/belegerfassung/), [Lexware digitaler Rechnungseingang](https://www.lexware.de/funktionen/digitaler-rechnungseingang/), [sevdesk wiederkehrende Belege](https://sevdesk.de/wiederkehrende-belege/). Beobachtung: OCR-Erfassung ist Standard-Marketing; erklärbare Entscheidungen und begründetes Abo-Radar sind dort nicht das sichtbare Kernversprechen — das ist unsere Differenzierung.
- Technik: [pypdf: Extract Text](https://pypdf.readthedocs.io/en/latest/user/extract-text.html), Vergleiche von PDF-Extraktoren und OCR ([ploomber](https://ploomber.io/blog/pdf-ocr/), [pdfmux zu PyMuPDF/pdfplumber](https://pdfmux.com/blog/pymupdf-vs-pdfplumber/)). Kernaussage: Textlayer-Extraktion deterministisch und offline; Bild-OCR fehleranfällig → Input-Leiter und Gate B0.
