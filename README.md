# OptiTax — SKAILE Building Challenge #2

> Öffentlicher Produktname: **OptiTax**. Der interne technische Name des
> Python-Pakets, der Datenbank und der Module bleibt aus
> Stabilitätsgründen `belegwaechter`.

> Stand Arbeitsblock 4 (23.07.2026): End-to-End-Vertical-Slice läuft,
> jetzt inklusive EML-Upload. Zentrale, manuelle Kosten-Inbox: Belege und
> heruntergeladene Rechnungs-E-Mails werden manuell zugeführt.
> OptiTax ist ein regelbasierter, zustandsabhängiger Agent. Er
> erstellt pro Eingang einen Ausführungsplan, wählt notwendige
> Prüfwerkzeuge, überspringt ungeeignete Schritte, verbindet die Dokumente
> einer E-Mail zu einem Kostenvorgang und entscheidet anhand von Evidenz
> und vorhandenem Bestand über die nächste Aktion.

## Das Problem

Als Solo-Founder kommen Rechnungen und Kostennachweise verstreut an (PDF,
Screenshot, Foto) und landen unsortiert in Ordnern. Abos und deren
Preisänderungen bleiben unbemerkt, und vor Steuerterminen kostet das
Aufräumen Stunden und Nerven.

## Was der Agent macht

Belege und Kostennachweise aus unterschiedlichen Quellen hinein.
OptiTax prüft, ordnet und verfolgt sie selbstständig bis zum
nachvollziehbaren Monatspaket: Datei erkennen, Quellenqualität bewerten,
bei PDFs die Felder lesen, fail-closed auf Vollständigkeit prüfen, gegen den
Bestand abgleichen (Dublette? bekanntes Abo? Preis eindeutig vergleichbar?)
und mit konkreter Begründung entscheiden: in das vorbereitete Belegpaket
übernehmen, als Dublette aussortieren, oder zur Prüfung mit "Original
anfordern" vorlegen. Dazu ein erklärbares Abo-Radar, das wiederkehrende
Kosten und Preisänderungen sichtbar macht, nur wenn der Vergleich wirklich
eindeutig ist.

Hinweis: Der Agent gibt keine Steuerberatung und verspricht keine
finanzamtkonforme oder GoBD-konforme Prüfung. Er bereitet Belege strukturiert
und nachvollziehbar vor, geprüft nach interner Checkliste.

## Stack

- [x] Claude Code (Agent / Skills)
- [ ] n8n
- [x] Sonstiges: Python (lokaler Verarbeitungskern + `pypdf`), SQLite (lokale Ablage), reine Standardbibliothek für den Web-Server

## Setup

Siehe `INSTALL.md` (an Claude adressiert). Kurzfassung:
```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe web\server.py
```
Dann `http://127.0.0.1:8850` öffnen und die Dateien aus `fixtures/` auf die
Upload-Fläche ziehen.

## Tatsächlich unterstützte Eingänge (ehrliche Fähigkeits-Matrix)

Ergebnis des Feasibility-Gates, siehe `docs/FEASIBILITY_INPUTS.md`.

| Format | Was der Agent wirklich tut |
|---|---|
| PDF mit Textebene | Vollständige, deterministische Extraktion (`pypdf`), Checkliste, Bestandsabgleich, Abo-Radar |
| PNG / JPG | Wird angenommen und per Dateisignatur korrekt klassifiziert. Keine automatische Feldextraktion (OCR-Gate nicht bestanden, kein lokales OCR-Werkzeug ohne systemweite Installation) — landet immer in Review mit "Original angefordert" |
| EML (heruntergeladene E-Mail) | Wird lokal zerlegt (reine Standardbibliothek `email`): ein Kostenvorgang pro E-Mail, PDF-Anhänge laufen per Dateisignatur (nie nach dem deklarierten MIME-Typ) durch die normale PDF-Pipeline, eine Rechnung nur im Mailtext wird als eigener Beleg gelesen. Rechnung und Zahlungsbeleg desselben Vorgangs werden per Dokumentart unterschieden und nie als Dublette verwechselt; byte-identische Wiederhol-Uploads werden als Datei-Duplikat aussortiert. Die nächste Aktivität wird nur mit Evidenz eingeordnet: explizites Verlängerungsdatum → "Nächste Zahlung (bestätigt)", Leistungszeitraum → höchstens "Nächster Beleg erwartet", sonst "unbekannt". Kein Postfach-Zugriff (kein IMAP/Gmail), keine Links werden geöffnet |
| Beschädigte/unlesbare PDF | Wird erkannt und ehrlich als "fehlgeschlagen" gemeldet, nichts wird erfunden |

Welche Entscheidungen sind regelbasiert und welche heuristisch: Dateityp-
Erkennung ist regelbasiert (Magic-Bytes). Feldextraktion aus PDF ist
regelbasiert (Zeilenmuster für "Label: Wert"-Rechnungen, kein allgemeiner
Rechnungs-Parser für beliebige Layouts). Checkliste ist regelbasiert
(fail-closed). Dublettenerkennung ist regelbasiert (Referenz+Betrag+Datum).
Abo-Vergleich ist regelbasiert auf den vier extrahierten Dimensionen
(Anbieter, Tarif, Währung, Zeitraum) — Menge/Seats, Netto/Brutto und
Rabatt/Gutschrift werden in diesem Slice nicht separat geprüft, da keine
Fixture sie variiert (siehe `belegwaechter/radar.py`).

