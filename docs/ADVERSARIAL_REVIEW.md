# Adversarial Review: Belegwächter aus neun Rollen

Datum: 23.07.2026 (Challenge Tag 1, Arbeitsblock 2)
Grundlage: `docs/decision-01-agent-selection.md`, Template-Regeln (START.md, ABGABE.md)
Zweck: Den Plan angreifen, bevor die Jury es tut. Jede Rolle prüft dieselbe Frage: Was verhindert Platz 1?

---

## Rolle 1: Challenge-Jury

- **Wichtigstes Nutzerziel:** Schnell erkennen, ob ein echtes Problem gelöst wird und ob der Agent wirklich agiert statt nur zu konvertieren.
- **Stärkster positiver Moment:** Der Agent begründet jede Entscheidung sichtbar ("Dublette, weil gleiche Referenz und gleicher Betrag wie Beleg X").
- **Größte Reibung:** Wenn die Demo mit Extraktion beginnt, ist das erste Urteil "OCR-Tool" und das bleibt kleben.
- **Größtes Vertrauensproblem:** Vorarbeit (Optifyx) muss glasklar von Challenge-Arbeit getrennt sein, sonst wirkt die Commit-Historie unehrlich.
- **Grund gegen Nutzung:** Nicht relevant (Jury nutzt nicht, sie bewertet).
- **Grund gegen Platz 1:** "Solide, aber schon tausendmal gesehen" bei Beleg-Tools; Differenzierung muss die erklärte Entscheidung sein, nicht die Erfassung.
- **Zwingende Verbesserung:** Demo-Dramaturgie umdrehen: nicht "Upload, Extraktion, Liste", sondern "Agent trifft sichtbar Entscheidungen, Mensch sieht nur die Fälle, die ihn brauchen".
- **Nicht in den MVP:** Kontenrahmen-Zuordnung, USt-Logik, Steuer-Features jeder Art.

## Rolle 2: Community-Voter ohne Finanzwissen

- **Wichtigstes Nutzerziel:** In 30 Sekunden verstehen, was passiert, ohne Buchhaltungsvokabular.
- **Stärkster positiver Moment:** Das Abo-Radar: "Dein CloudHost-Abo ist 4 Euro teurer geworden" versteht jeder sofort.
- **Größte Reibung:** Begriffe wie "Provenienz", "fail-closed", "Belegpaket" sagen einem Laien nichts.
- **Größtes Vertrauensproblem:** Wenn Zahlenkolonnen dominieren, schaltet der Voter ab und stimmt für das unterhaltsamere Projekt.
- **Grund gegen Nutzung:** "Ich habe doch gar keine Firma" — der private Nutzen (Abos!) muss mitschwingen.
- **Grund gegen Platz 1:** Voting ist ein Sympathie-Wettbewerb; ein trockenes Finanztool verliert gegen etwas mit sichtbarem Aha-Moment.
- **Zwingende Verbesserung:** UI-Sprache radikal vereinfachen: "Fertig", "Bitte ansehen", "Doppelt, aussortiert", "Abo teurer geworden". Fachbegriffe nur in Tooltips oder Doku.
- **Nicht in den MVP:** Konfigurierbare Regeln, Einstellungsseiten, Fachjargon-Modus.

## Rolle 3: Solo-Founder als täglicher Nutzer

- **Wichtigstes Nutzerziel:** Beleg loswerden in unter zehn Sekunden, Rest passiert ohne mich.
- **Stärkster positiver Moment:** Monatsende: Alles liegt geprüft und exportierbar bereit, statt Schuhkarton-Gefühl.
- **Größte Reibung:** Wenn ich Belege erst suchen, umbenennen oder konvertieren muss, nutze ich es nach Woche 1 nicht mehr.
- **Größtes Vertrauensproblem:** Stille Fehler: Ein verlorener Beleg ohne Meldung zerstört das Vertrauen dauerhaft.
- **Grund gegen Nutzung:** Wenn der Review-Bucket zur zweiten Inbox wird, die ständig Aufmerksamkeit will, ist nichts gewonnen.
- **Grund gegen Platz 1:** Andere Founder in der Community fragen: "Warum nicht einfach Lexware?" Antwort muss sitzen: lokal, erklärbar, ohne Abo-Kosten, erweiterbar.
- **Zwingende Verbesserung:** Der Normalfall (vollständiger Beleg) muss null Interaktion brauchen; Review nur für echte Ausnahmen.
- **Nicht in den MVP:** Mail-Postfach-Anbindung, automatischer Bank-Abgleich, Mehrmandanten.

