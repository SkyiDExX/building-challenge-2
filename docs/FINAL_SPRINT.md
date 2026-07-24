# Finale Abgabecheckliste — OptiTax

Feature-Freeze ist aktiv. Ab hier nur noch Demo, Video und Abgabe — keine
Produkt-, Parser-, Agenten- oder Designänderungen. Frühere Planungsstände
liegen in der Commit-Historie und unter `docs/` (historisch).

## Vor der Videoaufnahme

- [ ] Vollständige manuelle Demo-QA nach `docs/DEMO_SCRIPT.md` (mindestens
      ein kompletter Probedurchlauf ohne Stocken)
- [ ] Testsuite grün: `.venv\Scripts\python.exe -m unittest tests.test_belegwaechter`
- [ ] „Demo zurücksetzen" funktioniert; Aufnahme startet im leeren Zustand
- [ ] Bildschirm sauber: keine Benachrichtigungen, keine privaten Tabs,
      Downloadordner leer

## Aufnahme

- [ ] Ein Durchlauf, ungeschnitten, 2–3 Minuten, nur synthetische Fixtures
- [ ] Demo endet in verständlichem Zustand (eine Kostenposition,
      Abo-Übersicht, erledigte Duplikat-Szene)
- [ ] Video extern erreichbar hochgeladen (Loom oder YouTube „nicht
      gelistet") und Link aus zweitem Gerät/Inkognito geprüft

## Nach der Aufnahme

- [ ] Demo-Link-Platzhalter in `README.md` und `ABGABE.md` durch den echten
      Link ersetzt — danach existiert kein Platzhalter mehr im Repository
- [ ] Keine weiteren Vorlagen-Platzhalter in eckigen Klammern übrig
- [ ] Öffentlichen Repository-Stand im Inkognito-Fenster geprüft: README,
      INSTALL und ABGABE rendern korrekt auf GitHub
- [ ] Letzte Sichtprüfung: keine privaten Daten, keine Secrets, keine
      absoluten privaten Pfade, keine Runtime-Dateien im Repo
- [ ] Demo lokal zurückgesetzt

## Abgabe

- [ ] Abgabe-Post aus `ABGABE.md` in der SKAILE Academy veröffentlicht
      (Kategorie „Building Challenge"), deutlich vor Sonntag 13:00 mit
      Zeitpuffer
- [ ] Kurzer Community-Text (optional, aus `ABGABE.md`) gepostet
- [ ] Keine Produktänderungen nach dem Demo-Durchlauf — bei einem echten
      P0-Blocker: erst beheben, dann Demo komplett neu aufnehmen
