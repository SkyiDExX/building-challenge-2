# Entscheidung 01: Agenten-Auswahl für Building Challenge #2

Datum: 23.07.2026 (Challenge Tag 1)
Status: Entschieden, wartet auf Abnahme durch Enrico vor Implementierungsstart

---

## 1. Geprüfte Fakten

- Challenge-Repo `https://github.com/SkyiDExX/building-challenge-2` wurde aus dem offiziellen Template erstellt, lokal geklont nach `C:\dev\building-challenge\building-challenge-2`, Branch `main`.
- Template-Dateien gelesen: START.md, README.md, ABGABE.md, .env.example, .gitignore.
- Abgaberegeln laut Template: Demo-Video 2 bis 3 Minuten, EIN Durchlauf, ungeschnitten, Bildschirmaufnahme reicht. Abgabe als Skool-Post mit Vorlage aus ABGABE.md. Mindestens ein Commit pro Bautag. Vorarbeit ist erlaubt, muss aber ehrlich genannt werden.
- Ein separates Vorarbeit-Repository (Optifyx OS) wurde ausschließlich read-only untersucht: working tree sauber, keine `.db`-, `.env`- oder Nutzdaten-Dateien geöffnet, kein Code ausgeführt, keine Produktionsdienste berührt.
- Bisher wurde kein Optifyx-Code in dieses Repository übernommen.

## 2. Annahmen (keine Fakten)

- Enrico verarbeitet Belege und Abos heute manuell und unsystematisch; geschätzter Aufwand und Fehlerrisiko sind nicht gemessen.
- Das Abo-Volumen (SaaS-Tools, KI-Dienste, Hosting) wächst mit Optifyx weiter.
- Die Skool-Community bewertet sichtbare Vorher-Nachher-Demos stärker als reine Text-Outputs.
- Ein lokal laufender, deterministischer Demo-Slice ist bis Sonntag stabil schaffbar.

## 3. Fehlende Beweise

- Keine Zeitmessung der heutigen manuellen Abläufe (alle Zeitersparnis-Angaben sind Schätzungen).
- Keine externe Prüfung, welche Pflichtangaben eine Rechnung formal enthalten muss; das wird erst später anhand offizieller deutscher Quellen geprüft und vorsichtig formuliert. Bis dahin gilt nur eine interne Vollständigkeits-Checkliste ohne Rechtsanspruch.
- Demo-Wirkung auf die Jury ist eine Hypothese.

---

## 4. Optifyx-Inventur (read-only, nur Muster, kein Code kopiert)

| Muster | Belegte Funktion | Nutzen für Challenge-Agent | Kategorie | Risiko / fehlende Evidenz |
|---|---|---|---|---|
| UI-Shell | Vanilla JS, Hash-Routing mit Deep-Links, Dark Mode via `data-theme`, Stale-Banner, responsive Breakpoints | Vorbild für eine kleine lokale Ergebnis-Ansicht | UX-Muster | Im Original unübersichtlich groß; für Challenge nur Prinzip übernehmen |
| Datenservice | Reine Python-stdlib `http.server`, hart auf 127.0.0.1, Portkonflikt-Erkennung, kein CORS | Lokaler Single-User-Dienst ohne Dependencies | Architekturwissen | Kein Beleg, dass das Muster für Datei-Uploads geeignet ist |
| Persistenz | SQLite, WAL, nummerierte append-only Migrationen, `schema_version`, CHECK-Enums | Gleiche Migrationstechnik neu schreiben | Architekturwissen | - |
| Auditlog | Tabelle mit alt/neu-Zustand, Aktion, Quelle je Schreibvorgang | Kern der Nachvollziehbarkeit des Belegpakets | Sicherheitsmuster | - |
| Provenienz | Trennung Import-Herkunft vs. Analyse-Herkunft, Ergebnisse verweisen auf Beleg | Direkt übertragbar: jedes Extrakt verweist auf Original-Datei plus Extraktionslauf | Sicherheitsmuster | - |
| Fail-closed Validierung | Whitelist Feld zu Prüffunktion, unbekannte Felder sind Fehler, wertfreie Fehlermeldungen | Unvollständige Belege landen im Review statt still übernommen | Sicherheitsmuster | - |
| Review-Bucket | Unklare Fälle werden gesammelt statt verworfen | Muster für "Beleg unklar, Mensch entscheidet" | Sicherheitsmuster | - |
| Mail-Wache | IMAP-IDLE Daemon, debounced Subprozess-Sync, Backoff, Status in DB | Später: Postfach-Überwachung für echte Belege; nicht im MVP | Architekturwissen | Nur Code gelesen, nie ausgeführt |
| Test-Isolation | Temp-DB via `mkdtemp`, Server auf Port 0, synthetische Fixtures, Produktions-DB nie geöffnet | Von Tag 1 übernehmen: Test- und Demo-Daten strikt getrennt | Testmuster | - |
| Fehler-UX | Fehler nie still verschluckt, ehrliche Zustandsbadges, Stale-Banner | Vertrauensbildend für die Demo | UX-Muster | - |

