# Demo-Skript — OptiTax (ein Durchlauf, ungeschnitten, 2–3 Minuten)

Ziel: EIN ungeschnittener Bildschirm-Durchlauf mit ausschließlich
synthetischen Fixtures. Keine privaten Inhalte, kein Terminal im Bild,
keine technischen Exkurse, die die Geschichte unterbrechen.

## Vorbereitung vor der Aufnahme

1. Server starten (Terminal danach minimieren, nicht im Bild):
   `.venv\Scripts\python.exe web\server.py`
2. Browserfenster auf 1920×1080 bzw. Aufnahmegröße bringen, Zoom 100 %
   (bei kleiner Aufnahme 110 %), nur EIN Tab: `http://127.0.0.1:8850`.
3. In der Oberfläche **„Demo zurücksetzen"** klicken — die Aufnahme beginnt
   im leeren Zustand.
4. Diese synthetischen Dateien aus `fixtures/` griffbereit in einem eigenen
   kleinen Explorer-Fenster halten (nichts anderes im Ordner):
   - `cloudbasis_rechnung_und_zahlung.eml` (Normalfall, wird zweimal benutzt)
   - `mobiltel_zahlungsbestaetigung.eml` (Zahlungsnachweis ohne Rechnung)
5. Benachrichtigungen aus (Fokus-Assistent), Downloadordner leeren, keine
   persönlichen Tabs, Lesezeichen oder Konten sichtbar.
6. Einen kompletten Probedurchlauf machen, dann erneut zurücksetzen.
7. Ohne Stimme? Die kursiven Sprechertexte unten alternativ als kurze
   Bildschirm-Einblendungen (Untertitel) verwenden.

Notfallregel für alle Szenen: Lädt eine Aktion länger als zwei Sekunden,
ruhig warten und den Satz zu Ende sprechen — nicht erneut klicken, nicht
neu laden. Die Verarbeitung ist lokal und endet zuverlässig.

## Ablauf mit Zeitmarken

### 0:00–0:20 · Problem und leerer Zustand

- **Aktion:** Nichts klicken. Leere Kosten-Inbox, leere Belegliste, leere
  Abo-Übersicht zeigen.
- **Sichtbar:** OptiTax im leeren Ausgangszustand.
- *Sprechtext:* „Rechnungen, Zahlungsbelege und Abo-Mails kommen getrennt
  an — und vor dem Steuertermin fehlt dann genau das Original, das man
  braucht. Das hier ist OptiTax: eine E-Mail rein, der Rest passiert
  nachvollziehbar von selbst."

### 0:20–0:55 · Normalfall: E-Mail mit Rechnung und Zahlungsnachweis

- **Aktion:** `cloudbasis_rechnung_und_zahlung.eml` auf die Upload-Fläche
  ziehen. Danach im Vorgangskopf und den zwei Karten entlangfahren, auf
  einer Karte „Original-PDF" klicken (neuer Tab mit verständlichem
  Dateinamen), Tab schließen, „Original-E-Mail ansehen" kurz öffnen und
  schließen.
- **Sichtbar:** EIN E-Mail-Vorgang, getrennte Dokumentarten (Rechnung und
  Zahlungsbeleg), Produkt und Abrechnung auf der Karte, Zähler mit genau
  einer wirtschaftlichen Kostenposition im Export-Bereich, sichere
  E-Mail-Ansicht ohne Fremdinhalte.
- *Sprechtext:* „Eine E-Mail, zwei Dokumente: OptiTax erkennt Rechnung und
  Zahlungsnachweis, verbindet beide zu einem Vorgang — und zählt die Kosten
  genau einmal. Das Original bleibt unverändert und ist jederzeit einsehbar."

### 0:55–1:15 · Abo-Übersicht

- **Aktion:** Eine Karte in der Abo-Übersicht aufklappen.
- **Sichtbar:** Produkt, Tarif, „Abrechnung: monatlich", Kosten je
  Abrechnung, „Nächste Rechnung erwartet" (bzw. bestätigte Abbuchung nur
  bei belegtem Datum), aufgeklappt Rechnungsaussteller und Details.
- *Sprechtext:* „Die Abo-Übersicht zeigt nur echte wiederkehrende Kosten:
  Produkt, Tarif, Abrechnung — und was als Nächstes zu erwarten ist. Nur
  mit Evidenz, nie geraten."

### 1:15–1:35 · Technische Agentendetails (max. 10 Sekunden offen)

- **Aktion:** Auf einer Belegkarte „Details" klicken, im Modal „Technische
  Agentendetails" aufklappen, kurz scrollen, wieder schließen.
- **Sichtbar:** Ausführungsplan mit Werkzeugen (u. a.
  `kostenprofil_bestimmen`), eine Planrevision bzw. ein begründet
  übersprungenes Werkzeug, die begründete Entscheidung.
- *Sprechtext:* „Unter der Haube plant der Agent jeden Eingang, wählt seine
  Prüfwerkzeuge und revidiert den Plan, wenn neue Evidenz auftaucht — alles
  protokolliert."

### 1:35–1:55 · Ausnahmefall: Zahlungsnachweis ohne Rechnung

- **Aktion:** `mobiltel_zahlungsbestaetigung.eml` hochladen, die neue Karte
  zeigen.
- **Sichtbar:** Keine neue Kostenzeile (Zähler unverändert), offene Aufgabe
  „Rechnung oder Originalbeleg anfordern".
- *Sprechtext:* „Ein Zahlungsnachweis ohne Rechnung wird nicht einfach
  mitgezählt. OptiTax sagt ehrlich, was fehlt: die Rechnung anfordern."

### 1:55–2:15 · Zustandsabhängiger Duplikatfall

- **Aktion:** `cloudbasis_rechnung_und_zahlung.eml` ein zweites Mal
  hochladen. Die kompakte Duplikat-Zusammenfassung zeigen.
- **Sichtbar:** „2 Duplikate erkannt und aussortiert", Kostenposition und
  Abo-Übersicht unverändert.
- *Sprechtext:* „Dieselbe Datei noch einmal — und der Agent entscheidet
  anders als beim ersten Mal, weil er seinen Bestand kennt: Duplikat,
  aussortiert, nichts doppelt gezählt."

### 2:15–2:35 · Export

- **Aktion:** „Als CSV exportieren" klicken, die heruntergeladene Datei
  kurz öffnen (Spaltenkopf sichtbar).
- **Sichtbar:** Genau eine wirtschaftliche Kostenzeile; Produkt und
  Rechnungsaussteller als getrennte Spalten; keine Zahlungsbelege oder
  Duplikate.
- *Sprechtext:* „Am Ende steht ein prüfungsfreundlicher Export: nur echte
  Kosten, Produkt und Rechnungsaussteller sauber getrennt."

### 2:35–2:50 · Abschluss

- **Aktion:** Zurück zur Übersicht, nichts mehr klicken.
- **Sichtbar:** Verständlicher Endzustand (Belege, Abo-Übersicht, eine
  Kostenposition).
- *Sprechtext:* „OptiTax — ein lokaler, regelbasierter Agent, der
  nachvollziehbar arbeitet statt zu raten. Keine Steuerberatung, kein
  Versprechen auf Konformität — aber Ordnung, Originale und ehrliche
  nächste Schritte."

## Nach der Aufnahme

- Video ungeschnitten exportieren (2–3 Minuten) und extern erreichbar
  hochladen (z. B. Loom oder YouTube „nicht gelistet").
- Demo-Link-Platzhalter in `README.md` und `ABGABE.md` ersetzen.
- Demo in der Oberfläche zurücksetzen.
