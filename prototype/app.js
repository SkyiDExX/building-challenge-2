/* Belegwächter UX-Prototyp
   Rein statische Simulation: keine echte Verarbeitung, keine Persistenz,
   kein Netzwerk. Alle Daten unten sind erfunden. */

"use strict";

/* ---------- Synthetische Demo-Daten ---------- */

const DEMO_BELEGE = [
  {
    id: "b1",
    datei: "cloudhost_rechnung_juni.pdf",
    typ: "PDF mit Textebene",
    quelle: "original", quelleLabel: "Original vorhanden",
    anbieter: "CloudHost Pro",
    betrag: "19,00 EUR", datum: "01.06.2026", zeitraum: "monatlich",
    referenz: "RE-2026-4711",
    status: "fertig", statusLabel: "Fertig",
    begruendung: "Übernommen: alle 6 Checklisten-Punkte erfüllt, Original vorhanden.",
    felder: [
      ["Anbieter", "CloudHost Pro", "aus PDF-Text"],
      ["Datum", "01.06.2026", "aus PDF-Text"],
      ["Betrag", "19,00 EUR", "aus PDF-Text"],
      ["Zeitraum", "monatlich", "aus PDF-Text"],
      ["Rechnungsnummer", "RE-2026-4711", "aus PDF-Text"]
    ],
    checkliste: [
      ["Anbieter erkannt", true], ["Datum erkannt", true],
      ["Betrag und Währung erkannt", true], ["Rechnungsnummer vorhanden", true],
      ["Zeitraum eindeutig", true], ["Dokument vollständig lesbar", true]
    ],
    vorschau: "CloudHost Pro\nRechnung RE-2026-4711\nDatum: 01.06.2026\nTarif: Pro, monatlich\nBetrag: 19,00 EUR",
    abgeschnitten: false, exportierbar: true
  },
  {
    id: "b2",
    datei: "cloudhost_rechnung_juli.pdf",
    typ: "PDF mit Textebene",
    quelle: "original", quelleLabel: "Original vorhanden",
    anbieter: "CloudHost Pro",
    betrag: "23,00 EUR", datum: "01.07.2026", zeitraum: "monatlich",
    referenz: "RE-2026-4890",
    status: "fertig", statusLabel: "Fertig",
    begruendung: "Übernommen: alle 6 Checklisten-Punkte erfüllt. Hinweis ans Abo-Radar: Betrag weicht vom Vormonat ab.",
    felder: [
      ["Anbieter", "CloudHost Pro", "aus PDF-Text"],
      ["Datum", "01.07.2026", "aus PDF-Text"],
      ["Betrag", "23,00 EUR", "aus PDF-Text"],
      ["Zeitraum", "monatlich", "aus PDF-Text"],
      ["Rechnungsnummer", "RE-2026-4890", "aus PDF-Text"]
    ],
    checkliste: [
      ["Anbieter erkannt", true], ["Datum erkannt", true],
      ["Betrag und Währung erkannt", true], ["Rechnungsnummer vorhanden", true],
      ["Zeitraum eindeutig", true], ["Dokument vollständig lesbar", true]
    ],
    vorschau: "CloudHost Pro\nRechnung RE-2026-4890\nDatum: 01.07.2026\nTarif: Pro, monatlich\nBetrag: 23,00 EUR",
    abgeschnitten: false, exportierbar: true
  },
  {
    id: "b3",
    datei: "schreibki_jahresrechnung.pdf",
    typ: "PDF mit Textebene",
    quelle: "original", quelleLabel: "Original vorhanden",
    anbieter: "SchreibKI Plus",
    betrag: "120,00 EUR", datum: "05.07.2026", zeitraum: "jährlich",
    referenz: "INV-88213",
    status: "fertig", statusLabel: "Fertig",
    begruendung: "Übernommen: alle 6 Checklisten-Punkte erfüllt. Hinweis ans Abo-Radar: Zeitraum wechselt von monatlich auf jährlich.",
    felder: [
      ["Anbieter", "SchreibKI Plus", "aus PDF-Text"],
      ["Datum", "05.07.2026", "aus PDF-Text"],
      ["Betrag", "120,00 EUR", "aus PDF-Text"],
      ["Zeitraum", "jährlich", "aus PDF-Text"],
      ["Rechnungsnummer", "INV-88213", "aus PDF-Text"]
    ],
    checkliste: [
      ["Anbieter erkannt", true], ["Datum erkannt", true],
      ["Betrag und Währung erkannt", true], ["Rechnungsnummer vorhanden", true],
      ["Zeitraum eindeutig", true], ["Dokument vollständig lesbar", true]
    ],
    vorschau: "SchreibKI Plus\nJahresrechnung INV-88213\nDatum: 05.07.2026\nZeitraum: 12 Monate\nBetrag: 120,00 EUR",
    abgeschnitten: false, exportierbar: true
  },
  {
    id: "b4",
    datei: "cloudhost_rechnung_juli_kopie.pdf",
    typ: "PDF mit Textebene",
    quelle: "original", quelleLabel: "Original vorhanden",
    anbieter: "CloudHost Pro",
    betrag: "23,00 EUR", datum: "01.07.2026", zeitraum: "monatlich",
    referenz: "RE-2026-4890",
    status: "dublette", statusLabel: "Doppelt, aussortiert",
    begruendung: "Doppelt, aussortiert: gleiche Rechnungsnummer RE-2026-4890 und gleicher Betrag wie der bereits übernommene Beleg vom 01.07. Nicht doppelt gezählt.",
    felder: [
      ["Anbieter", "CloudHost Pro", "aus PDF-Text"],
      ["Datum", "01.07.2026", "aus PDF-Text"],
      ["Betrag", "23,00 EUR", "aus PDF-Text"],
      ["Zeitraum", "monatlich", "aus PDF-Text"],
      ["Rechnungsnummer", "RE-2026-4890", "aus PDF-Text"]
    ],
    checkliste: [
      ["Anbieter erkannt", true], ["Datum erkannt", true],
      ["Betrag und Währung erkannt", true], ["Rechnungsnummer vorhanden", true],
      ["Zeitraum eindeutig", true], ["Dokument vollständig lesbar", true]
    ],
    vorschau: "CloudHost Pro\nRechnung RE-2026-4890\nDatum: 01.07.2026\nTarif: Pro, monatlich\nBetrag: 23,00 EUR",
    abgeschnitten: false, exportierbar: false
  },
  {
    id: "b5",
    datei: "mobilfunk_app_screenshot.png",
    typ: "Screenshot (PNG)",
    quelle: "erfassung", quelleLabel: "Erfassungsnachweis",
    anbieter: "MobilTel",
    betrag: "24,99 EUR", datum: "18.07.2026", zeitraum: "unklar",
    referenz: null,
    status: "review", statusLabel: "Bitte ansehen",
    zusatzBadge: "Original angefordert",
    begruendung: "Bitte ansehen: Betrag und Datum erkannt, aber keine Rechnungsnummer erkennbar (Screenshot, unten abgeschnitten). Ein Screenshot ist nicht der Originalbeleg. Original angefordert.",
    felder: [
      ["Anbieter", "MobilTel", "aus Bild erfasst"],
      ["Datum", "18.07.2026", "aus Bild erfasst"],
      ["Betrag", "24,99 EUR", "aus Bild erfasst"],
      ["Zeitraum", null, "fehlt"],
      ["Rechnungsnummer", null, "fehlt"]
    ],
    checkliste: [
      ["Anbieter erkannt", true], ["Datum erkannt", true],
      ["Betrag und Währung erkannt", true], ["Rechnungsnummer vorhanden", false],
      ["Zeitraum eindeutig", false], ["Dokument vollständig lesbar", false]
    ],
    vorschau: "MobilTel App\nIhre Abbuchung: 24,99 EUR\n18.07.2026\nVertrag: Smart L\n[unterer Bildrand abgeschnitten]",
    abgeschnitten: true, exportierbar: false
  }
];