Kategorie "eventuell später transparent übernehmbarer Code": keine Datei in dieser Runde. Alles wird bei Bedarf neu geschrieben und die Herkunft der Idee dokumentiert.

---

## 5. Bewertungsmatrix (fixe Gewichtung)

Gewichte: Problem/Zeitersparnis 30, Demo 20, Agentik 15, Stabilität bis Sonntag 15, Dauernutzen 10, Datenschutz 5, Community-Appeal 5. Maximum 100.

| Kriterium (max) | 1. Rechnungs-/Abo | 2. Founder-Inbox | 3. Follow-up | 4. Content-Produktion | 5. Campaign-Delivery |
|---|---|---|---|---|---|
| Problem + Zeitersparnis (30) | 26 | 25 | 20 | 18 | 16 |
| Demo-Stärke (20) | 18 | 14 | 12 | 13 | 13 |
| Agentisches Verhalten (15) | 13 | 12 | 11 | 9 | 11 |
| Stabilität bis Sonntag (15) | 13 | 10 | 12 | 12 | 11 |
| Dauerhafter Nutzen (10) | 9 | 7 | 7 | 7 | 6 |
| Datenschutz der Demo (5) | 5 | 3 | 3 | 5 | 4 |
| Community-Appeal (5) | 4 | 3 | 3 | 3 | 3 |
| **Summe** | **88** | **74** | **68** | **67** | **64** |

### Kandidat 1: Rechnungs- und Abo-Agent

- **Ein-Satz-Versprechen:** Der Agent verwandelt eingehende Rechnungen in ein geprüftes, nachvollziehbares und buchhaltungsvorbereitendes Belegpaket und macht wiederkehrende Kosten sichtbar.
- **Zielperson:** Solo-Founder und Selbständige, konkret Enrico mit Optifyx.
- **Konkretes Problem:** Belege kommen verstreut an (Mail, PDF, Screenshot), landen unsortiert in Ordnern; Abos und Preiserhöhungen bleiben unbemerkt; vor Steuerterminen fehlt Überblick und Nerven.
- **Heutiger manueller Ablauf:** Beleg suchen, öffnen, Betrag/Datum/Anbieter abtippen, in Ordner ablegen, Abos aus dem Kopf erinnern; oft passiert nichts davon.
- **Plausible Zeitersparnis:** Schätzung 1 bis 2 Stunden pro Monat plus vermiedene Fehlkosten durch unbemerkte Abo-Erhöhungen (nicht gemessen).
- **Autonome Schritte:** 1) Beleg aus Eingangsordner einlesen und Felder extrahieren (Anbieter, Datum, Betrag, Währung, Referenz), 2) fail-closed gegen Vollständigkeits-Checkliste prüfen, 3) gegen Bestand abgleichen (Dublette? bekanntes Abo? Preis verändert?), 4) Entscheidung mit Begründung: in das vorbereitete Belegpaket übernehmen oder Review-Bucket, 5) Abo-Radar, Monatsübersicht und Auditlog aktualisieren.
- **Direkt nutzbarer Output:** Geprüftes Belegpaket (strukturierte Daten mit Verweis auf Original), Monatsübersicht, Abo-Radar, CSV-Export als Buchhaltungs-Vorbereitung.
- **Demo-Moment:** Drei Dateien in den Eingangsordner ziehen; Sekunden später steht das geprüfte Belegpaket da, das Abo-Radar meldet eine Preiserhöhung, eine Dublette wurde aussortiert, mit Begründung.
- **Notwendige Integrationen:** Keine im MVP (lokaler Ordner, lokale DB). Später optional Postfach.
- **Optifyx-Beschleuniger:** Auditlog-, Provenienz-, Validierungs-, Review- und Test-Isolationsmuster (siehe Inventur).
- **Technisches Hauptrisiko:** Extraktion aus unstrukturierten Belegen; im MVP durch synthetische, kontrollierte Fixtures entschärft.
- **Produkt-Hauptrisiko:** Wirkt als "nur Dokumentextraktion", wenn die Bestandsintelligenz (Abo, Dublette, Preis) nicht sichtbar wird; Demo muss genau diese zeigen.
- **Realistischer MVP-Aufwand:** 2 bis 3 Bautage für den Vertical Slice.
- **Wow-Faktor:** Abo-Radar mit Preissteigerungs-Alarm.
- **Spätere Nutzung:** Ja, real bei Optifyx (Kosten laufen bereits heute auf); später Zulieferer für den Finance-Bereich von Optifyx OS.
- **Annahmen:** Abo-Volumen wächst; Enrico nutzt einen Eingangsordner-Workflow.
- **Fehlende Beweise:** Keine Zeitmessung; formale Rechnungsanforderungen noch nicht anhand offizieller Quellen geprüft.
- **Kill-Kriterium:** Wenn der Slice bis Freitagabend keinen stabilen Durchlauf Normalfall plus Ausnahmefall schafft, wird auf den Zweitplatzierten gewechselt.

