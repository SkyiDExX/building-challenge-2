/* Belegwaechter — echte Oberflaeche, spricht mit der lokalen JSON-API unter
   /api/*. Keine simulierten Daten, keine externen Aufrufe. */

"use strict";

const $ = (id) => document.getElementById(id);

const AUSGANG_LABEL = {
  uebernommen: ["Fertig", "badge-fertig"],
  review: ["Bitte ansehen", "badge-review"],
  dublette: ["Doppelt, aussortiert", "badge-dublette"],
  original_anfordern: ["Original angefordert", "badge-original"],
  fehlgeschlagen: ["Fehlgeschlagen", "badge-review"],
};

const QUELLE_LABEL = {
  original_vorhanden: "Original vorhanden",
  erfassungsnachweis: "Erfassungsnachweis",
  hinweis: "Hinweis, kein Beleg",
};

const RADAR_LABEL = {
  neu: ["Neu erfasst", "badge-fertig"],
  stabil: ["Stabil", "badge-fertig"],
  veraendert_eindeutig: ["Preis verändert", "badge-review"],
  vergleich_erforderlich: ["Vergleich erforderlich", "badge-review"],
  beleg_fehlt: ["Beleg fehlt", "badge-dublette"],
};

const DOKUMENTART_LABEL = {
  rechnung: "Rechnung",
  zahlungsbeleg: "Zahlungsbeleg",
  abo_bestaetigung: "Abo-Bestätigung",
  sonstiger_kostennachweis: "Kostennachweis",
};

let letzteBelege = [];
let letzteVorgaenge = [];

function aktivitaetBadge(v) {
  if (v.naechste_aktivitaet_status === "bestaetigt" && v.naechste_aktivitaet_art === "zahlung") {
    return badge(`Nächste Zahlung: ${v.naechste_aktivitaet_datum} (bestätigt)`, "badge-fertig");
  }
  if (v.naechste_aktivitaet_status === "erwartet" && v.naechste_aktivitaet_art === "beleg") {
    const bis = v.naechste_aktivitaet_datum ? ` bis ${v.naechste_aktivitaet_datum}` : "";
    return badge(`Nächster Beleg erwartet${bis}`, "badge-quelle");
  }
  return badge("Nächste Aktivität unbekannt", "badge-quelle");
}

function badge(text, klasse) {
  const span = document.createElement("span");
  span.className = `badge ${klasse}`;
  span.textContent = text;
  return span;
}

function fehlerZeigen(text) {
  const el = $("fehler-hinweis");
  el.textContent = text;
  el.hidden = false;
}

function fehlerVerstecken() {
  $("fehler-hinweis").hidden = true;
}

/* ---------- Laden und Rendern ---------- */

async function ladeAlles() {
  const [ergebnis, radar, audit] = await Promise.all([
    fetch("/api/ergebnis").then((r) => r.json()),
    fetch("/api/radar").then((r) => r.json()),
    fetch("/api/audit").then((r) => r.json()),
  ]);
  letzteBelege = ergebnis.belege;
  letzteVorgaenge = ergebnis.vorgaenge || [];
  renderBelege(letzteBelege);
  renderRadar(radar.radar);
  renderAudit(audit.audit);
}

function pdfOriginalLink(b, klassen) {
  const link = document.createElement("a");
  link.className = klassen;
  link.href = `/api/belege/${encodeURIComponent(b.id)}/original`;
  link.target = "_blank";
  link.rel = "noopener";
  link.textContent = "Original-PDF";
  link.setAttribute(
    "aria-label",
    `Original-PDF von ${b.felder.anbieter.wert || b.dateiname} in neuem Tab öffnen`
  );
  return link;
}