## Rolle 4: Mobiler Nutzer

- **Wichtigstes Nutzerziel:** Papierbeleg oder App-Rechnung unterwegs per Foto/Screenshot loswerden.
- **Stärkster positiver Moment:** Teilen-Knopf, Beleg ist drin, Handy wieder in die Tasche.
- **Größte Reibung:** Der MVP ist Desktop-Web; mobil gibt es in der Challenge-Woche nur eine responsive Ansicht, keinen Share-Adapter.
- **Größtes Vertrauensproblem:** Ein Foto ist oft schief, abgeschnitten, unscharf; wenn der Agent daraus stillschweigend Daten "errät", ist das gefährlich.
- **Grund gegen Nutzung:** Ohne mobilen Eingang bleibt der Papierbeleg-Fall ungelöst.
- **Grund gegen Platz 1:** Gering; die Jury bewertet die Demo am Desktop.
- **Zwingende Verbesserung:** Ehrliche Roadmap-Kennzeichnung: mobile Erfassung ist Stufe-B-Eingang und späterer Adapter, kein MVP-Versprechen.
- **Nicht in den MVP:** Mobile Share-Integration, Kamera-Workflow, PWA.

## Rolle 5: Finanz- oder Buchhaltungsmitarbeiter

- **Wichtigstes Nutzerziel:** Vollständige, konsistente, nachvollziehbare Belegdaten ohne Nacharbeit.
- **Stärkster positiver Moment:** Jeder Eintrag verweist auf die Quelldatei; Original und Erfassung sind unterscheidbar.
- **Größte Reibung:** Brutto/Netto, Währung und Zeitraum müssen konsistent behandelt sein, sonst ist der Export wertlos.
- **Größtes Vertrauensproblem:** Ein Screenshot, der wie ein Originalbeleg behandelt wird. Das ist fachlich falsch und muss sichtbar unterschieden werden ("Original vorhanden" vs. "Erfassungsnachweis").
- **Grund gegen Nutzung:** Wenn Beträge ohne Kennzeichnung von Schätzung vs. sicherer Extraktion erscheinen.
- **Grund gegen Platz 1:** Fachliche Schnitzer in der Demo (z.B. Bruttobetrag als "Preis" eines Netto-Abos verglichen) fallen Fachleuten sofort auf.
- **Zwingende Verbesserung:** Preisvergleich nur bei eindeutiger Vergleichbarkeit (Anbieter, Tarif, Währung, Zeitraum, Menge, Netto/Brutto, Rabatt, anteilige Abrechnung); sonst ehrlich "Vergleich erforderlich".
- **Nicht in den MVP:** Kontierung, USt-Ausweis-Prüfung, DATEV-Export.

## Rolle 6: Steuerberater / vorbereitender Buchhaltungsdienstleister

- **Wichtigstes Nutzerziel:** Saubere, vollständige Belegsammlung mit klarem Status, keine Rechtsbehauptungen.
- **Stärkster positiver Moment:** Fail-closed: Unklares landet im Review statt in der Ablage.
- **Größte Reibung:** Jede Formulierung, die nach geprüfter Rechtskonformität klingt, ist ein rotes Tuch; das Tool ist Zubringer, nicht Prüfer.
- **Größtes Vertrauensproblem:** Behauptete Vollständigkeitsprüfung ohne Offenlegung der Checkliste.
- **Grund gegen Nutzung:** Übernahme-Aufwand, wenn der Export kein gängiges Format hat (CSV reicht für den Anfang, muss aber sauber sein).
- **Grund gegen Platz 1:** Gering, aber falsche Rechtsbegriffe könnten in der Community zerpflückt werden.
- **Zwingende Verbesserung:** Sprachregel konsequent durchziehen: "geprüft nach interner Checkliste", "buchhaltungsvorbereitend", niemals "korrekt", "konform", "rechtssicher". Checkliste im Repo offenlegen.
- **Nicht in den MVP:** Aufbewahrungs-Compliance-Aussagen, E-Rechnungs-Validierung (XRechnung/ZUGFeRD), Kanzlei-Schnittstellen.

## Rolle 7: Agentur mit mehreren Kunden