const DEMO_RADAR = [
  {
    name: "CloudHost Pro", rhythmus: "monatlich", betrag: "23,00 EUR",
    einschaetzung: "teurer", label: "Teurer geworden",
    begruendung: "19,00 → 23,00 EUR seit Juli, gleicher Tarif, gleiche Währung, gleicher Zeitraum. Vergleich eindeutig."
  },
  {
    name: "SchreibKI Plus", rhythmus: "wechselt", betrag: "120,00 EUR/Jahr",
    einschaetzung: "unklar", label: "Vergleich erforderlich",
    begruendung: "Preisänderung möglich: Zeitraum wechselt von monatlich (12,00 EUR, aus simuliertem Vormonats-Bestand) auf jährlich. Beträge nicht direkt vergleichbar."
  },
  {
    name: "NotizCloud", rhythmus: "monatlich", betrag: "zuletzt 6,00 EUR",
    einschaetzung: "fehlt", label: "Beleg fehlt",
    begruendung: "Im Juli kein NotizCloud-Beleg eingegangen, zuletzt 6,00 EUR im Juni (simulierter Vormonats-Bestand)."
  },
  {
    name: "Domainly", rhythmus: "monatlich", betrag: "9,00 EUR",
    einschaetzung: "stabil", label: "Stabil",
    begruendung: "9,00 EUR unverändert seit drei Monaten (simulierter Vormonats-Bestand)."
  }
];