function belegKarte(b) {
  // Kompakte Karte: Titel, Betrag/Datum, Dokumentart, Status, offene
  // Aufgabe und Aktionen. Der vollstaendige Entscheidungstext, Dateiname
  // und Technikdetails stehen in der Detailansicht.
  const karte = document.createElement("div");
  karte.className = "beleg";
  const titel = b.felder.anbieter.wert || b.dateiname;
  const [label, klasse] = AUSGANG_LABEL[b.ausgang] || [b.ausgang, "badge-quelle"];

  const z1 = document.createElement("div");
  z1.className = "beleg-zeile1";
  const name = document.createElement("span");
  name.className = "beleg-anbieter";
  name.textContent = titel;
  z1.appendChild(name);
  const metaTeile = [];
  if (b.felder.betrag.wert) {
    metaTeile.push(`${b.felder.betrag.wert} ${b.felder.waehrung.wert || ""}`.trim());
  }
  if (b.felder.datum.wert) metaTeile.push(b.felder.datum.wert);
  if (metaTeile.length > 0) {
    const meta = document.createElement("span");
    meta.className = "beleg-meta";
    meta.textContent = metaTeile.join(" · ");
    z1.appendChild(meta);
  }
  z1.appendChild(badge(label, klasse));
  if (b.dokumentart && DOKUMENTART_LABEL[b.dokumentart]) {
    z1.appendChild(badge(DOKUMENTART_LABEL[b.dokumentart], "badge-quelle"));
  }
  karte.appendChild(z1);

  if (b.reviewstatus === "offen" && b.review_aufgabe) {
    const aufgabe = document.createElement("div");
    aufgabe.className = "beleg-aufgabe";
    aufgabe.textContent = `Nächster Schritt: ${b.review_aufgabe}`;
    karte.appendChild(aufgabe);
  }

  const aktionen = document.createElement("div");
  aktionen.className = "beleg-aktionen";
  const detailsBtn = document.createElement("button");
  detailsBtn.type = "button";
  detailsBtn.className = "btn btn-sekundaer btn-klein";
  detailsBtn.textContent = "Details";
  detailsBtn.setAttribute("aria-label", `Details zu ${titel} öffnen (Status: ${label})`);
  detailsBtn.addEventListener("click", () => detailOeffnen(b));
  aktionen.appendChild(detailsBtn);
  if (b.dateityp === "PDF") {
    aktionen.appendChild(pdfOriginalLink(b, "btn btn-pdf btn-klein"));
  }
  karte.appendChild(aktionen);
  return karte;
}

function renderBelege(belege) {
  const liste = $("beleg-liste");
  liste.textContent = "";
  $("leerzustand").hidden = belege.length > 0;
  $("zaehler").hidden = belege.length === 0;

  if (belege.length > 0) {
    const zaehlung = {};
    belege.forEach((b) => { zaehlung[b.ausgang] = (zaehlung[b.ausgang] || 0) + 1; });
    const teile = Object.entries(zaehlung).map(
      ([ausgang, n]) => `${n} ${(AUSGANG_LABEL[ausgang] || [ausgang])[0].toLowerCase()}`
    );
    $("zaehler").textContent = `${belege.length} Belege verarbeitet: ${teile.join(", ")}.`;
  }

  const vorgangJeId = {};
  letzteVorgaenge.forEach((v) => { vorgangJeId[v.id] = v; });
  const gezeigteVorgaenge = new Set();

  // Aussortierte Duplikate erscheinen nicht als eigene grosse Karte,
  // sondern kompakt zusammengefasst am Listenende. Datenbank, Audit und
  // Detailansicht behalten den vollstaendigen Nachweis.
  const dubletten = belege.filter((b) => b.ausgang === "dublette");
  const sichtbare = belege.filter((b) => b.ausgang !== "dublette");

  sichtbare.forEach((b) => {
    // Gruppenkopf: alle Dokumente eines E-Mail-Vorgangs stehen zusammen,
    // mit Betreff, Absender und der naechsten Aktivitaet (nur mit Evidenz).
    if (b.vorgang_id && vorgangJeId[b.vorgang_id] && !gezeigteVorgaenge.has(b.vorgang_id)) {
      gezeigteVorgaenge.add(b.vorgang_id);
      const v = vorgangJeId[b.vorgang_id];
      const kopf = document.createElement("li");
      kopf.className = "vorgang-kopf";
      const zeile = document.createElement("div");
      zeile.className = "vorgang-zeile";
      const titel = document.createElement("span");
      titel.className = "vorgang-titel";
      titel.textContent = `E-Mail-Vorgang: ${v.betreff || v.eml_dateiname}`;
      const absender = document.createElement("span");
      absender.className = "vorgang-absender";
      absender.textContent = v.absender || "";
      zeile.append(titel, absender, aktivitaetBadge(v));
      kopf.appendChild(zeile);
      if (v.naechste_aktivitaet_begruendung) {
        const beg = document.createElement("div");
        beg.className = "vorgang-begruendung";
        beg.textContent = v.naechste_aktivitaet_begruendung;
        kopf.appendChild(beg);
      }
      liste.appendChild(kopf);
    }

    const li = document.createElement("li");
    if (b.vorgang_id) li.classList.add("vorgang-mitglied");
    if (b.ausgang === "review" || b.ausgang === "original_anfordern" || b.ausgang === "fehlgeschlagen") {
      li.classList.add("review-zuerst");
    }
    li.appendChild(belegKarte(b));
    liste.appendChild(li);
  });

  if (dubletten.length > 0) {
    const li = document.createElement("li");
    li.className = "dubletten-kompakt";
    const kopf = document.createElement("div");
    kopf.className = "dubletten-titel";
    kopf.textContent =
      dubletten.length === 1
        ? "1 Duplikat erkannt und aussortiert"
        : `${dubletten.length} Duplikate erkannt und aussortiert`;
    li.appendChild(kopf);
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = "Aussortierte Duplikate anzeigen";
    details.appendChild(summary);
    const ul = document.createElement("ul");
    dubletten.forEach((b) => {
      const zeile = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "dublette-link";
      btn.textContent = b.dateiname;
      btn.setAttribute("aria-label", `Details zum aussortierten Duplikat ${b.dateiname} öffnen`);
      btn.addEventListener("click", () => detailOeffnen(b));
      zeile.appendChild(btn);
      zeile.appendChild(document.createTextNode(` — ${b.begruendung}`));
      ul.appendChild(zeile);
    });
    details.appendChild(ul);
    li.appendChild(details);
    liste.appendChild(li);
  }
}