### Kandidat 2: Founder-Inbox-Agent

- **Ein-Satz-Versprechen:** Der Agent sortiert das Founder-Postfach, priorisiert und legt fertige Antwortentwürfe vor.
- **Zielperson:** Enrico als Solo-Founder.
- **Konkretes Problem:** Posteingang frisst täglich Zeit; Wichtiges geht zwischen Newslettern unter.
- **Heutiger manueller Ablauf:** Alles selbst lesen, sortieren, beantworten, Follow-ups erinnern.
- **Plausible Zeitersparnis:** 30 bis 60 Minuten täglich (Schätzung).
- **Autonome Schritte:** Klassifizieren, Priorisieren, Antwortentwurf erstellen, Follow-up-Kandidaten markieren.
- **Direkt nutzbarer Output:** Sortierte Übersicht plus versandfertige Entwürfe (Versand bleibt beim Menschen).
- **Demo-Moment:** Synthetisches Postfach rein, sortierte Prioritätenliste mit Entwürfen raus.
- **Notwendige Integrationen:** IMAP oder synthetisches Postfach.
- **Optifyx-Beschleuniger:** Mail-Wache-Architektur, Mail-Statusmodell, Entwurfs-Feld.
- **Technisches Hauptrisiko:** Echter Mailzugriff bis Sonntag fragil; synthetisch wirkt weniger echt.
- **Produkt-Hauptrisiko:** Sehr häufig gezeigter Use Case, geringer Erinnerungswert; Antwortqualität subjektiv.
- **Realistischer MVP-Aufwand:** 3 Bautage.
- **Wow-Faktor:** Entwurf im richtigen Ton inklusive Kontext aus früheren Mails.
- **Spätere Nutzung:** Hoch, überschneidet sich aber mit bereits existierender Optifyx-Mail-Wache.
- **Annahmen:** Genug synthetische Mails erzeugbar, die glaubwürdig wirken.
- **Fehlende Beweise:** Keine Messung des Mailaufkommens.
- **Kill-Kriterium:** Kein stabiler synthetischer Posteingang bis Donnerstag.

### Kandidat 3: Kunden- oder Creator-Follow-up-Agent