const BADGE_KLASSEN = { fertig: "badge-fertig", review: "badge-review", dublette: "badge-dublette" };
const RADAR_BADGES = { teurer: "badge-review", unklar: "badge-review", fehlt: "badge-dublette", stabil: "badge-fertig" };
const SCHRITTE = ["Erfassen", "Lesen", "Prüfen", "Abgleichen", "Entscheiden"];
const SCHRITT_DAUER_MS = 260;

/* ---------- Zustand ---------- */

let laufAktiv = false;
let verarbeitet = false;
let auditEintraege = [];
let demoUhr = null; // simulierte Demo-Zeit, keine echte Systemzeit nötig

const $ = (id) => document.getElementById(id);

/* ---------- Audit ---------- */

function auditZeit() {
  // Simulierte, fortlaufende Demo-Uhr (bewusst nicht die echte Zeit)
  if (demoUhr === null) demoUhr = 9 * 3600 + 14 * 60; // 09:14:00
  demoUhr += 2 + (auditEintraege.length % 3);
  const h = String(Math.floor(demoUhr / 3600)).padStart(2, "0");
  const m = String(Math.floor((demoUhr % 3600) / 60)).padStart(2, "0");
  const s = String(demoUhr % 60).padStart(2, "0");
  return `${h}:${m}:${s}`;
}

function audit(text) {
  auditEintraege.push({ zeit: auditZeit(), text });
  const li = document.createElement("li");
  const zeit = document.createElement("span");
  zeit.className = "audit-zeit";
  zeit.textContent = auditEintraege[auditEintraege.length - 1].zeit;
  li.appendChild(zeit);
  li.appendChild(document.createTextNode(text));
  $("audit-liste").appendChild(li);
}

/* ---------- Rendering ---------- */

function badge(text, klasse) {
  const span = document.createElement("span");
  span.className = `badge ${klasse}`;
  span.textContent = text;
  return span;
}

function belegRendern(b) {
  const li = document.createElement("li");
  if (b.status === "review") li.className = "review-zuerst";
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "beleg";
  btn.setAttribute("aria-label", `${b.anbieter}, ${b.betrag}, Status: ${b.statusLabel}. Details öffnen.`);

  const z1 = document.createElement("div");
  z1.className = "beleg-zeile1";
  const name = document.createElement("span");
  name.className = "beleg-anbieter";
  name.textContent = b.anbieter;
  const meta = document.createElement("span");
  meta.className = "beleg-meta";
  meta.textContent = `${b.betrag} · ${b.datum} · ${b.datei}`;
  z1.append(name, meta, badge(b.statusLabel, BADGE_KLASSEN[b.status]));
  if (b.zusatzBadge) z1.appendChild(badge(b.zusatzBadge, "badge-original"));
  z1.appendChild(badge(b.quelleLabel, "badge-quelle"));

  const beg = document.createElement("div");
  beg.className = "beleg-begruendung";
  beg.textContent = b.begruendung;

  btn.append(z1, beg);
  btn.addEventListener("click", () => detailOeffnen(b));
  li.appendChild(btn);
  $("beleg-liste").appendChild(li);
}

function radarRendern() {
  const liste = $("radar-liste");
  DEMO_RADAR.forEach((r) => {
    const li = document.createElement("li");
    li.className = "radar-karte";
    const z1 = document.createElement("div");
    z1.className = "radar-zeile1";
    const name = document.createElement("span");
    name.className = "radar-name";
    name.textContent = `${r.name} (${r.rhythmus})`;
    const rechts = document.createElement("span");
    rechts.className = "radar-betrag";
    rechts.textContent = r.betrag + " ";
    rechts.appendChild(badge(r.label, RADAR_BADGES[r.einschaetzung]));
    z1.append(name, rechts);
    const beg = document.createElement("div");
    beg.className = "radar-begruendung";
    beg.textContent = r.begruendung;
    li.append(z1, beg);
    liste.appendChild(li);
  });
  $("radar-leer").hidden = true;
}