function renderRadar(radar) {
  const liste = $("radar-liste");
  liste.textContent = "";
  $("radar-leer").hidden = radar.length > 0;
  radar.forEach((r) => {
    const li = document.createElement("li");
    li.className = "radar-karte";
    const z1 = document.createElement("div");
    z1.className = "radar-zeile1";
    const name = document.createElement("span");
    name.className = "radar-name";
    name.textContent = `${r.anbieter} (${r.zeitraum || "unbekannt"})`;
    const rechts = document.createElement("span");
    rechts.className = "radar-betrag";
    rechts.textContent = r.betrag ? `${r.betrag} ${r.waehrung || ""} ` : "";
    // r.einschaetzung ist null, wenn der Abovergleich fuer diesen Beleg
    // bewusst deaktiviert war (z.B. juengster Beleg des Anbieters ist ein
    // Zahlungsbeleg, kein Rechnungsvergleich). Dann keinen Badge erfinden.
    const eintrag = RADAR_LABEL[r.einschaetzung];
    if (eintrag) {
      const [label, klasse] = eintrag;
      rechts.appendChild(badge(label, klasse));
    }
    z1.append(name, rechts);
    li.appendChild(z1);
    if (r.begruendung) {
      const beg = document.createElement("div");
      beg.className = "radar-begruendung";
      beg.textContent = r.begruendung;
      li.appendChild(beg);
    }
    liste.appendChild(li);
  });
}

function renderAudit(audit) {
  const liste = $("audit-liste");
  liste.textContent = "";
  audit.forEach((a) => {
    const li = document.createElement("li");
    const zeit = document.createElement("span");
    zeit.className = "audit-zeit";
    zeit.textContent = (a.zeit || "").replace("T", " ").slice(0, 19);
    li.appendChild(zeit);
    li.appendChild(document.createTextNode(`${a.aktion}: ${a.objekt}`));
    liste.appendChild(li);
  });
}

/* ---------- Detailansicht ---------- */

