# Belegwächter — SKAILE Building Challenge #2

> Stand Tag 1 (23.07.2026): Agenten-Discovery abgeschlossen. Aus fünf
> Kandidaten wurde der Belegwächter gewählt (Bewertung und Begründung in
> `docs/decision-01-agent-selection.md`). Implementierung startet nach
> Freigabe des MVP-Plans.

## Das Problem

Als Solo-Founder kommen Rechnungen und Belege verstreut an (Mail, PDF,
Screenshot) und landen unsortiert in Ordnern. Abos und deren Preiserhöhungen
bleiben unbemerkt, und vor Steuerterminen kostet das Aufräumen Stunden und
Nerven.

## Was der Agent macht

Belege in einen Eingangsordner legen, fertig. Der Agent liest jeden Beleg,
prüft ihn auf Vollständigkeit, gleicht ihn mit dem Bestand ab (Dublette?
bekanntes Abo? Preis gestiegen?) und entscheidet mit Begründung: in das
vorbereitete Belegpaket übernehmen oder zur Prüfung vorlegen. Heraus kommt ein geprüftes,
nachvollziehbares und buchhaltungsvorbereitendes Belegpaket, dazu ein
Abo-Radar, das wiederkehrende Kosten und Preiserhöhungen sichtbar macht.

Hinweis: Der Agent gibt keine Steuerberatung und verspricht keine rechtliche
Konformität. Er bereitet Belege strukturiert und nachvollziehbar vor.

## Stack

- [x] Claude Code (Agent / Skills)
- [ ] n8n
- [x] Sonstiges: Python (lokaler Verarbeitungskern), SQLite (lokale Ablage)

## Setup

Folgt mit dem ersten Vertical Slice. Geplant ist eine an Claude adressierte
INSTALL.md.

## Was während der Challenge entstanden ist

Ehrliche Abgrenzung zur Vorarbeit:

- **Existierte vorher schon:** Optifyx OS, ein separates lokales
  Dashboard-Projekt (Leads, Creator, Content, Finance) in einem eigenen
  Repository. Es wird NICHT als Challenge-Ergebnis ausgegeben.
- **Wird aus Optifyx nur als Wissen genutzt:** Architektur-, UX-, Sicherheits-
  und Testmuster (Auditlog mit alt/neu-Zustand, Provenienz-Verweise,
  fail-closed Validierung, Review-Bucket, Test-Isolation mit Temp-DB).
  Bisher wurde kein Optifyx-Code übernommen; alles wird neu geschrieben.
- **Entsteht neu in der Challenge:** Der komplette Belegwächter,
  ausschließlich in diesem Repository, nachvollziehbar über die
  Commit-Historie ab 23.07.2026.

## Learnings

Wird im Laufe der Challenge gefüllt.

---

**Demo-Video:** [folgt zur Abgabe — EIN Durchlauf, ungeschnitten]

*SKAILE Academy Building Challenge — Juli 2026*