/* ---------- Detailansicht ---------- */

function detailOeffnen(b) {
  $("detail-titel").textContent = `${b.anbieter} — ${b.statusLabel}`;

  const q = $("detail-quelle-inhalt");
  q.textContent = "";
  const karte = document.createElement("div");
  karte.className = "quelle-karte";
  [
    ["Datei", b.datei], ["Typ", b.typ],
    ["Eingangsweg", "Web-Upload (simuliert)"], ["Eingang", "23.07.2026 (Demo)"],
    ["Quellenstatus", b.quelleLabel]
  ].forEach(([k, v]) => {
    const zeile = document.createElement("div");
    const key = document.createElement("strong");
    key.textContent = k + ": ";
    zeile.append(key, document.createTextNode(v));
    karte.appendChild(zeile);
  });
  const vorschau = document.createElement("div");
  vorschau.className = "quelle-vorschau" + (b.abgeschnitten ? " vorschau-abgeschnitten" : "");
  vorschau.setAttribute("aria-label", "Vereinfachte Vorschau des Belegs (simuliert)");
  vorschau.textContent = b.vorschau;
  karte.appendChild(vorschau);
  q.appendChild(karte);

  const dl = $("detail-felder-liste");
  dl.textContent = "";
  b.felder.forEach(([feld, wert, herkunft]) => {
    const dt = document.createElement("dt");
    dt.textContent = feld;
    const dd = document.createElement("dd");
    if (wert === null) {
      const fehlt = document.createElement("span");
      fehlt.className = "feld-fehlt";
      fehlt.textContent = "fehlt";
      dd.appendChild(fehlt);
    } else {
      dd.textContent = wert + " ";
      const h = document.createElement("span");
      h.className = "feld-herkunft";
      h.textContent = `(${herkunft})`;
      dd.appendChild(h);
    }
    dl.append(dt, dd);
  });

  const cl = $("detail-checkliste");
  cl.textContent = "";
  b.checkliste.forEach(([punkt, ok]) => {
    const li = document.createElement("li");
    if (!ok) li.className = "check-fehlt";
    li.textContent = punkt;
    cl.appendChild(li);
  });

  $("detail-entscheidung").textContent = b.begruendung;
  $("detail-overlay").hidden = false;
  $("detail-schliessen").focus();
}

function detailSchliessen() {
  $("detail-overlay").hidden = true;
}

/* ---------- Simulierter Agentenlauf ---------- */

function laufStarten() {
  if (laufAktiv || verarbeitet) return;
  laufAktiv = true;
  $("upload-zone").disabled = true;
  $("schritte").hidden = false;
  $("leerzustand").hidden = true;
  audit("Simulierter Lauf gestartet: 5 Demo-Belege im Eingang.");

  const schrittEl = Array.from(document.querySelectorAll(".schritte-liste li"));
  let belegIdx = 0;

  function naechsterBeleg() {
    if (belegIdx >= DEMO_BELEGE.length) {
      laufAbschliessen();
      return;
    }
    const b = DEMO_BELEGE[belegIdx];
    $("schritte-beleg").textContent = `Beleg ${belegIdx + 1} von ${DEMO_BELEGE.length}: ${b.datei}`;
    let schritt = 0;

    function naechsterSchritt() {
      schrittEl.forEach((el, i) => {
        el.classList.toggle("aktiv", i === schritt);
        el.classList.toggle("fertig", i < schritt);
      });
      if (schritt < SCHRITTE.length) {
        schritt += 1;
        window.setTimeout(naechsterSchritt, SCHRITT_DAUER_MS);
      } else {
        schrittEl.forEach((el) => { el.classList.remove("aktiv"); el.classList.add("fertig"); });
        belegRendern(b);
        audit(`${b.datei}: ${b.begruendung}`);
        belegIdx += 1;
        window.setTimeout(naechsterBeleg, SCHRITT_DAUER_MS);
      }
    }
    naechsterSchritt();
  }

  function laufAbschliessen() {
    laufAktiv = false;
    verarbeitet = true;
    $("schritte-beleg").textContent = "Alle Demo-Belege verarbeitet.";
    const fertig = DEMO_BELEGE.filter((b) => b.status === "fertig").length;
    const dublette = DEMO_BELEGE.filter((b) => b.status === "dublette").length;
    const review = DEMO_BELEGE.filter((b) => b.status === "review").length;
    const z = $("zaehler");
    z.textContent = `${DEMO_BELEGE.length} Belege verarbeitet: ${fertig} fertig, ${dublette} doppelt, ${review} bitte ansehen.`;
    z.hidden = false;
    radarRendern();
    audit("Abo-Radar aktualisiert: 1x teurer geworden, 1x Vergleich erforderlich, 1x Beleg fehlt, 1x stabil.");
    $("export-btn").disabled = false;
  }

  const reduziert = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduziert) {
    DEMO_BELEGE.forEach((b) => { belegRendern(b); audit(`${b.datei}: ${b.begruendung}`); });
    belegIdx = DEMO_BELEGE.length;
    laufAbschliessen();
  } else {
    naechsterBeleg();
  }
}