function detailOeffnen(b) {
  const anbieter = b.felder.anbieter.wert || b.dateiname;
  const [label] = AUSGANG_LABEL[b.ausgang] || [b.ausgang];
  $("detail-titel").textContent = `${anbieter} — ${label}`;

  const q = $("detail-quelle-inhalt");
  q.textContent = "";
  const karte = document.createElement("div");
  karte.className = "quelle-karte";
  [
    ["Datei", b.dateiname],
    ["Typ", b.dateityp],
    ["Datei-Hash", b.dateihash.slice(0, 16) + "…"],
    ["Quellenstatus", QUELLE_LABEL[b.quellenstatus] || b.quellenstatus],
    ["Erfasst am", (b.erfasst_am || "").replace("T", " ")],
  ].forEach(([k, v]) => {
    const zeile = document.createElement("div");
    const key = document.createElement("strong");
    key.textContent = k + ": ";
    zeile.append(key, document.createTextNode(v));
    karte.appendChild(zeile);
  });
  q.appendChild(karte);

  const dl = $("detail-felder-liste");
  dl.textContent = "";
  Object.entries(b.felder).forEach(([feld, info]) => {
    const dt = document.createElement("dt");
    dt.textContent = feld;
    const dd = document.createElement("dd");
    if (info.wert === null) {
      const fehlt = document.createElement("span");
      fehlt.className = "feld-fehlt";
      fehlt.textContent = "fehlt";
      dd.appendChild(fehlt);
    } else {
      dd.textContent = info.wert + " ";
      const h = document.createElement("span");
      h.className = "feld-herkunft";
      h.textContent = `(${info.herkunft})`;
      dd.appendChild(h);
    }
    dl.append(dt, dd);
  });

  const cl = $("detail-checkliste");
  cl.textContent = "";
  b.checkliste.forEach((punkt) => {
    const li = document.createElement("li");
    if (!punkt.erfuellt) li.className = "check-fehlt";
    li.textContent = punkt.name;
    cl.appendChild(li);
  });
  if (b.checkliste.length === 0) {
    const li = document.createElement("li");
    li.textContent = "Keine Checkliste angewendet (kein lesbarer Originalbeleg).";
    cl.appendChild(li);
  }

  $("detail-entscheidung").textContent = b.begruendung;

  const reviewHinweis = $("detail-review-hinweis");
  if (b.reviewstatus === "offen") {
    reviewHinweis.textContent = `Nächste Aktion: ${b.review_aufgabe || "Beleg prüfen"}.`;
    reviewHinweis.hidden = false;
  } else {
    reviewHinweis.hidden = true;
  }

  const pdfBtn = $("detail-pdf-btn");
  if (b.dateityp === "PDF") {
    pdfBtn.href = `/api/belege/${encodeURIComponent(b.id)}/original`;
    pdfBtn.hidden = false;
  } else {
    pdfBtn.removeAttribute("href");
    pdfBtn.hidden = true;
  }

  const planContainer = $("detail-plan");
  planContainer.textContent = "";
  (b.plaene || []).forEach((plan, index) => {
    const box = document.createElement("div");
    box.className = "plan-karte";
    if (index > 0) {
      const revision = document.createElement("p");
      revision.className = "plan-revision";
      revision.textContent = `Plan aktualisiert: ${plan.revisionsgrund || ""}`;
      box.appendChild(revision);
    }
    const ziel = document.createElement("p");
    ziel.textContent = `Ziel: ${plan.ziel}`;
    box.appendChild(ziel);
    const quelle = document.createElement("p");
    quelle.textContent = `Quellenklasse: ${plan.quellenklasse}`;
    box.appendChild(quelle);

    const werkzeugeListe = document.createElement("ul");
    (plan.werkzeuge || []).forEach((w) => {
      const li = document.createElement("li");
      li.textContent = `${w.ausfuehren ? "Aktiv" : "Übersprungen"} — ${w.name} (${w.werkzeug}): ${w.begruendung}`;
      werkzeugeListe.appendChild(li);
    });
    box.appendChild(werkzeugeListe);

    if ((plan.stopbedingungen || []).length > 0) {
      const stop = document.createElement("p");
      stop.textContent = `Stop-/Reviewbedingungen: ${plan.stopbedingungen.join(", ")}`;
      box.appendChild(stop);
    }
    planContainer.appendChild(box);
  });

  const schritteListe = $("detail-schritte");
  schritteListe.textContent = "";
  const schritteFuerBeleg = (window.__letzteSchritte || []).filter((s) => s.beleg_id === b.id);
  schritteFuerBeleg.forEach((s) => {
    const li = document.createElement("li");
    const zeit = document.createElement("span");
    zeit.className = "audit-zeit";
    zeit.textContent = (s.start || "").replace("T", " ").slice(11, 19);
    li.appendChild(zeit);
    li.appendChild(document.createTextNode(`${s.schritt} [${s.status}, ${s.werkzeug}]: ${s.begruendung}`));
    schritteListe.appendChild(li);
  });

  // Technikbereich startet bei jedem Oeffnen eingeklappt.
  $("technik-details").open = false;

  $("detail-overlay").hidden = false;
  $("detail-schliessen").focus();
}