- **Ein-Satz-Versprechen:** Der Agent erkennt liegengebliebene Konversationen und legt passende Follow-up-Entwürfe vor.
- **Zielperson:** Enrico im Optifyx-Outreach.
- **Konkretes Problem:** Follow-ups werden vergessen, Leads verlaufen im Sand.
- **Heutiger manueller Ablauf:** Threads manuell durchsehen, erinnern, formulieren.
- **Plausible Zeitersparnis:** 1 bis 2 Stunden pro Woche (Schätzung), stark volumenabhängig.
- **Autonome Schritte:** Threads scannen, Überfälligkeit bewerten, Kontext zusammenfassen, Entwurf erstellen.
- **Direkt nutzbarer Output:** Follow-up-Liste mit fertigen Entwürfen.
- **Demo-Moment:** Aus einem Stapel synthetischer Threads entsteht eine priorisierte Follow-up-Liste.
- **Notwendige Integrationen:** Mail- oder CRM-Daten (im MVP synthetisch).
- **Optifyx-Beschleuniger:** Lead-Status-Workflows, Aktivitäten-Tabellen.
- **Technisches Hauptrisiko:** Überfälligkeits-Logik braucht Historie, die synthetisch aufwendig ist.
- **Produkt-Hauptrisiko:** Aktuell geringes Outreach-Volumen, Nutzen schwer belegbar; unspektakuläre Demo.
- **Realistischer MVP-Aufwand:** 2 bis 3 Bautage.
- **Wow-Faktor:** Kontextbewusstes Timing ("nicht nachfassen, Antwort kam gestern").
- **Spätere Nutzung:** Mittel, abhängig vom Outreach-Volumen.
- **Annahmen:** Follow-up-Disziplin ist tatsächlich der Engpass.
- **Fehlende Beweise:** Keine Zahlen zu verlorenen Leads.
- **Kill-Kriterium:** Demo wirkt in Probeaufnahme nicht verständlich.

### Kandidat 4: Content-Produktionsagent

- **Ein-Satz-Versprechen:** Der Agent macht aus einer Rohidee fertige Post-Entwürfe im eigenen Stil.
- **Zielperson:** Enrico für Optifyx-Content (LinkedIn, Instagram).
- **Konkretes Problem:** Content-Erstellung ist zäh und unregelmäßig.
- **Heutiger manueller Ablauf:** Idee notieren, formulieren, überarbeiten, oft bleibt es liegen.
- **Plausible Zeitersparnis:** 2 bis 3 Stunden pro Woche (Schätzung), Qualität schwer messbar.
- **Autonome Schritte:** Idee analysieren, Format wählen, Entwurf erstellen, Varianten liefern.
- **Direkt nutzbarer Output:** Publikationsfertige Entwürfe.
- **Demo-Moment:** Rohidee rein, drei formatgerechte Entwürfe raus.
- **Notwendige Integrationen:** Keine.
- **Optifyx-Beschleuniger:** Content-Workflows und Stil-Wissen (optifyx-voice-Skill existiert bereits).
- **Technisches Hauptrisiko:** Gering.
- **Produkt-Hauptrisiko:** Wirkt wie ein Prompt, nicht wie ein Agent; sehr generisch; Qualität subjektiv; Jury sieht solche Demos oft.
- **Realistischer MVP-Aufwand:** 1 bis 2 Bautage.
- **Wow-Faktor:** Stiltreue über mehrere Formate.
- **Spätere Nutzung:** Ja, aber teils durch bestehende Skills abgedeckt.
- **Annahmen:** Stil ist aus Beispielen lernbar.
- **Fehlende Beweise:** Kein Beleg, dass Output ungeprüft publikationsfähig ist.
- **Kill-Kriterium:** Entwürfe brauchen mehr Nacharbeit als Eigenerstellung.

### Kandidat 5: Creator-Campaign-Delivery-Agent

- **Ein-Satz-Versprechen:** Der Agent verwandelt eine Kampagnen-Zusage in Briefing, Deliverable-Plan und Termin-Tracking.
- **Zielperson:** Enrico beim Creator-Matching für DACH-Brands.
- **Konkretes Problem:** Kampagnenabwicklung ist kleinteilig und fehleranfällig.
- **Heutiger manueller Ablauf:** Briefings manuell schreiben, Deadlines im Kopf, Status in Nachrichtenverläufen.
- **Plausible Zeitersparnis:** Erst bei laufenden Kampagnen relevant; aktuell spekulativ.
- **Autonome Schritte:** Briefing generieren, Deliverables ableiten, Termine planen, Statusverfolgung aufsetzen.
- **Direkt nutzbarer Output:** Briefing-Dokument plus Delivery-Plan.
- **Demo-Moment:** Zusage-Nachricht rein, komplettes Kampagnenpaket raus.
- **Notwendige Integrationen:** Keine im MVP.
- **Optifyx-Beschleuniger:** Briefing-Artefakte, Status-Workflows.
- **Technisches Hauptrisiko:** Gering.
- **Produkt-Hauptrisiko:** Kein akuter Schmerz, da aktuell wenig Kampagnen laufen; Nutzen für Jury schwer nachvollziehbar.
- **Realistischer MVP-Aufwand:** 2 Bautage.
- **Wow-Faktor:** Vollständiges Paket aus einer einzigen Nachricht.
- **Spätere Nutzung:** Abhängig von Optifyx-Geschäftsentwicklung.
- **Annahmen:** Kampagnenformat ist standardisierbar.
- **Fehlende Beweise:** Kein reales Kampagnenvolumen.
- **Kill-Kriterium:** Kein glaubwürdiges synthetisches Kampagnenszenario formulierbar.