Upload-Dateinamen werden bereinigt: der Originalname bleibt nur als
Anzeigename erhalten, gespeichert wird ein aus Hash und einer harten
Zeichen-Whitelist gebildeter Name (siehe `belegwaechter/dateinamen.py`).
Dateiendung und Dateisignatur müssen übereinstimmen, sonst landet der Beleg
in Review statt automatisch übernommen zu werden. Transportfehler (Datei
oder Charge zu groß, zu viele Dateien, falscher Content-Type) lehnen die
gesamte Charge ab, bevor irgendetwas gespeichert wird; fachliche Fehler
(defektes PDF, fehlender Originalbeleg) betreffen nur die jeweilige Datei,
die restliche Charge läuft weiter. Ein unklarer Preisvergleich nimmt den
Beleg zwar ins vorbereitete Paket auf, zählt aber nicht automatisch als
bestätigte Vergleichsbasis für den nächsten Preisvergleich (siehe
`dokumentstatus`/`reviewstatus`/`review_aufgabe` in der Ergebnis-API).
CSV-Export: Textspalten werden gegen Formel-Injektion escaped, Beträge
werden ausschließlich aus dem intern kanonisierten Dezimalwert exportiert,
nie aus dem Rohtext des Dokuments.

## Warum das ein Agent ist, kein Parser

OptiTax erstellt pro Eingang einen echten Ausführungsplan
(`belegwaechter/planen.py`): abhängig von Quellenklasse und Dateisignatur
wählt er, welche Werkzeuge laufen (Extraktion, Checkliste, Bestandsabgleich,
Abo-Radar) und welche übersprungen werden, jeweils mit Begründung. Neue
Evidenz während der Verarbeitung — ein Lesefehler, eine erkannte Dublette,
eine unvollständige Checkliste — löst eine protokollierte Planrevision aus,
die zum Beispiel das Abo-Radar nachträglich deaktiviert. Der Executor fragt
ausschließlich diesen Plan ab; er verzweigt nirgends ein zweites Mal
eigenständig. Ob ein Preis "eindeutig teurer", "Vergleich erforderlich" oder
"erste Erfassung" ist, hängt von der bestätigten Vergleichsbasis im Bestand
ab, nicht von einer festen Regel pro Datei. Jeder Lauf erzeugt einen echten,
protokollierten Schritteverlauf (Wahrnehmen, Planen, Werkzeuge ausführen,
Bewerten, Handeln, Erklären, Erinnern — Details in `docs/MASTER_PLAN.md`
Abschnitt 30b). Für dieselbe Datei kann die Entscheidung unterschiedlich
ausfallen, je nachdem was vorher schon verarbeitet wurde.

## Bekannte Einschränkungen (Stand Arbeitsblock 4)

- Feldextraktion aus PDF und Mailtext ist musterbasiert für
  "Label: Wert"-Zeilen, kein allgemeiner Rechnungs-Parser für beliebige
  reale Rechnungs- oder Mail-Layouts.
- EML-Verarbeitung meint hochgeladene .eml-Dateien: kein Postfach-Zugriff
  (kein IMAP, keine Gmail-API), keine Links werden geöffnet, keine Inhalte
  nachgeladen. Nicht-PDF-Anhänge laufen ohne Extraktion in "Original
  anfordern".
- Die Dokumentart-Einordnung ist eine feste Schlüsselwort-Prioritätsliste
  (fail-closed "unbestimmt"), keine allgemeine Klassifikation.
- Die nächste Aktivität eines Vorgangs wird nur mit expliziter Evidenz
  gesetzt (Verlängerungsdatum oder Leistungszeitraum); es gibt bewusst
  keine Wahrscheinlichkeits- oder Rhythmusschätzung.
- Bild-OCR ist nicht aktiviert (siehe Feasibility-Gate); Bilder werden immer
  in Review geroutet.
- Radar-Zustand "Beleg fehlt" (erwarteter, aber nicht eingegangener
  wiederkehrender Beleg) ist im Datenmodell vorgesehen, wird aber von den
  aktuellen Demo-Fixtures nicht ausgelöst.
- Kein Mehrbenutzer-/Mandantenbetrieb, keine Postfach-Anbindung, kein
  Bank-Abgleich (bewusste Nicht-Ziele, siehe MASTER_PLAN Abschnitt 12).

## Was während der Challenge entstanden ist

Ehrliche Abgrenzung zur Vorarbeit:

- **Existierte vorher schon:** Optifyx OS, ein separates lokales
  Dashboard-Projekt (Leads, Creator, Content, Finance) in einem eigenen
  Repository. Es wird NICHT als Challenge-Ergebnis ausgegeben.
- **Wird aus Optifyx nur als Wissen genutzt:** Architektur-, UX-, Sicherheits-
  und Testmuster (Auditlog mit alt/neu-Zustand, Provenienz-Verweise,
  fail-closed Validierung, Review-Bucket, Test-Isolation mit Temp-DB).
  Bisher wurde kein Optifyx-Code übernommen; alles wird neu geschrieben.
- **Entsteht neu in der Challenge:** Der komplette OptiTax-Agent,
  ausschließlich in diesem Repository, nachvollziehbar über die
  Commit-Historie ab 23.07.2026.

## Learnings

Wird im Laufe der Challenge gefüllt.

---

**Demo-Video:** [folgt zur Abgabe — EIN Durchlauf, ungeschnitten]

*SKAILE Academy Building Challenge — Juli 2026*