- **Wichtigstes Nutzerziel:** Belege pro Mandant/Kunde trennen.
- **Stärkster positiver Moment:** Erklärbare Entscheidungen wären auch gegenüber Kunden Gold wert.
- **Größte Reibung:** MVP ist Single-User, Single-Mandant; für Agenturen unbrauchbar.
- **Größtes Vertrauensproblem:** Vermischte Datenbestände wären ein No-Go; das existiert im MVP nicht, muss aber als Grenze benannt sein.
- **Grund gegen Nutzung:** Fehlende Mandantenfähigkeit.
- **Grund gegen Platz 1:** Gering; die Zielgruppe ist bewusst Solo-Founder.
- **Zwingende Verbesserung:** Mandantenfähigkeit explizit als Nicht-Ziel und ausgeschlossene Zielgruppe dokumentieren, damit die Story fokussiert bleibt.
- **Nicht in den MVP:** Mandanten, Rollen, Rechte, Team-Features.

## Rolle 8: Datenschutz- und Security-Verantwortlicher

- **Wichtigstes Nutzerziel:** Keine echten personenbezogenen oder Finanzdaten in Demo, Repo oder Video.
- **Stärkster positiver Moment:** Komplett lokal, keine Cloud, keine externen Dienste, synthetische Fixtures.
- **Größte Reibung:** Runtime-Artefakte (Uploads, DB, Exporte, Logs) könnten versehentlich committet werden; .gitignore muss das hart ausschließen.
- **Größtes Vertrauensproblem:** Ein einziger echter Beleg im öffentlichen Repo oder im Video wäre ein Totalschaden.
- **Grund gegen Nutzung:** Keiner, solange lokal.
- **Grund gegen Platz 1:** Ein sichtbarer Datenschutz-Patzer im Video (echter Name, echte Mail, echter Betrag) disqualifiziert moralisch.
- **Zwingende Verbesserung:** .gitignore-Härtung (runtime/, Uploads, Exporte, DBs, Logs, Screenshots) plus Regel: Demo-Aufnahme nur mit frischem Demo-Datenstand.
- **Nicht in den MVP:** Jede echte Integration (Mail, Konten, Portale).

## Rolle 9: QA- und Demo-Regisseur

- **Wichtigstes Nutzerziel:** Ein ungeschnittener Durchlauf, der beim fünften Versuch genauso funktioniert wie beim ersten.
- **Stärkster positiver Moment:** Reset-Befehl macht jede Probe identisch reproduzierbar.
- **Größte Reibung:** Asynchrone Verarbeitung mit unklarer Dauer ruiniert das Timing; die Demo braucht deterministische, sichtbar getaktete Schritte.
- **Größtes Vertrauensproblem:** Live-Überraschungen (Encoding, Pfade, Fenstergrößen, Benachrichtigungen).
- **Grund gegen Nutzung:** Nicht relevant.
- **Grund gegen Platz 1:** Demo länger als 3 Minuten, Kernnutzen erst nach Minute 1, oder ein sichtbarer Fehler im ungeschnittenen Video.
- **Zwingende Verbesserung:** Demo-Choreografie sekundengenau festlegen (UX_DEMO_SPEC), mindestens drei komplette Proben vor der Aufnahme, Aufnahme-Checkliste (Benachrichtigungen aus, festes Fenster-Layout, frischer Reset).
- **Nicht in den MVP:** Alles, was den Durchlauf variabel macht (Zufall, Netzwerk, lange Ladezeiten).

---

## Konsolidierte Top-Erkenntnisse

1. **Die Story muss "Entscheidungen, nicht Extraktion" sein.** Jury und Voter urteilen in den ersten 30 Sekunden.
2. **Screenshot ist niemals das Original.** Statusmodell braucht die Unterscheidung "Original vorhanden" vs. "Erfassungsnachweis" mit ehrlichem Review-Routing.
3. **Preisvergleich nur bei eindeutiger Vergleichbarkeit**, sonst "Preisänderung möglich, Vergleich erforderlich". Fachliche Glaubwürdigkeit schlägt Alarm-Drama.
4. **UI-Sprache für Laien**, Fachbegriffe raus aus der Oberfläche.
5. **Demo sekundengenau choreografieren und proben**; Reset ist das wichtigste Demo-Feature.
6. **Sicherheitsgrenzen technisch erzwingen** (.gitignore, runtime-Trennung), nicht nur versprechen.