---

## 6. Entscheidung

**Favorit: Kandidat 1, Rechnungs- und Abo-Agent (88 Punkte). Arbeitstitel: Belegwächter.**
**Zweitplatzierter: Kandidat 2, Founder-Inbox-Agent (74 Punkte).**

Begründung, warum die Rechnungs-Idee hier tatsächlich die höchste Gewinnwahrscheinlichkeit hat und nicht nur Enricos Startpräferenz gewinnt:

1. **Bestes Demo-Profil:** Sichtbares Vorher-Nachher in unter 60 Sekunden, komplett offline, deterministisch, ohne externe Dienste und ohne Datenschutzrisiko. Kein anderer Kandidat erreicht das gleichzeitig.
2. **Echte Agentik statt Extraktion:** Die Entscheidung fällt über Bestandsintelligenz (Dublette, bekanntes Abo, Preisänderung, Review-Routing mit Begründung), nicht über das bloße Auslesen von Feldern. Punkt 8 der Prüffragen unten belegt das im Detail.
3. **Stabilität:** Kandidat 2 und 3 hängen an glaubwürdigen synthetischen Postfächern oder Historien; Kandidat 1 braucht nur kontrollierte Beleg-Fixtures.
4. **Breitester Community-Resonanzraum:** Jeder in der Academy hat ungeordnete Belege und vergessene Abos; Follow-ups und Kampagnen-Delivery sind nischiger.
5. **Dauernutzen belegbar:** Optifyx verursacht bereits heute laufende Tool-Kosten; der Agent wird nach der Challenge real eingesetzt und kann später den Finance-Bereich von Optifyx OS beliefern.

Kandidat 2 wird Zweiter, weil das Problem ähnlich groß ist, aber Demo-Stärke, Stabilität bis Sonntag und Datenschutz klar schwächer abschneiden und der Use Case in Jurys häufig gesehen wird.

## 7. Vertiefte Prüffragen zur Rechnungs-Idee (ergebnisoffen geprüft)

1. **Mehr als Dokumentextraktion?** Ja. Die Extraktion ist nur Schritt 1. Der Kern ist der Abgleich jedes neuen Belegs gegen den Bestand: Ist das eine Dublette? Gehört er zu einem bekannten Abo? Hat sich der Preis geändert? Fehlt ein erwarteter Beleg? Diese Bestandsintelligenz existiert in keinem reinen Extraktions-Tool.
2. **Welche drei oder mehr Schritte sind wirklich autonom?** Einlesen/Extrahieren, fail-closed Vollständigkeitsprüfung, Bestandsabgleich, begründete Verbuchungs- oder Review-Entscheidung, Aktualisierung von Abo-Radar, Übersicht und Auditlog. Fünf Schritte ohne Menscheneingriff im Normalfall.
3. **Welche Ausnahmebehandlung wirkt intelligent?** Drei Kandidaten: a) Dublette (gleiche Rechnung doppelt eingereicht, wird erkannt und nicht doppelt gezählt), b) Preiserhöhung eines bekannten Abos (Alarm mit alt/neu-Vergleich), c) unvollständiger Beleg (landet mit Begründung im Review statt geraten zu werden). Die Demo zeigt mindestens b) und c).
4. **Stärkste Wow-Funktion?** Das **Abo-Radar mit Preissteigerungs-Alarm**. Begründung: Dubletten- und Fehlbeleg-Erkennung sind Ausnahmebehandlung (Vertrauen), aber das Abo-Radar erzeugt den "das will ich auch"-Moment, weil es Geld sichtbar macht, das still verloren geht. Es ist die eine Wow-Funktion des MVP; Dublette und Review sind Ausnahmefälle, keine zweite Wow-Funktion.
5. **Demo in unter 60 Sekunden verständlich erfolgreich?** Ja: Drei synthetische Belege in den Eingangsordner ziehen, Agent verarbeitet, Ergebnisansicht zeigt Belegpaket plus Abo-Radar mit einem Preisalarm. Das ist in etwa 45 Sekunden zeigbar; die restliche Zeit gehört Ausnahmefall, Auditlog und Reset.

