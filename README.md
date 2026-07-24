# OptiTax

**Eine Rechnungs-E-Mail hinein — OptiTax erkennt Produkt, Rechnung und
Zahlungsnachweis, verbindet zusammengehörige Dokumente, verhindert
Doppelzählungen und sagt nachvollziehbar, was als Nächstes zu tun ist.**

> SKAILE Building Challenge #2 · lokales Finanz-Tool mit regelbasiertem,
> zustandsabhängigem Agentenkern · keine Steuer-, Rechts- oder
> Compliance-Garantie

## Das Problem

Solo-Selbstständige erhalten Rechnungen, Zahlungsbelege und Abo-Nachweise
getrennt per E-Mail. Das kostet Zeit, führt zu fehlenden Originalen und
birgt das Risiko, Kosten doppelt oder gar nicht zu erfassen. Vor
Steuerterminen beginnt dann die Suche: Welche Rechnung gehört zu welcher
Zahlung? Was ist ein Abo? Was wurde schon erfasst?

## Was der Agent macht

Du ziehst eine heruntergeladene Rechnungs-E-Mail (.eml) oder ein
Rechnungs-PDF auf die Kosten-Inbox. Danach arbeitet OptiTax selbstständig:

1. **Erkennen:** Dateityp per Signatur, E-Mail lokal zerlegen, Rechnung,
   Zahlungsbeleg und Abo-Bestätigung unterscheiden.
2. **Verstehen:** Produkt, Tarif, Rechnungsaussteller, Abrechnungskanal,
   Zahlungsdienst und Abrechnungsintervall bestimmen — nur mit Evidenz,
   nichts wird geraten.
3. **Verbinden:** Rechnung und Zahlungsnachweis derselben E-Mail werden ein
   Kostenvorgang mit genau einer wirtschaftlichen Kostenposition.
4. **Schützen:** Byte-identische und inhaltliche Duplikate werden
   aussortiert, der Kostenbestand bleibt unverändert.
5. **Entscheiden:** Jeder Beleg endet mit einer begründeten nächsten
   Aktion — übernommen, „Rechnung oder Originalbeleg anfordern" oder eine
   konkrete Prüf-/Ergänzungsaufgabe, die du direkt im Dialog erledigst.

Dazu eine **Abo-Übersicht** (Radar für wiederkehrende Kosten und fehlende
Rechnungen) und ein prüfungsfreundlicher CSV-Export, der Produkt und
rechtlichen Aussteller sauber trennt.

## Demo

**Demo-Video (ein Durchlauf, ungeschnitten, 2–3 Minuten):**
`DEMO_LINK_EINFÜGEN`

Ablauf und Drehbuch: `docs/DEMO_SCRIPT.md`

## Was im sichtbaren Ablauf passiert

- **Normalfall:** Eine synthetische Hosting-E-Mail mit Rechnungs-PDF und
  Zahlungsbeleg wird zu einem Vorgang mit zwei getrennten Dokumentarten,
  einem Produktprofil und genau einer Kostenzeile. Original-PDF und eine
  sichere E-Mail-Ansicht sind einen Klick entfernt.
- **Ausnahmefall:** Eine Zahlungsbestätigung ohne Rechnung erzeugt keine
  Kostenzeile und keine Vergleichsbasis, sondern die ehrliche Aufgabe
  „Rechnung oder Originalbeleg anfordern".
- **Zustandsabhängiger Duplikatfall:** Dieselbe Datei ein zweites Mal
  hochgeladen wird als Duplikat aussortiert — gleiche Eingabe, anderes
  Ergebnis, weil der Agent seinen Bestand kennt.

## Warum es ein Agent ist

OptiTax ist ein regelbasierter, zustandsabhängiger Agent: Er erstellt pro
Eingang einen protokollierten Ausführungsplan (`belegwaechter/planen.py`),
wählt Prüfwerkzeuge (Extraktion, Dokumentart, `kostenprofil_bestimmen`,
Checkliste, Bestandsabgleich, Abo-Vergleich) und revidiert den Plan anhand
neuer Evidenz — ein Lesefehler, ein erkanntes Duplikat oder „Zahlungsnachweis
ohne Rechnung" deaktiviert Werkzeuge mit protokolliertem Grund. Der Executor
fragt ausschließlich den Plan ab; Testinvarianten stellen sicher, dass Plan
und tatsächliche Ausführung nie auseinanderlaufen. Entscheidungen hängen vom
Bestand ab: dieselbe Datei kann heute übernommen und morgen als Duplikat
aussortiert werden. Nach manuellen Korrekturen bewertet der Agent den Beleg
komplett neu. Er ist nicht selbstlernend und gibt keine Steuer-, Rechts-
oder Compliance-Garantie.

## Stack

- **Claude Code** für die Entwicklung (kein n8n)
- **Python** (Verarbeitungskern), **SQLite** (lokale Ablage), **pypdf**
  (PDF-Textebene)