function detailSchliessen() {
  $("detail-overlay").hidden = true;
}

/* ---------- Upload ---------- */

async function dateienVerarbeiten(dateiListe) {
  if (!dateiListe || dateiListe.length === 0) return;
  fehlerVerstecken();
  const formData = new FormData();
  for (const datei of dateiListe) formData.append("dateien", datei, datei.name);

  $("upload-zone").disabled = true;
  $("schritte").hidden = false;
  $("schritte-status").textContent = `Agent verarbeitet ${dateiListe.length} Datei(en) …`;

  try {
    const resp = await fetch("/api/verarbeiten", { method: "POST", body: formData });
    const daten = await resp.json();
    if (!resp.ok) {
      fehlerZeigen(daten.fehler || "Verarbeitung fehlgeschlagen.");
    } else {
      window.__letzteSchritte = daten.schritte || [];
      $("schritte-status").textContent = `Zuletzt verarbeitet: ${daten.belege.length} Datei(en).`;
      await ladeAlles();
    }
  } catch (err) {
    fehlerZeigen("Verbindung zum lokalen Agenten fehlgeschlagen: " + err.message);
  } finally {
    $("upload-zone").disabled = false;
  }
}

$("upload-zone").addEventListener("click", () => $("datei-input").click());
$("datei-input").addEventListener("change", (e) => {
  dateienVerarbeiten(e.target.files);
  e.target.value = "";
});

["dragover", "dragenter"].forEach((ev) =>
  $("upload-zone").addEventListener(ev, (e) => { e.preventDefault(); $("upload-zone").classList.add("drag"); })
);
["dragleave", "drop"].forEach((ev) =>
  $("upload-zone").addEventListener(ev, (e) => {
    e.preventDefault();
    $("upload-zone").classList.remove("drag");
    if (ev === "drop" && e.dataTransfer.files.length > 0) {
      dateienVerarbeiten(e.dataTransfer.files);
    }
  })
);

/* ---------- Detail-, Reset- und Export-Ereignisse ---------- */

$("detail-schliessen").addEventListener("click", detailSchliessen);
$("detail-overlay").addEventListener("click", (e) => { if (e.target === $("detail-overlay")) detailSchliessen(); });

$("reset-btn").addEventListener("click", () => { $("reset-overlay").hidden = false; $("reset-nein").focus(); });
$("reset-nein").addEventListener("click", () => { $("reset-overlay").hidden = true; });
$("reset-schliessen").addEventListener("click", () => { $("reset-overlay").hidden = true; });
$("reset-overlay").addEventListener("click", (e) => { if (e.target === $("reset-overlay")) $("reset-overlay").hidden = true; });
$("reset-ja").addEventListener("click", async () => {
  await fetch("/api/reset", { method: "POST" });
  $("reset-overlay").hidden = true;
  $("schritte").hidden = true;
  window.__letzteSchritte = [];
  await ladeAlles();
});

$("export-btn").addEventListener("click", () => {
  $("export-status").textContent = "optitax_export.csv wird heruntergeladen …";
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if (!$("detail-overlay").hidden) detailSchliessen();
    if (!$("reset-overlay").hidden) $("reset-overlay").hidden = true;
  }
});

ladeAlles();