Sprachregel für alle Projekttexte: Es gilt ausschließlich das Versprechen "geprüftes, nachvollziehbares und buchhaltungsvorbereitendes Belegpaket". Keine Aussagen zu Finanzamt-Konformität, GoBD-Konformität, Steuerberatung oder rechtlicher Sicherheit. Formale Anforderungen werden erst später anhand offizieller deutscher Quellen geprüft und dann vorsichtig beschrieben.

---

## 8. Produktplan Belegwächter (MVP / Vertical Slice)

- **Arbeitstitel:** Belegwächter
- **Ein-Satz-Versprechen:** Der Agent verwandelt eingehende Rechnungen in ein geprüftes, nachvollziehbares und buchhaltungsvorbereitendes Belegpaket und macht wiederkehrende Kosten sichtbar.
- **Zielperson:** Solo-Founder und Selbständige; erste Nutzerperson ist Enrico.
- **Konkreter Schmerz:** Belege verstreut, Abos unbemerkt, vor Steuerterminen Chaos.
- **Synthetischer Input:** Ordner `fixtures/eingang/` mit erfundenen Belegen (Textform, später auch Screenshot-Fälle): z.B. "CloudHost Nov", "CloudHost Dez mit Preiserhöhung", "Design-Tool-Jahresrechnung", "Dublette CloudHost Dez", "Beleg ohne Betrag". Keine echten Daten, keine echten Anbieterbeziehungen.
- **Autonome Schritte (mindestens drei):** Extrahieren, fail-closed prüfen, Bestandsabgleich, begründete Entscheidung, Radar/Übersicht/Audit aktualisieren.
- **Direkt nutzbarer Output:** Belegpaket-Übersicht (pro Beleg: Felder, Status, Begründung, Verweis auf Originaldatei), Abo-Radar, CSV-Export.
- **Sichtbare Provenienz:** Jeder übernommene Eintrag verweist auf Originaldatei plus Extraktionslauf (Muster aus Optifyx-Provenienz, neu implementiert).
- **Aktivitätsverlauf:** Auditlog mit alt/neu-Zustand je Aktion (Muster aus Optifyx-Auditlog, neu implementiert).
- **Unsicherheits- und Review-Behandlung:** Unvollständige oder widersprüchliche Belege landen fail-closed im Review-Bucket mit Begründung; nichts wird geraten oder still verworfen.
- **Normalfall:** Vollständiger Beleg wird nach interner Checkliste geprüft, in das vorbereitete Belegpaket übernommen und erscheint in Übersicht und Radar.
- **Intelligenter Ausnahmefall:** Preiserhöhung eines bekannten Abos wird erkannt und alarmiert; unvollständiger Beleg geht in Review.
- **Academy-Demo-Modus:** Ein Befehl startet mit frischen Fixtures und leerer Demo-DB; komplett offline vorführbar.
- **Spätere produktive Integration:** Echter Belegordner, optional Postfach-Anbindung (Mail-Wache-Muster), Export in den Finance-Bereich von Optifyx OS.
- **Nicht-Ziele:** Keine Steuerberatung, keine Konformitätszusagen, kein echter Mailzugriff im MVP, kein Multi-User, keine echten Belege in der Demo, keine Zahlungsauslösung.
- **Genau eine Wow-Funktion:** Abo-Radar mit Preissteigerungs-Alarm.

**Vertical-Slice-Eigenschaften:** ausschließlich synthetische Daten; ohne externe Dienste vorführbar; sichtbares Vorher-Nachher (voller Eingangsordner gegen geprüfte Übersicht); Normal- plus Ausnahmefall; jede Entscheidung mit Begründung; isolierte Persistenz (eigene SQLite-Datei im Challenge-Repo, per .gitignore ausgeschlossen); Reset-Befehl; stabil für ein ungeschnittenes Demo-Video.

## 9. Demo-Drehbuch (2 bis 3 Minuten, ein Durchlauf, ungeschnitten)