- Python-Standardbibliothek für E-Mail-Verarbeitung (`email`) und den
  lokalen Webserver (`http.server`)
- **HTML, CSS und JavaScript** ohne Frameworks
- Keine externen Laufzeitdienste, keine API-Keys, alles läuft lokal auf
  `127.0.0.1`

Technischer Hinweis: Der interne Name des Python-Pakets und der Datenbank
lautet aus Stabilitätsgründen weiterhin `belegwaechter`.

## Setup

Ausführliche Schritt-für-Schritt-Anleitung inkl. Fehlerbehebung:
`INSTALL.md`. Kurzfassung (Windows PowerShell):

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m unittest tests.test_belegwaechter
.venv\Scripts\python.exe web\server.py
```

Dann `http://127.0.0.1:8850` öffnen und die synthetischen Dateien aus
`fixtures/` auf die Upload-Fläche ziehen.

## Was während der Challenge entstanden ist

Ehrliche Abgrenzung: Vorher existierte nur ein separates, privates
Dashboard-Projekt (Optifyx), aus dem ausschließlich Wissen (Test-, Audit-
und Sicherheitsmuster) genutzt wurde — kein Code. Der komplette
OptiTax-Agent entstand neu in diesem Repository, nachvollziehbar über die
Commit-Historie ab 23.07.2026:

- **Plansteuerbarer, zustandsabhängiger Agent** mit protokollierten
  Planrevisionen, Schritteverlauf und getesteten Plan-Invarianten.
- **Sichere Verarbeitung von PDFs und EML-Dateien** mit Signaturprüfung,
  Kostenvorgängen, Original-PDF-Zugriff und einer E-Mail-Ansicht, die nie
  fremdes HTML ausführt oder Inhalte nachlädt.
- **Produkt- und Abo-Profil, Duplikaterkennung, append-only
  Review-Korrekturen mit Neubewertung und prüfbarer CSV-Export** mit
  zentraler Exportregel (genau eine Kostenzeile pro Vorgang).

## Drei Learnings

1. **Ein protokollierter Plan ist erst dann agentisch, wenn er die
   Werkzeugausführung tatsächlich steuert.** Solange der Code selbst
   verzweigt, ist der Plan nur Dekoration — deshalb prüfen Tests bei jedem
   Lauf, dass kein Werkzeug ohne aktiven Planeintrag läuft und keine
   Revision ohne Grund passiert.
2. **Betreff, Mailtext und Anhänge brauchen getrennte Evidenzstufen, sonst
   entstehen überzeugend wirkende Fehlklassifikationen.** Der Betreff
   „Zahlungsbeleg" darf eine angehängte Rechnung nie umklassifizieren, und
   ein beiläufiges „Ihr Abo verlängert sich" macht aus einer Rechnung keine
   Abo-Bestätigung.
3. **Vertrauen entsteht durch ehrliche Unsicherheit, unveränderte Originale
   und nachvollziehbare Korrekturen statt durch geraten wirkende
   Automatisierung.** „Produkt nicht eindeutig" mit Prüfaufgabe schlägt
   jede erfundene Angabe; jede manuelle Korrektur bleibt append-only
   protokolliert, das Original bleibt unangetastet.

## Grenzen und ehrliche Hinweise

- Feldextraktion ist musterbasiert („Label: Wert"-Vorlagen plus verbreitete
  deutsche/englische Rechnungsmuster), kein allgemeiner Parser für beliebige
  Layouts.
- EML heißt hochgeladene .eml-Datei: kein Postfach-Zugriff, keine Links,
  kein Nachladen. Bilder ohne Textebene landen ehrlich in „Original
  angefordert" (kein OCR).
- „Nächste Abbuchung" nur bei explizit belegtem Datum; aus Zeiträumen wird
  höchstens eine erwartete Rechnung abgeleitet, nie eine Zahlungszusage.
- Kein Mehrbenutzerbetrieb, kein Bank-Abgleich, keine automatische Buchung,
  kein Ersatz für Steuerberatung, keine Aussage zu Finanzamts- oder
  GoBD-Konformität.

## Build Journal

Die Commit-Historie dieses Repositories ist das Build Journal der
Challenge (23.–24.07.2026): vom Agenten-Konzept und Premortem über den
ersten echten Agenten-Slice, EML-Zerlegung, Kostenvorgänge und
Sicherheitshärtung bis zu Pflichtfeldmatrix, manuellen Korrekturen,
Produktprofil, Abo-Übersicht und sicherer Originalansicht. Historische
Planungsdokumente liegen unter `docs/` (u. a. `MASTER_PLAN.md`,
`PREMORTEM.md`, `FEASIBILITY_INPUTS.md`).

---

*SKAILE Academy Building Challenge — Juli 2026*