/* ---------- Export ---------- */

function csvExport() {
  const zeilen = [["Anbieter", "Datum", "Betrag", "Zeitraum", "Rechnungsnummer", "Quellenstatus", "Quelldatei"]];
  DEMO_BELEGE.filter((b) => b.exportierbar).forEach((b) => {
    zeilen.push([b.anbieter, b.datum, b.betrag, b.zeitraum, b.referenz || "", b.quelleLabel, b.datei]);
  });
  const csv = zeilen.map((z) => z.map((f) => `"${String(f).replace(/"/g, '""')}"`).join(";")).join("\r\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "belegwaechter_demo_export.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  const n = zeilen.length - 1;
  $("export-status").textContent = `belegwaechter_demo_export.csv erstellt, ${n} Belege (simulierte Daten).`;
  audit(`CSV-Export erstellt: ${n} übernommene Belege.`);
}

/* ---------- Reset ---------- */

function resetAusfuehren() {
  laufAktiv = false;
  verarbeitet = false;
  auditEintraege = [];
  demoUhr = null;
  $("beleg-liste").textContent = "";
  $("radar-liste").textContent = "";
  $("audit-liste").textContent = "";
  $("leerzustand").hidden = false;
  $("radar-leer").hidden = false;
  $("zaehler").hidden = true;
  $("schritte").hidden = true;
  $("schritte-beleg").textContent = "";
  document.querySelectorAll(".schritte-liste li").forEach((el) => el.classList.remove("aktiv", "fertig"));
  $("export-btn").disabled = true;
  $("export-status").textContent = "";
  $("upload-zone").disabled = false;
  $("reset-overlay").hidden = true;
  $("audit-details").open = false;
  $("upload-zone").focus();
}

/* ---------- Ereignisse ---------- */

$("upload-zone").addEventListener("click", laufStarten);

["dragover", "dragenter"].forEach((ev) =>
  $("upload-zone").addEventListener(ev, (e) => { e.preventDefault(); $("upload-zone").classList.add("drag"); })
);
["dragleave", "drop"].forEach((ev) =>
  $("upload-zone").addEventListener(ev, (e) => {
    e.preventDefault();
    $("upload-zone").classList.remove("drag");
    if (ev === "drop") {
      // Ehrlichkeit: echte Dateien werden im Prototyp nicht gelesen.
      $("upload-hinweis").textContent = "Prototyp: Deine Datei wurde NICHT gelesen. Der simulierte Lauf nutzt 5 erfundene Demo-Belege.";
      laufStarten();
    }
  })
);

$("detail-schliessen").addEventListener("click", detailSchliessen);
$("detail-overlay").addEventListener("click", (e) => { if (e.target === $("detail-overlay")) detailSchliessen(); });

$("reset-btn").addEventListener("click", () => { $("reset-overlay").hidden = false; $("reset-nein").focus(); });
$("reset-ja").addEventListener("click", resetAusfuehren);
$("reset-nein").addEventListener("click", () => { $("reset-overlay").hidden = true; });
$("reset-overlay").addEventListener("click", (e) => { if (e.target === $("reset-overlay")) $("reset-overlay").hidden = true; });

$("export-btn").addEventListener("click", csvExport);

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if (!$("detail-overlay").hidden) detailSchliessen();
    if (!$("reset-overlay").hidden) $("reset-overlay").hidden = true;
  }
});