1. **0:00 bis 0:15:** Bildschirm zeigt links den chaotischen Eingangsordner, rechts die leere Belegwächter-Ansicht. Eingeblendeter Satz: Problem (Belege verstreut, Abos unbemerkt) plus Versprechen plus ein Blick auf das fertige Endergebnis.
2. **0:15 bis 0:60:** Kernautomation: Belege in den Eingangsordner ziehen, Agent starten, Übersicht füllt sich sichtbar; erster Erfolg klar erkennbar.
3. **1:00 bis 1:40:** Ausnahmefälle: Abo-Radar schlägt bei Preiserhöhung an (alt/neu sichtbar), Dublette wird aussortiert, unvollständiger Beleg liegt im Review, jeweils mit Begründungstext.
4. **1:40 bis 2:20:** Nachvollziehbarkeit: Klick von einem übernommenen Eintrag zur Originaldatei (Provenienz), Blick ins Auditlog, CSV-Export öffnen.
5. **2:20 bis 2:45:** Reset-Befehl, System startet frisch, beweist Reproduzierbarkeit.

## 10. Datenschutzgrenzen

Demo und Tests verwenden ausschließlich erfundene Belege. Keine echten Rechnungen, Anbieter-Konten, Mails oder Optifyx-Produktionsdaten. Die Produktions-DB von Optifyx bleibt vollständig unberührt.

## 11. Risiken

- Extraktionsqualität bei später echten, unstrukturierten Belegen (im MVP bewusst durch Fixtures kontrolliert).
- "Nur-Extraktion"-Wahrnehmung, falls die Demo die Bestandsintelligenz nicht klar zeigt (Drehbuch adressiert das direkt).
- Zeitrisiko bis Sonntag; Kill-Kriterium: kein stabiler Komplettdurchlauf bis Freitagabend, dann Wechsel auf Kandidat 2.
- Formale Anforderungen an Rechnungen sind noch ungeprüft; bis zur Prüfung offizieller Quellen bleibt die Checkliste intern und ohne Rechtsanspruch.

## 12. Exakt ein nächster Implementierungsschritt

**Vertical Slice 1: "Eingang zu geprüftem Belegpaket"**

- **Zweck:** Der kleinste vollständige Durchlauf: Belege aus `fixtures/eingang/` werden verarbeitet und als geprüftes Belegpaket mit Abo-Radar sichtbar.
- **Sichtbarer Nutzereffekt:** Aus fünf unsortierten Dateien entsteht ohne Handarbeit eine geprüfte Übersicht mit einem Preisalarm, einer aussortierten Dublette und einem Review-Fall.
- **Synthetische Fixtures:** Fünf erfundene Belege (zwei Monats-Abos desselben Anbieters mit Preiserhöhung, eine Jahresrechnung, eine exakte Dublette, ein unvollständiger Beleg).
- **Autonome Verarbeitungsschritte:** Einlesen/Extrahieren, Vollständigkeitsprüfung (fail-closed), Bestandsabgleich (Dublette/Abo/Preis), Entscheidung mit Begründung, Persistieren plus Audit plus Radar-Update.
- **Erwarteter Output:** Übersicht (zunächst als lokale Ansicht oder strukturierter Report), `export.csv`, Auditlog-Einträge.
- **Isolierte Persistenz:** `speicher/belegwaechter.db` (SQLite, per .gitignore ausgeschlossen), Migrationsmuster mit `schema_version`.
- **Vorgeschlagener Dateikreis:** `belegwaechter/` (Verarbeitungskern), `fixtures/eingang/`, `tests/test_slice.py`, Ergänzungen in README und `.gitignore`.
- **Akzeptanzkriterien:** Alle fünf Fixtures landen im jeweils richtigen Zustand (3 übernommen, 1 Dublette aussortiert, 1 Review); Preisalarm mit alt/neu-Werten vorhanden; jeder Eintrag verweist auf seine Quelldatei; Auditlog vollständig; Reset stellt den Ausgangszustand wieder her; Testlauf grün.
- **Tests:** Ein Testmodul mit Temp-DB (mkdtemp-Muster), das den kompletten Durchlauf plus Reset prüft.
- **Stop-Bedingungen:** Kein stabiler Durchlauf bis Freitagabend (Kill-Kriterium); jede Notwendigkeit echter Daten; jede Ausweitung über den Dateikreis hinaus.
- **Demo-Auswirkung:** Dieser Slice deckt Drehbuch-Szenen 2, 3 und 5 vollständig ab.

Dieser Schritt wird erst nach Enricos Abnahme begonnen.
