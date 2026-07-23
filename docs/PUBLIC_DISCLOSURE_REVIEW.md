# Öffentliche Offenlegungsprüfung

Datum: 23.07.2026. Zweck: prüfen, was über die Commit-Historie dieses
öffentlichen Repositories bereits sichtbar geworden ist, und ehrlich
festhalten, wie damit umgegangen wird.

## Prüfmethode und Prüfumfang

Vollständige Historie geprüft: alle jemals hinzugefügten Dateien
(`git log --diff-filter=A --name-only`) sowie ein Musterabgleich über alle
Patches (`git log -p`) auf Schlüsselbegriffe für Zugangsdaten, Tokens,
Passwörter und Datenbank-/Umgebungsdateien.

## Befund

Ein früherer Commit dokumentierte eine Inventur eines separaten
Vorarbeit-Repositories und enthielt dabei interne technische Metadaten
dieses Vorarbeit-Repositories (unter anderem einen lokalen Entwicklungspfad,
einen Commit-Verweis, einen internen Port sowie interne Dateinamen mit
Zeilennummern). Diese Metadaten sind rein technischer Natur.

Es wurden **keine** Secrets, Datenbankinhalte, Mailinhalte, echten Belege
oder Zugangsdaten gefunden. Die einzigen Treffer des Schlüsselbegriff-Scans
sind Platzhaltertext in der Vorlagendatei `.env.example` (z.B. ein
Beispiel-Feldname ohne echten Wert) sowie Prosa-Erwähnungen von
Sicherheitsregeln in der Dokumentation.

## Umgang damit

Der aktuelle Dokumentenstand wurde bereinigt: die genannten internen
Metadaten sind aus den aktuell getrackten Dateien entfernt (siehe
`docs/decision-01-agent-selection.md`).

Die Git-Historie selbst wird **nicht** umgeschrieben. Kein `force push`,
kein `rebase`, kein `filter-repo`, kein `amend` bestehender Commits. Das ist
eine bewusste Entscheidung aus Transparenz- und Fairnessgründen: die
Commit-Historie soll den tatsächlichen Arbeitsverlauf ehrlich zeigen, auch
den früheren, ungenaueren Stand. Eine nachträgliche Bereinigung der
Historie würde diesen Nachweis zerstören, ohne einen echten Schutzgewinn zu
bringen, da es sich nicht um Secrets oder personenbezogene Daten handelt.

## Ergebnis

Kein Stopp erforderlich. Freigabe zur Fortsetzung der Arbeit unter der
Maßgabe, dass ab sofort keine internen Pfade, Ports oder Dateiverweise
externer Vorarbeit-Repositories mehr in getrackte Dateien dieses Repos
aufgenommen werden.
